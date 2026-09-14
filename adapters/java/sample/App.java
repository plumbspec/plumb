import java.util.concurrent.*;

/** Stands in for an adopter's production code. `handleRequest` is the declared entry point. */
public final class App {
    public static final ExecutorService POOL = Executors.newFixedThreadPool(1);

    /** The wired surface — where the real system begins (`dev07-1-3`). */
    public static int handleRequest(int n) { return work(n); }

    /** Reachable only through the entry point. */
    static int work(int n) { return dense(n) + sparse(n); }

    /** A `tableswitch` — dense cases, so javac emits the table form. */
    static int dense(int n) {
        switch (n) {
            case 1: return 1;
            case 2: return 3;
            case 3: return 5;
            default: return 0;
        }
    }

    /**
     * A `lookupswitch` — cases far apart, so javac emits the lookup form.
     *
     * Both switches are here because they are the only variable-length instructions in the set:
     * each is padded so its table starts on a four-byte boundary measured from the start of the
     * method, so a prologue whose length is not a multiple of four changes the padding a switch
     * needs and leaves the one already written the wrong size. A four-byte prologue preserves
     * alignment by luck and hides it; this is the shape that does not.
     */
    static int sparse(int n) {
        switch (n) {
            case 1: return 9;
            case 500: return 2;
            case 100000: return 7;
            default: return 1;
        }
    }

    /** An entry point that throws. The window `dev07-1-3` opens on entry has to close on this path
     *  too, which is the whole reason the exit probe is a generated wrapper with a `finally`
     *  rather than a store before each `return`. */
    public static int failingRequest(int n) { throw new IllegalStateException("no"); }

    /** Reachable from no entry point at all — the orphan (`dev07-1-4`). */
    public static int orphan(int n) { return n + 1; }
}
