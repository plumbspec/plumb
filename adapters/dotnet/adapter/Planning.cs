using System;
using System.Collections.Generic;
using System.Collections.Immutable;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Reflection.Metadata;
using System.Reflection.Metadata.Ecma335;

namespace PlumbSpec
{
    /// <summary>
    /// What is production, what is a test, what is an async step and which calls are hand-offs, read
    /// off an assembly's metadata — and the plan for one module that follows from it.
    /// </summary>
    /// <remarks>
    /// Compiled into the adapter, which weaves a copy, and into the instrumenter, which weaves as the
    /// runtime compiles, so both read an assembly the same way. The instrumenter reads the module as
    /// it is loaded, never as it was before the run: another tool may rewrite it on disk first —
    /// measured, Microsoft's coverage does, for the length of its run — and a token read before is
    /// then a token of something else.
    /// </remarks>
    internal static class Planning
    {
        /// <summary>The test attributes VSTest's frameworks mark a test with, by name. A test whose
        /// attribute derives from one of these in another assembly is not seen, and reads
        /// <c>not-checked</c>: its window never opened, so nothing could be asked.</summary>
        internal static readonly HashSet<string> TestAttributes = new HashSet<string>(StringComparer.Ordinal)
        {
            "Xunit.FactAttribute", "Xunit.TheoryAttribute",
            "NUnit.Framework.TestAttribute", "NUnit.Framework.TestCaseAttribute",
            "NUnit.Framework.TestCaseSourceAttribute", "NUnit.Framework.TheoryAttribute",
            "Microsoft.VisualStudio.TestTools.UnitTesting.TestMethodAttribute",
            "Microsoft.VisualStudio.TestTools.UnitTesting.DataTestMethodAttribute",
        };

        internal static bool Matches(string name, string pattern) =>
            pattern.EndsWith("*", StringComparison.Ordinal)
                ? name.StartsWith(pattern.Substring(0, pattern.Length - 1), StringComparison.Ordinal)
                : string.Equals(name, pattern, StringComparison.Ordinal);

        /// <summary>A step of an async method or iterator: the <c>MoveNext</c> of a type the compiler
        /// made to implement <c>IAsyncStateMachine</c>.</summary>
        internal static bool IsAsyncStep(MetadataReader md, TypeDefinitionHandle type, MethodDefinition def)
        {
            if (!md.GetString(def.Name).EndsWith("MoveNext", StringComparison.Ordinal)) return false;
            foreach (var handle in md.GetTypeDefinition(type).GetInterfaceImplementations())
            {
                var implemented = md.GetInterfaceImplementation(handle).Interface;
                if (implemented.Kind != HandleKind.TypeReference) continue;
                var reference = md.GetTypeReference((TypeReferenceHandle)implemented);
                if (md.GetString(reference.Namespace) == "System.Runtime.CompilerServices" &&
                    md.GetString(reference.Name) == "IAsyncStateMachine")
                    return true;
            }
            return false;
        }

        /// <summary>Every method with an IL body, named as an entry point is declared:
        /// <c>Namespace.Type.Method</c>, a nested type joined to its parent by <c>+</c>.</summary>
        internal static IEnumerable<(TypeDefinitionHandle, MethodDefinitionHandle, MethodDefinition, string)> Methods(
            MetadataReader md)
        {
            foreach (var typeHandle in md.TypeDefinitions)
            {
                var typeName = TypeName(md, typeHandle);
                foreach (var handle in md.GetTypeDefinition(typeHandle).GetMethods())
                {
                    var def = md.GetMethodDefinition(handle);
                    if (def.RelativeVirtualAddress == 0) continue;
                    if ((def.ImplAttributes & MethodImplAttributes.CodeTypeMask) != MethodImplAttributes.IL) continue;
                    yield return (typeHandle, handle, def, typeName + "." + md.GetString(def.Name));
                }
            }
        }

        internal static string TypeName(MetadataReader md, TypeDefinitionHandle handle)
        {
            var type = md.GetTypeDefinition(handle);
            var name = md.GetString(type.Name);
            var declaring = type.GetDeclaringType();
            if (!declaring.IsNil) return TypeName(md, declaring) + "+" + name;
            var ns = md.GetString(type.Namespace);
            return ns.Length == 0 ? name : ns + "." + name;
        }

        internal static bool IsTest(MetadataReader md, MethodDefinition def)
        {
            foreach (var handle in def.GetCustomAttributes())
            {
                var constructor = md.GetCustomAttribute(handle).Constructor;
                EntityHandle type = constructor.Kind switch
                {
                    HandleKind.MemberReference => md.GetMemberReference((MemberReferenceHandle)constructor).Parent,
                    HandleKind.MethodDefinition => md.GetMethodDefinition((MethodDefinitionHandle)constructor).GetDeclaringType(),
                    _ => default,
                };
                if (IsTestAttribute(md, type)) return true;
            }
            return false;
        }

        /// <summary>The attribute's own name, or a base class's while the chain stays inside this
        /// assembly — a project's own <c>[MyFact]</c> deriving from <c>[Fact]</c> is a test.</summary>
        internal static bool IsTestAttribute(MetadataReader md, EntityHandle type)
        {
            for (var depth = 0; depth < 16 && !type.IsNil; depth++)
            {
                if (type.Kind == HandleKind.TypeReference)
                {
                    var r = md.GetTypeReference((TypeReferenceHandle)type);
                    return TestAttributes.Contains(md.GetString(r.Namespace) + "." + md.GetString(r.Name));
                }
                if (type.Kind != HandleKind.TypeDefinition) return false;
                var d = (TypeDefinitionHandle)type;
                if (TestAttributes.Contains(TypeName(md, d))) return true;
                type = md.GetTypeDefinition(d).BaseType;
            }
            return false;
        }

        internal static bool CallsHandoff(System.Reflection.PortableExecutable.PEReader pe, MethodDefinition def,
                                         List<HandoffMatch.Site> sites)
        {
            if (sites.Count == 0) return false;
            var calls = new HashSet<int>(sites.Select(s => s.Call));
            try
            {
                var code = Il.Read(pe.GetMethodBody(def.RelativeVirtualAddress)).Code;
                return Il.Decode(code).Any(i => i.Op is 0x28 or 0x6F or 0x73 &&
                                                calls.Contains(BitConverter.ToInt32(i.Operand, 0)));
            }
            catch (Il.Unweavable)
            {
                return false;
            }
        }

        /// <summary>One module's plan, by method token: the entry points it holds, its async steps, its
        /// tests, and its hand-off calls with the methods that make them.</summary>
        internal sealed record ModulePlan(
            Dictionary<int, string> Entries, HashSet<int> Steps,
            Dictionary<int, (bool Static, string Type, string Method)> Tests,
            List<HandoffMatch.Site> Handoffs, HashSet<int> Calls);

        internal static ModulePlan ForModule(System.Reflection.PortableExecutable.PEReader pe, bool isTests,
                                             ISet<string> entryPoints, ISet<string> found,
                                             IReadOnlyDictionary<string, (string Shim, Call Call)> shims)
        {
            var md = pe.GetMetadataReader();
            var plan = new ModulePlan(new Dictionary<int, string>(), new HashSet<int>(),
                                      new Dictionary<int, (bool, string, string)>(),
                                      HandoffMatch.Find(md, shims), new HashSet<int>());
            foreach (var (type, handle, def, method) in Methods(md))
            {
                var token = MetadataTokens.GetToken(handle);
                if (!isTests && entryPoints.Contains(method))
                {
                    plan.Entries[token] = method;
                    found.Add(method);
                }
                else if (IsAsyncStep(md, type, def))
                    plan.Steps.Add(token);
                else if (isTests && IsTest(md, def))
                {
                    var dot = method.LastIndexOf('.');
                    plan.Tests[token] = ((def.Attributes & MethodAttributes.Static) != 0,
                                         method.Substring(0, dot), md.GetString(def.Name));
                }
                if (CallsHandoff(pe, def, plan.Handoffs)) plan.Calls.Add(token);
            }
            return plan;
        }
    }
}
