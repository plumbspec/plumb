using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Reflection.Metadata;
using System.Reflection.Metadata.Ecma335;

namespace PlumbSpec
{
    /// <summary>
    /// Weaves a copy of the build's output before VSTest runs it (dev07-1-3-sr11): production gets
    /// its probes, each declared entry point its window, and each test the line that opens its own.
    /// </summary>
    /// <remarks>
    /// Run by the launcher as <c>dotnet PlumbSpec.Adapter.dll weave &lt;copy&gt; &lt;tests&gt;
    /// &lt;run file&gt; &lt;report&gt;</c>, on whatever runtime runs the project's tests. What is
    /// production is decided by which assembly the code is in (dev07-1-3-sr04), named in the run file
    /// by the launcher, and the test assembly is the one the launcher hands over. Nothing here
    /// decides a grounding; it puts the probes where the collector can read them.
    /// </remarks>
    public static class Weaver
    {
        public static int Main(string[] args)
        {
            if (args.Length != 5 || (args[0] != "weave" && args[0] != "plan"))
            {
                Console.Error.WriteLine("usage: PlumbSpec.Adapter weave|plan <output> <tests> <run file> <report>");
                return 2;
            }
            var report = new List<string>();
            try
            {
                if (args[0] == "weave") Weave(args[1], args[2], args[3], report);
                else Declare(args[2], args[3], report);
            }
            catch (Exception failed)
            {
                // An instrument failure costs the wiring fact and never the run (dev07-1-3-nfr2):
                // whatever was not written yet is still as it was built.
                report.Add($"failed\t{failed.GetType().Name}: {failed.Message}");
            }
            File.WriteAllLines(args[4], report);
            return 0;
        }

        private static void Weave(string copy, string tests, string runFile, List<string> report)
        {
            var production = RunFile.Read(runFile, "production").Select(f => f[0]).ToList();
            var entryPoints = new HashSet<string>(RunFile.Read(runFile, "entrypoint").Select(f => f[0]),
                                                  StringComparer.Ordinal);
            var found = new HashSet<string>(StringComparer.Ordinal);
            foreach (var path in Directory.GetFiles(copy, "*.dll").OrderBy(p => p, StringComparer.Ordinal))
            {
                var file = Path.GetFileName(path);
                var isTests = string.Equals(file, tests, StringComparison.Ordinal);
                string name;
                try
                {
                    name = AssemblyName.GetAssemblyName(path).Name ?? "";
                }
                catch (BadImageFormatException)
                {
                    continue; // native, or not an assembly at all: nothing of ours
                }
                if (!isTests && !production.Any(p => Planning.Matches(name, p))) continue;
                try
                {
                    var rewriter = new Rewriter(File.ReadAllBytes(path));
                    var counts = WeaveAssembly(rewriter, isTests, entryPoints, found, report, file);
                    if (!rewriter.Changed) continue;
                    var woven = rewriter.Build();
                    File.WriteAllBytes(path + ".plumb", woven);
                    File.Move(path + ".plumb", path, true);
                    report.Add($"woven\t{file}\t{counts.Methods}\t{counts.Entries}\t{counts.Tests}\t" +
                               $"{counts.Handoffs}\t{counts.Steps}");
                }
                catch (Rewriter.Refused refused)
                {
                    report.Add($"left\t{file}\t{refused.Message}");
                }
            }
            foreach (var missing in entryPoints.Except(found).OrderBy(e => e, StringComparer.Ordinal))
                report.Add($"unfound\t{missing}");
        }

        /// <summary>
        /// What the instrumenter needs to weave as the runtime compiles (dev07-1-3-sr11, sr03): which
        /// assembly is the tests, which are production, the entry points, and the shims — and no
        /// token. Tokens are read by the instrumenter from each module as it loads, because another
        /// tool may rewrite the file between now and then (<see cref="Planning"/>).
        /// </summary>
        private static void Declare(string tests, string runFile, List<string> report)
        {
            report.Add($"tests\t{tests}");
            foreach (var production in RunFile.Read(runFile, "production")) report.Add($"production\t{production[0]}");
            foreach (var entry in RunFile.Read(runFile, "entrypoint")) report.Add($"entrypoint\t{entry[0]}");
            foreach (var (key, (shim, call)) in HandoffSites.Table.OrderBy(s => s.Key, StringComparer.Ordinal))
                report.Add($"shim\t{key}\t{shim}\t{call}");
        }

        private static int ProbeType(Rewriter rewriter, string name)
        {
            var self = typeof(Probe).Assembly.GetName();
            var assembly = rewriter.AssemblyRef(self.Name!, self.Version!);
            return rewriter.TypeRef(assembly, "PlumbSpec", name);
        }

        /// <summary>
        /// One assembly. In production, every method reports that it ran and each declared entry point
        /// opens a window; in the tests, each test opens its own. In both, every hand-off is seen and
        /// every async step says whose flow it resumes (dev07-1-4-sr2, dev07-1-3-sr05).
        /// </summary>
        private static Counts WeaveAssembly(Rewriter rewriter, bool isTests, HashSet<string> entryPoints,
                                            HashSet<string> found, List<string> report, string file)
        {
            var md = rewriter.Md;
            var probe = ProbeType(rewriter, nameof(Probe));
            int Member(string name, params byte[] signature) => rewriter.MemberRef(probe, name, signature);
            var ran = Member(nameof(Probe.Ran), 0x00, 0x00, 0x01);
            var enter = Member(nameof(Probe.Enter), 0x00, 0x01, 0x01, 0x0E);
            var exit = Member(nameof(Probe.Exit), 0x00, 0x00, 0x01);
            var resume = Member(nameof(Probe.Resume), 0x00, 0x00, 0x01);
            var suspend = Member(nameof(Probe.Suspend), 0x00, 0x00, 0x01);
            var begin = Member(nameof(Probe.Begin), 0x00, 0x03, 0x01, 0x1C, 0x0E, 0x0E);
            var handoffs = new HandoffSites(rewriter, () => ProbeType(rewriter, nameof(Handoff))).Retarget;
            var counts = new Counts();
            foreach (var (type, handle, def, name) in Planning.Methods(md))
            {
                try
                {
                    var (body, retargeted) = Il.Retarget(
                        Il.Read(rewriter.Pe.GetMethodBody(def.RelativeVirtualAddress)), handoffs);
                    counts.Handoffs += retargeted;
                    if (!isTests && entryPoints.Contains(name))
                    {
                        var (local, signature) = ResultLocal(md, def, body);
                        rewriter.SetBody(handle, Il.Encode(Il.Wrap(body,
                            Il.Op(0x72, rewriter.UserString(name)).Concat(Il.Op(0x28, enter)).ToArray(),
                            Il.Op(0x28, exit), local,
                            signature == null ? body.LocalSignatureToken : rewriter.StandAloneSig(signature))));
                        found.Add(name);
                        counts.Entries++;
                    }
                    else if (Planning.IsAsyncStep(md, type, def))
                    {
                        var prologue = isTests ? Il.Op(0x28, resume)
                            : Il.Op(0x28, ran).Concat(Il.Op(0x28, resume)).ToArray();
                        rewriter.SetBody(handle, Il.Encode(Il.Wrap(body, prologue, Il.Op(0x28, suspend),
                                                                   null, body.LocalSignatureToken)));
                        if (isTests) counts.Steps++; else counts.Methods++;
                    }
                    else if (!isTests)
                    {
                        rewriter.SetBody(handle, Il.Encode(Il.Prefix(body, Il.Op(0x28, ran), 0)));
                        counts.Methods++;
                    }
                    else if (Planning.IsTest(md, def))
                    {
                        rewriter.SetBody(handle, Il.Encode(Il.Prefix(body, BeginPrologue(rewriter, def, name, begin), 3)));
                        counts.Tests++;
                    }
                    else if (retargeted > 0)
                    {
                        rewriter.SetBody(handle, Il.Encode(body));
                    }
                }
                catch (Il.Unweavable why)
                {
                    report.Add($"left\t{file}\t{name}: {why.Message}");
                }
            }
            return counts;
        }

        private sealed class Counts
        {
            public int Methods, Entries, Tests, Steps, Handoffs;
        }

        private static byte[] BeginPrologue(Rewriter rewriter, MethodDefinition def, string name, int begin)
        {
            var md = rewriter.Md;
            var prologue = new List<byte>
            {
                // The instance, so a test inherited from a base class is named for the class it
                // ran in, as VSTest names it; nothing for a static test.
                (def.Attributes & MethodAttributes.Static) != 0 ? (byte)0x14 : (byte)0x02,
            };
            prologue.AddRange(Il.Op(0x72, rewriter.UserString(name.Substring(0, name.LastIndexOf('.')))));
            prologue.AddRange(Il.Op(0x72, rewriter.UserString(md.GetString(def.Name))));
            prologue.AddRange(Il.Op(0x28, begin));
            return prologue.ToArray();
        }

        /// <summary>The local a wrapped entry point holds its result in, and the new local
        /// signature that declares it, or neither for a method that returns nothing.</summary>
        private static (int?, byte[]?) ResultLocal(MetadataReader md, MethodDefinition def, Il.Body body)
        {
            var signature = md.GetBlobBytes(def.Signature);
            var at = 0;
            var convention = signature[at++];
            if ((convention & 0x10) != 0) Signature.Compressed(signature, ref at);
            Signature.Compressed(signature, ref at);
            var start = at;
            var peek = at;
            while (signature[peek] == 0x1F || signature[peek] == 0x20) { peek++; Signature.Compressed(signature, ref peek); }
            if (signature[peek] == 0x01) return (null, null);
            Signature.SkipType(signature, ref at);
            var returned = signature.Skip(start).Take(at - start).ToArray();

            var count = 0;
            var types = Array.Empty<byte>();
            if (body.LocalSignatureToken != 0)
            {
                var locals = md.GetBlobBytes(md.GetStandaloneSignature(
                    (StandaloneSignatureHandle)MetadataTokens.EntityHandle(body.LocalSignatureToken)).Signature);
                var p = 1;
                count = Signature.Compressed(locals, ref p);
                types = locals.Skip(p).ToArray();
            }
            var o = new MemoryStream();
            o.WriteByte(0x07);
            var c = count + 1;
            if (c < 0x80) o.WriteByte((byte)c);
            else if (c < 0x4000) { o.WriteByte((byte)(0x80 | (c >> 8))); o.WriteByte((byte)c); }
            else throw new Il.Unweavable("it has more locals than this writer encodes");
            o.Write(types, 0, types.Length);
            o.Write(returned, 0, returned.Length);
            return (count, o.ToArray());
        }
    }
}
