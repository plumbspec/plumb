package org.plumbspec;

import java.io.ByteArrayOutputStream;

/**
 * What to run at a join point, and the bytecode that makes it run.
 *
 * <p>The adapter weaves three kinds and the differences between them are the whole model: how much
 * they cost, and how much they can say. Adding a fourth is adding a subclass — the weaver asks an
 * advice for its length and its opcodes and never knows which one it has.
 *
 * <ul>
 *   <li>{@link #flag} — a store to a static boolean. The cheapest thing observable at all, measured
 *       below the noise floor, and it can only say <em>something happened</em>. This is what
 *       `inert` reads (`dev07-1-3`).
 *   <li>{@link #signal} — a call to a no-argument static. It can consult the thread it is on, which
 *       is what separates `grounded` from `dispatched` (`dev07-1-3`).
 *   <li>{@link #report} — a call naming the site it was woven into. It can say <em>which</em>
 *       method ran, which is what chapter 4 scopes a mutant to (`dev07-2-1`) and the only one that
 *       costs a constant per site.
 * </ul>
 *
 * <p>Every advice here is a fixed-width prologue with no branches and no new locals. That is not an
 * accident of what has been needed so far — it is what keeps a weave from having to recompute
 * anything: a fixed insertion at offset zero shifts every absolute offset in the method by the same
 * amount, and branch offsets are relative and do not move at all. An advice that branched would
 * turn a shift into a rewrite.
 *
 * <p><b>And every advice is a multiple of four bytes long, which is not a style rule.</b>
 * `tableswitch` and `lookupswitch` are the only variable-length instructions in the set, and they
 * are variable because each is padded with up to three bytes so that its jump table starts on a
 * four-byte boundary <em>measured from the start of the method</em>. Shift a switch by a number of
 * bytes that is not a multiple of four and its required padding changes — so the padding already
 * written is now the wrong length, the table is read from the wrong place, and the method is
 * garbage from that instruction on.
 *
 * <p>This is the one way a fixed-width prologue can still be wrong, and it hides well: `flag` is
 * four bytes and preserves alignment by luck, so an instrument built on it works everywhere and
 * the first advice of another width breaks every method containing a switch. Measured — a six-byte
 * prologue produces `VerifyError: Bad instruction` at a `lookupswitch`, in 38 tests, in code a
 * four-byte prologue weaves correctly.
 *
 * <p>So the alignment is not each advice's business. A subclass declares the width of its opcodes;
 * this class pads to the boundary with `nop`, and no advice can be written that gets it wrong.
 */
abstract class Advice {

    static final String FLAG = "org/plumbspec/PlumbFlag";

    /** How many bytes this advice's own opcodes occupy, before alignment. */
    abstract int width();

    /** How much stack this advice needs while it runs. */
    abstract int stack();

    /** Write the opcodes, resolving whatever the constant pool has to carry. */
    abstract void write(ByteArrayOutputStream out, Constants pool);

    /** What the weaver shifts the method's body by: the width, rounded up to the switch boundary. */
    final int length() { return (width() + 3) / 4 * 4; }

    /** The opcodes, then `nop` to the boundary. The padding is why a switch survives the shift. */
    final void emit(ByteArrayOutputStream out, Constants pool) {
        write(out, pool);
        for (int i = width(); i < length(); i++) out.write(0x00);        // nop
    }

    /**
     * Two advices at one join point, in order.
     *
     * <p>A method can deserve more than one. An entry point that sits inside the production surface
     * is both — it opens the window <em>and</em> it is production code that ran inside it — and
     * without this it silently got only the first, so the front door was the one method chapter 4
     * never mutated. Order matters and is the caller's: `entered` before `wired`, because `wired`
     * records only while the window is open.
     *
     * <p>Null-tolerant on the right, because "and whatever else this method deserves" is usually
     * nothing and a caller should not have to branch on it.
     */
    static Advice and(final Advice first, final Advice second) {
        if (second == null) return first;
        if (first == null) return second;
        return new Advice() {
            int width() { return first.length() + second.length(); }
            int stack() { return Math.max(first.stack(), second.stack()); }
            void write(ByteArrayOutputStream out, Constants pool) {
                first.emit(out, pool);
                second.emit(out, pool);
            }
        };
    }

    /** `iconst_1; putstatic PlumbFlag.<field>` — four bytes, one stack slot. */
    static Advice flag(final String field) {
        return new Advice() {
            int width() { return 4; }
            int stack() { return 1; }
            void write(ByteArrayOutputStream out, Constants pool) {
                int ref = pool.member(Constants.Member.field(FLAG, field, "Z"));
                out.write(0x04);                              // iconst_1
                out.write(0xB3);                              // putstatic
                out.write(ref >> 8); out.write(ref);
            }
        };
    }

    /**
     * `getstatic PlumbFlag.sites:[Z; sipush <index>; iconst_1; bastore` — eight bytes, three stack
     * slots, and no call (`dev07-1-3`).
     *
     * <p><b>Neither end of the edge exists at run time.</b> The weaver knows the method it is
     * rewriting and reads the invoked method out of the constant pool, so both names are settled
     * before the program starts; what is left for the running program is a store of `true` at a
     * constant index. That is the cost class of {@link #flag} — measured at 0.49ns — where the
     * obvious shape, a `signal` carrying two constants, would pay an `invokestatic` and a set
     * insertion on every execution to deliver names the weaver already had.
     *
     * <p>The store runs on every execution and cannot be made conditional. It does not need to be:
     * it is idempotent, so what is recorded is a set by construction and the cost never grows with
     * how often the edge is taken.
     */
    static Advice site(final int index) {
        return new Advice() {
            int width() { return 8; }
            int stack() { return 3; }
            void write(ByteArrayOutputStream out, Constants pool) {
                int ref = pool.member(Constants.Member.field(FLAG, "sites", "[Z"));
                out.write(0xB2);                              // getstatic
                out.write(ref >> 8); out.write(ref);
                out.write(0x11);                              // sipush
                out.write(index >> 8); out.write(index);
                out.write(0x04);                              // iconst_1
                out.write(0x54);                              // bastore
            }
        };
    }

    /** `invokestatic PlumbFlag.<method>()V` — three bytes, no stack. */
    static Advice signal(final String method) {
        return new Advice() {
            int width() { return 3; }
            int stack() { return 0; }
            void write(ByteArrayOutputStream out, Constants pool) {
                int ref = pool.member(Constants.Member.method(FLAG, method, "()V"));
                out.write(0xB8);                              // invokestatic
                out.write(ref >> 8); out.write(ref);
            }
        };
    }

    /**
     * `aload_N; invokestatic PlumbFlag.<method>(T)T; astore_N` — five bytes, one stack slot.
     *
     * <p>The one advice that CHANGES what the method sees rather than only observing it: a
     * reference argument is passed through a probe and the result stored back. Used to wrap a task
     * handed to a pool so the window travels with it (`dev07-1-4`), which is the only correlation a
     * queued hand-off allows — the pool picks the thread later, so there is no thread to file it
     * under at the moment of hand-off.
     *
     * <p>Type-safe by construction, and it has to be: the probe takes and returns the argument's
     * own declared type, so the local's verification type is unchanged and every stack-map frame
     * that mentions it stays correct. A probe returning something wider would need a checkcast and
     * would not be a fixed-width prologue any more.
     *
     * <p><b>Never on a slot the method might read before it runs</b> — which for a prologue at
     * offset zero is nothing, because nothing has run yet.
     */
    static Advice replaceArgument(final int slot, final String method, final String type) {
        return new Advice() {
            // `aload <slot>` and `astore <slot>` are TWO bytes each — the one-byte forms are the
            // `aload_0`..`aload_3` opcodes, and this takes a slot. 2 + 3 + 2.
            int width() { return 7; }
            int stack() { return 1; }
            void write(ByteArrayOutputStream out, Constants pool) {
                int ref = pool.member(Constants.Member.method(
                        FLAG, method, "(L" + type + ";)L" + type + ";"));
                out.write(0x19); out.write(slot);             // aload <slot>
                out.write(0xB8);                              // invokestatic
                out.write(ref >> 8); out.write(ref);
                out.write(0x3A); out.write(slot);             // astore <slot>
            }
        };
    }

    /** `aload_0; invokestatic PlumbFlag.<method>(T)V` — five bytes, one stack slot.
     *
     *  <p>Hands the receiver to a probe. `Thread.start` is the case: it runs on the starting
     *  thread and `this` is the thread being started, which is the only moment those two facts are
     *  both in hand. */
    static Advice passReceiver(final String method, final String type) {
        return new Advice() {
            int width() { return 5; }                        // `aload 0` is 2, invokestatic 3
            int stack() { return 1; }
            void write(ByteArrayOutputStream out, Constants pool) {
                int ref = pool.member(Constants.Member.method(
                        FLAG, method, "(L" + type + ";)V"));
                out.write(0x19); out.write(0);                // aload 0
                out.write(0xB8);                              // invokestatic
                out.write(ref >> 8); out.write(ref);
            }
        };
    }

    /**
     * `ldc_w "<site>"; invokestatic PlumbFlag.<method>(String)V` — six bytes, one stack slot.
     *
     * <p>`ldc_w` rather than `ldc` deliberately: `ldc` takes a one-byte index and a woven class can
     * easily push the appended entries past 255, so the narrow form would work on small classes and
     * fail on large ones. A width that depends on how big the class was is not a width.
     */
    static Advice report(final String method, final String site) {
        return new Advice() {
            int width() { return 6; }
            int stack() { return 1; }
            void write(ByteArrayOutputStream out, Constants pool) {
                int text = pool.string(site);
                int ref = pool.member(
                        Constants.Member.method(FLAG, method, "(Ljava/lang/String;)V"));
                out.write(0x13);                              // ldc_w
                out.write(text >> 8); out.write(text);
                out.write(0xB8);                              // invokestatic
                out.write(ref >> 8); out.write(ref);
            }
        };
    }
}
