using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace PlumbSpec
{
    /// <summary>
    /// What the instrumenter needs to weave as the runtime compiles (dev07-1-3-sr11, sr03), written by
    /// the launcher's one call into this assembly before the run.
    /// </summary>
    /// <remarks>
    /// Run as <c>dotnet PlumbSpec.Adapter.dll plan &lt;output&gt; &lt;tests&gt; &lt;run file&gt;
    /// &lt;plan&gt;</c>, on whatever runtime runs the project's tests. It declares which assembly is
    /// the tests, which are production, the entry points, and the hand-off shims — names only, and no
    /// token: the instrumenter reads each module's tokens as the runtime loads it, because another tool
    /// may rewrite the file between now and then (dev07-1-3-sr16, <see cref="Planning"/>). The output
    /// directory is not read here; it is named so the call says what it plans for.
    /// </remarks>
    public static class Weaver
    {
        public static int Main(string[] args)
        {
            if (args.Length != 5 || args[0] != "plan")
            {
                Console.Error.WriteLine("usage: PlumbSpec.Adapter plan <output> <tests> <run file> <plan>");
                return 2;
            }
            var declared = new List<string> { $"tests\t{args[2]}" };
            declared.AddRange(RunFile.Read(args[3], "production").Select(p => $"production\t{p[0]}"));
            declared.AddRange(RunFile.Read(args[3], "entrypoint").Select(e => $"entrypoint\t{e[0]}"));
            declared.AddRange(HandoffSites.Table.OrderBy(s => s.Key, StringComparer.Ordinal)
                                  .Select(s => $"shim\t{s.Key}\t{s.Value.Shim}\t{s.Value.Call}"));
            File.WriteAllLines(args[4], declared);
            return 0;
        }
    }
}
