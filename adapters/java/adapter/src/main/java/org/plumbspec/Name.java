package org.plumbspec;

/**
 * The one place a member becomes a name (``dev07-1-3-sr08``).
 *
 * <p>This was {@code + "#" +} in five places — the two ends of an edge, the wired report, and
 * mutation's scope and its sites. Five spellings of one rule is a rule nobody can change: the
 * naming that keeps an observation steady across toolchains (``dev07-1-3-ur11``) has to reach
 * every name a run produces, and it can only do that from one place.
 *
 * <p>The spelling is the language's own and never plumb's invention. {@code Class#method} is how
 * Java writes a member, as {@code module:function} is how Python writes one — a caller declaring
 * an entry point writes what they already know (``dev07-3-2``).
 */
final class Name {

    private Name() { }

    /** {@code com.example.Shop#handle} — the citable name of a member. */
    static String of(String owner, String member) {
        return owner + "#" + member;
    }
}
