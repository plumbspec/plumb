# The Java adapter

A JUnit Platform run in, a manifest out (`dev07-3-3`). Nothing else — the core reads the manifest and
derives every status from it, so nothing here decides anything.

    mvn -f pom.xml package              # compile, write the classpath, and jar the adapter
    plumb board --project .             # one command, same as any Python project
    plumb board --project . --mutation  # …and the same flag

**There is no `ground.sh` any more.** Loading the agent, handing it the declared entry points and
then mutating are all the launcher's job. What makes Java adoption expensive is never the adapter —
it is *"run two shell scripts, then point `plumb` at a file"*, and a config file in a shape no
Python project uses.

The build only compiles. Plumb does not build your project; your build tool does, and it writes a
classpath the same way (`mvn dependency:build-classpath`).

**The suite JVM outlives its own run.** `sample/App.java` holds a non-daemon `ExecutorService`, so
that process does not exit when the manifest is written — real suites do this constantly, and it is
the same hazard the observer works around by not waiting for `VMDeath`. The launcher terminates it
rather than waiting, which is why the command returns.

The `adapter` module also produces `build/plumb-java.jar` — the shippable half, everything the
adapter owns and nothing of the sample. That jar is what rides inside the artifact, so an adopter never
compiles this and never configures where it is: the launcher extracts it from its own archive on
first use, into a cache keyed by version.

Three modules: `annotations` — the citation vocabulary alone, published to Maven Central and
compiled at its own floor — `adapter`, which carries the vocabulary's classes inside the shipped
jar, and `sample`, the fixture the suite boards. The aggregator lists them and none of them
inherits from it, because a published pom whose parent is unpublished is one nobody can resolve.
Package naming is deliberately provisional — a published artifact needs a
reverse-domain name and Maven coordinates, which is a branding decision and not one to invent
here.

## What it does

- **`@Proves(value, depth, ref)`** — the one authored link, on the test (`dev05`). Repeatable,
  because a citation is per (test, story) pair and each carries its own depth and external key.
- **Result normalization** (`dev07-3-1`) — JUnit's own signal, without translation loss. An
  `Assumptions.abort` is the "specified, not built" signal, exactly as pytest's skip is.
- **Archetypes** (`dev07-4-2`, `dev07-3-2`) — **handed over already resolved**. The adapter keeps no copy
  and reads no config: the launcher decides, from `[archetypes]` in `plumb.toml`. Declared on the
  story, never on the test, which would let the thing being judged pick its own gate. Silence
  means behavioral.
- **Manifest emission** (`dev07-3-3`, `dev07-3-2`, `dev07-3-1`) — the document, at the declared schema version,
  naming the instrument that made its measurements.

## Grounding

    plumb board --project .    # runs the suite with the agent loaded

One process. The suite runs with a `java.lang.instrument` agent loaded, which weaves probes into
classes as they load; the listener writes the manifest. It watches three things and nothing else,
because cost is per event: the probe anchors (which test owns the window, and on which thread),
each declared entry point, and a short fixed list of dispatch primitives.

Entry points are declared in `plumb.toml`, in Java's own spelling (`dev07-1-3`):

    entry_points = ["com.myapp.Api#handleRequest"]
    production   = ["com.myapp.*"]
    sources      = ["src/main/java"]

    [java]
    tests          = "target/test-classes"
    classpath_file = "target/plumb-classpath.txt"

The **values** stay adapter-native — `Class#method` here, `module:function` in Python — because
one invented spelling would make every adapter translate out of a form none of them use. The
**file** is shared, and that is what makes one command work.

**Why from outside the process.** A flag set on a thread cannot survive a hand-off to a pool that
already existed — measured, and true of `ThreadLocal`, `InheritableThreadLocal` and `ScopedValue`
alike. So there is nothing to propagate. A debugger sees *both ends* of the hand-off and can
attribute it, which is what makes `dispatched` reachable rather than theoretical.

**Two things the observer must not assume.** That the debuggee exits — a suite leaving a
non-daemon executor keeps the JVM alive forever, so `PlumbProbe.runFinished` says when the run is
over rather than waiting for `VMDeath`. And that it can see everything — it watches entry points,
not every method.

## All five grounding values, including `inert`

`inert` is a positive claim that **no** production code ran anywhere, so it looked at first as
though an observer watching entry points could never support it — and therefore that structural
stories could never be proven on Java, which would have cut out most of what a JVM estate wants
this for.

It costs one event. `inert` needs a **bit**, not a count: *did any production method run at all*.
So the observer arms a `MethodEntryRequest` filtered to declared production classes when a test
opens, and **switches it off the instant it fires**. A test that touches production code pays
exactly one event; a genuinely inert test pays none. Watching every method entry for a whole run
is what makes `MethodEntry` infamous — this is not that.

Without `production` the observer cannot tell *inspected the artifact* from *ran code we
were not watching*, and reports the weaker `ungrounded` rather than guessing.

## Mutation — do the tests actually check the code?

    plumb board --project . --mutation

A third step after the suite and the observer, because it needs what both produced: which tests
cited which story, and which methods ran with an entry point above them. It mutates that code, runs
**every test citing the story** against each mutant, and reports **killed out of total**.

    mutation: 4 mutants over 2 stories — at least 5s (1.1s compile+JVM floor, measured here)
      [1/2] APP-1: 2/2 killed
      [2/2] APP-5: 0/2 killed

Both tests drive the same entry point and both ground. `APP-5` asserts nothing about the answer, and
nothing but this notices. It stays PROVEN — the score is advisory and never a gate.

**Java's own parser, not a mutation engine.** `com.sun.source` is to Java what `ast` is to Python:
already installed, no PIT or Stryker to take a version on. Three operators — flip a comparison,
negate a branch, swap a return — applied as a one-span edit to the source rather than a re-print, so
the file on disk mid-run is the original with exactly one token changed.

**A returned value has to stay the type it was.** Python can return `None` from anything; here that
would not compile, and a mutant that will not compile has told you nothing about the test. The
declared return type is read off the tree — `boolean` negates, a numeric returns `(type)(expr + 1)`,
a reference returns `null` — and a mutant that fails to compile anyway is **skipped, not counted as
killed**, because scoring it would inflate every score by the number this tool got wrong.

**It costs more here than in Python**, and it is the same three operators doing the same work: a
mutant there is one test process, and here it is a `javac` *and* a JVM. Measured on the sample,
~1.1s before a single assertion runs. That does not change what mutation is worth — nothing else
finds a test that cannot fail — it changes when you can afford to ask, which is why the count and a
measured floor are printed before any of it runs.

**Entry points are suspended while mutation is on**, and only then. Grounding needs to know an entry
point was *reached*, so it pauses nothing; the wired scope needs the window open *before* the calls
inside it happen, and with `SUSPEND_NONE` the debuggee runs on while the event is still queued — so
the probe arms after the first callees have gone by, and the scope comes out as the entry point
alone. That was a real bug here, and its symptom was a plausible-looking smaller number.

## Where the two adapters genuinely differ

They are not interchangeable, and the manifest says which produced a fact (`dev07-3-1`), so a reader
can tell an instrumental difference from a real one:

- **Java is more precise on async.** It distinguishes `dispatched` from `ungrounded` by *seeing*
  the hand-off. The Python adapter has only a coarse "some other thread was alive" and must
  decline to use it, so it reports `ungrounded` where Java reports `dispatched`.
- **The two `inert`s rest on different evidence.** Python's comes from a per-thread call tree;
  Java's from a filtered method-entry probe over declared production classes. Same value, same
  meaning, different instruments — which is why the manifest names the instrument.

**A project that declares no entry points** is not observed at all: citations only, grounding
reads `not-checked` — honest rather than guessed, and still a usable board at `dev07-5-1`'s lowest
input level.
