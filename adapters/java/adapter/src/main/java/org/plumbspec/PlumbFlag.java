package org.plumbspec;

// The only import in this file, and it earns its place twice over: `Path` is `java.base`, so the
// bootstrap loader resolves it for the instrumented JDK classes that call in here, and the probe's
// signature has to read `Path read(Path` for the check that the advice and the probe agree — a
// fully-qualified spelling is the same type and fails that check, which is the check standing
// between a mismatch and a `NoSuchMethodError` inside `java.nio.file.Files`.
import java.nio.file.Path;

/**
 * The one bit `inert` needs, written by the code itself instead of watched from outside.
 *
 * <p>`inert` is a positive claim that no production code ran, and proving a negative meant asking
 * the VM to watch every production method. Both ways of asking cost: a breakpoint charges per
 * location armed, a method-entry request charges for every second it is armed, and which one is
 * ruinous depends on runtime behaviour no static property predicts. Measured on two real suites,
 * each instrument was the cheap one on one of them and catastrophic on the other.
 *
 * <p>A store to a static is neither. Measured at 0.49ns per call volatile, 1,000,000 production
 * calls in one test for half a millisecond, against a budget of 45ms — and independent of how large
 * the surface is or how long a test runs before it reaches production code.
 *
 * <p>Volatile because a test may hand work to a pool and the answer is still about that test: a
 * plain store is free but carries no promise the reading thread sees it.
 */
public final class PlumbFlag {

    private PlumbFlag() { }

    /** Set by every instrumented production method. Read and cleared around each test. */
    public static volatile boolean ran;

    /** How many call sites can be named. A slot is a byte, so the whole array is 32KB. */
    public static final int SITES = 32768;

    /**
     * One slot per woven call site (``dev07-1-3``). Set to `true` by an eight-byte advice at the site
     * itself; the `(caller, callee)` pair each index stands for is held by the weaver and never by
     * the running program.
     *
     * <p>Not volatile, and that is a deliberate difference from {@link #ran}. A missed write costs
     * one edge on one run out of a set that a suite fills many times over, where making every
     * production call site pay a memory barrier would be the one cost this design exists to avoid.
     * {@link #ran} is volatile because a single missed write there is a story graded wrongly.
     */
    public static final boolean[] sites = new boolean[SITES];


    /** How many production classes were actually rewritten.
     *
     *  <p><b>`inert` is read from the ABSENCE of a hit, and an instrument that never ran produces
     *  exactly that absence.</b> The two are indistinguishable from the flag alone, and the wrong
     *  one of them is the strongest claim the gate can make — so `inert` needs a positive fact that
     *  something was watching, which is what this is.
     *
     *  <p>Three separate defects reached this the long way, and each was a different route to the
     *  same place: a test root matched by bare string prefix so production was excluded with the
     *  tests; production and tests compiled to one directory so the question could not be answered;
     *  and javac implicitly compiling a production class into the test output as well, which came
     *  and went with file timestamps. Each was fixed where it happened. This is the check that
     *  makes the next one — a symlinked output, a shaded jar, a layout nobody here has seen — fail
     *  loudly instead of proving every structural story on the strength of nothing looking. */
    public static final java.util.concurrent.atomic.AtomicInteger instrumented =
            new java.util.concurrent.atomic.AtomicInteger();

    /** Called from instrumented bytecode. Kept as a field write rather than a method call so the
     *  inserted sequence is `iconst_1; putstatic` — four bytes, no stack depth beyond one, and
     *  nothing for the verifier to reason about. */
    public static boolean take() {
        boolean was = ran;
        ran = false;
        return was;
    }

    /** Threads that ran a declared entry point since the window opened (`dev07-1-3`).
     *
     *  <p>Grounding was watched by a debugger attached to the running suite, which is a second
     *  process on a socket and everything that has to survive: an attach retried against a
     *  deadline, a breakpoint whose class the VM unloaded, a suspended VM nothing will finish. None
     *  of that was about grounding. An entry point is a method, a method can carry a prologue, and
     *  the listener that needs the answer is already in this process.
     *
     *  <p>A set of threads rather than a bit, because the thread is the whole distinction: the
     *  test's own means `grounded`, another means the work was handed off and still arrived
     *  (`dev07-1-4`) — which is more than a hand-off primitive firing tells you, since that says work
     *  left and not that it got anywhere. */
    private static final java.util.Set<Long> entered =
            java.util.Collections.newSetFromMap(new java.util.concurrent.ConcurrentHashMap<Long, Boolean>());

    /** How deep inside a declared entry point this thread currently is (`dev07-2-1`).
     *
     *  <p>A count rather than a flag because an entry point can call itself, directly or through
     *  code it dispatches to, and a flag cleared by the first return would close a window still
     *  open. Thread-local because the question is per thread — the same entry point may be running
     *  on two at once. */
    //  NO INNER CLASSES, NO LAMBDAS, IN THIS FILE. It ships as its own jar on the bootstrap
    //  class path so that instrumented JDK classes can resolve it, and a bootstrap loader that
    //  finds `PlumbFlag` and not `PlumbFlag$1` fails during the agent's premain — which is a fatal
    //  VM error before a line of the suite runs, not a missing fact. An anonymous ThreadLocal
    //  subclass is the ordinary way to write this and it is the way that breaks.
    private static final ThreadLocal<int[]> depth = new ThreadLocal<int[]>();

    private static int[] here() {
        int[] held = depth.get();
        if (held == null) { held = new int[1]; depth.set(held); }
        return held;
    }

    /** Threads this window explicitly started (`dev07-1-4`).
     *
     *  <p><b>The window travels with the work, and only with the work.</b> The first fix for a
     *  dispatching system was a global count of open entry points — record on any thread while any
     *  window is open. That recovered the work and swept in every unrelated thread that happened to
     *  run production code at the same moment, which on a scheduled application is a great deal of
     *  it. A mutant made where no test reached is a survivor nobody can kill, and `dev07-2-3` is
     *  already about how expensive one of those is to read.
     *
     *  <p>So a hand-off is *correlated* rather than assumed. `Thread.start` runs on the starting
     *  thread and names the thread it starts, so the window is filed under that thread and read
     *  back by the code it runs. A pooled task names no thread — the pool picks one later and the
     *  same thread serves everybody — so that window is filed against the TASK instead, by
     *  wrapping it, and the wrapper opens the window on whichever thread ends up running it. */
    private static final java.util.Map<Thread, Boolean> started =
            new java.util.concurrent.ConcurrentHashMap<Thread, Boolean>();

    /** Called on entering a declared entry point. */
    public static void entered() {
        entered.add(Thread.currentThread().getId());
        here()[0]++;
    }

    /** Called on leaving one, by whichever path — returned or threw.
     *
     *  <p>Woven by generating a method around the original rather than by inserting before every
     *  return, so this runs from a `finally` that was authored rather than derived. */
    public static void left() {
        int[] held = here();
        if (held[0] > 0) held[0]--;
    }

    /** Production methods that ran while an entry point was on this thread's stack (`dev07-2-1`).
     *
     *  <p>Chapter 4 mutates this and no wider — never the whole call tree, which pulls in every
     *  helper a test brushed past and stops the fact distinguishing anything. Recorded only while
     *  scoping: an ordinary run wants the bit `inert` reads and pays a store, this pays a call and
     *  a constant per site. */
    private static final java.util.Set<String> wired =
            java.util.Collections.newSetFromMap(new java.util.concurrent.ConcurrentHashMap<String, Boolean>());

    /** Called from an instrumented production method while chapter 4 is scoping. */
    public static void wired(String site) {
        ran = true;
        if (here()[0] > 0 || started.containsKey(Thread.currentThread())) wired.add(site);
    }

    /** Called on `Thread.start`, naming the thread being started (`dev07-1-4`).
     *
     *  <p>Filed against that thread, so the window is read back by the code it runs rather than
     *  offered to every thread alive at the time. A thread started outside the window files
     *  nothing, which is what keeps unrelated work out. */
    public static void handoffTo(Thread receiving) {
        handedOff = true;
        if (here()[0] > 0 && receiving != null) started.put(receiving, Boolean.TRUE);
    }

    //  WHAT THIS COSTS, MEASURED. A pool creates its worker threads lazily, so a worker first
    //  needed inside a window is STARTED inside it and carries the window for the rest of that
    //  test — including tasks another thread hands it. That is the one imprecision left, and it
    //  is bounded by `reset()` at the test boundary.
    //
    //  Measured on a suite whose front door dispatches to a single-threaded executor: disabling
    //  this mark entirely changed the scope by nothing at all — 33 classes and 147 methods either
    //  way — because a pooled task is correlated by the task, which is exact. What the mark buys
    //  is `new Thread(runnable).start()`, which correlates no other way; what it risks did not
    //  arise. Kept on that evidence rather than on the reasoning, and the reasoning alone would
    //  have argued either way.

    /** Called on a pooled hand-off, wrapping the task so the window travels with it.
     *
     *  <p>Returns the task unchanged when no window is open, which is almost always the case: a
     *  JVM submits work to pools constantly and none of it is this run's business. */
    public static Runnable carry(Runnable task) {
        handedOff = true;
        if (task == null || here()[0] < 1) return task;
        return new PlumbCarrier(task);
    }

    /** Called by a carrier as it begins, on whichever thread the pool gave it. */
    public static void carried() {
        here()[0]++;
    }

    /** Called by a carrier as it ends, by whichever path. */
    public static void released() {
        int[] held = here();
        if (held[0] > 0) held[0]--;
    }

    /** What ran under an entry point during this window, and nothing wider. */
    public static java.util.Set<String> wiredHere() {
        return new java.util.TreeSet<String>(wired);
    }

    /** Work left for a thread this run is not following (`dev07-1-4`).
     *
     *  <p>An arrival is the better fact and this is not it: `entered` says the wired system was
     *  reached, on whichever thread. This says only that work departed, which is what remains
     *  knowable when it arrives after the test that sent it has finished. Without it such a test
     *  reads `ungrounded` — a definite negative — where the truth is that we stopped looking. */
    public static volatile boolean handedOff;

    /** Did this test's own thread reach a declared entry point? */
    public static boolean enteredOn(long thread) {
        return entered.contains(thread);
    }

    /** Did any thread — including one the test handed work to? */
    public static boolean enteredAnywhere() {
        return !entered.isEmpty();
    }

    /** Whether the agent's premain ran at all, and whether a production surface was declared to it.
     *
     *  <p>Neither is inferable from the flag. An unset flag means <em>nothing ran</em> or
     *  <em>nothing was watching</em>, and reading the second as the first is how `inert` gets
     *  asserted where nobody looked (`dev07-1-4`). These two say which case it is, so the adapter can
     *  answer `not-checked` — a question that was not asked — instead of a claim it cannot support. */
    public static volatile boolean armed;
    public static volatile boolean surface;

    /** Did the agent run and rewrite something? A declared surface that matched nothing is not an
     *  observation about the project; it is the instrument having failed to reach it. */
    public static boolean instrumentedAnything() {
        return armed && instrumented.get() > 0;
    }

    /** Was a production surface declared? `inert` is assertable only where one was (`dev07-1-4`). */
    public static boolean surfaceDeclared() {
        return surface;
    }

    /** Production classes as RESOURCE prefixes — `com/acme/` for a declared `com.acme.*`.
     *
     *  <p>A plain array and a hand-rolled loop because this class is resolved by the bootstrap
     *  loader on behalf of instrumented JDK classes: no lambdas, no inner classes, no streams, and
     *  nothing it can be made to load that the boot loader cannot satisfy. */
    private static volatile String[] productionPaths = new String[0];

    /** Told once at premain, from the same patterns the weaver is given. */
    public static void declareProduction(String[] paths) {
        productionPaths = paths == null ? new String[0] : paths;
    }

    /** Did a test READ the production artifact as data, rather than run it?
     *
     *  <p>`inert` is the positive half of `dev07-4-2` — *read it and ran none of it* — and from
     *  manifest major 8 it may be asserted only where the read was actually seen. Without this the
     *  JVM adapter granted `inert` from an absence, which is the orphaned-"done" fake wearing the
     *  one costume the gate was built to trust, and is why the adapter could not leave major 7.
     *
     *  <p>Under-reporting is the safe direction and is why one join point is enough to start: a
     *  read this misses falls back to `untouched`, which WITHHOLDS a structural story's proof. A
     *  read it invented would grant one. */
    private static volatile boolean readProduction;

    /** Sits in the argument slot of a resource load, so the name passes through unchanged. */
    public static String sawRead(String resource) {
        if (resource != null && names(resource)) readProduction = true;
        return resource;
    }

    /** The same, where the primitive names a path rather than a resource. */
    public static Path sawReadPath(Path path) {
        if (path != null && names(path.toString())) readProduction = true;
        return path;
    }

    /** Does what was read name a declared production class?
     *
     *  <p>A read names a FILE or a resource; production is declared as classes and packages, and
     *  the two are spelled differently — `com.acme.*` against `.../com/acme/Foo.class`, and a bare
     *  `App` against `build/out/App.class`. Both forms are checked because both are what adopters
     *  write, and a miss costs a structural story its proof rather than granting one. */
    private static boolean names(String read) {
        String path = read.replace('\\', '/');
        String[] declared = productionPaths;
        for (int i = 0; i < declared.length; i++) {
            String pattern = declared[i];
            if (pattern == null || pattern.length() == 0) continue;
            boolean wildcard = pattern.endsWith("*");
            while (pattern.endsWith("*")) pattern = pattern.substring(0, pattern.length() - 1);
            while (pattern.endsWith(".")) pattern = pattern.substring(0, pattern.length() - 1);
            String slashed = pattern.replace('.', '/');
            if (slashed.length() == 0) continue;
            if (wildcard) {
                if (path.indexOf(slashed + "/") >= 0) return true;
            } else {
                if (path.endsWith("/" + slashed + ".class") || path.equals(slashed + ".class")
                        || path.indexOf(slashed + ".class") >= 0) return true;
            }
        }
        return false;
    }

    /** Whether the artifact was read as data during this window. */
    public static boolean readSomething() {
        return readProduction;
    }


    /** Did the mutant on this run's mutated line actually execute (`dev07-2-4`)?
     *
     *  <p><b>A survivor nobody reached is not a weak test.</b> The mutation scope is the methods a
     *  test drove, and a method is scoped whole — so a story whose test sends one kind of event
     *  gets mutants on the guard clauses for every other kind, on lines it never enters. Those
     *  cannot be killed by that test however good it is, and reporting them beside real gaps sends
     *  a reader to fix code their test was never going to reach.
     *
     *  <p>Unlike equivalence, which is undecidable and stays open as `dev07-2-4`, reachedness is a
     *  fact anyone can observe: run the mutant and see whether the changed expression evaluated.
     *  {@code Mutants} wraps the mutated expression in a call to {@link #hit}, so the probe is
     *  exactly one call on exactly the line in question, and no coverage tool is taken on
     *  (`dev07-1-3`).
     *
     *  <p>Overloaded per primitive rather than generic-only, so a mutant in a hot path does not
     *  start boxing, and so inference cannot fail where a bare `<T> T` would. */
    private static volatile boolean hit;

    public static boolean hit(boolean v) { hit = true; return v; }
    public static int hit(int v) { hit = true; return v; }
    public static long hit(long v) { hit = true; return v; }
    public static double hit(double v) { hit = true; return v; }
    public static float hit(float v) { hit = true; return v; }
    public static char hit(char v) { hit = true; return v; }
    public static byte hit(byte v) { hit = true; return v; }
    public static short hit(short v) { hit = true; return v; }
    public static <T> T hit(T v) { hit = true; return v; }

    /** Cleared as each test begins, so the answer is per test rather than per run. */
    public static void clearHit() { hit = false; }

    public static boolean wasHit() { return hit; }

    /** Open a window. Everything observed belongs to one test, so nothing carries into the next. */
    public static void reset() {
        ran = false;
        handedOff = false;
        readProduction = false;
        entered.clear();
        wired.clear();
        started.clear();
        here()[0] = 0;
    }
}
