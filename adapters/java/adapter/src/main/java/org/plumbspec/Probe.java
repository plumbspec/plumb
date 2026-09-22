package org.plumbspec;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;

/**
 * Weave advice into one class: read it, insert what a {@link Pointcut} asks for, write it back.
 *
 * <p><b>Hand-rolled, and deliberately.</b> The alternative is ASM, which would be the first
 * third-party library inside an artifact that is signed and installed by a one-line curl. What this
 * needs is the narrowest edit the class-file format allows, and an edit that small is worth owning.
 *
 * <p>Everything absolute shifts by the length of the advice inserted in front of it. Branch offsets
 * are <em>relative</em>, so intra-method jumps are untouched; the exception table, line numbers and
 * local-variable ranges are absolute and move. The stack map is the subtle one: every frame after
 * the first carries a delta from its predecessor and so does not move, only the first frame's
 * offset changes — and a verification type of {@code ITEM_Uninitialized} carries a bytecode offset
 * that moves in <em>every</em> frame, while {@code ITEM_Object}, identical on the wire, carries a
 * constant-pool index that must not.
 *
 * <p>Leaving a method is woven by {@link Wrapper} instead, because an exit is not one insertion at
 * a known offset — it is one before every return and one on the exceptional path, which turns a
 * shift into a rewrite. See that class for why renaming beats inserting.
 */
final class Probe {

    private final byte[] in;
    private int at;
    private final ByteArrayOutputStream out = new ByteArrayOutputStream();
    private String[] utf8;
    private String thisClass = "";

    //: The methods this class declares, kept because `EnclosingMethod` is read after them: a class
    //: file puts its own attributes last, so where a class came from is known only once every
    //: member that has to be reported against it has gone by.
    private final java.util.Set<String> ownMembers = new java.util.HashSet<String>();
    private final Pointcut where;
    private Constants pool;
    /** Advice for the method being written, and how far its body therefore moves. */
    private Advice advice;
    private int inserted;
    /** Methods that also need their exit watched, collected while walking and appended after. */
    private final java.util.List<Wrapper.Wrapped> wrapped = new java.util.ArrayList<Wrapper.Wrapped>();
    private int major;

    private Probe(byte[] in, Pointcut where) { this.in = in; this.where = where; }

    static byte[] weave(byte[] classfile, Pointcut where) {
        return new Probe(classfile, where).run();
    }

    private int u1() { return in[at++] & 0xFF; }
    private int u2() { return (u1() << 8) | u1(); }
    private long u4() { return ((long) u2() << 16) | u2(); }
    private byte[] bytes(int n) { byte[] b = Arrays.copyOfRange(in, at, at + n); at += n; return b; }

    private void w1(int v) { out.write(v & 0xFF); }
    private void w2(int v) { w1(v >> 8); w1(v); }
    private void w4(long v) { w2((int) (v >> 16)); w2((int) v); }
    private void wb(byte[] b) { out.write(b, 0, b.length); }

    private byte[] run() {
        long magic = u4();
        int minor = u2();
        major = u2();

        int poolCount = u2();
        int poolStart = at;
        readPool(poolCount);
        int poolEnd = at;

        // The class's own name, needed before any advice is emitted: a report names its site.
        int access = u2(), thisIndex = u2(), superIndex = u2();
        thisClass = className(thisIndex).replace('/', '.');
        int interfaces = u2();
        byte[] interfaceBytes = bytes(interfaces * 2);

        // Members are walked into a buffer first, because the pool cannot be written until every
        // advice that will be emitted has asked it for what it needs.
        ByteArrayOutputStream body = new ByteArrayOutputStream();
        pool = new Constants(poolCount);
        ByteArrayOutputStream fields = new ByteArrayOutputStream();
        int fieldCount = members(fields, false);
        ByteArrayOutputStream methods = new ByteArrayOutputStream();
        int methodCount = members(methods, true);
        int attrs = u2();
        ByteArrayOutputStream tail = new ByteArrayOutputStream();
        write2(tail, attrs);
        for (int i = 0; i < attrs; i++) copyAttribute(tail);

        byte[] extra = Wrapper.methods(wrapped, pool, thisClass.replace('.', '/'), major);

        w4(magic); w2(minor); w2(major);
        w2(pool.count());
        wb(Arrays.copyOfRange(in, poolStart, poolEnd));
        wb(pool.appended());
        w2(access); w2(thisIndex); w2(superIndex);
        w2(interfaces); wb(interfaceBytes);
        w2(fieldCount);
        wb(fields.toByteArray());
        w2(methodCount + wrapped.size());
        wb(methods.toByteArray());
        wb(extra);
        wb(tail.toByteArray());
        return out.toByteArray();
    }

    /** Walk the pool, keeping the Utf8 entries — attribute and class names are read through them. */
    private void readPool(int count) {
        utf8 = new String[count];
        classRefs = new int[count];
        refClass = new int[count];
        refNameType = new int[count];
        refName = new int[count];
        for (int i = 1; i < count; i++) {
            int tag = u1();
            switch (tag) {
                case 1: { int n = u2(); utf8[i] = new String(bytes(n), StandardCharsets.UTF_8); break; }
                case 7: classRefs[i] = u2(); break;
                case 8: case 16: case 19: case 20: at += 2; break;
                case 15: at += 3; break;
                case 5: case 6: at += 8; i++; break;
                // A method reference names its owner and its name-and-type, and a name-and-type
                // names the method. Skipped as four opaque bytes until `dev07-1-3` needed to read the
                // far end of a call out of the pool rather than discover it at run time.
                case 9: case 10: case 11: refClass[i] = u2(); refNameType[i] = u2(); break;
                case 12: refName[i] = u2(); at += 2; break;
                default: at += 4;
            }
        }
    }

    private int[] classRefs;
    private int[] refClass, refNameType, refName;

    /** The class a method reference names, dotted. Empty when it cannot be resolved. */
    private String refOwner(int ref) {
        return ref > 0 && ref < refClass.length && refClass[ref] > 0
                ? className(refClass[ref]).replace('/', '.') : "";
    }

    /** The method a reference names. Empty when it cannot be resolved. */
    private String refMethod(int ref) {
        if (ref <= 0 || ref >= refNameType.length) return "";
        int nt = refNameType[ref];
        if (nt <= 0 || nt >= refName.length) return "";
        int name = refName[nt];
        return name > 0 && name < utf8.length && utf8[name] != null ? utf8[name] : "";
    }

    private String className(int classIndex) {
        int nameIndex = classRefs[classIndex];
        return nameIndex > 0 && utf8[nameIndex] != null ? utf8[nameIndex] : "";
    }

    /** The member entries only. The COUNT is the caller's, because the method count is not the
     *  one that was read: a wrapped method leaves two behind it. */
    private int members(ByteArrayOutputStream to, boolean methods) {
        int count = u2();
        // Gathered over the whole class rather than decided per member, because a bridge carries
        // the flag and the name of the method it stands in front of: told member by member, the
        // real one would be refused along with it.
        java.util.Set<String> declared = new java.util.HashSet<String>();
        java.util.Set<String> made = new java.util.HashSet<String>();
        java.util.Map<String, int[]> spans = new java.util.HashMap<String, int[]>();
        for (int i = 0; i < count; i++) {
            lowLine = highLine = -1;
            int access = u2();
            int nameIndex = u2();
            int descriptorIndex = u2();
            String name = String.valueOf(utf8[nameIndex]);
            String descriptor = String.valueOf(utf8[descriptorIndex]);
            boolean exits = methods && where.leaving(thisClass, name)
                    && Wrapper.wrappable(access, name);
            // A watched exit is woven by renaming this method and generating a new one around it,
            // so the body written here keeps the compiler's bytes and carries no advice at all —
            // the wrapper holds both halves, which is also what keeps them bracketed.
            // A wrapped method gets no `entered` — its generated wrapper carries that — but it
            // still gets whatever it deserves as production code, inside the window the
            // wrapper just opened.
            advice = !methods ? null
                    : exits ? where.onSurface(thisClass, name)
                            : where.entering(thisClass, name);
            inserted = advice == null ? 0 : advice.length();
            write2(to, exits ? Wrapper.hiddenAccess(access) : access);
            write2(to, exits ? pool.utf8(name + Wrapper.SUFFIX) : nameIndex);
            write2(to, descriptorIndex);
            int attrs = u2(); write2(to, attrs);
            for (int a = 0; a < attrs; a++) {
                int attrName = u2();
                if (methods && "Code".equals(utf8[attrName])) { write2(to, attrName); code(to, name); }
                else { write2(to, attrName); long len = u4(); write4(to, len); to.write(bytes((int) len), 0, (int) len); }
            }
            if (exits) wrapped.add(new Wrapper.Wrapped(access, name, descriptor, nameIndex, descriptorIndex));
            if (methods) {
                ((access & Wrapper.ACC_SYNTHETIC) != 0 ? made : declared).add(name);
                widen(spans, name, lowLine, highLine);
                ownMembers.add(name);
            }
        }
        for (String one : made) {
            if (declared.contains(one)) continue;             // a bridge fronting a real method
            String host = writtenInside(spans, declared, spans.get(one));
            if (host != null) Sites.writtenInside(Name.of(thisClass, one), Name.of(thisClass, host));
            else Sites.toolchainMade(Name.of(thisClass, one));
        }
        return count;
    }

    private static void widen(java.util.Map<String, int[]> spans, String name, int low, int high) {
        if (low < 0) return;
        int[] held = spans.get(name);
        if (held == null) spans.put(name, new int[]{low, high});
        else { held[0] = Math.min(held[0], low); held[1] = Math.max(held[1], high); }
    }

    /**
     * The declared method a compiler-made one was written inside, or null where none was.
     *
     * <p>The narrowest containing span wins, so a body inside a nested declaration reports the
     * nearest one. {@code <init>} and {@code <clinit>} are not candidates: an accessor the compiler
     * emits for a nested class reads carries the class's own line, which falls inside the implicit
     * constructor and nowhere else — reporting a field read as a call to the constructor would be
     * a false edge in place of an unsteady one. Those two names are the JVM's own and not a
     * compiler's habit, so keying on them is not the guessing ``dev07-1-3-sr10`` rules out.
     */
    private static String writtenInside(java.util.Map<String, int[]> spans,
                                        java.util.Set<String> declared, int[] mine) {
        if (mine == null) return null;
        String best = null;
        int narrowest = Integer.MAX_VALUE;
        for (String name : declared) {
            if ("<init>".equals(name) || "<clinit>".equals(name)) continue;
            int[] theirs = spans.get(name);
            if (theirs == null || theirs[0] > mine[0] || theirs[1] < mine[1]) continue;
            int width = theirs[1] - theirs[0];
            if (width < narrowest) { narrowest = width; best = name; }
        }
        return best;
    }

    private void copyAttribute(ByteArrayOutputStream to) {
        int nameIndex = u2();
        write2(to, nameIndex);
        long len = u4(); write4(to, len);
        byte[] payload = bytes((int) len);
        if ("EnclosingMethod".equals(utf8[nameIndex])) declaredInside(payload);
        to.write(payload, 0, payload.length);
    }

    /**
     * A class the source declared inside a method, and the method that declared it
     * (``dev07-1-3-sr10``).
     *
     * <p>{@code EnclosingMethod} is the class file's own account of where a class came from, so
     * one written inside a method is reported against that method and its number stops mattering.
     * A compiler numbers anonymous classes in declaration order — add one above and every one
     * below is renamed, while nothing the source says has changed.
     *
     * <p>A named nested class carries no such attribute and stays a member of its own: it was
     * declared beside the methods rather than inside one.
     *
     * <p>The method index is zero where a class was declared in an initializer and not in a
     * method. There is no member to report against then, and the class keeps its own name.
     */
    private void declaredInside(byte[] payload) {
        if (payload.length < 4) return;
        int classIndex = ((payload[0] & 0xFF) << 8) | (payload[1] & 0xFF);
        int nameAndType = ((payload[2] & 0xFF) << 8) | (payload[3] & 0xFF);
        if (nameAndType <= 0 || nameAndType >= refName.length) return;
        int name = refName[nameAndType];
        if (name <= 0 || name >= utf8.length || utf8[name] == null) return;
        String host = Name.of(className(classIndex).replace('/', '.'), utf8[name]);
        for (String mine : ownMembers) Sites.writtenInside(Name.of(thisClass, mine), host);
    }

    /**
     * Advice for every call site in this body whose far end is production too (``dev07-1-3``).
     *
     * <p>Both names come out of the constant pool, so nothing is discovered while the program runs.
     * A site the table has no room for is simply not woven — the edge goes unrecorded, which is the
     * one cost this may impose, and it never changes what the method does.
     */
    private byte[][] callSites(byte[] body, String methodName) {
        byte[][] insertAt = new byte[body.length][];
        String caller = Name.of(thisClass, methodName);
        for (int p = 0; p < body.length; ) {
            int op = body[p] & 0xFF;
            if (op >= 0xB6 && op <= 0xB9) {                       // invokevirtual/special/static/interface
                int ref = ((body[p + 1] & 0xFF) << 8) | (body[p + 2] & 0xFF);
                String owner = refOwner(ref), member = refMethod(ref);
                if (where.joins(thisClass, methodName, owner, member)) {
                    int slot = Sites.claim(caller, Name.of(owner, member));
                    if (slot >= 0) {
                        ByteArrayOutputStream one = new ByteArrayOutputStream();
                        Advice.site(slot).emit(one, pool);
                        insertAt[p] = one.toByteArray();
                    }
                }
            }
            p += Remap.instructionLength(body, p);
        }
        return insertAt;
    }

    /** Lowest and highest source line the method being rewritten carries, or -1 for neither. */
    private int lowLine = -1, highLine = -1;

    /**
     * Read the lines a method covers out of its own table.
     *
     * <p>A row is {@code start_pc, line_number}. The span is what says which declared method a
     * compiler-made one was written inside: a lambda body carries the lines of the expression it
     * came from, and those lie within the method that wrote it.
     */
    private void span(byte[] lineTable) {
        lowLine = highLine = -1;
        int rows = ((lineTable[0] & 0xFF) << 8) | (lineTable[1] & 0xFF);
        for (int r = 0; r < rows; r++) {
            int at = 2 + r * 4 + 2;
            if (at + 1 >= lineTable.length) break;
            int line = ((lineTable[at] & 0xFF) << 8) | (lineTable[at + 1] & 0xFF);
            if (lowLine < 0 || line < lowLine) lowLine = line;
            if (line > highLine) highLine = line;
        }
    }

    /** The whole edit. Read the Code attribute, rewrite it `inserted` bytes longer, emit it. */
    private void code(ByteArrayOutputStream to, String methodName) {
        long declared = u4();
        int end = at + (int) declared;

        int maxStack = u2();
        int maxLocals = u2();
        int codeLength = (int) u4();
        byte[] codeBody = bytes(codeLength);

        // **The call-site path is a different rewrite and says so.** A prologue shifts everything
        // by one known amount; call sites shift different parts by different amounts, which moves
        // branch targets, switch padding and stack map deltas. `Remap` answers that, and is asked
        // only when there is something to ask about — a body with no woven site takes the original
        // path byte for byte, so nothing that worked before pays for a facility it does not use.
        Remap map = null;
        byte[] wovenBody = null;
        if (where.drawingEdges()) {
            try {
                byte[][] sites = callSites(codeBody, methodName);
                boolean any = false;
                for (byte[] one : sites) if (one != null) { any = true; break; }
                if (any) {
                    if (advice != null) sites[0] = ahead(advice, sites[0]);
                    map = Remap.of(codeBody, sites);
                    wovenBody = map.rewrite();
                }
            } catch (Remap.Refused refused) {
                // This method keeps its edges unrecorded and everything else about it unchanged.
                map = null;
                wovenBody = null;
            }
        }

        ByteArrayOutputStream rebuilt = new ByteArrayOutputStream();
        int stack = advice == null ? maxStack : Math.max(maxStack, advice.stack());
        if (wovenBody != null) stack = Math.max(stack, maxStack + 3);   // the array, the index, the value
        write2(rebuilt, stack);
        write2(rebuilt, maxLocals);
        if (wovenBody != null) {
            write4(rebuilt, wovenBody.length);
            rebuilt.write(wovenBody, 0, wovenBody.length);
        } else {
            write4(rebuilt, codeLength + inserted);
            if (advice != null) advice.emit(rebuilt, pool);
            rebuilt.write(codeBody, 0, codeBody.length);
        }

        int handlers = u2();
        write2(rebuilt, handlers);
        for (int i = 0; i < handlers; i++) {
            int start = u2(), stop = u2(), handler = u2(), type = u2();
            if (map != null) {
                write2(rebuilt, map.at(start));
                write2(rebuilt, map.at(stop));
                write2(rebuilt, map.at(handler));
            } else {
                write2(rebuilt, start + inserted);
                write2(rebuilt, stop + inserted);
                write2(rebuilt, handler + inserted);
            }
            write2(rebuilt, type);                             // catch_type — an index, not an offset
        }

        int attrs = u2();
        write2(rebuilt, attrs);
        for (int i = 0; i < attrs; i++) {
            int nameIndex = u2();
            long len = u4();
            byte[] payload = bytes((int) len);
            String kind = String.valueOf(utf8[nameIndex]);
            if ("LineNumberTable".equals(kind)) span(payload);
            byte[] fixed;
            if (map != null) {
                fixed = "LineNumberTable".equals(kind) ? map.fixLines(payload)
                      : "LocalVariableTable".equals(kind) || "LocalVariableTypeTable".equals(kind)
                            ? map.fixLocals(payload)
                      : "StackMapTable".equals(kind) ? map.fixStackMap(payload)
                      : payload;
            }
            else if (inserted == 0) fixed = payload;
            else if ("LineNumberTable".equals(kind)) fixed = shiftPairs(payload, 0);
            else if ("LocalVariableTable".equals(kind) || "LocalVariableTypeTable".equals(kind))
                fixed = shiftPairs(payload, 6);
            else if ("StackMapTable".equals(kind)) fixed = shiftStackMap(payload);
            else fixed = payload;
            write2(rebuilt, nameIndex);
            write4(rebuilt, fixed.length);
            rebuilt.write(fixed, 0, fixed.length);
        }

        at = end;
        byte[] result = rebuilt.toByteArray();
        write4(to, result.length);
        to.write(result, 0, result.length);
    }

    /** The method's own prologue, ahead of any call-site advice that lands at offset zero. */
    private byte[] ahead(Advice prologue, byte[] rest) {
        ByteArrayOutputStream both = new ByteArrayOutputStream();
        prologue.emit(both, pool);
        if (rest != null) both.write(rest, 0, rest.length);
        return both.toByteArray();
    }

    static void write2(ByteArrayOutputStream o, int v) { o.write(v >> 8); o.write(v); }
    static void write4(ByteArrayOutputStream o, long v) { write2(o, (int) (v >> 16)); write2(o, (int) v); }

    /**
     * Tables of fixed-width rows whose first u2 is a start_pc. {@code skip} is the rest of the row.
     *
     * A LineNumberTable row is {@code start_pc, line_number} — four bytes. A LocalVariableTable row
     * is {@code start_pc, length, name_index, descriptor_index, index} — ten. Getting that wrong
     * strides into the middle of each row and rewrites name and descriptor indices as though they
     * were offsets; the class then fails to load with HotSpot reporting a bad *field* signature,
     * because that is how it phrases a LocalVariableTable it cannot read. `javap` and a hand-rolled
     * structural walk both accept the result.
     */
    private byte[] shiftPairs(byte[] table, int skip) {
        byte[] copy = table.clone();
        int count = ((copy[0] & 0xFF) << 8) | (copy[1] & 0xFF);
        int p = 2;
        int row = 4 + skip;
        for (int i = 0; i < count && p + 1 < copy.length; i++, p += row) {
            int pc = (((copy[p] & 0xFF) << 8) | (copy[p + 1] & 0xFF)) + inserted;
            copy[p] = (byte) (pc >> 8);
            copy[p + 1] = (byte) pc;
        }
        return copy;
    }

    /** Rewrite the stack map for a body that moved `inserted` bytes later. */
    private byte[] shiftStackMap(byte[] table) {
        if (table.length < 2) return table;
        int count = ((table[0] & 0xFF) << 8) | (table[1] & 0xFF);
        if (count == 0) return table;

        ByteArrayOutputStream o = new ByteArrayOutputStream();
        write2(o, count);
        int p = 2;
        for (int frame = 0; frame < count && p < table.length; frame++) {
            int tag = table[p++] & 0xFF;
            boolean first = frame == 0;
            if (tag <= 63) {
                int delta = tag + (first ? inserted : 0);
                if (delta <= 63) o.write(delta); else { o.write(251); write2(o, delta); }
            } else if (tag <= 127) {
                int delta = tag - 64 + (first ? inserted : 0);
                if (delta <= 63) o.write(64 + delta); else { o.write(247); write2(o, delta); }
                p = verification(table, p, o);
            } else if (tag == 247) {
                int delta = read2(table, p) + (first ? inserted : 0); p += 2;
                o.write(247); write2(o, delta);
                p = verification(table, p, o);
            } else if (tag >= 248 && tag <= 251) {
                int delta = read2(table, p) + (first ? inserted : 0); p += 2;
                o.write(tag); write2(o, delta);
            } else if (tag <= 254) {
                int delta = read2(table, p) + (first ? inserted : 0); p += 2;
                o.write(tag); write2(o, delta);
                for (int i = 0; i < tag - 251; i++) p = verification(table, p, o);
            } else {
                int delta = read2(table, p) + (first ? inserted : 0); p += 2;
                o.write(255); write2(o, delta);
                int locals = read2(table, p); p += 2; write2(o, locals);
                for (int i = 0; i < locals; i++) p = verification(table, p, o);
                int stack = read2(table, p); p += 2; write2(o, stack);
                for (int i = 0; i < stack; i++) p = verification(table, p, o);
            }
        }
        return o.toByteArray();
    }

    private static int read2(byte[] b, int p) { return ((b[p] & 0xFF) << 8) | (b[p + 1] & 0xFF); }

    /** Copy one verification type, moving it only if it names a place in the code. */
    private int verification(byte[] b, int p, ByteArrayOutputStream o) {
        int tag = b[p] & 0xFF;
        o.write(tag);
        if (tag == 7) { write2(o, read2(b, p + 1)); return p + 3; }              // Object: a cp index
        if (tag == 8) { write2(o, read2(b, p + 1) + inserted); return p + 3; }   // Uninitialized: an offset
        return p + 1;
    }
}
