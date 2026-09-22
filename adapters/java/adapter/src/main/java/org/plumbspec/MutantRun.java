package org.plumbspec;

import org.junit.platform.engine.TestExecutionResult;
import org.junit.platform.engine.discovery.DiscoverySelectors;
import org.junit.platform.launcher.TestIdentifier;
import org.junit.platform.launcher.TestExecutionListener;
import org.junit.platform.launcher.core.LauncherDiscoveryRequestBuilder;
import org.junit.platform.launcher.core.LauncherFactory;

import java.util.Arrays;

/**
 * Run tests against one mutant and say <em>which</em> of them noticed it (`dev07-2-3`).
 *
 * <p>Separate from {@link PlumbRunner} because it wants none of what that does. A mutant run needs
 * no manifest, no citations and no probe — every fact the full runner collects would be a fact
 * about broken code. This runs once per mutant, so what it does <em>not</em> do is the point.
 *
 * <p><b>Which tests, not whether any.</b> It used to answer with an exit code, which is one bit and
 * enough only while a mutant is compiled once per story. A mutant sitting in the scope of thirty
 * stories was compiled and run thirty times to learn the same thing about the same bytes, and the
 * only reason it had to be was that the answer could not be shared: *some test failed* cannot be
 * re-read as *this story's tests failed*. Naming the tests makes one run answer for every story
 * that scopes the mutant, and each story is still judged by its own citing tests and no others.
 *
 * <p>Usage: MutantRun &lt;unique-id&gt;...
 */
public final class MutantRun {

    /** Printed once per test that noticed. Read by {@code Mutate}; matched as a whole line. */
    static final String NOTICED = "plumb-noticed\t";

    /** Printed when nothing ran, so a broken selector cannot read as a surviving mutant. */
    static final String NOTHING_RAN = "plumb-nothing-ran";

    /** Printed once per test that actually EVALUATED the mutated expression (`dev07-2-4`).
     *
     *  <p>A test that never reaches a mutant cannot kill it, and saying so is what separates a
     *  gap in the tests from a mutant on a line the story's tests were never going to run. */
    static final String REACHED = "plumb-reached\t";

    public static void main(String[] args) {
        StringBuilder noticed = new StringBuilder();
        int[] started = {0};
        TestExecutionListener watching = new TestExecutionListener() {
            @Override
            public void executionStarted(TestIdentifier id) {
                if (!id.isTest()) return;
                started[0]++;
                // Per test, not per run: the same mutant is faced by every citing test of every
                // story that scoped it, and *which* of them reached it is the question.
                PlumbFlag.clearHit();
            }

            @Override
            public void executionFinished(TestIdentifier id, TestExecutionResult result) {
                // A test that FAILED noticed the mutant. Aborted is not noticing — an assumption
                // that did not hold says nothing about whether the code changed underneath it.
                if (!id.isTest()) return;
                if (result.getStatus() == TestExecutionResult.Status.FAILED)
                    noticed.append(NOTICED).append(id.getUniqueId()).append('\n');
                if (PlumbFlag.wasHit())
                    noticed.append(REACHED).append(id.getUniqueId()).append('\n');
            }
        };
        LauncherFactory.create().execute(
                LauncherDiscoveryRequestBuilder.request()
                        .selectors(Arrays.stream(args)
                                .map(DiscoverySelectors::selectUniqueId).collect(java.util.stream.Collectors.toList()))
                        .build(),
                watching);

        System.out.print(noticed);
        // A mutant nothing ran is not a mutant anything survived. Said rather than left to the
        // reader of an empty list, and the caller treats it as noticed by everything it asked for
        // — the direction that cannot invent confidence: it never credits a test with a kill it
        // earned, but a selector resolving to nothing is a broken invocation, not a weak test.
        if (started[0] == 0) System.out.println(NOTHING_RAN);
        System.out.flush();
        // END THE PROCESS. A suite that leaves a non-daemon executor running keeps the JVM alive
        // after the last test, and this one is waited on.
        System.exit(0);
    }
}
