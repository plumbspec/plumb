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

    /** Every edge whose site was reached, as `caller\tcallee`. A set by construction. */
    static synchronized List<String> taken() {
        List<String> found = new ArrayList<String>();
        for (int i = 0; i < next; i++) if (PlumbFlag.sites[i]) found.add(callers[i] + "\t" + callees[i]);
        return found;
    }

    /** Forget what was reached, keeping what the slots mean. Called around each test. */
    static synchronized void clear() {
        for (int i = 0; i < next; i++) PlumbFlag.sites[i] = false;
    }

    static synchronized int claimed() { return next; }
}
