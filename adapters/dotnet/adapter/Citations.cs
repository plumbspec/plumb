using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;

namespace PlumbSpec
{
    /// <summary>
    /// What a test claims, read off its attributes — by the attribute's NAME, never its type.
    /// </summary>
    /// <remarks>
    /// The collector is loaded into somebody else's testhost, beside whichever copy of the
    /// vocabulary their project compiled against. A reference to <c>ProvesAttribute</c> would bind
    /// this to one version of it; a name binds to none, so any vocabulary that keeps its names is
    /// read. <c>tests/test_the_dotnet_adapter.py</c> holds these names to the ones it declares.
    /// </remarks>
    internal static class Citations
    {
        public const string Proves = "PlumbSpec.ProvesAttribute";
        public const string Informs = "PlumbSpec.InformsAttribute";

        public sealed record Claim(string Kind, string Id, string Depth, string? Ref, string? About);

        /// <summary>Every citation on the test method VSTest named, and on its class.</summary>
        public static List<Claim> On(string source, string fullyQualifiedName)
        {
            var found = new List<Claim>();
            var (typeName, methodName) = Split(fullyQualifiedName);
            if (typeName == null) return found;
            Type? owner;
            try
            {
                owner = Loaded(source)?.GetType(typeName, false);
            }
            catch (Exception)
            {
                // A test whose class cannot be read cites nothing we can read. Report no citation
                // rather than inventing one — an adapter never decides (dev07-3-1).
                return found;
            }
            if (owner == null) return found;
            const BindingFlags all = BindingFlags.Public | BindingFlags.NonPublic |
                                     BindingFlags.Instance | BindingFlags.Static;
            var method = owner.GetMethods(all).FirstOrDefault(m => m.Name == methodName);
            if (method != null) found.AddRange(Read(method.GetCustomAttributesData()));
            found.AddRange(Read(owner.GetCustomAttributesData()));
            return found;
        }

        /// <summary><c>Namespace.Type.Method</c>, with any row's arguments dropped — NUnit puts
        /// them in the name, xUnit and MSTest in the display name.</summary>
        internal static (string? Type, string Method) Split(string fullyQualifiedName)
        {
            var name = fullyQualifiedName;
            var open = name.IndexOf('(');
            if (open >= 0) name = name.Substring(0, open);
            var dot = name.LastIndexOf('.');
            return dot <= 0 ? (null, name) : (name.Substring(0, dot), name.Substring(dot + 1));
        }

        /// <summary>The test assembly as the testhost already loaded it, so the attributes read
        /// are the ones the framework ran under.</summary>
        private static Assembly? Loaded(string source)
        {
            var wanted = Path.GetFullPath(source);
            foreach (var assembly in AppDomain.CurrentDomain.GetAssemblies())
            {
                if (assembly.IsDynamic || string.IsNullOrEmpty(assembly.Location)) continue;
                if (string.Equals(Path.GetFullPath(assembly.Location), wanted, StringComparison.Ordinal))
                    return assembly;
            }
            return Assembly.LoadFrom(wanted);
        }

        private static IEnumerable<Claim> Read(IEnumerable<CustomAttributeData> attributes)
        {
            foreach (var a in attributes)
            {
                var kind = a.AttributeType.FullName;
                if (kind != Proves && kind != Informs) continue;
                var args = a.ConstructorArguments;
                string? Named(string member) =>
                    a.NamedArguments.Where(n => n.MemberName == member)
                     .Select(n => n.TypedValue.Value as string).FirstOrDefault();
                if (args.Count < 1 || !(args[0].Value is string id)) continue;
                yield return kind == Proves
                    ? new Claim(kind, id, args.Count > 1 ? args[1].Value as string ?? "" : "",
                                Named("Ref"), null)
                    // No depth, and none invented: a rung the run cannot refute would be a claim
                    // nothing could lose.
                    : new Claim(kind, id, "", Named("Ref"), Named("About"));
            }
        }
    }
}
