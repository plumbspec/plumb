package org.plumbspec;

import java.io.ByteArrayOutputStream;
import java.util.ArrayList;
import java.util.List;

/**
 * Weave a join point onto LEAVING a method, by renaming it and generating a new one around it.
 *
 * <p>Entering is one insertion at offset zero, so every absolute offset in the method shifts by the
 * same amount and nothing has to be recomputed. Leaving is not: a probe before every {@code return}
 * shifts different parts of a method by different amounts, which means recomputing branch targets,
 * exception ranges, line numbers and stack-map frames — a rewriter, and the reason ASM exists.
 *
 * <p>So the original body is not edited at all. It is renamed to {@code foo$plumb$orig}, made
 * private and synthetic, and a new {@code foo} is generated with the original's name, descriptor
 * and access:
 *
 * <pre>
 *     entered();
 *     try { return foo$plumb$orig(args); } finally { left(); }
 * </pre>
 *
 * <p>Every byte of that is authored here, so every offset and its stack map are known rather than
 * derived. The original keeps whatever the compiler emitted, byte for byte, which is the strongest
 * guarantee available that weaving an exit cannot corrupt a method body.
 *
 * <p>Overriding still works — the wrapper keeps the name a subclass overrides and a {@code super}
 * call reaches. A recursive self-call re-enters the wrapper, which is what a depth count wants. The
 * private original is invoked with {@code invokespecial}, so it never re-dispatches to an override.
 */
final class Wrapper {

    private static final int ACC_STATIC = 0x0008;
    private static final int ACC_PRIVATE = 0x0002;
    private static final int ACC_SYNTHETIC = 0x1000;
    private static final int ACC_ABSTRACT = 0x0400;
    private static final int ACC_NATIVE = 0x0100;
    private static final int VISIBILITY = 0x0001 | 0x0002 | 0x0004;      // public|private|protected

    static final String SUFFIX = "$plumb$orig";

    /** One method whose exit is watched: what it was, so a wrapper can be written for it. */
    static final class Wrapped {
        final int access; final String name, descriptor;
        final int nameIndex, descriptorIndex;
        Wrapped(int access, String name, String descriptor, int nameIndex, int descriptorIndex) {
            this.access = access; this.name = name; this.descriptor = descriptor;
            this.nameIndex = nameIndex; this.descriptorIndex = descriptorIndex;
        }
    }

    /**
     * Can this method be wrapped at all?
     *
     * <p>Abstract and native have no body to rename. A constructor cannot be renamed — its name is
     * how the JVM knows what it is — and neither can a static initialiser. None of them is a place
     * a project declares the wired system to begin, so refusing them costs nothing and guessing
     * would produce a class that will not load.
     */
    static boolean wrappable(int access, String name) {
        if ((access & (ACC_ABSTRACT | ACC_NATIVE)) != 0) return false;
        return !"<init>".equals(name) && !"<clinit>".equals(name);
    }

    /** What the renamed original should be called, and how it should be declared. */
    static int hiddenAccess(int access) {
        return (access & ~VISIBILITY) | ACC_PRIVATE | ACC_SYNTHETIC;
    }

    /** Generate the wrapper for each watched method, as a run of `method_info` structures. */
    static byte[] methods(List<Wrapped> all, Constants pool, String owner, int major) {
        ByteArrayOutputStream out = new ByteArrayOutputStream();
        for (Wrapped each : all) {
            byte[] generated = one(each, pool, owner, major);
            out.write(generated, 0, generated.length);
        }
        return out.toByteArray();
    }

    private static byte[] one(Wrapped m, Constants pool, String owner, int major) {
        boolean isStatic = (m.access & ACC_STATIC) != 0;
        List<String> params = parameters(m.descriptor);
        String returns = returnType(m.descriptor);

        ByteArrayOutputStream code = new ByteArrayOutputStream();
        Advice.signal("entered").emit(code, pool);                       // 3 bytes
        int tryStart = code.size();

        int slot = isStatic ? 0 : 1;
        if (!isStatic) { code.write(0x19); code.write(0); }              // aload_0 (wide form)
        for (String p : params) {
            code.write(loadOpcode(p));
            code.write(slot);
            slot += width(p);
        }
        int hidden = pool.member(Constants.Member.method(owner, m.name + SUFFIX, m.descriptor));
        code.write(isStatic ? 0xB8 : 0xB7);                              // invokestatic | invokespecial
        code.write(hidden >> 8); code.write(hidden);
        int tryEnd = code.size();

        Advice.signal("left").emit(code, pool);                          // 3 bytes
        code.write(returnOpcode(returns));
        int handler = code.size();
        Advice.signal("left").emit(code, pool);
        code.write(0xBF);                                                // athrow

        byte[] body = code.toByteArray();
        int locals = slot;
        int stack = Math.max(1, slot + width(returns));

        ByteArrayOutputStream attr = new ByteArrayOutputStream();
        Probe.write2(attr, stack);
        Probe.write2(attr, locals);
        Probe.write4(attr, body.length);
        attr.write(body, 0, body.length);
        Probe.write2(attr, 1);                                           // one exception handler
        Probe.write2(attr, tryStart);
        Probe.write2(attr, tryEnd);
        Probe.write2(attr, handler);
        Probe.write2(attr, 0);                                           // catch_type 0 — any (finally)

        // A class at major 50 or above carries a stack map or the verifier refuses it. One frame,
        // at the handler, where the stack holds the throwable and the locals are the parameters.
        boolean mapped = major >= 50;
        Probe.write2(attr, mapped ? 1 : 0);
        if (mapped) {
            ByteArrayOutputStream map = new ByteArrayOutputStream();
            Probe.write2(map, 1);                                        // one frame
            map.write(255);                                              // full_frame
            Probe.write2(map, handler);                                  // offset_delta — first frame
            List<String> localTypes = new ArrayList<String>();
            if (!isStatic) localTypes.add("L" + owner + ";");
            localTypes.addAll(params);
            Probe.write2(map, localTypes.size());
            for (String t : localTypes) verification(map, t, pool);
            Probe.write2(map, 1);
            map.write(7);                                                // ITEM_Object
            int thrown = pool.classRef("java/lang/Throwable");
            Probe.write2(map, thrown);
            byte[] frame = map.toByteArray();
            Probe.write2(attr, pool.utf8("StackMapTable"));
            Probe.write4(attr, frame.length);
            attr.write(frame, 0, frame.length);
        }

        byte[] codeAttr = attr.toByteArray();
        ByteArrayOutputStream method = new ByteArrayOutputStream();
        Probe.write2(method, m.access);
        Probe.write2(method, m.nameIndex);
        Probe.write2(method, m.descriptorIndex);
        Probe.write2(method, 1);                                         // one attribute: Code
        Probe.write2(method, pool.utf8("Code"));
        Probe.write4(method, codeAttr.length);
        method.write(codeAttr, 0, codeAttr.length);
        return method.toByteArray();
    }

    private static void verification(ByteArrayOutputStream to, String type, Constants pool) {
        char c = type.charAt(0);
        if (c == 'J') { to.write(4); return; }                           // ITEM_Long
        if (c == 'F') { to.write(2); return; }                           // ITEM_Float
        if (c == 'D') { to.write(3); return; }                           // ITEM_Double
        if (c == 'L' || c == '[') {
            to.write(7);
            String internal = c == '[' ? type : type.substring(1, type.length() - 1);
            Probe.write2(to, pool.classRef(internal));
            return;
        }
        to.write(1);                                                     // ITEM_Integer
    }

    private static int width(String type) {
        char c = type.charAt(0);
        if (c == 'V') return 0;
        return (c == 'J' || c == 'D') ? 2 : 1;
    }

    private static int loadOpcode(String type) {
        switch (type.charAt(0)) {
            case 'J': return 0x16;                                       // lload
            case 'F': return 0x17;                                       // fload
            case 'D': return 0x18;                                       // dload
            case 'L': case '[': return 0x19;                             // aload
            default: return 0x15;                                        // iload
        }
    }

    private static int returnOpcode(String type) {
        switch (type.charAt(0)) {
            case 'V': return 0xB1;
            case 'J': return 0xAD;
            case 'F': return 0xAE;
            case 'D': return 0xAF;
            case 'L': case '[': return 0xB0;
            default: return 0xAC;
        }
    }

    /** The parameter types of a descriptor, each as its own field descriptor. */
    static List<String> parameters(String descriptor) {
        List<String> found = new ArrayList<String>();
        int i = descriptor.indexOf('(') + 1;
        while (descriptor.charAt(i) != ')') {
            int start = i;
            while (descriptor.charAt(i) == '[') i++;
            if (descriptor.charAt(i) == 'L') i = descriptor.indexOf(';', i);
            i++;
            found.add(descriptor.substring(start, i));
        }
        return found;
    }

    static String returnType(String descriptor) {
        return descriptor.substring(descriptor.indexOf(')') + 1);
    }
}
