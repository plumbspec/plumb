package org.plumbspec;

import java.util.ArrayList;
import java.util.List;

/**
 * The `(caller, callee)` pair each probe slot stands for (``dev07-1-3``).
 *
 * <p><b>Held by the weaver, never by the running program.</b> Both names are known before the
 * program starts, so carrying them at run time would be paying to deliver what was already settled.
 * What the program carries is one boolean per site; this is the table that gives those booleans
 * their meaning, and it is read once when a test finishes.
 */
final class Sites {

    private Sites() { }

    private static final String[] callers = new String[PlumbFlag.SITES];
    private static final String[] callees = new String[PlumbFlag.SITES];
    private static int next = 0;

    /** A slot for this pair, or -1 when the table is full and the site goes unwoven. */
    static synchronized int claim(String caller, String callee) {
        if (next >= PlumbFlag.SITES) return -1;
        callers[next] = caller;
        callees[next] = callee;
        return next++;
    }

    /**
     * Members the class file flags as made by the toolchain, which the source declares none of.
     *
     * <p>Whether one exists at all is the compiler's decision and compilers change it: a private
     * member read from a nested class needed an {@code access$N} bridge until nest-based access
     * arrived, and the same source compiled either side of that has a different member in it. A
     * name that can come and go with the build is not a name a series can be compared on
     * (``dev07-1-3-ur11``), so such a member is not an end of an edge.
     *
     * <p>Read off the flag and never off the name — what these are called is the compiler's habit
     * and matching it is the guessing this method exists to avoid (``dev07-1-3-sr10``).
     */
    private static final java.util.Set<String> undeclared = new java.util.HashSet<String>();

    /** Told once per class, as it is woven. */
    static synchronized void toolchainMade(String member) { undeclared.add(member); }

    /**
     * A compiler-made member and the declared one it was written inside (``dev07-1-3-ur09``).
     *
     * <p>A lambda body is a method the source never declared, and it carries the lines of the
     * expression it came from — which lie inside the method that wrote it. So an edge at either
     * end of it is reported against that method, and what the body calls stays in the picture
     * whatever the compiler called the body.
     */
    private static final java.util.Map<String, String> inside = new java.util.HashMap<String, String>();

    /** Told once per class, as it is woven. */
    static synchronized void writtenInside(String member, String host) { inside.put(member, host); }

    private static String settled(String member) {
        String host = inside.get(member);
        return host == null ? member : host;
    }

    /** Every edge whose site was reached and whose both ends the source declares. */
    static synchronized List<String> taken() {
        List<String> found = new ArrayList<String>();
        java.util.Set<String> already = new java.util.HashSet<String>();
        for (int i = 0; i < next; i++) {
            if (!PlumbFlag.sites[i]) continue;
            String from = settled(callers[i]), to = settled(callees[i]);
            // Folding two ends into one definition turns a call into a definition calling itself,
            // which `Pointcut.joins` already refuses before the fold and has to refuse after it.
            if (undeclared.contains(from) || undeclared.contains(to) || from.equals(to)) continue;
            if (already.add(from + "\t" + to)) found.add(from + "\t" + to);
        }
        return found;
    }

    /** Forget what was reached, keeping what the slots mean. Called around each test. */
    static synchronized void clear() {
        for (int i = 0; i < next; i++) PlumbFlag.sites[i] = false;
    }

    static synchronized int claimed() { return next; }
}
