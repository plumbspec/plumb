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
    /// Which calls in one assembly are hand-offs, and the token each is retargeted to.
    /// </summary>
    /// <remarks>
    /// A call matches a shim only on its exact signature, spelled the same way on both sides — from
    /// the call's metadata here and from the shim's reflection below — so a call with no shim of
    /// its exact shape is left alone rather than pointed at something that is not there, which would
    /// be a <c>MissingMethodException</c> inside their code.
    /// </remarks>
    internal sealed class HandoffSites
    {
        /// <summary>Every shim, by the signature of the call it stands in for.</summary>
        private static readonly Dictionary<string, (MethodInfo Shim, Call Call)> Shims = typeof(Handoff)
            .GetMethods(BindingFlags.Public | BindingFlags.Static)
            .Select(m => (Method: m, For: m.GetCustomAttribute<StandsInForAttribute>()))
            .Where(m => m.For != null)
            .ToDictionary(m => Key(m.For!.Type.FullName!, m.For.Member, m.Method.GetGenericArguments().Length,
                                   m.Method.GetParameters().Skip(m.For.Call == Call.Instance ? 1 : 0)
                                    .Select(p => Name(p.ParameterType))),
                          m => (m.Method, m.For!.Call), StringComparer.Ordinal);

        public readonly Dictionary<int, int> Retarget = new Dictionary<int, int>();

        public HandoffSites(Rewriter rewriter, Func<int> handoffType)
        {
            var md = rewriter.Md;
            int? type = null;
            foreach (var handle in md.MemberReferences)
            {
                var reference = md.GetMemberReference(handle);
                if (reference.Parent.Kind != HandleKind.TypeReference) continue;
                var owner = TypeName(md, (TypeReferenceHandle)reference.Parent);
                var name = md.GetString(reference.Name);
                MethodSignature<string> signature;
                try
                {
                    signature = reference.DecodeMethodSignature(new SignatureNames(), null);
                }
                catch (BadImageFormatException)
                {
                    continue; // a field reference
                }
                var key = Key(owner, name, signature.GenericParameterCount, signature.ParameterTypes);
                if (!Shims.TryGetValue(key, out var shim)) continue;
                type ??= handoffType();
                var parent = MetadataTokens.GetRowNumber(reference.Parent);
                var shimSignature = ShimSignature(md.GetBlobBytes(reference.Signature), shim.Call, parent);
                Retarget[MetadataTokens.GetToken(handle)] =
                    rewriter.MemberRef(type.Value, shim.Shim.Name, shimSignature);
            }
            // A generic hand-off — `Task.Run<T>` — is called through its instantiation, which is
            // made again over the shim with the same type arguments.
            for (var row = 1; row <= md.GetTableRowCount(TableIndex.MethodSpec); row++)
            {
                var handle = MetadataTokens.MethodSpecificationHandle(row);
                var spec = md.GetMethodSpecification(handle);
                if (spec.Method.Kind != HandleKind.MemberReference) continue;
                if (!Retarget.TryGetValue(MetadataTokens.GetToken(spec.Method), out var shim)) continue;
                Retarget[MetadataTokens.GetToken(handle)] = rewriter.MethodSpec(shim, spec.Signature);
            }
        }

        /// <summary>The shim's signature, from the call's: the same for a static call; the receiver
        /// as a first parameter for an instance; the built object as the result for a constructor.</summary>
        private static byte[] ShimSignature(byte[] call, Call kind, int parentTypeRefRow)
        {
            if (kind == Call.Static) return call;
            var at = 0;
            var header = call[at++];
            var generic = (header & 0x10) != 0 ? Signature.Compressed(call, ref at) : 0;
            var count = Signature.Compressed(call, ref at);
            var returned = at;
            Signature.SkipType(call, ref at);
            var o = new MemoryStream();
            o.WriteByte((byte)(header & ~0x60)); // no longer HASTHIS, nor EXPLICITTHIS
            if ((header & 0x10) != 0) Signature.WriteCompressed(o, generic);
            Signature.WriteCompressed(o, count + (kind == Call.Instance ? 1 : 0));
            if (kind == Call.Instance) o.Write(call, returned, at - returned);
            o.WriteByte(0x12); // CLASS, then the type as a TypeDefOrRef: a TypeRef is tag 1
            Signature.WriteCompressed(o, (parentTypeRefRow << 2) | 1);
            o.Write(call, at, call.Length - at);
            return o.ToArray();
        }

        private static string Key(string type, string member, int arity, IEnumerable<string> parameters) =>
            $"{type}::{member}`{arity}({string.Join(",", parameters)})";

        /// <summary>A parameter's type, as <see cref="SignatureNames"/> spells it from metadata.</summary>
        private static string Name(Type type)
        {
            if (type.IsByRef) return Name(type.GetElementType()!) + "&";
            if (type.IsArray) return Name(type.GetElementType()!) + "[]";
            if (type.IsGenericParameter)
                return (type.DeclaringMethod != null ? "!!" : "!") + type.GenericParameterPosition;
            if (type.IsGenericType)
                return type.GetGenericTypeDefinition().FullName + "<" +
                       string.Join(",", type.GetGenericArguments().Select(Name)) + ">";
            return type.FullName!;
        }

        private static string TypeName(MetadataReader md, TypeReferenceHandle handle)
        {
            var type = md.GetTypeReference(handle);
            var name = md.GetString(type.Name);
            if (type.ResolutionScope.Kind == HandleKind.TypeReference)
                return TypeName(md, (TypeReferenceHandle)type.ResolutionScope) + "+" + name;
            var ns = md.GetString(type.Namespace);
            return ns.Length == 0 ? name : ns + "." + name;
        }

        private sealed class SignatureNames : ISignatureTypeProvider<string, object?>
        {
            public string GetArrayType(string element, ArrayShape shape) => element + "[" + shape.Rank + "]";
            public string GetByReferenceType(string element) => element + "&";
            public string GetFunctionPointerType(MethodSignature<string> signature) => "method*";
            public string GetGenericInstantiation(string generic, ImmutableArray<string> arguments) =>
                generic + "<" + string.Join(",", arguments) + ">";
            public string GetGenericMethodParameter(object? context, int index) => "!!" + index;
            public string GetGenericTypeParameter(object? context, int index) => "!" + index;
            public string GetModifiedType(string modifier, string unmodified, bool isRequired) => unmodified;
            public string GetPinnedType(string element) => element;
            public string GetPointerType(string element) => element + "*";
            public string GetPrimitiveType(PrimitiveTypeCode code) => "System." + code switch
            {
                PrimitiveTypeCode.IntPtr => "IntPtr",
                PrimitiveTypeCode.UIntPtr => "UIntPtr",
                _ => code.ToString(),
            };
            public string GetSZArrayType(string element) => element + "[]";
            public string GetTypeFromDefinition(MetadataReader md, TypeDefinitionHandle handle, byte kind)
            {
                var type = md.GetTypeDefinition(handle);
                var name = md.GetString(type.Name);
                var declaring = type.GetDeclaringType();
                if (!declaring.IsNil) return GetTypeFromDefinition(md, declaring, kind) + "+" + name;
                var ns = md.GetString(type.Namespace);
                return ns.Length == 0 ? name : ns + "." + name;
            }
            public string GetTypeFromReference(MetadataReader md, TypeReferenceHandle handle, byte kind) =>
                TypeName(md, handle);
            public string GetTypeFromSpecification(MetadataReader md, object? context,
                                                   TypeSpecificationHandle handle, byte kind) =>
                md.GetTypeSpecification(handle).DecodeSignature(this, context);
        }
    }

    /// <summary>The pieces of ECMA-335 II.23.2 the weave reads and writes by hand.</summary>
    internal static class Signature
    {
        public static int Compressed(byte[] b, ref int at)
        {
            var first = b[at];
            if ((first & 0x80) == 0) { at += 1; return first; }
            if ((first & 0xC0) == 0x80) { at += 2; return ((first & 0x3F) << 8) | b[at - 1]; }
            at += 4;
            return ((first & 0x1F) << 24) | (b[at - 3] << 16) | (b[at - 2] << 8) | b[at - 1];
        }

        public static void WriteCompressed(Stream o, int value)
        {
            if (value < 0x80) o.WriteByte((byte)value);
            else if (value < 0x4000) { o.WriteByte((byte)(0x80 | (value >> 8))); o.WriteByte((byte)value); }
            else
            {
                o.WriteByte((byte)(0xC0 | (value >> 24))); o.WriteByte((byte)(value >> 16));
                o.WriteByte((byte)(value >> 8)); o.WriteByte((byte)value);
            }
        }

        /// <summary>One type in a signature (II.23.2.12), so its bytes can be copied whole.</summary>
        public static void SkipType(byte[] b, ref int at)
        {
            while (b[at] == 0x1F || b[at] == 0x20) { at++; Compressed(b, ref at); }
            var element = b[at++];
            switch (element)
            {
                case >= 0x01 and <= 0x0E:
                case 0x16: case 0x18: case 0x19: case 0x1C:
                    return;
                case 0x0F: case 0x10: case 0x1D: case 0x45:
                    SkipType(b, ref at);
                    return;
                case 0x11: case 0x12: case 0x13: case 0x1E:
                    Compressed(b, ref at);
                    return;
                case 0x14:
                    SkipType(b, ref at);
                    Compressed(b, ref at);
                    var sizes = Compressed(b, ref at);
                    for (var i = 0; i < sizes; i++) Compressed(b, ref at);
                    var bounds = Compressed(b, ref at);
                    for (var i = 0; i < bounds; i++) Compressed(b, ref at);
                    return;
                case 0x15:
                    at++;
                    Compressed(b, ref at);
                    var arguments = Compressed(b, ref at);
                    for (var i = 0; i < arguments; i++) SkipType(b, ref at);
                    return;
                case 0x1B:
                    var convention = b[at++];
                    if ((convention & 0x10) != 0) Compressed(b, ref at);
                    var parameters = Compressed(b, ref at);
                    SkipType(b, ref at);
                    for (var i = 0; i < parameters; i++)
                    {
                        if (b[at] == 0x41) at++;
                        SkipType(b, ref at);
                    }
                    return;
                default:
                    throw new Il.Unweavable($"a signature holds an element 0x{element:x2} this writer does not read");
            }
        }
    }
}
