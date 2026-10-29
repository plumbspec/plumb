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
    /// The shims, as the matcher reads them: each by the signature of the call it stands in for,
    /// spelled from the shim's reflection the same way <see cref="HandoffMatch"/> spells a call
    /// from metadata.
    /// </summary>
    internal static class HandoffSites
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
