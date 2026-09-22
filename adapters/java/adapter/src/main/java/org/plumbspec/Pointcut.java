package org.plumbspec;

import java.security.ProtectionDomain;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Where advice goes: given a class and a method, which advice runs on the way in, and whether the
 * way out is watched too.
 *
 * <p>This was an if-chain in the transformer with three parameters threaded through the weaver —
 * a set of "marked" names, the method to call for them, and a flag for whether the rest of the
 * class counted. That shape answers one question per weave and has to be widened every time a new
 * question is asked. This answers per method, so the weaver does not know what a production class
 * or an entry point is, and a new join point is a new branch here rather than a new parameter
 * everywhere.
 *
 * <p><b>What is production and what is a test is decided by where a class was loaded from</b>, not
 * by what it is called. Maven puts tests in the same package tree as the code they test, so a
 * surface of {@code com.myapp.*} matches {@code com.myapp.FooTest} too, and every observer built on
 * package names has carried a correction for it.
 */
final class Pointcut {

    /** Where work escapes to a thread the run is not following (`dev07-1-4`). Short and fixed.
     *
     *  <p>Each names the method AND the advice its hand-off needs, because the two primitives
     *  correlate differently and nothing else about them differs. `Thread.start` names the thread
     *  it starts, so the window is filed under that thread. A pooled task names no thread — the
     *  pool picks one later and the same thread serves everybody — so the task itself is wrapped
     *  and carries the window to whichever thread runs it. */
    static final Map<String, String> DISPATCH = new HashMap<String, String>();
    static {
        DISPATCH.put("java.lang.Thread", "start");
        DISPATCH.put("java.util.concurrent.ThreadPoolExecutor", "execute");
    }

    /** Where a test reads the production artifact as DATA rather than running it (`dev07-4-2`).
     *
     *  <p>`inert` is a positive claim — *read it and ran none of it* — and manifest major 8 lets it
     *  be made only where the read was seen. This adapter had no read observation at all, so it
     *  granted `inert` from an absence and could not leave major 7; this is the join point that
     *  makes the claim honest.
     *
     *  <p>One primitive to begin with, and the direction of its error is why that is sound: a read
     *  this does not see leaves the fact at `untouched`, which withholds a structural story's
     *  proof. Widening it is a pointcut change and a measurement, never an assumption — the same
     *  rule {@link #DISPATCH} states about its own set. */
    static final Map<String, String> READS = new HashMap<String, String>();
    static {
        // The chokepoints, not the APIs. Commons IO, Guava, Okio and Spring's Resource cannot
        // read a byte without bottoming out here, so instrumenting the libraries would be an
        // open-ended list where instrumenting what they funnel through is a closed one — the
        // same argument DISPATCH makes for `ThreadPoolExecutor.execute`.
        READS.put("java.lang.ClassLoader", "getResourceAsStream");   // classpath, incl. jars
        READS.put("java.nio.file.Files", "");                        // all NIO reads
    }

    /** The read family on `java.nio.file.Files`. Every one takes the path first. */
    private static boolean readsAPath(String methodName) {
        return "readAllBytes".equals(methodName) || "newInputStream".equals(methodName)
            || "readString".equals(methodName) || "readAllLines".equals(methodName)
            || "newBufferedReader".equals(methodName) || "lines".equals(methodName)
            || "newByteChannel".equals(methodName);
    }

    /** Every JDK primitive this weaves, whichever question it answers. The three decisions below
     *  ask <em>is this class ours to touch</em> and must give one answer for all of them. */
    private static boolean jdkJoinPoint(String name) {
        return DISPATCH.containsKey(name) || READS.containsKey(name);
    }

    /** Every JDK class this weaves. The agent must ask for all of them back: they are loaded while
     *  the VM starts, so a transformer registered at premain never sees one arrive. */
    static List<String> jdkClasses() {
        List<String> all = new ArrayList<String>(DISPATCH.keySet());
        all.addAll(READS.keySet());
        return all;
    }

    /** The advice one dispatch primitive's hand-off needs, or null if this is not that method. */
    private static Advice handoff(String className, String methodName) {
        if ("java.lang.Thread".equals(className) && "start".equals(methodName))
            return Advice.passReceiver("handoffTo", "java/lang/Thread");
        if ("java.util.concurrent.ThreadPoolExecutor".equals(className)
                && "execute".equals(methodName))
            // Slot 1: `execute(Runnable command)` on an instance, so 0 is `this`.
            return Advice.replaceArgument(1, "carry", "java/lang/Runnable");
        return null;
    }

    private final List<String> production;
    private final List<String> testRoots;
    private final List<String> entryPoints;
    /** Chapter 4 needs to know WHICH production methods ran, and only chapter 4 pays for it. */
    private final boolean scoping;
    private final boolean edges;

    Pointcut(List<String> production, List<String> testRoots, List<String> entryPoints,
             boolean scoping, boolean edges) {
        this.production = production;
        this.testRoots = testRoots;
        this.entryPoints = entryPoints;
        this.scoping = scoping;
        this.edges = edges;
    }

    /** Whether call sites are woven at all (``dev07-1-3``). Off unless asked for. */
    boolean drawingEdges() { return edges; }

    /**
     * Whether a call from one member to another is an edge worth a slot.
     *
     * <p>Both ends must be inside the declared surface. A call arriving from outside it has no far
     * end in the graph being drawn, and inventing one would put the test framework's own shape into
     * a picture of the system under it — the same rule the Python tracer follows when a test calls
     * into production.
     *
     * <p><b>A member is the grain, not a class.</b> Comparing the two classes dropped every call
     * whose target was declared beside its caller, so a surface of one class drew no graph at all
     * — while the Python recorder refused only a member calling itself. Two adapters drawing
     * different graphs from one system is what ``dev07-1-3-sr08`` forbids; this is that rule, in
     * the one place that builds a name.
     */
    boolean joins(String callerClass, String callerMember, String calleeClass, String calleeMember) {
        return edges
                && inSurface(callerClass) && inSurface(calleeClass)
                && !Name.of(callerClass, callerMember).equals(Name.of(calleeClass, calleeMember));
    }

    /** Nothing on this class at all — the common answer, and the cheap one. */
    boolean skips(String name, ProtectionDomain domain) {
        if (name.startsWith("org.plumbspec.")) return true;     // never the probe itself
        if (jdkJoinPoint(name)) return false;
        if (fromTestRoot(domain)) return true;
        return !inSurface(name) && entryPointsOn(name).isEmpty();
    }

    /**
     * Whether weaving this class is evidence the instrument reached <em>the project</em>.
     *
     * <p>False for a dispatch primitive, which is a JDK class present in every JVM. `dev07-1-4` lets
     * `inert` be asserted only where something was actually watching the declared surface, and
     * `java.lang.Thread` having been rewritten says nothing about whether this project's classes
     * were — so counting it answers "did the instrument reach the project" with a fact about the
     * JVM. The board that results reads `inert` everywhere, which is the strongest claim available,
     * made on the strength of nobody having looked.
     */
    boolean reachesProject(String name) {
        return !jdkJoinPoint(name);
    }

    /** The advice to run on entry to one method, or null for none. */
    Advice entering(String className, String methodName) {
        if ("java.lang.ClassLoader".equals(className))
            // Slot 1: `getResourceAsStream(String name)` on an instance, so 0 is `this`. The name
            // passes through the probe unchanged — this observes, it never redirects a load.
            return "getResourceAsStream".equals(methodName)
                ? Advice.replaceArgument(1, "sawRead", "java/lang/String") : null;
        if ("java.nio.file.Files".equals(className))
            // Static, so slot 0 is the Path itself.
            return readsAPath(methodName)
                ? Advice.replaceArgument(0, "sawReadPath", "java/nio/file/Path") : null;
        if (DISPATCH.containsKey(className)) return handoff(className, methodName);
        Advice surface = onSurface(className, methodName);
        if (!entryPointsOn(className).contains(methodName)) return surface;
        // Both, when it is both. `entered` first: `wired` records only while the window is open,
        // and a front door that opened the window after reporting itself would report itself into
        // the previous test's scope.
        return Advice.and(Advice.signal("entered"), surface);
    }

    /**
     * What a method deserves as ordinary production code, entry point or not.
     *
     * <p>Split out because a wrapped method still deserves it: the wrapper opens and closes the
     * window, so the original body carries no `entered` — but it is production code that ran, and
     * leaving it bare made the entry point the one method chapter 4 never mutated.
     *
     * <p>In an ordinary run all that is wanted is the bit `inert` reads; when chapter 4 is scoping
     * a mutant it has to name the method, which costs a constant per site instead of a store.
     */
    Advice onSurface(String className, String methodName) {
        if (!inSurface(className)) return null;
        return scoping ? Advice.report("wired", Name.of(className, methodName))
                       : Advice.flag("ran");
    }

    /**
     * Whether leaving this method is a join point too.
     *
     * <p>Only entry points, and only while scoping. Chapter 4 mutates what a test drove <em>under</em>
     * an entry point (`dev07-2-1`), so the window has to close as well as open — and closing it is the
     * expensive half to weave, so nothing pays for it that does not need it. Grounding never does:
     * that an entry point was reached is answered by arriving.
     */
    boolean leaving(String className, String methodName) {
        return scoping && entryPointsOn(className).contains(methodName);
    }

    boolean inSurface(String name) {
        for (String pattern : production) {
            if (pattern.endsWith("*")
                    ? name.startsWith(pattern.substring(0, pattern.length() - 1))
                    : name.equals(pattern)) return true;
        }
        return false;
    }

    List<String> entryPointsOn(String className) {
        List<String> found = new ArrayList<String>();
        for (String declared : entryPoints) {
            int hash = declared.indexOf('#');
            if (hash > 0 && declared.substring(0, hash).equals(className))
                found.add(declared.substring(hash + 1));
        }
        return found;
    }

    private boolean fromTestRoot(ProtectionDomain domain) {
        if (domain == null || domain.getCodeSource() == null
                || domain.getCodeSource().getLocation() == null) return false;
        String where = domain.getCodeSource().getLocation().getPath();
        for (String root : testRoots) {
            // On a SEPARATOR, not a prefix. `build/sample-app` starts with `build/sample` and is
            // not inside it, and excluding production as though it were a test leaves the surface
            // uninstrumented while every test still reports a verdict.
            if (where.equals(root)) return true;
            if (where.startsWith(root.endsWith("/") ? root : root + "/")) return true;
        }
        return false;
    }
}
