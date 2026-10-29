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
        internal static readonly Dictionary<string, (MethodInfo Shim, Call Call)> Shims = typeof(Handoff)
            .GetMethods(BindingFlags.Public | BindingFlags.Static)
            .Select(m => (Method: m, For: m.GetCustomAttribute<StandsInForAttribute>()))
            .Where(m => m.For != null)
            .ToDictionary(m => HandoffMatch.Key(m.For!.Type.FullName!, m.For.Member, m.Method.GetGenericArguments().Length,
                                   m.Method.GetParameters().Skip(m.For.Call == Call.Instance ? 1 : 0)
                                    .Select(p => Name(p.ParameterType))),
                          m => (m.Method, m.For!.Call), StringComparer.Ordinal);

        /// <summary>The shims as the matcher reads them: by the call's signature, the shim's name and
        /// how the call stands.</summary>
        internal static readonly Dictionary<string, (string Shim, Call Call)> Table =
            Shims.ToDictionary(s => s.Key, s => (s.Value.Shim.Name, s.Value.Call), StringComparer.Ordinal);

        public readonly Dictionary<int, int> Retarget = new Dictionary<int, int>();

        public HandoffSites(Rewriter rewriter, Func<int> handoffType)
        {
            int? type = null;
            var minted = new Dictionary<int, int>();
            foreach (var site in HandoffMatch.Find(rewriter.Md, Table))
            {
                type ??= handoffType();
                if (site.Instantiation is null)
                    Retarget[site.Call] = minted[site.Call] =
                        rewriter.MemberRef(type.Value, site.Shim, site.ShimSignature);
                else
                    Retarget[site.Call] = rewriter.MethodSpec(minted[site.Through], site.Instantiation.Value);
            }
        }

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

    }
}
