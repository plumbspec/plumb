package org.plumbspec;

import java.io.ByteArrayOutputStream;
import java.util.Arrays;

/**
 * Rewrite a method body with advice inserted at arbitrary offsets, and move everything that names
 * a place in it (`dev07-1-3`).
 *
 * <p><b>Why this exists at all.</b> {@link Probe} inserts a prologue: one advice, at offset zero,
 * so every absolute offset shifts by one known amount and relative branches do not move. A call
 * site is in the middle of a method and there are many of them, so offsets shift by <em>different</em>
 * amounts — which moves branch targets that were previously safe, changes the padding a switch
 * computes from its own position, and alters the deltas between stack map frames rather than only
 * the first. That is the rewrite {@code dev07-1-3} avoided for the exit probe by renaming the method
 * instead, and renaming cannot help here: an edge is not one insertion at a known offset.
 *
 * <p><b>Two passes, because padding is self-referential.</b> A {@code tableswitch} pads so its jump
 * table starts on a four-byte boundary measured from the start of the method, so how long it is
 * depends on where it ends up, and where it ends up depends on how long everything before it is.
 * The map is therefore settled by iteration rather than computed in one go, and the loop is bounded:
 * each pass can only push instructions later, so it either stops changing or is refused.
 *
 * <p><b>What it refuses rather than guesses at.</b> An unknown opcode, a {@code jsr} (obsolete since
 * Java 6 and carrying a return address this cannot follow), or a branch whose new offset no longer
 * fits in the signed 16 bits its instruction has room for. Refusal means <em>this method is woven
 * without call-site advice</em> — it still runs, and its edges are simply not recorded. Emitting a
 * class the verifier rejects is the one outcome that is worse than recording nothing, and
 * {@code dev07-1-3} already has the scar: a six-byte advice produced {@code VerifyError: Bad
 * instruction} at a {@code lookupswitch} in 38 tests of a project that had been woven correctly for
 * weeks.
 */
final class Remap {

    /** A method this cannot rewrite safely. Caught per method, never per class. */
    static final class Refused extends RuntimeException {
        Refused(String why) { super(why); }
    }

    private final byte[] code;
    /** Bytes to insert immediately before each old offset. Null entries insert nothing. */
    private final byte[][] insertAt;
    /** Old offset -> new offset, for every offset that begins an instruction. */
    private int[] moved;

    private Remap(byte[] code, byte[][] insertAt) {
        this.code = code;
        this.insertAt = insertAt;
    }

    static Remap of(byte[] code, byte[][] insertAt) {
        Remap r = new Remap(code, insertAt);
        r.settle();
        return r;
    }

    /** Where an old offset ended up. */
    int at(int old) {
        if (old < 0 || old > code.length) throw new Refused("offset " + old + " is outside the body");
        int to = moved[old];
        // **Only instruction starts have an answer.** Every other slot is left at -1 rather than 0,
        // because a silent 0 is the worst possible wrong answer: it maps a frame or a handler to the
        // top of the method, and the verifier reports it as a missing stack map frame somewhere else
        // entirely. Whatever asked for a mid-instruction offset has a bug, and this says so here.
        if (to < 0) throw new Refused("offset " + old + " does not begin an instruction");
        return to;
    }

    int length() { return moved[code.length]; }

    // ── the instruction walk ────────────────────────────────────────────────────────────────

    /**
     * Length of the instruction at {@code p}, given the position it will occupy once moved —
     * which only a switch cares about, and only for its padding.
     */
    /** The length of the instruction at {@code p}, where it currently sits. */
    static int instructionLength(byte[] code, int p) {
        return new Remap(code, null).lengthAt(p, p);
    }

    private int lengthAt(int p, int placed) {
        int op = code[p] & 0xFF;
        switch (op) {
            case 0xAA: {                                            // tableswitch
                int pad = (4 - ((placed + 1) & 3)) & 3;
                int q = p + 1 + ((4 - ((p + 1) & 3)) & 3);
                int low = readInt(q + 4), high = readInt(q + 8);
                if (high < low) throw new Refused("tableswitch high < low");
                return 1 + pad + 12 + (high - low + 1) * 4;
            }
            case 0xAB: {                                            // lookupswitch
                int pad = (4 - ((placed + 1) & 3)) & 3;
                int q = p + 1 + ((4 - ((p + 1) & 3)) & 3);
                int pairs = readInt(q + 4);
                if (pairs < 0) throw new Refused("lookupswitch pair count is negative");
                return 1 + pad + 8 + pairs * 8;
            }
            case 0xC4: {                                            // wide
                int inner = code[p + 1] & 0xFF;
                return inner == 0x84 ? 6 : 4;                       // wide iinc, else wide load/store
            }
            case 0xA8: case 0xC9: throw new Refused("jsr is not followed");
            default: {
                int n = OPERANDS[op];
                if (n < 0) throw new Refused("unknown opcode 0x" + Integer.toHexString(op));
                return 1 + n;
            }
        }
    }

    /**
     * Settle old->new in one forward pass.
     *
     * <p>No iteration is needed and it is worth saying why, because a switch's self-referential
     * padding looks like it demands a fixpoint. It does not: an instruction's new length depends
     * only on where it lands, and where it lands depends only on everything before it — so a single
     * left-to-right sweep has every input it needs by the time it needs it. What *would* need
     * iterating is widening a branch that no longer reaches, because widening moves everything after
     * it and can push a second branch out of range. That is refused instead (see {@link #rewrite}),
     * which is what keeps this a pass rather than a loop that has to be proven to terminate.
     */
    private void settle() {
        moved = new int[code.length + 1];
        Arrays.fill(moved, -1);
        int placed = 0;
        int p = 0;
        while (p < code.length) {
            byte[] advice = insertAt != null && p < insertAt.length ? insertAt[p] : null;
            // **The old offset maps to the START of the advice, not past it**, and that is the
            // whole of what a stack map frame needs. The verifier requires a frame wherever control
            // can arrive — a branch target, and the instruction after an unconditional transfer.
            // Mapping to the instruction instead puts the frame four bytes late and the advice
            // becomes an unreachable prologue: measured, `VerifyError: Expecting a stack map frame`
            // at exactly the inserted `nop`. It is also the answer that records more: a call site
            // reached by a jump runs the advice rather than skipping over it.
            moved[p] = placed;
            if (advice != null) placed += advice.length;
            // Padding is measured from the instruction's own position, which is after the advice,
            // so the old length and the new one are read at two different positions.
            placed += lengthAt(p, placed);
            p += lengthAt(p, p);
        }
        moved[code.length] = placed;
    }

    /**
     * Emit the moved body, rewriting every operand that names a place inside it.
     *
     * <p>Branch operands are <em>relative</em>, which is what makes them the subtle case: unchanged
     * bytes are wrong the moment the distance between two instructions changes, and the distance
     * changes whenever advice lands between them. Each is therefore recomputed from the new
     * positions of both ends rather than shifted.
     */
    byte[] rewrite() {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        int p = 0;
        while (p < code.length) {
            byte[] advice = insertAt != null && p < insertAt.length ? insertAt[p] : null;
            if (advice != null) out.write(advice, 0, advice.length);
            // Where the INSTRUCTION lands, which is past its own advice. Branch deltas and switch
            // padding are both measured from here and not from the mapped offset.
            int here = moved[p] + (advice != null ? advice.length : 0);
            int op = code[p] & 0xFF;
            int oldLen = lengthAt(p, p);
            switch (op) {
                case 0xAA: case 0xAB: writeSwitch(out, p, here, op); break;
                case 0xC8: {                                              // goto_w — already wide
                    out.write(op);
                    writeInt(out, target(p, readInt(p + 1)) - here);
                    break;
                }
                default: {
                    if (OPERANDS[op] == 2 && isBranch(op)) {
                        int delta = target(p, (short) read2(p + 1)) - here;
                        if (delta < Short.MIN_VALUE || delta > Short.MAX_VALUE)
                            throw new Refused("a branch no longer reaches in 16 bits");
                        out.write(op);
                        out.write(delta >> 8);
                        out.write(delta);
                    } else {
                        out.write(code, p, oldLen);
                    }
                }
            }
            p += oldLen;
        }
        byte[] result = out.toByteArray();
        if (result.length != moved[code.length])
            throw new Refused("rewrote " + result.length + " bytes where the map says "
                    + moved[code.length]);
        return result;
    }

    /** Where an old branch pointed, in new coordinates. */
    private int target(int from, int relative) {
        int destination = from + relative;
        if (destination < 0 || destination > code.length) throw new Refused("branch leaves the body");
        return moved[destination];
    }

    private void writeSwitch(ByteArrayOutputStream out, int p, int here, int op) {
        out.write(op);
        for (int i = 0; i < ((4 - ((here + 1) & 3)) & 3); i++) out.write(0);
        int q = p + 1 + ((4 - ((p + 1) & 3)) & 3);
        writeInt(out, target(p, readInt(q)) - here);                  // default
        if (op == 0xAA) {
            int low = readInt(q + 4), high = readInt(q + 8);
            writeInt(out, low); writeInt(out, high);
            for (int i = 0; i <= high - low; i++)
                writeInt(out, target(p, readInt(q + 12 + i * 4)) - here);
        } else {
            int pairs = readInt(q + 4);
            writeInt(out, pairs);
            for (int i = 0; i < pairs; i++) {
                writeInt(out, readInt(q + 8 + i * 8));                 // the match value
                writeInt(out, target(p, readInt(q + 12 + i * 8)) - here);
            }
        }
    }

    private static boolean isBranch(int op) {
        return (op >= 0x99 && op <= 0xA7) || op == 0xC6 || op == 0xC7;
    }

    private int read2(int p) { return ((code[p] & 0xFF) << 8) | (code[p + 1] & 0xFF); }

    private static void writeInt(ByteArrayOutputStream o, int v) {
        o.write(v >> 24); o.write(v >> 16); o.write(v >> 8); o.write(v);
    }

    private int readInt(int p) {
        return ((code[p] & 0xFF) << 24) | ((code[p + 1] & 0xFF) << 16)
                | ((code[p + 2] & 0xFF) << 8) | (code[p + 3] & 0xFF);
    }

    // ── everything else that names a place in the body ──────────────────────────────────────

    /** Exception table entries: three offsets and a constant-pool index that must not move. */
    byte[] fixHandlers(byte[] table) {
        byte[] copy = table.clone();
        int count = ((copy[0] & 0xFF) << 8) | (copy[1] & 0xFF);
        int p = 2;
        for (int i = 0; i < count && p + 7 < copy.length; i++, p += 8) {
            put2(copy, p, at(read2(copy, p)));
            put2(copy, p + 2, at(read2(copy, p + 2)));
            put2(copy, p + 4, at(read2(copy, p + 4)));
        }
        return copy;
    }

    /** {@code LineNumberTable}: rows of {@code start_pc, line_number}. */
    byte[] fixLines(byte[] table) {
        byte[] copy = table.clone();
        int count = ((copy[0] & 0xFF) << 8) | (copy[1] & 0xFF);
        int p = 2;
        for (int i = 0; i < count && p + 3 < copy.length; i++, p += 4) put2(copy, p, at(read2(copy, p)));
        return copy;
    }

    /**
     * {@code LocalVariableTable} and its Type twin: {@code start_pc, length, ...}.
     *
     * <p><b>The length is a span, not an offset</b>, so it is recomputed as the distance between the
     * mapped ends rather than carried across. Shifting it instead leaves a variable's scope ending
     * where it used to, which a debugger reports as the wrong variable and the verifier does not
     * catch at all.
     */
    byte[] fixLocals(byte[] table) {
        byte[] copy = table.clone();
        int count = ((copy[0] & 0xFF) << 8) | (copy[1] & 0xFF);
        int p = 2;
        for (int i = 0; i < count && p + 9 < copy.length; i++, p += 10) {
            int start = read2(copy, p), span = read2(copy, p + 2);
            int from = at(start), to = at(Math.min(start + span, code.length));
            put2(copy, p, from);
            put2(copy, p + 2, to - from);
        }
        return copy;
    }

    /**
     * {@code StackMapTable}, which is the one that cannot be shifted at all.
     *
     * <p>A frame carries a <em>delta</em> from the frame before it, not an offset — so when advice
     * lands between two frames only that pair's delta changes, and when it lands before the first
     * frame only that one does. Every delta is therefore recovered to an absolute offset, mapped,
     * and re-encoded from the new absolute positions.
     *
     * <p>Re-encoding can need a wider tag than it started with: a {@code same_frame} carries its
     * delta in the tag itself and only reaches 63, so a delta pushed past that becomes
     * {@code same_frame_extended}. The reverse is never done — a frame that could narrow is left
     * wide, because correctness does not depend on it and a table that changes shape twice is
     * harder to reason about than one that only grows.
     */
    byte[] fixStackMap(byte[] table) {
        if (table.length < 2) return table;
        int count = read2(table, 0);
        if (count == 0) return table;
        ByteArrayOutputStream o = new ByteArrayOutputStream();
        write2(o, count);
        int p = 2, oldAbs = -1, newPrev = -1;
        for (int frame = 0; frame < count && p < table.length; frame++) {
            int tag = table[p++] & 0xFF;
            int delta;
            if (tag <= 63) delta = tag;
            else if (tag <= 127) delta = tag - 64;
            else { delta = read2(table, p); p += 2; }
            int oldHere = oldAbs < 0 ? delta : oldAbs + delta + 1;
            int newHere = at(oldHere);
            int newDelta = newPrev < 0 ? newHere : newHere - newPrev - 1;
            if (newDelta < 0) throw new Refused("stack map frames would run backwards");
            oldAbs = oldHere;
            newPrev = newHere;

            if (tag <= 63) {
                if (newDelta <= 63) o.write(newDelta); else { o.write(251); write2(o, newDelta); }
            } else if (tag <= 127) {
                if (newDelta <= 63) o.write(64 + newDelta); else { o.write(247); write2(o, newDelta); }
                p = verification(table, p, o);
            } else if (tag == 247) {
                o.write(247); write2(o, newDelta);
                p = verification(table, p, o);
            } else if (tag >= 248 && tag <= 251) {
                o.write(tag); write2(o, newDelta);
            } else if (tag <= 254) {
                o.write(tag); write2(o, newDelta);
                for (int i = 0; i < tag - 251; i++) p = verification(table, p, o);
            } else {
                o.write(255); write2(o, newDelta);
                int locals = read2(table, p); p += 2; write2(o, locals);
                for (int i = 0; i < locals; i++) p = verification(table, p, o);
                int stack = read2(table, p); p += 2; write2(o, stack);
                for (int i = 0; i < stack; i++) p = verification(table, p, o);
            }
        }
        return o.toByteArray();
    }

    /** One verification type. {@code Uninitialized} names a {@code new} site and moves; Object does not. */
    private int verification(byte[] b, int p, ByteArrayOutputStream o) {
        int tag = b[p] & 0xFF;
        o.write(tag);
        if (tag == 7) { write2(o, read2(b, p + 1)); return p + 3; }
        if (tag == 8) { write2(o, at(read2(b, p + 1))); return p + 3; }
        return p + 1;
    }

    private static int read2(byte[] b, int p) { return ((b[p] & 0xFF) << 8) | (b[p + 1] & 0xFF); }
    private static void put2(byte[] b, int p, int v) { b[p] = (byte) (v >> 8); b[p + 1] = (byte) v; }
    private static void write2(ByteArrayOutputStream o, int v) { o.write(v >> 8); o.write(v); }

    /**
     * Operand byte count per opcode; -1 is "not fixed width, or not known".
     *
     * <p>Filled by <em>range</em> and never by enumeration. Written out opcode by opcode first, and
     * it silently omitted {@code bastore}, {@code castore} and {@code sastore} — 95 methods
     * refused for an opcode the JVM has had since 1.0, and one of them is the exact
     * instruction this chapter's advice emits. A range says what a list only implies.
     */
    private static final int[] OPERANDS = new int[256];
    private static void span(int from, int to, int operands) {
        for (int op = from; op <= to; op++) OPERANDS[op] = operands;
    }
    static {
        Arrays.fill(OPERANDS, -1);
        span(0x00, 0x0F, 0);                    // nop, consts
        span(0x10, 0x10, 1); span(0x11, 0x11, 2);
        span(0x12, 0x12, 1); span(0x13, 0x14, 2);
        span(0x15, 0x19, 1);                    // iload..aload
        span(0x1A, 0x35, 0);                    // *load_<n>, *aload
        span(0x36, 0x3A, 1);                    // istore..astore
        span(0x3B, 0x83, 0);                    // *store_<n>, *astore, stack, arithmetic
        span(0x84, 0x84, 2);                    // iinc
        span(0x85, 0x98, 0);                    // conversions, comparisons
        span(0x99, 0xA7, 2);                    // if*, goto
        span(0xA8, 0xA8, 2);                    // jsr — refused, width kept honest anyway
        span(0xA9, 0xA9, 1);                    // ret — likewise
        span(0xAC, 0xB1, 0);                    // returns
        span(0xB2, 0xB8, 2);                    // field and method refs
        span(0xB9, 0xBA, 4);                    // invokeinterface, invokedynamic
        span(0xBB, 0xBB, 2);                    // new
        span(0xBC, 0xBC, 1);                    // newarray
        span(0xBD, 0xBD, 2);                    // anewarray
        span(0xBE, 0xBF, 0);                    // arraylength, athrow
        span(0xC0, 0xC1, 2);                    // checkcast, instanceof
        span(0xC2, 0xC3, 0);                    // monitorenter, monitorexit
        span(0xC5, 0xC5, 3);                    // multianewarray
        span(0xC6, 0xC7, 2);                    // ifnull, ifnonnull
        span(0xC8, 0xC9, 4);                    // goto_w, jsr_w
        // 0xAA/0xAB (switches) and 0xC4 (wide) are variable and answered in lengthAt.
    }
}
