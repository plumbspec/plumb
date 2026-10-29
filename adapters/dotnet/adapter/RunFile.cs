using System.Collections.Generic;
using System.IO;

namespace PlumbSpec
{
    /// <summary>
    /// The launcher's resolved facts, one <c>kind&lt;TAB&gt;value…</c> per line. Answers, not
    /// questions: nothing here parses a configuration format, so the reader is one split.
    /// </summary>
    internal static class RunFile
    {
        public static List<string[]> Read(string? path, string kind)
        {
            var found = new List<string[]>();
            // A missing file reads as nothing declared, never as an error (dev07-5-1).
            if (path == null || !File.Exists(path)) return found;
            foreach (var line in File.ReadAllLines(path))
            {
                var fields = line.Split('\t');
                if (fields.Length > 1 && fields[0] == kind) found.Add(fields[1..]);
            }
            return found;
        }
    }
}
