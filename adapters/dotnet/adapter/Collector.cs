using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Xml;
using Microsoft.VisualStudio.TestPlatform.ObjectModel;
using Microsoft.VisualStudio.TestPlatform.ObjectModel.DataCollection;
using Microsoft.VisualStudio.TestPlatform.ObjectModel.DataCollector.InProcDataCollector;
using Microsoft.VisualStudio.TestPlatform.ObjectModel.InProcDataCollector;

namespace PlumbSpec
{
    /// <summary>
    /// Watches a VSTest run from inside the testhost and turns it into facts (dev07-3-1) — never a
    /// verdict.
    /// </summary>
    /// <remarks>
    /// An in-process data collector, because it is the one seam every VSTest framework passes
    /// through: VSTest tells it each test's start and end on the thread the test runs on, whatever
    /// framework ran it. That is what lets one collector serve xUnit, NUnit and MSTest, as the JUnit
    /// Platform lets one listener serve every JVM engine. The launcher names it in the run settings,
    /// with where the run file and the manifest are, and nothing else configures it.
    /// </remarks>
    public sealed class Collector : InProcDataCollection
    {
        /// <summary>No observation yet, so grounding is honestly unanswered (dev07-1-4).</summary>
        private const string NotChecked = "not-checked";

        private readonly Manifest manifest = new Manifest();

        /// <summary>Every test case this run saw, cited or not (dev07-3-2) — by VSTest's id, so
        /// each row of a theory is one.</summary>
        private readonly HashSet<Guid> seen = new HashSet<Guid>();

        /// <summary>Every test's grounding, cited or not, in the order they finished — what a reader
        /// needs when a board is not what they expected.</summary>
        private readonly List<(string Test, string Grounding)> groundingByTest =
            new List<(string, string)>();

        /// <summary>One reading of the clock for the whole run: every fact here was measured by one
        /// run, so facts from a single observation must not disagree about when they happened.</summary>
        private readonly string measuredAt =
            DateTime.UtcNow.ToString("yyyy-MM-dd'T'HH:mm:ss'Z'", CultureInfo.InvariantCulture);

        private string? manifestPath, runFile;

        public void Initialize(IDataCollectionSink dataCollectionSink) { }

        public void TestSessionStart(TestSessionStartArgs testSessionStartArgs)
        {
            ReadConfiguration(testSessionStartArgs.Configuration);
            // The archetype is declared on the story, never on the test (dev07-4-2); the launcher
            // has already resolved it, so this keeps no copy and reads no config.
            foreach (var fact in RunFile.Read(runFile, "archetype"))
                if (fact.Length == 2) manifest.DeclareArchetype(fact[0], fact[1]);
            // The moment "not reported" becomes a real zero: from here an empty count means this
            // run looked and found nothing (dev07-3-2).
            manifest.ObservedTests = 0;
        }

        public void TestCaseStart(TestCaseStartArgs testCaseStartArgs) { }

        public void TestCaseEnd(TestCaseEndArgs testCaseEndArgs)
        {
            var test = testCaseEndArgs.DataCollectionContext.TestCase;
            if (test == null) return;
            seen.Add(test.Id);
            manifest.ObservedTests = seen.Count;
            var name = NameOf(test);
            var result = Outcome(testCaseEndArgs.TestOutcome);
            groundingByTest.Add((name, NotChecked));
            foreach (var claim in Citations.On(test.Source, test.FullyQualifiedName))
                manifest.Add(claim.Id, new Manifest.Citation(
                    name, claim.Depth, result, NotChecked, claim.Ref, claim.About, measuredAt));
        }

        public void TestSessionEnd(TestSessionEndArgs testSessionEndArgs)
        {
            if (manifestPath == null) return;
            var version = RunFile.Read(runFile, "version");
            // After the run, as the JVM adapter records it: what made the measurements is only
            // known once they have been made (dev07-3-1).
            manifest.Observer = new Manifest.Provenance(
                "plumb-dotnet", version.Count == 0 ? "unreported" : version[0][0],
                RuntimeInformation.FrameworkDescription,
                "none — citations only, grounding not observed");
            manifest.Write(manifestPath);
            Report();
        }

        /// <summary>
        /// The runner's own word for what happened, untranslated (dev07-3-1). A skip is "specified,
        /// not built" in every framework VSTest runs.
        /// </summary>
        /// <remarks>
        /// <c>None</c> is NUnit's inconclusive — measured: MSTest's arrives as <c>Skipped</c> and
        /// NUnit's as <c>None</c>. Neither passed nor failed, so it reads as nothing observed either
        /// way, as MSTest's does; reading it as failed would claim evidence against that no test
        /// produced. <c>NotFound</c> is a test VSTest could not run at all, which is a break.
        /// </remarks>
        private static string Outcome(TestOutcome outcome) => outcome switch
        {
            TestOutcome.Passed => "passed",
            TestOutcome.Skipped => "skipped",
            TestOutcome.None => "skipped",
            _ => "failed",
        };

        /// <summary>
        /// The test, named so every row of a theory is its own. VSTest names each row of an xUnit
        /// theory or an MSTest data row by the same method, and puts the row only in the display
        /// name; NUnit puts it in the name itself. Keyed by the method alone, a failing row would
        /// hide behind a passing one.
        /// </summary>
        internal static string NameOf(TestCase test)
        {
            var name = test.FullyQualifiedName;
            var display = test.DisplayName ?? "";
            var row = display.IndexOf('(');
            if (name.IndexOf('(') < 0 && row >= 0 && display.EndsWith(")", StringComparison.Ordinal))
                name += display.Substring(row);
            return name;
        }

        private void ReadConfiguration(string? configuration)
        {
            if (string.IsNullOrWhiteSpace(configuration)) return;
            var document = new XmlDocument();
            document.LoadXml(configuration);
            manifestPath = document.SelectSingleNode("//Manifest")?.InnerText;
            runFile = document.SelectSingleNode("//RunFile")?.InnerText;
        }

        /// <summary>
        /// What was observed about every test, beside the manifest, in the lines the JVM runner
        /// prints. A file rather than stdout, because the testhost's stdout is not the launcher's
        /// to read.
        /// </summary>
        private void Report()
        {
            var o = new StringBuilder();
            o.Append("grounded ").Append(groundingByTest.Count).Append(" test(s) -> ")
             .Append(manifestPath).Append('\n');
            foreach (var (test, grounding) in groundingByTest)
                o.Append("   ").Append(grounding.PadRight(11)).Append(' ').Append(test).Append('\n');
            // Nothing cited anything: a real answer, said, because a silent empty manifest is how a
            // broken adapter looks like a spec with no work in it.
            if (manifest.IsEmpty)
                o.Append("plumb: no [Proves] citations found — nothing to derive a board from\n");
            File.WriteAllText(Path.Combine(Path.GetDirectoryName(manifestPath!)!, "report.txt"),
                              o.ToString(), new UTF8Encoding(false));
        }
    }
}
