package org.plumbspec;

import org.junit.platform.engine.TestExecutionResult;
import org.junit.platform.engine.support.descriptor.MethodSource;
import org.junit.platform.launcher.TestExecutionListener;
import org.junit.platform.launcher.TestIdentifier;
import org.junit.platform.launcher.TestPlan;

import java.lang.reflect.Method;
import java.util.*;

/**
 * Watches a JUnit Platform run and turns it into facts (`dev07-3-1`) — never a verdict.
 *
 * Two things arrive at different moments and only the pair is a fact: what a test *claims*, read
 * from its annotations, and how the runner *finished* it. Both are collected here and nothing is
 * decided; the core reads the manifest and derives status.
 */
public final class PlumbListener implements TestExecutionListener {

    /** No trace yet, so grounding is honestly unanswered rather than guessed (`dev07-1-4`, dev07-1-4). */
    static final String NOT_CHECKED = "not-checked";

    private final Manifest manifest = new Manifest();

    /** Every test this run saw, cited or not (`dev07-3-2`).
     *
     *  A set rather than a counter because a test reaches this listener by more than one route —
     *  a skip arrives at `executionSkipped` and a run at `executionFinished` — and counting
     *  events would report a number that is not the number of tests. */
    private final Set<String> seen = new HashSet<>();

    public Manifest manifest() { return manifest; }

    /** Where to write progress, and how many tests this run discovered (`dev07-1-3`).
     *
     *  <p>A LONG RUN HAS TO SAY WHERE IT IS, not only that it is still going. Measured on a suite:
     *  9h46m in which the only signal was a heartbeat repeating the same sentence, test position
     *  obtainable only by grepping the raw output, and no way to estimate what remained — so the
     *  run was killed at a scheduling cap, minutes or hours from the evidence it was about to
     *  deliver. An operator who cannot estimate completion kills correct runs.
     *
     *  <p>To a file rather than to stdout, which the project's own logging owns — thousands of
     *  lines of it on a real suite. A file is also what a second process can read at any moment
     *  without having consumed the stream. */
    private java.nio.file.Path progress;
    private int discovered;

    public void reportProgressTo(java.nio.file.Path file) { this.progress = file; }

    @Override
    public void testPlanExecutionStarted(TestPlan plan) {
        // The denominator, known before the first test runs and never after — this is the moment
        // it exists. A percentage without it is a count wearing a percent sign.
        discovered = (int) plan.countTestIdentifiers(TestIdentifier::isTest);
        say(0);
        // The moment "not reported" becomes a real zero: the launcher is running, so from here on
        // an empty count means this run looked and found nothing, rather than never having looked.
        // Recorded at the START for that reason — set it at the end and a run that dies mid-flight
        // reports the strong claim on the strength of not having finished (`dev07-3-2`, `dev07-3-3`).
        manifest.observed(0);
    }

    @Override
    public void executionStarted(TestIdentifier id) {
        // Opens the window (`dev07-1-4`). Cleared rather than merely read, so what a test sees is its
        // own execution and never the residue of the one before it.
        if (id.isTest()) PlumbFlag.reset();
    }



    @Override
    public void executionFinished(TestIdentifier id, TestExecutionResult result) {
        if (id.isTest()) {
            grounding = grounding();
            groundingByTest.put(id.getUniqueId(), grounding);
            // Read BEFORE the reset below, which is what makes it this test's scope and not the
            // suite's. Empty on an ordinary run: the site names are only recorded while chapter 4
            // is scoping, so this costs a lookup of an empty set per test the rest of the time.
            Set<String> drove = PlumbFlag.wiredHere();
            if (!drove.isEmpty()) wiredByTest.put(id.getUniqueId(), drove);
            // CLOSE the window as well as open it. Work handed to a pool can reach an entry point
            // after the test that submitted it has finished, and with nothing closing the window
            // that arrival was still in the set when the NEXT test opened — charging one test's
            // hand-off to a test that did nothing. Both readings are wrong, and they are not
            // equally wrong: a missed arrival costs the guilty test its status, a borrowed one
            // grants status to an innocent, and only the second can turn an unproven story proven.
            PlumbFlag.reset();
        }
        record(id, outcome(result.getStatus()));
    }

    /** The runner's own word for what happened, untranslated (``dev07-3-1``). */
    private static String outcome(TestExecutionResult.Status status) {
        switch (status) {
            case SUCCESSFUL: return "passed";
            // JUnit's abort is the "specified but not built" signal, exactly as pytest's skip is.
            case ABORTED:    return "skipped";
            case FAILED:     return "failed";
            default:         return "failed";
        }
    }

    @Override
    public void executionSkipped(TestIdentifier id, String reason) {
        record(id, "skipped");
    }

    /** One reading of the clock for the whole run (`dev07-3-2`'s reason, one field over): every
     *  fact here was measured by one run, so re-reading it per citation would make facts from a
     *  single observation disagree about when they happened. RFC 3339 in UTC, the one spelling
     *  every language reads without an argument about format. */
    private final String measuredAt = java.time.Instant.now()
            .truncatedTo(java.time.temporal.ChronoUnit.SECONDS).toString();

    /** What this run is entitled to say about the test that just closed (`dev07-1-4`, `dev07-1-4`, `dev07-1-4`).
     *
     *  <p>Read here rather than watched from outside. A debugger attached to the running suite was
     *  442 lines of which almost none was about grounding — a port, a handshake, an attach retried
     *  against a deadline, a breakpoint whose class the VM unloaded, a VM suspended at startup that
     *  nothing would finish. The listener is already in the process where the answer is, and an
     *  entry point is a method that can carry a probe (`dev07-1-3`).
     *
     *  <p><b>The thread is the whole distinction.</b> The test's own thread reaching a declared
     *  entry point is `grounded`. Another thread reaching one is `dispatched` — and that says more
     *  than a hand-off primitive firing did, because it reports the entry point was actually
     *  reached rather than that work went somewhere unobservable. */
    private String grounding() {
        if (PlumbFlag.enteredOn(Thread.currentThread().getId())) return "grounded";
        if (PlumbFlag.enteredAnywhere()) return "dispatched";
        // `inert` is the positive claim that no production code ran, and it may be made only where
        // a surface was declared and instrumented — otherwise the honest answer is the weaker one
        // (`dev07-1-4`). `PlumbFlag` cannot tell an undeclared surface from an unwatched one, so the
        // agent's own count is what separates them.
        // Work left for a thread this run is not following, and did not arrive before the window
        // closed. `dev07-1-4`: a hand-off SEEN is what licenses `dispatched`, and it is the honest fact
        // when the alternative is claiming the wired system was not reached by work we stopped
        // watching. An arrival is the better answer and is checked first; this is what is left.
        if (PlumbFlag.handedOff) return "dispatched";
        if (PlumbFlag.ran) return "ungrounded";
        if (!PlumbFlag.surfaceDeclared()) return "ungrounded";
        // The split manifest major 8 asks for. `inert` is the POSITIVE claim that the artifact was
        // read and none of it run — the proof a structural story needs (`dev07-4-2`) — so it is made
        // only where a read was actually seen. Nothing touched in either way is `untouched`, which
        // proves nothing and says so. Granting `inert` from the absence alone is what pinned this
        // adapter at major 7.
        return PlumbFlag.readSomething() ? "inert" : "untouched";
    }

    /** Settle what only the finished run can answer, and correct every fact that assumed otherwise.
     *
     *  <p>Whether the instrument reached the project is a property of the run, not of a test:
     *  nothing is instrumented until classes load, so asking it while the first test closes gets a
     *  different answer than asking while the last one does. Asked once, at the end, and applied to
     *  everything — `grounded` and `dispatched` stand either way, because they are positive
     *  observations; `inert` and `ungrounded` were read from an absence and become `not-checked`
     *  when there was nothing there to observe with (`dev07-1-4`, `dev07-1-3`). */
    public void settle() {
        if (PlumbFlag.instrumentedAnything()) return;
        for (java.util.Map.Entry<String, String> each : groundingByTest.entrySet())
            if (!"grounded".equals(each.getValue()) && !"dispatched".equals(each.getValue()))
                each.setValue(NOT_CHECKED);
        manifest.ground(groundingByTest);
    }

    /** The grounding of the test currently closing, read before its citations are recorded. */
    private String grounding = NOT_CHECKED;

    /** Every test's grounding, cited or not, in the order they finished.
     *
     *  <p>The manifest carries the cited half, because grounding is recorded against a citation.
     *  This is the other half, and it is what a person reads when a board is not what they
     *  expected: an uncited test reading `inert` says the surface was watched, and one reading
     *  `not-checked` says it was not, and neither fact reaches a board. The observer used to print
     *  it and there is no reason for losing it to be the price of retiring the observer. */
    private final java.util.Map<String, String> groundingByTest = new java.util.LinkedHashMap<>();

    public java.util.Map<String, String> groundingByTest() { return groundingByTest; }

    /** What each test drove **under a declared entry point**, and nothing wider (`dev07-2-1`).
     *
     *  <p>Per test rather than per run, because that is the granularity chapter 4 mutates at: a
     *  story's scope is the union over the tests that cite it, and a union taken over the whole
     *  suite would hand every story every method any test touched — which stops the fact
     *  distinguishing anything and mutates the codebase once per story.
     *
     *  <p>Only tests that drove something appear. An absent test is one that drove nothing under an
     *  entry point, which is the same answer as an empty set and does not need a row to say it. */
    private final java.util.Map<String, Set<String>> wiredByTest = new java.util.LinkedHashMap<>();

    public java.util.Map<String, Set<String>> wiredByTest() { return wiredByTest; }

    /** One line, rewritten in place: `<done> <discovered> <unix-millis>`.
     *
     *  <p>Rewritten rather than appended so the file is the current position and never a log to
     *  scan, and written on every test rather than on a timer because the cost is one small write
     *  against a test that has just done real work. Failures are swallowed: a run must not die
     *  because nobody could be told how far along it was. */
    private void say(int done) {
        if (progress == null) return;
        try {
            Text.write(progress,
                    done + " " + discovered + " " + System.currentTimeMillis());
        } catch (Exception unreportable) {
            // Progress is a courtesy. The run is the point.
        }
    }

    private void record(TestIdentifier id, String result) {
        if (!id.isTest()) return;
        // Counted before the citations are read, and deliberately outside that loop: the fact
        // wanted here is that a test was *observed*, which is true whether or not it cites
        // anything. Counting citations instead would make an uncited suite report zero and put
        // every project's first run back under the same alarm (`dev07-3-2`).
        seen.add(id.getUniqueId());
        manifest.observed(seen.size());
        // Here, not at the top of `executionFinished`: this is where a test becomes one this run
        // has *finished*, and it is the one place both routes into the listener pass through — a
        // skip arrives at `executionSkipped` and never at the other, so counting there would stall
        // the position on any suite that skips.
        say(seen.size());
        for (Proves cited : citationsOn(id, Proves.class)) {
            manifest.add(cited.value(), new Manifest.Citation(
                    id.getUniqueId(), cited.depth(), result, grounding,
                    cited.ref().isEmpty() ? null : cited.ref(),
                    // A story has one aspect, so @Proves names none (`dev07-3-1`, `dec1-17`).
                    null, measuredAt));
        }
        for (Informs informed : citationsOn(id, Informs.class)) {
            manifest.add(informed.value(), new Manifest.Citation(
                    // No depth, and none invented: a rung the run cannot refute would be a claim
                    // nothing could lose, which is `dec1-3`'s prohibition wearing a new name.
                    id.getUniqueId(), "", result, grounding,
                    informed.ref().isEmpty() ? null : informed.ref(),
                    informed.about().isEmpty() ? null : informed.about(), measuredAt));
        }
    }

    /** The citations of one kind a test declares, class-level ones included. */
    private <A extends java.lang.annotation.Annotation> List<A> citationsOn(
            TestIdentifier id, Class<A> kind) {
        Object source = id.getSource().orElse(null);
        if (!(source instanceof MethodSource)) return java.util.Collections.emptyList();
        MethodSource method = (MethodSource) source;
        try {
            Class<?> owner = Class.forName(method.getClassName());
            Method target = Arrays.stream(owner.getDeclaredMethods())
                    .filter(m -> m.getName().equals(method.getMethodName()))
                    .findFirst().orElse(null);
            List<A> found = new ArrayList<A>();
            if (target != null) found.addAll(Arrays.asList(target.getAnnotationsByType(kind)));
            found.addAll(Arrays.asList(owner.getAnnotationsByType(kind)));
            return found;
        } catch (NoClassDefFoundError older) {
            // Their `plumb-annotations` predates this citation kind. Every other citation on the
            // test still reads, so the run degrades rather than losing the lot (`dev07-5-1`) — the
            // failure mode found the hard way, where a missing member took every citation in a
            // project with it and the board read "you have not cited anything yet".
            return java.util.Collections.emptyList();
        } catch (ClassNotFoundException unavailable) {
            // A test whose class cannot be loaded cites nothing we can read. Report no citation
            // rather than inventing one — an adapter never decides (`dev07-3-1`).
            return java.util.Collections.emptyList();
        }
    }
}
