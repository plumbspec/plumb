package org.plumbspec;

import org.junit.platform.launcher.core.LauncherFactory;
import org.junit.platform.launcher.core.LauncherDiscoveryRequestBuilder;
import org.junit.platform.engine.discovery.DiscoverySelectors;

import java.nio.file.Path;

/**
 * Run a JUnit Platform suite and emit the manifest. This is the adapter's whole entry point:
 * a test run in, one document out (`dev07-3-3`).
 *
 * Usage: PlumbRunner <test-classpath-root> <manifest-out> [resolved-run-file]
 */
public final class PlumbRunner {

    public static void main(String[] args) throws Exception {
        // One argument, one or more roots, split on the platform separator the way a classpath is
        // (`dev07-1-4`). A spec can describe a system whose modules compile separately, and a runner
        // that discovers from one of them answers for a subset of the spec while presenting itself
        // as answering for all of it.
        java.util.Set<Path> classes = new java.util.LinkedHashSet<>();
        for (String one : args[0].split(java.io.File.pathSeparator))
            if (!one.isBlank()) classes.add(Path.of(one));
        Path out = Path.of(args.length > 1 ? args[1] : "manifest.json");

        // **Before the suite runs, and whether or not this is a mutation run** (`dev07-2-3`). A
        // mutant left by a killed run is silent: the source compiles, the tests pass or fail
        // against code the project never wrote, and the board reports it as the project. Recovered
        // here rather than only in `Mutate` because an ordinary board is what an adopter runs next.
        Path put = Mutate.restore(out.toAbsolutePath().getParent());
        if (put != null)
            System.out.println("plumb: put back " + put + " — a previous mutation run was interrupted");

        PlumbListener listener = new PlumbListener();
        // Beside the manifest, because that is the directory the launcher already owns and
        // watches. A run that cannot say where it is gets killed by an operator who cannot
        // tell it from a hang (`dev07-1-3`).
        listener.reportProgressTo(out.resolveSibling("progress.txt"));
        // What made these measurements, carried beside them (`dev07-3-1`). One mechanism now: there is
        // no second process, so there is no run that produced facts a different way.
        Path runFile = args.length > 2 ? Path.of(args[2]) : null;
        boolean declaredEntryPoints = !RunFile.read(runFile, "entrypoint").isEmpty();
        // Told, never known: this jar ships inside the tool, so the tool is the only thing that
        // can say which version it is. A constant here is a second home for that fact.
        var declaredVersion = RunFile.read(runFile, "version");
        // dev07-4-2: the archetype is declared on the story, in the spec — never on the test, which
        // would let the thing being judged pick its own gate. This adapter no longer keeps its
        // own copy: the launcher resolves them and hands them over already decided, so there is
        // one reader of configuration and it is not here. Silence means behavioral, so a project
        // that never mentions one is unchanged.
        for (String[] fact : RunFile.read(runFile, "archetype"))
            if (fact.length == 2) listener.manifest().declareArchetype(fact[0], fact[1]);
        LauncherFactory.create().execute(
                LauncherDiscoveryRequestBuilder.request()
                        .selectors(DiscoverySelectors.selectClasspathRoots(classes))
                        .build(),
                listener);

        // AFTER the run, not before it. What made these measurements is only known once they have
        // been made: nothing is instrumented until the classes load, so a provenance recorded at
        // setup reports "grounding not observed" on a run that observed it perfectly (`dev07-3-1`).
        listener.manifest().observedBy(new Manifest.Provenance(
                "plumb-java",
                declaredVersion.isEmpty() ? "unreported" : declaredVersion.get(0)[0],
                System.getProperty("java.vm.name") + " " + System.getProperty("java.version"),
                PlumbFlag.instrumentedAnything()
                        ? "bytecode probes, in process (production surface and entry points)"
                        : "none — citations only, grounding not observed"));

        listener.settle();
        // What was observed about every test, cited or not. The board carries only the cited half
        // (`dev07-3-2`), and this is what a reader needs when a board is not what they expected.
        System.out.println("grounded " + listener.groundingByTest().size() + " test(s) -> " + out);
        for (java.util.Map.Entry<String, String> each : listener.groundingByTest().entrySet())
            System.out.printf("   %-11s %s%n", each.getValue(), each.getKey());

        Path written = listener.manifest().write(out);
        System.out.println("manifest -> " + written);
        // `story<TAB>test<TAB>result`, beside the manifest. Chapter 4 runs as a third step, after
        // the observer has had its say, and it needs the citations as data — reading them back
        // out of the JSON would mean writing a parser for a document we are holding.
        StringBuilder citations = new StringBuilder();
        listener.manifest().stories().forEach((story, cited) -> cited.forEach(c ->
                citations.append(story).append('\t').append(c.test())
                         .append('\t').append(c.result()).append('\n')));
        java.nio.file.Files.writeString(out.resolveSibling("citations.tsv"), citations.toString());
        // `test<TAB>site,site,...`, beside the citations, for the same reason: chapter 4 runs as a
        // separate process after this one and needs both as data. Written on every run, empty when
        // nothing was scoping — a file that is present and empty says "asked, nothing drove
        // anything", where an absent one cannot be told from a run that never collected.
        StringBuilder drove = new StringBuilder();
        listener.wiredByTest().forEach((test, sites) ->
                drove.append(test).append('\t').append(String.join(",", sites)).append('\n'));
        java.nio.file.Files.writeString(out.resolveSibling("wired.txt"), drove.toString());
        // `caller<TAB>callee`, one line per distinct edge, beside the citations for the same reason
        // the scope is (`dev07-1-3`). A set, so the file says which joins exist and never how often
        // one was taken. Written on every run and empty when edges were not asked for — present
        // and empty is "asked, nothing joined", which an absent file cannot say.
        StringBuilder joins = new StringBuilder();
        for (String edge : Sites.taken()) joins.append(edge).append('\n');
        java.nio.file.Files.writeString(out.resolveSibling("edges.tsv"), joins.toString());
        // `dev07-1-3`, with the cause it has now. `not-checked` from `dev07-1-4` means nobody said where
        // the wired system begins; from here it means they did and the instrument never reached it,
        // and the reader's next move differs. One word, two causes, said apart.
        if (!PlumbFlag.instrumentedAnything() && (PlumbFlag.surfaceDeclared() || declaredEntryPoints))
            System.out.println(NOTHING_INSTRUMENTED + " — the surface or entry points were declared "
                    + "and the agent rewrote nothing, so no grounding was observed. Check that the "
                    + "production classes are not under a declared test root.");
        if (listener.manifest().isEmpty()) {
            // Nothing cited anything. Say so: a manifest with no stories is a real answer, and a
            // silent empty file is how a broken adapter looks like a spec with no work in it.
            System.out.println("WARNING: no @Proves citations found — nothing to derive a board from");
        }
        // END THE PROCESS. A suite that leaves a non-daemon executor running keeps the JVM alive
        // indefinitely after the last test — most real ones do — and nothing waits for this process
        // any more. `dev07-1-3` removed the observer, which is what used to notice the run was over
        // and let the launcher stop waiting; the runner says it itself now, by ending.
        System.out.flush();
        System.exit(0);
    }

    /** Printed when a declared surface was never reached by the instrument (`dev07-1-3`). Matched as a
     *  prefix by the launcher, so the sentence beside it can be reworded without breaking the read. */
    public static final String NOTHING_INSTRUMENTED = "plumb: nothing was instrumented";
}
