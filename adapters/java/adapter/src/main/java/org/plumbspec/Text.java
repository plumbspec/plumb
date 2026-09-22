package org.plumbspec;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;

/**
 * Write a file of text, at the floor this adapter declares (``dev07-3-1-ur12``).
 *
 * <p>{@code Files.writeString} arrived in Java 11 and the adapter runs in the project's runtime,
 * which is older than that wherever an adopter's is. One place rather than the five it was
 * written in, because the encoding is the decision here and a decision spelled five times is one
 * nobody can change (``dev07-1-3-sr08`` says the same of a name).
 */
final class Text {

    private Text() { }

    /** UTF-8, stated rather than inherited: a default charset is the machine's, not the file's. */
    static void write(Path path, String body) throws IOException {
        Files.write(path, body.getBytes(StandardCharsets.UTF_8));
    }

    /** The twin of {@link #write}: {@code Files.readString} is 11 and up. */
    static String read(Path path) throws IOException {
        return new String(Files.readAllBytes(path), StandardCharsets.UTF_8);
    }

    /** Drain a stream to its end. {@code InputStream.readAllBytes} is 9 and up. */
    static byte[] drain(java.io.InputStream in) throws IOException {
        java.io.ByteArrayOutputStream held = new java.io.ByteArrayOutputStream();
        byte[] chunk = new byte[8192];
        for (int got; (got = in.read(chunk)) > 0; ) held.write(chunk, 0, got);
        return held.toByteArray();
    }
}
