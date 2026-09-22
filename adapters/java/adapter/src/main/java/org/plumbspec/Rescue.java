package org.plumbspec;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

/**
 * Put back whatever an interrupted mutation run left on disk (``dev07-2-3``).
 *
 * <p>Apart from {@link Mutate} on purpose. A leftover mutant corrupts the <b>test run</b> first of
 * all, so this is called before the tests on every ordinary board — a board that is not mutating
 * still has to recover from one that was. Mutation itself needs a compiler the adapter's floor
 * does not carry (``dev07-3-1-sr3``); recovery needs a file, so it holds at the floor and an
 * ordinary run never reaches for what is not there.
 */
final class Rescue {

    private Rescue() { }

    /** Where the original is parked while a mutant stands in for it. */
    static final String PARKED = ".plumb-mutation-rescue";

    /** Put back whatever was parked, and say which file it was. Null when nothing was. */
    static Path restore(Path build) throws IOException {
        Path parked = build.resolve(PARKED);
        if (!Files.isRegularFile(parked)) return null;
        String held = new String(Files.readAllBytes(parked), StandardCharsets.UTF_8);
        int split = held.indexOf('\n');
        Path file = Paths.get(held.substring(0, split));
        Files.write(file, held.substring(split + 1).getBytes(StandardCharsets.UTF_8));
        Files.delete(parked);
        return file;
    }
}
