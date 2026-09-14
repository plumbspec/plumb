package org.plumbspec;

/**
 * A task handed to a pool, carrying the window it was handed over from (`dev07-1-4`, `dev07-2-1`).
 *
 * <p>A pooled hand-off names no thread. The pool picks one later, and the same thread serves every
 * submitter, so filing the window under a thread — which is right for {@code Thread.start} — would
 * hand this run's window to whatever the pool ran next. Filing it against the TASK is the
 * correlation that survives being queued.
 *
 * <p><b>A top-level class, and the second thing in the boot jar.</b> {@link PlumbFlag} may hold no
 * inner classes and no lambdas: it is resolved by the bootstrap loader on behalf of instrumented
 * JDK classes, and a reference that loader cannot satisfy is a fatal VM error during the agent's
 * premain rather than a missing fact. This is that rule obeyed rather than worked around — the
 * wrapper has to exist somewhere, so it exists as its own file and ships beside the probe.
 *
 * <p>Deliberately not a {@code Callable} or a {@code ForkJoinTask} as well. The one primitive this
 * wraps is {@code ThreadPoolExecutor.execute(Runnable)}, which is what every {@code ExecutorService}
 * funnels through — including the {@code CompletableFuture.supplyAsync(…, executor)} form, whose
 * supplier runs inside an {@code AsyncSupply} runnable. Widening the set is a pointcut change and
 * needs a measurement, not an assumption.
 */
final class PlumbCarrier implements Runnable {

    private final Runnable task;

    PlumbCarrier(Runnable task) {
        this.task = task;
    }

    @Override
    public void run() {
        PlumbFlag.carried();
        try {
            task.run();
        } finally {
            // BY WHICHEVER PATH. A task that throws has still done the work it did, and a window
            // left open would follow this thread into whatever the pool ran next — which is the
            // imprecision this class exists to remove, reintroduced by an exception.
            PlumbFlag.released();
        }
    }

    /** What the wrapped task says it is. A pool that logs or compares its queue should see the
     *  task rather than the wrapper, and a thread dump reading `PlumbCarrier` tells an operator
     *  looking at their own system the wrong thing. */
    @Override
    public String toString() {
        return String.valueOf(task);
    }
}
