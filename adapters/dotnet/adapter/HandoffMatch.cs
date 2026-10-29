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
    /// <summary>How a hand-off call stands: static, on an instance (passed first), or a constructor
    /// (returning what it built).</summary>
    internal enum Call { Static, Instance, Constructor }

    /// <summary>
    /// Which calls in one assembly are hand-offs, matched to the shim that stands in for each.
    /// </summary>
    /// <remarks>
    /// A call matches a shim only on its exact signature, spelled the same way on both sides — from
    /// the call's metadata here and from the shim's reflection in <see cref="HandoffSites"/> — so a
    /// call with no shim of its exact shape is left alone rather than pointed at something that is
    /// not there, which would be a <c>MissingMethodException</c> inside their code. Compiled into the
    /// adapter and into the instrumenter alike, so there is one matcher.
    /// </remarks>
    internal static class HandoffMatch
    {
        /// <summary>
        /// One call to a hand-off primitive: the token it calls, the shim that stands in for it and
        /// the shim's signature; for a generic hand-off, the instantiation it is called through and
        /// the member reference it instantiates. Found without writing anything, so the same finding
        /// serves the planner and the instrumenter alike.
        /// </summary>
        internal sealed record Site(int Call, string Shim, byte[] ShimSignature,
                                    BlobHandle? Instantiation, int Through);

        /// <summary>Every hand-off call in the assembly, member references before the instantiations
        /// made over them.</summary>
        internal static List<Site> Find(MetadataReader md, IReadOnlyDictionary<string, (string Shim, Call Call)> shims)
        {
            var found = new List<Site>();
            var references = new Dictionary<int, Site>();
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
                if (!shims.TryGetValue(key, out var shim)) continue;
                var parent = MetadataTokens.GetRowNumber(reference.Parent);
                var site = new Site(MetadataTokens.GetToken(handle), shim.Shim,
                    ShimSignature(md.GetBlobBytes(reference.Signature), shim.Call, parent), null, 0);
                references[site.Call] = site;
                found.Add(site);
            }
            // A generic hand-off — `Task.Run<T>` — is called through its instantiation, which is
            // made again over the shim with the same type arguments.
            for (var row = 1; row <= md.GetTableRowCount(TableIndex.MethodSpec); row++)
            {
                var handle = MetadataTokens.MethodSpecificationHandle(row);
                var spec = md.GetMethodSpecification(handle);
                if (spec.Method.Kind != HandleKind.MemberReference) continue;
                if (!references.TryGetValue(MetadataTokens.GetToken(spec.Method), out var through)) continue;
                found.Add(new Site(MetadataTokens.GetToken(handle), through.Shim, through.ShimSignature,
                                   spec.Signature, through.Call));
            }
            return found;
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

        internal static string Key(string type, string member, int arity, IEnumerable<string> parameters) =>
            $"{type}::{member}`{arity}({string.Join(",", parameters)})";

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

}
