package org.plumbspec;

import java.io.ByteArrayOutputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Constant-pool entries a weave needs, appended to a class's own and handed back as indices.
 *
 * <p>Appending never moves an existing index, which is the whole reason weaving is affordable
 * without re-writing a class: everything the compiler emitted keeps its references.
 *
 * <p><b>Built rather than counted.</b> This was ten hardcoded entries and arithmetic like
 * {@code first + 8}, which is a second copy of the layout kept in the reader's head — and it was
 * wrong once, silently: a `NameAndType` pointing two slots short produced a class the JVM refused
 * with "Invalid constant pool index". Advice declares the members it needs and gets an index back,
 * so adding a new kind of advice does not require anybody to re-derive the offsets.
 */
final class Constants {

    /** A member reference: a field or a method on some owner. */
    static final class Member {
        final int tag;                       // 9 Fieldref, 10 Methodref
        final String owner, name, descriptor;

        Member(int tag, String owner, String name, String descriptor) {
            this.tag = tag; this.owner = owner; this.name = name; this.descriptor = descriptor;
        }

        static Member field(String owner, String name, String descriptor) {
            return new Member(9, owner, name, descriptor);
        }

        static Member method(String owner, String name, String descriptor) {
            return new Member(10, owner, name, descriptor);
        }

        @Override public boolean equals(Object other) {
            if (!(other instanceof Member)) return false;
            Member m = (Member) other;
            return tag == m.tag && owner.equals(m.owner) && name.equals(m.name)
                    && descriptor.equals(m.descriptor);
        }

        @Override public int hashCode() {
            return (tag * 31 + owner.hashCode()) * 31 + name.hashCode() * 31 + descriptor.hashCode();
        }
    }

    private final int first;                                  // index the appended run starts at
    private int next;
    private final ByteArrayOutputStream bytes = new ByteArrayOutputStream();
    private final Map<String, Integer> utf8 = new LinkedHashMap<String, Integer>();
    private final Map<String, Integer> classes = new LinkedHashMap<String, Integer>();
    private final Map<String, Integer> strings = new LinkedHashMap<String, Integer>();
    private final Map<Member, Integer> members = new LinkedHashMap<Member, Integer>();

    Constants(int existingCount) { this.first = existingCount; this.next = existingCount; }

    /** The new `constant_pool_count`: entries plus one, as the format defines it. */
    int count() { return next; }

    byte[] appended() { return bytes.toByteArray(); }

    private int put(int tag, byte[] body) {
        bytes.write(tag);
        bytes.write(body, 0, body.length);
        return next++;
    }

    private static byte[] u2(int v) { return new byte[] {(byte) (v >> 8), (byte) v}; }

    int utf8(String text) {
        Integer known = utf8.get(text);
        if (known != null) return known;
        byte[] raw = text.getBytes(StandardCharsets.UTF_8);
        ByteArrayOutputStream body = new ByteArrayOutputStream();
        body.write(raw.length >> 8); body.write(raw.length);
        body.write(raw, 0, raw.length);
        int at = put(1, body.toByteArray());
        utf8.put(text, at);
        return at;
    }

    int classRef(String internalName) {
        Integer known = classes.get(internalName);
        if (known != null) return known;
        int at = put(7, u2(utf8(internalName)));
        classes.put(internalName, at);
        return at;
    }

    /** A `String` constant, for advice that names the site it was woven into. */
    int string(String value) {
        Integer known = strings.get(value);
        if (known != null) return known;
        int at = put(8, u2(utf8(value)));
        strings.put(value, at);
        return at;
    }

    int member(Member wanted) {
        Integer known = members.get(wanted);
        if (known != null) return known;
        int owner = classRef(wanted.owner);
        int name = utf8(wanted.name);
        int descriptor = utf8(wanted.descriptor);
        ByteArrayOutputStream nameAndType = new ByteArrayOutputStream();
        nameAndType.write(name >> 8); nameAndType.write(name);
        nameAndType.write(descriptor >> 8); nameAndType.write(descriptor);
        int nt = put(12, nameAndType.toByteArray());
        ByteArrayOutputStream ref = new ByteArrayOutputStream();
        ref.write(owner >> 8); ref.write(owner);
        ref.write(nt >> 8); ref.write(nt);
        int at = put(wanted.tag, ref.toByteArray());
        members.put(wanted, at);
        return at;
    }

    List<String> describe() {
        List<String> said = new ArrayList<String>();
        said.add("appended " + (next - first) + " entries from " + first);
        return said;
    }
}
