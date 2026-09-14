package org.plumbspec;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/**
 * The document this adapter exists to produce (`dev07-3-3`). Nothing else here is the product.
 *
 * Written by hand rather than through a JSON library on purpose: the shape is fixed by
 * `docs/adapter-contract.md`, small, and entirely ours, so a dependency would buy nothing and
 * cost a version to track — the same reasoning `dev07-1-3` applies to coverage tools.
 */
public final class Manifest {

    /** Was 7 for two majors: major 8 made `inert` the positive claim *the artifact was read and
     *  none of it run*, and this observer could not see a read, so at 8 its `inert` would have
     *  asserted something it never observed. `Pointcut.READS` is that observation, so the claim is
     *  now made on evidence and the lag is over. */
    public static final int SCHEMA_MAJOR = 9;
    public static final int SCHEMA_MINOR = 0;

    /** The shape this adapter writes, spelled `major.minor` as `docs/adapter-contract.md` fixes it
     *  and as the Python adapter spells it.
     *
     *  A bare integer is the **pre-6 spelling**, which the core still reads for majors 1-5 and
     *  nothing else. Emitting one declared every Java manifest in a form that cannot carry a minor
     *  at all: it parsed, and the minor was silently lost, so the two shipped adapters disagreed
     *  about the same field while every board stayed green. That is `dev07-3-3`'s disagreement between
     *  manifests, reached before anyone merged two. */
    public static final String SCHEMA_VERSION = SCHEMA_MAJOR + "." + SCHEMA_MINOR;

    /** The instrument that made these measurements (`dev07-3-1`). */
    public record Provenance(String adapter, String version, String runtime, String mechanism) { }

    private Provenance observer;

    public void observedBy(Provenance provenance) { this.observer = provenance; }

    /** How many tests this run observed at all, cited or not (`dev07-3-2`).
     *
     *  Boxed so that "not reported" has a spelling. A primitive would default to 0, which is the
     *  one wrong answer: it claims the run looked and found nothing, and a run that never got as
     *  far as looking would then be indistinguishable from a broken classpath — which is the whole
     *  failure this field exists to expose. */
    private Integer observedTests;

    public void observed(int count) { this.observedTests = count; }

    /** One citing test's facts for a story (`dev07-3-1`).
     *
     *  <p>{@code about} names which of the subject's aspects this citation bears on (`dev07-3-1`);
     *  null is the ordinary case and means the subject has exactly one. Nothing here can set it
     *  yet — {@code @Proves} carries no such member, because a story has one aspect and a story
     *  with parts already has nested ids. It arrives with the annotation that cites a decision. */
    public record Citation(String test, String depth, String result, String grounding, String ref,
                           String about, String when) { }

    /** How many mutants of a story's wired code its tests noticed (`dev07-2-4`). A score rather than
     *  a word, and on the STORY rather than the citation, because every mutant is run against
     *  every test citing that story — one fact, not the same number repeated per citation. */
    public record Score(int total, int killed) { }

    private final Map<String, List<Citation>> byStory = new TreeMap<>();
    private final Map<String, String> archetypes = new HashMap<>();
    private final Map<String, Score> scores = new HashMap<>();

    /** Absent stays absent: an unfilled slot is *not asked* (`dev07-3-3`), never a zero (`dev07-2-2`). */
    public void scored(String storyId, Score score) { scores.put(storyId, score); }

    /** Read off the SPEC, never the run (``dev07-3-2``) — the one thing a test may not claim. */
    public void declareArchetype(String storyId, String archetype) {
        archetypes.put(storyId, archetype);
    }

    /** Replace every citation's grounding from a per-test map, once the run's own facts are in.
     *
     *  <p>Grounding cannot be settled while a test is finishing. Whether the instrument reached the
     *  project at all is a fact about the <em>run</em> — nothing is instrumented until classes load,
     *  so a test that finishes before any production class has loaded would read `not-checked` and
     *  the next one `inert`, from the same run and the same instrument. The observer had the same
     *  problem and solved it by patching a written document from another process; this is that
     *  correction made where the facts are. */
    public void ground(Map<String, String> byTest) {
        for (var entry : byStory.entrySet()) {
            List<Citation> settled = new ArrayList<>();
            for (Citation c : entry.getValue()) {
                String fact = byTest.get(c.test());
                settled.add(fact == null ? c : new Citation(
                        c.test(), c.depth(), c.result(), fact, c.ref(), c.about(), c.when()));
            }
            entry.setValue(settled);
        }
    }

    public void add(String storyId, Citation citation) {
        byStory.computeIfAbsent(storyId, k -> new ArrayList<>()).add(citation);
    }

    public boolean isEmpty() { return byStory.isEmpty(); }

    /** What was cited, for a later step that needs the facts rather than the document. Reading
     *  them back out of the JSON would mean writing a parser for a format we already hold. */
    public Map<String, List<Citation>> stories() { return Collections.unmodifiableMap(byStory); }

    public String toJson() {
        StringBuilder out = new StringBuilder();
        out.append("{\n  \"schema_version\": \"").append(SCHEMA_VERSION).append("\",\n");
        // Emitted even when absent, because `null` is the value that says *not reported* and
        // omitting the key entirely would leave a consumer unable to tell this adapter's silence
        // from a manifest written before the field existed (`dev07-3-3`, `dev07-3-2`).
        out.append("  \"observed_tests\": ")
           .append(observedTests == null ? "null" : observedTests.toString()).append(",\n");
        out.append("  \"stories\": {");
        String storySep = "\n";
        for (var entry : byStory.entrySet()) {
            out.append(storySep).append("    ").append(quote(entry.getKey())).append(": {\n");
            out.append("      \"archetype\": ")
               .append(quote(archetypes.getOrDefault(entry.getKey(), "behavioral")))
               .append(",\n      \"mutation\": ").append(score(entry.getKey()))
               .append(",\n      \"citations\": [");
            String citeSep = "\n";
            for (Citation c : entry.getValue()) {
                out.append(citeSep).append("        {")
                   .append("\"test\": ").append(quote(c.test()))
                   .append(", \"depth\": ").append(quote(c.depth()))
                   .append(", \"result\": ").append(quote(c.result()))
                   .append(", \"grounding\": ").append(quote(c.grounding()))
                   .append(", \"ref\": ").append(c.ref() == null ? "null" : quote(c.ref()))
                   .append(", \"about\": ").append(c.about() == null ? "null" : quote(c.about()))
                   .append(", \"when\": ").append(c.when() == null ? "null" : quote(c.when()))
                   // On the fact, never the document (`dev07-3-2`): a board may carry this adapter's
                   // measurements beside another's, and two facts are comparable only when the
                   // same kind of observer produced them (`dev07-3-1`).
                   .append(observer == null ? "" : ", \"observer\": {\"adapter\": "
                           + quote(observer.adapter()) + ", \"version\": " + quote(observer.version())
                           + ", \"runtime\": " + quote(observer.runtime()) + ", \"mechanism\": "
                           + quote(observer.mechanism()) + "}")
                   .append("}");
                citeSep = ",\n";
            }
            out.append("\n      ]\n    }");
            storySep = ",\n";
        }
        out.append("\n  }\n}\n");
        return out.toString();
    }

    private String score(String storyId) {
        Score s = scores.get(storyId);
        return s == null ? "null"
                : "{\"total\": " + s.total() + ", \"killed\": " + s.killed() + "}";
    }

    public Path write(Path path) throws IOException {
        Files.createDirectories(path.toAbsolutePath().getParent());
        Files.writeString(path, toJson());
        return path;
    }

    private static String quote(String raw) {
        StringBuilder q = new StringBuilder("\"");
        for (char c : raw.toCharArray()) {
            switch (c) {
                case '"'  -> q.append("\\\"");
                case '\\' -> q.append("\\\\");
                case '\n' -> q.append("\\n");
                case '\r' -> q.append("\\r");
                case '\t' -> q.append("\\t");
                default   -> { if (c < 0x20) q.append(String.format("\\u%04x", (int) c)); else q.append(c); }
            }
        }
        return q.append('"').toString();
    }
}
