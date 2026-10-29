using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;

namespace PlumbSpec
{
    /// <summary>
    /// The document this adapter exists to produce (dev07-3-3), at the schema the JVM adapter and the
    /// core speak. Written by hand, as the JVM one is: the shape is small, fixed and ours, and a
    /// serializer would be a dependency loaded into somebody else's testhost.
    /// </summary>
    internal sealed class Manifest
    {
        public const string SchemaVersion = "9.0";

        public sealed record Citation(string Test, string Depth, string Result, string Grounding,
                                      string? Ref, string? About, string When);

        public sealed record Provenance(string Adapter, string Version, string Runtime,
                                        string Mechanism);

        private readonly SortedDictionary<string, List<Citation>> byStory =
            new SortedDictionary<string, List<Citation>>(System.StringComparer.Ordinal);
        private readonly Dictionary<string, string> archetypes = new Dictionary<string, string>();

        /// <summary>Null until the run has started: <c>null</c> is <em>not reported</em>, and a
        /// zero would claim the run looked and found nothing (dev07-3-2).</summary>
        public int? ObservedTests { get; set; }

        public Provenance? Observer { get; set; }

        public bool IsEmpty => byStory.Count == 0;

        public void Add(string story, Citation citation)
        {
            if (!byStory.TryGetValue(story, out var cited)) byStory[story] = cited = new List<Citation>();
            cited.Add(citation);
        }

        /// <summary>Read off the spec, never the run (dev07-3-2).</summary>
        public void DeclareArchetype(string story, string archetype) => archetypes[story] = archetype;

        public string ToJson()
        {
            var o = new StringBuilder();
            o.Append("{\n  \"schema_version\": \"").Append(SchemaVersion).Append("\",\n");
            o.Append("  \"observed_tests\": ")
             .Append(ObservedTests?.ToString(CultureInfo.InvariantCulture) ?? "null").Append(",\n");
            o.Append("  \"stories\": {");
            var storySep = "\n";
            foreach (var entry in byStory)
            {
                o.Append(storySep).Append("    ").Append(Quote(entry.Key)).Append(": {\n");
                o.Append("      \"archetype\": ")
                 .Append(Quote(archetypes.TryGetValue(entry.Key, out var a) ? a : "behavioral"))
                 .Append(",\n      \"mutation\": null,\n      \"citations\": [");
                var citeSep = "\n";
                foreach (var c in entry.Value)
                {
                    o.Append(citeSep).Append("        {")
                     .Append("\"test\": ").Append(Quote(c.Test))
                     .Append(", \"depth\": ").Append(Quote(c.Depth))
                     .Append(", \"result\": ").Append(Quote(c.Result))
                     .Append(", \"grounding\": ").Append(Quote(c.Grounding))
                     .Append(", \"ref\": ").Append(c.Ref == null ? "null" : Quote(c.Ref))
                     .Append(", \"about\": ").Append(c.About == null ? "null" : Quote(c.About))
                     .Append(", \"when\": ").Append(Quote(c.When));
                    // On the fact, never the document (dev07-3-2): a board may carry this adapter's
                    // measurements beside another's, comparable only by who made them (dev07-3-1).
                    if (Observer != null)
                        o.Append(", \"observer\": {\"adapter\": ").Append(Quote(Observer.Adapter))
                         .Append(", \"version\": ").Append(Quote(Observer.Version))
                         .Append(", \"runtime\": ").Append(Quote(Observer.Runtime))
                         .Append(", \"mechanism\": ").Append(Quote(Observer.Mechanism)).Append('}');
                    o.Append('}');
                    citeSep = ",\n";
                }
                o.Append("\n      ]\n    }");
                storySep = ",\n";
            }
            o.Append("\n  }\n}\n");
            return o.ToString();
        }

        public IEnumerable<(string Story, Citation Citation)> All() =>
            byStory.SelectMany(e => e.Value.Select(c => (e.Key, c)));

        public void Write(string path)
        {
            Directory.CreateDirectory(Path.GetDirectoryName(Path.GetFullPath(path))!);
            // Whole, then moved: a manifest is the evidence a run happened, and a half-written one
            // must never be found under the name the launcher trusts.
            var partial = path + ".part";
            File.WriteAllText(partial, ToJson(), new UTF8Encoding(false));
            File.Move(partial, path, true);
        }

        private static string Quote(string raw)
        {
            var q = new StringBuilder("\"");
            foreach (var c in raw)
            {
                switch (c)
                {
                    case '"': q.Append("\\\""); break;
                    case '\\': q.Append("\\\\"); break;
                    case '\n': q.Append("\\n"); break;
                    case '\r': q.Append("\\r"); break;
                    case '\t': q.Append("\\t"); break;
                    default:
                        if (c < 0x20) q.Append("\\u").Append(((int)c).ToString("x4"));
                        else q.Append(c);
                        break;
                }
            }
            return q.Append('"').ToString();
        }
    }
}
