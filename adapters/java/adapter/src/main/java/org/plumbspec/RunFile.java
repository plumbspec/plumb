package org.plumbspec;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

/**
 * The launcher's resolved facts, read back. Not a configuration format.
 *
 * <p>Everything this adapter needs to know about the project — where the wired system begins, what
 * counts as production code, which stories are structural — is <b>decided by the core</b> and
 * handed over as `kind&lt;TAB&gt;value…` lines. That direction is the point: one reader of
 * configuration exists, it lives in the launcher, and every adapter is told rather than asked to
 * agree about a file format. This adapter previously read two of its own, in two different
 * shapes, which is precisely how a Java project came to be configured differently from a Python
 * one that meant the same thing.
 *
 * <p>Splitting on a tab is the whole implementation, and that is the measure of whether the split
 * of responsibility is right: an adapter that needs a parser has been given the wrong job.
 */
public final class RunFile {

    private RunFile() { }

    /**
     * Every fact of one kind, each as its remaining fields.
     *
     * A missing file yields nothing rather than failing. The launcher writes it, so its absence
     * means an adapter was driven directly — and the honest result of asking a question nobody
     * answered is an empty answer, which downstream already treats as *not declared* (`dev07-5-1`).
     */
    public static List<String[]> read(Path path, String kind) {
        List<String[]> found = new ArrayList<>();
        if (path == null || !Files.isRegularFile(path)) return found;
        try {
            for (String line : Files.readAllLines(path)) {
                String[] fields = line.split("\t");
                if (fields.length > 1 && fields[0].equals(kind))
                    found.add(java.util.Arrays.copyOfRange(fields, 1, fields.length));
            }
        } catch (IOException unreadable) {
            // Same reasoning as absence: report nothing rather than assert something.
            return found;
        }
        return found;
    }
}
