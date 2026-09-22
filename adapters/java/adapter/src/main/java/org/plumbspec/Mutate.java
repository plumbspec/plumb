package org.plumbspec;

import java.io.IOException;
import java.nio.file.*;
import java.util.*;

/**
 * Chapter 4 for the JVM: mutate the code a story's tests drove, and see whether they notice.
 *
 * The **third** step of the run, after the suite and the observer, because it needs what both of
 * them produced — which tests cited which story (the runner) and which methods ran with an entry
 * point above them (the observer). It patches the score into the manifest the same way grounding
 * is patched in.
 *
 * <p><b>Java's cost is not Python's.</b> There a mutant is one test process; here it is a
 * <em>compile</em> and then a JVM, and both are slower than the tests they wrap. That does not
 * change what mutation is worth — it finds tests that cannot fail, which nothing else here does —
 * it changes when you can afford to ask. So the count and a measured floor are reported before
 * any of it runs (`dev07-2-2`), and the honest place for a full pass is a nightly, not a desk.
 *
 * <p>Usage: Mutate &lt;source-dir&gt; &lt;classes-out&gt; &lt;classpath&gt; &lt;build-dir&gt;
 */
public final class Mutate {

    /** Where the original is parked while a mutant stands in for it (`dev07-2-3`). If this file is
     *  still here, a run died and the tree needs putting back — which the next run does. */
    /** Owned by {@link Rescue}, which puts it back — recovery holds at a floor mutation does not. */
    public static final String RESCUE = Rescue.PARKED;

    /** A mutant can make a loop never terminate — negating a `while` is one of three operators. */
    private static final int TIMEOUT_SECONDS = 120;

    private final Path sources;
    private final Path classes;
    private final String classpath;

    private Mutate(Path sources, Path classes, String classpath) {
        this.sources = sources;
        this.classes = classes;
        this.classpath = classpath;
    }

    /** One story's pass, costed before any of it runs (`dev07-2-2`). */
    private static final class Plan {
        private final String story;
        private final List<String> tests;
        private final Map<Path, Set<String>> byFile;
        private final Set<String> methods;
        private final int mutants;

        Plan(String story, List<String> tests, Map<Path, Set<String>> byFile,
             Set<String> methods, int mutants) {
            this.story = story; this.tests = tests; this.byFile = byFile;
            this.methods = methods; this.mutants = mutants;
        }

        String story() { return story; }
        List<String> tests() { return tests; }
        Map<Path, Set<String>> byFile() { return byFile; }
        Set<String> methods() { return methods; }
        int mutants() { return mutants; }

        boolean runnable() { return mutants > 0 && !tests.isEmpty(); }
    }

    public static void main(String[] args) throws Exception {
        Path build = Paths.get(args[3]);
        // A MUTANT GETS ITS OWN OUTPUT DIRECTORY, FIRST ON THE CLASSPATH.
        //
        // It used to be compiled into the tests root, which had two consequences and neither was
        // visible from a mutation run. The mutant only shadows the original if the tests root comes
        // first on the classpath, which is the project's arrangement and not ours to assume. And it
        // is a PRODUCTION class left inside a test root, which `dev07-1-3` excludes from
        // instrumentation — so a `--mutation` run poisoned every board after it, the surface went
        // unwatched, and every test read `inert`. That defect was silent until `inert` was made to
        // require a live instrument.
        Path mutants = build.resolve("mutants");
        Files.createDirectories(mutants);
        Mutate mutate = new Mutate(Paths.get(args[0]), mutants, mutants + ":" + args[2]);

        Path recovered = Rescue.restore(build);
        if (recovered != null)
            System.out.println("mutation: put back " + recovered + " — a previous run was interrupted");

        Map<String, List<String>> testsByStory = passingCitations(build.resolve("citations.tsv"));
        Map<String, Set<String>> wiredByTest = wired(build.resolve("wired.txt"));

        List<Plan> plans = new ArrayList<>();
        for (Map.Entry<String, List<String>> entry : testsByStory.entrySet())
            plans.add(mutate.plan(entry.getKey(), entry.getValue(), wiredByTest));
        int pairs = plans.stream().mapToInt(Plan::mutants).sum();
        long runnable = plans.stream().filter(Plan::runnable).count();
        if (pairs == 0) {
            System.out.println("mutation: nothing to mutate — no story drove code under a declared entry point");
            return;
        }

        // ONE COMPILE PER MUTANT, NOT ONE PER STORY THAT SCOPES IT. The same source mutant sat in
        // the scope of many stories and was compiled and run once for each — the same bytes, the
        // same javac, the same JVM start, to learn the same thing. Measured, that was 3,877 runs
        // over a union of about a thousand distinct mutants. The only reason it had to be that way
        // was that `MutantRun` answered *did any test fail*, which cannot be re-read per story;
        // now it names the tests, so one run answers for every story that scopes the mutant and
        // each is still judged by its own citing tests and no others (`dev07-2-3`).
        List<Job> jobs = mutate.jobs(plans);
        System.out.printf("mutation: %d mutants over %d stories, %d distinct — at least %s "
                        + "(%.1fs compile+JVM floor, measured here), plus the tests themselves%n",
                pairs, runnable, jobs.size(),
                duration(jobs.size() * mutate.floor(plans)), mutate.floor(plans));

        long started = System.nanoTime();
        // THIS is the long phase — the suite pass is seconds and this is minutes to hours — so it
        // is the one that most needs to say where it has got to (`dev07-1-3`). Per mutant, which is
        // now also the unit of work rather than only the unit of counting.
        mutate.position = build.resolve("progress.txt");
        mutate.total = jobs.size();
        mutate.report();
        for (Job job : jobs) {
            job.noticedBy = mutate.noticedBy(job, build);
            mutate.finished++;
            mutate.report();
        }
        System.out.printf("  %d distinct mutants run in %ds%n",
                jobs.size(), (System.nanoTime() - started) / 1_000_000_000L);

        // Each story judged by ITS OWN tests against the shared results.
        StringBuilder scores = new StringBuilder();
        Map<String, List<Survivor>> survivors = new LinkedHashMap<>();
        int done = 0;
        for (Plan plan : plans) {
            if (!plan.runnable()) continue;
            List<Survivor> survived = new ArrayList<>();
            int killed = 0, seen = 0;
            for (Job job : jobs) {
                if (!plan.methods().contains(job.mutant.where())) continue;
                seen++;
                if (job.noticedByAnyOf(plan.tests())) killed++;
                else survived.add(new Survivor(job.mutant.operator(), job.mutant.where(),
                        mutate.relative(job.file), job.mutant.line(),
                        job.reachedByAnyOf(plan.tests())));
            }
            survivors.put(plan.story(), survived);
            scores.append(plan.story()).append('\t').append(seen)
                  .append('\t').append(killed).append('\n');
            System.out.printf("  [%d/%d] %s: %d/%d killed%n", ++done, runnable, plan.story(),
                    killed, seen);
        }
        Text.write(build.resolve("scores.tsv"), scores.toString());
        applyTo(build.resolve("manifest.json"), build.resolve("scores.tsv"), survivors);
    }

    /** One distinct mutant, and every test that could possibly notice it. */
    private static final class Job {
        final Path file;
        final Mutants.Mutant mutant;
        /** The union of the citing tests of every story that scopes this mutant's method. Run
         *  once; each story then reads back only its own. */
        final List<String> tests;
        Set<String> noticedBy = java.util.Collections.<String>emptySet();
        /** The tests that actually evaluated the mutated expression. A story whose tests are all
         *  absent from this never had a chance at the mutant (`dev07-2-4`). */
        Set<String> reachedBy = java.util.Collections.<String>emptySet();

        Job(Path file, Mutants.Mutant mutant, List<String> tests) {
            this.file = file; this.mutant = mutant; this.tests = tests;
        }

        boolean noticedByAnyOf(List<String> mine) {
            for (String test : mine) if (noticedBy.contains(test)) return true;
            return false;
        }

        boolean reachedByAnyOf(List<String> mine) {
            for (String test : mine) if (reachedBy.contains(test)) return true;
            return false;
        }
    }

    /** Every distinct mutant, each carrying the tests that could kill it.
     *
     *  <p>Generated over the UNION of the methods any story scoped, so a method in thirty stories
     *  yields its mutants once. Filtering that set by a story's own methods gives back exactly what
     *  generating over that story alone would have — the same denominator as before, at a fraction
     *  of the work. */
    private List<Job> jobs(List<Plan> plans) throws IOException {
        Map<Path, Set<String>> byFile = new TreeMap<>();
        for (Plan plan : plans)
            for (Map.Entry<Path, Set<String>> entry : plan.byFile().entrySet())
                byFile.computeIfAbsent(entry.getKey(), k -> new TreeSet<>()).addAll(entry.getValue());

        List<Job> jobs = new ArrayList<>();
        for (Map.Entry<Path, Set<String>> entry : byFile.entrySet()) {
            for (Mutants.Mutant mutant : Mutants.of(entry.getKey(), entry.getValue())) {
                Set<String> tests = new LinkedHashSet<>();
                for (Plan plan : plans)
                    if (plan.methods().contains(mutant.where())) tests.addAll(plan.tests());
                if (!tests.isEmpty())
                    jobs.add(new Job(entry.getKey(), mutant, new ArrayList<>(tests)));
            }
        }
        return jobs;
    }

    // ---- what to mutate ------------------------------------------------------------------

    /**
     * The union of wired methods across every passing citation, grouped by the file holding them.
     *
     * The union, and then every mutant faces all of them: a mutant only one of three citing tests
     * would catch is still caught, so an unnoticed mutant means "no test of this story noticed"
     * rather than "the one I picked did not" (`dev07-2-3`).
     */
    private Plan plan(String story, List<String> tests, Map<String, Set<String>> wiredByTest) throws IOException {
        Set<String> methods = new TreeSet<>();
        for (String test : tests) methods.addAll(wiredByTest.getOrDefault(test, java.util.Collections.<String>emptySet()));

        Map<Path, Set<String>> byFile = new TreeMap<>();
        for (String method : methods) {
            Path file = locate(method);
            if (file != null) byFile.computeIfAbsent(file, k -> new TreeSet<>()).add(method);
        }
        int mutants = 0;
        for (Map.Entry<Path, Set<String>> entry : byFile.entrySet()) mutants += Mutants.count(entry.getKey(), entry.getValue());
        return new Plan(story, tests, byFile, methods, mutants);
    }

    /** ``pkg.Outer$Inner#method`` back to the file that declares it — {@code Mutants}' naming,
     *  run backwards. A nested class lives in its outer class's file, and a name from outside the
     *  declared sources resolves to nothing rather than to a guess. */
    private Path locate(String method) {
        String type = method.substring(0, method.indexOf('#'));
        String outer = type.contains("$") ? type.substring(0, type.indexOf('$')) : type;
        Path candidate = sources.resolve(outer.replace('.', '/') + ".java");
        return Files.isRegularFile(candidate) ? candidate : null;
    }

    // ---- running it ----------------------------------------------------------------------

    /** Where to say how far this phase has got, and out of how many (`dev07-1-3`). */
    private Path position;
    private int total;
    private int finished;

    /** `<done> <total> <unix-millis>`, rewritten in place — the same shape the suite phase writes,
     *  because the launcher reads one contract and should not learn a second. */
    private void report() {
        if (position == null) return;
        try {
            Text.write(position, finished + " " + total + " " + System.currentTimeMillis());
        } catch (IOException unreportable) {
            // Progress is a courtesy. The run is the point.
        }
    }

    /** One mutant no test noticed, named the way the reader's next move needs it (`dev07-2-4`). */
    private static final class Survivor {
        private final String operator, where, file;
        private final long line;
        private final boolean reached;

        Survivor(String operator, String where, String file, long line, boolean reached) {
            this.operator = operator; this.where = where; this.file = file;
            this.line = line; this.reached = reached;
        }

        String operator() { return operator; }
        String where() { return where; }
        String file() { return file; }
        long line() { return line; }
        boolean reached() { return reached; }
    }

    /** The source file as the reader types it, not as this process happens to have resolved it. */
    private String relative(Path file) {
        Path from = Paths.get("").toAbsolutePath();
        Path absolute = file.toAbsolutePath().normalize();
        return absolute.startsWith(from) ? from.relativize(absolute).toString() : absolute.toString();
    }

    /**
     * Park the original, write the mutant, recompile it, run every test that could notice it, put
     * it back (`dev07-2-3`) — and answer with the tests that DID.
     *
     * <p>A mutant that will not compile is noticed by <b>nothing</b>. It is not a test failing; it
     * is this tool emitting something that was never a valid program, and scoring it as a kill
     * would quietly inflate every score by the number of mutants we got wrong.
     *
     * <p>Every test in the union runs, with no stopping at the first failure: which stories this
     * mutant is dead for is exactly the question, and an early exit answers it for one of them and
     * leaves the rest unknown (`dev07-2-3`).
     */
    private Set<String> noticedBy(Job job, Path build) throws Exception {
        byte[] original = Files.readAllBytes(job.file);
        Path rescue = build.resolve(RESCUE);
        Text.write(rescue, job.file.toAbsolutePath() + "\n" + new String(original));
        try {
            Text.write(job.file, job.mutant.source());
            if (!compiles(job.file)) {
                System.out.println("    skipped (would not compile): " + job.mutant.operator()
                        + " @ " + job.mutant.where() + ":" + job.mutant.line());
                return java.util.Collections.<String>emptySet();
            }
            String said = capture(command("org.plumbspec.MutantRun", job.tests));
            if (said.contains(MutantRun.NOTHING_RAN)) {
                // A mutant nothing ran is not a mutant anything survived: treated as noticed by
                // everything that asked, which never credits a test with a kill it earned.
                job.reachedBy = new LinkedHashSet<>(job.tests);
                return new LinkedHashSet<>(job.tests);
            }
            Set<String> noticed = new LinkedHashSet<>();
            Set<String> reached = new LinkedHashSet<>();
            for (String line : said.split("\n")) {
                if (line.startsWith(MutantRun.NOTICED))
                    noticed.add(line.substring(MutantRun.NOTICED.length()).trim());
                else if (line.startsWith(MutantRun.REACHED))
                    reached.add(line.substring(MutantRun.REACHED.length()).trim());
            }
            job.reachedBy = reached;
            return noticed;
        } finally {
            Files.write(job.file, original);
            compiles(job.file);      // leave the class files matching the source, not the mutant
            Files.deleteIfExists(rescue);
        }
    }

    private boolean compiles(Path file) throws Exception {
        return exec(java.util.Arrays.asList("javac", "-cp", classpath + ":" + classes,
                "-d", classes.toString(), file.toString())) == 0;
    }

    private List<String> command(String main, List<String> tests) {
        List<String> command = new ArrayList<>(
                java.util.Arrays.asList("java", "-ea", "-cp", classpath + ":" + classes, main));
        command.addAll(tests);
        return command;
    }

    /** Run and hand back what it said. A hang is noticed by everything, the way it always was:
     *  a mutant that stops the suite finishing did not pass over it unmoved. */
    private String capture(List<String> command) throws Exception {
        Process process = new ProcessBuilder(command).redirectErrorStream(true).start();
        byte[] said = Text.drain(process.getInputStream());   // drained, or the pipe fills
        if (!process.waitFor(TIMEOUT_SECONDS, java.util.concurrent.TimeUnit.SECONDS)) {
            process.destroyForcibly();
            return MutantRun.NOTHING_RAN;
        }
        return new String(said, java.nio.charset.StandardCharsets.UTF_8);
    }

    private int exec(List<String> command) throws Exception {
        Process process = new ProcessBuilder(command).redirectErrorStream(true).start();
        Text.drain(process.getInputStream());     // drained, or the pipe fills and it hangs
        if (!process.waitFor(TIMEOUT_SECONDS, java.util.concurrent.TimeUnit.SECONDS)) {
            process.destroyForcibly();
            return 1;    // a mutant that hangs did not pass over the tests unmoved
        }
        return process.exitValue();
    }

    /** One compile plus one JVM, which every mutant pays before a single assertion runs. */
    private double floorSeconds = -1;

    private double floor(List<Plan> plans) throws Exception {
        if (floorSeconds >= 0) return floorSeconds;
        Plan first = plans.stream().filter(Plan::runnable).findFirst().orElse(null);
        if (first == null) return floorSeconds = 0;
        long started = System.nanoTime();
        compiles(first.byFile().keySet().iterator().next());
        exec(command("org.plumbspec.MutantRun", java.util.Collections.emptyList()));
        return floorSeconds = (System.nanoTime() - started) / 1_000_000_000.0;
    }

    private static String duration(double seconds) {
        if (seconds < 90) return Math.round(seconds) + "s";
        if (seconds < 5400) return Math.round(seconds / 60) + " min";
        return String.format("%.1f hours", seconds / 3600);
    }

    // ---- the tree, and the document ------------------------------------------------------

    /** Put back whatever an interrupted run left mutated (`dev07-2-3`). Before anything is read: a
     *  leftover mutant is silent, and every fact taken from it would be slightly wrong.
     *
     *  <p><b>Static, and called by the ordinary runner as well as by this one.</b> It used to run
     *  only here, so a mutation killed part-way left the adopter's source rewritten until somebody
     *  ran mutation *again* — and every board in between measured the mutant and reported it as the
     *  project. The Python adapter has always recovered on every run "whether or not mutation is on
     *  this time", for exactly that reason, and this is the same rule arriving on the other side. */


    private static Map<String, List<String>> passingCitations(Path tsv) throws IOException {
        Map<String, List<String>> found = new TreeMap<>();
        if (!Files.exists(tsv)) return found;
        for (String line : Files.readAllLines(tsv)) {
            String[] parts = line.split("\t", -1);
            // Only passing citations. A failing test kills every mutant for the reason it was
            // already failing, which would credit a test for not working.
            if (parts.length == 3 && parts[2].equals("passed"))
                found.computeIfAbsent(parts[0], k -> new ArrayList<>()).add(parts[1]);
        }
        return found;
    }

    private static Map<String, Set<String>> wired(Path file) throws IOException {
        Map<String, Set<String>> found = new LinkedHashMap<>();
        if (!Files.exists(file)) return found;
        for (String line : Files.readAllLines(file)) {
            String[] parts = line.split("\t", -1);
            if (parts.length == 2 && !parts[1].isEmpty())
                found.put(parts[0], new TreeSet<>(Arrays.asList(parts[1].split(","))));
        }
        return found;
    }

    /** Patch the score into the story's slot, the way the observer patches in grounding. */
    private static void applyTo(Path manifest, Path scores, Map<String, List<Survivor>> survivors)
            throws IOException {
        if (!Files.exists(manifest) || !Files.exists(scores)) return;
        String json = Text.read(manifest);
        for (String line : Files.readAllLines(scores)) {
            String[] parts = line.split("\t");
            if (parts.length != 3) continue;
            String needle = "\"" + parts[0] + "\": {";
            int at = json.indexOf(needle);
            if (at < 0) continue;
            int slot = json.indexOf("\"mutation\": null", at);
            if (slot < 0) continue;
            StringBuilder named = new StringBuilder();
            for (Survivor s : survivors.getOrDefault(parts[0], java.util.Collections.emptyList())) {
                if (named.length() > 0) named.append(", ");
                named.append("{\"operator\": \"").append(s.operator())
                     .append("\", \"where\": \"").append(s.where())
                     .append("\", \"file\": \"").append(s.file().replace("\\", "\\\\"))
                     .append("\", \"line\": ").append(s.line())
                     .append(", \"reached\": ").append(s.reached()).append("}");
            }
            json = json.substring(0, slot)
                 + "\"mutation\": {\"total\": " + parts[1] + ", \"killed\": " + parts[2]
                 + ", \"survivors\": [" + named + "]}"
                 + json.substring(slot + "\"mutation\": null".length());
        }
        Text.write(manifest, json);
        System.out.println("scored -> " + manifest);
    }
}
