# The Java adapter

A JUnit Platform run in, a manifest out (`dev07-3-3`). Nothing else — the core reads the manifest and
derives every status from it, so nothing here decides anything.

    mvn -f pom.xml package              # compile, write the classpath, and jar the adapter
    plumb board --project .             # one command, same as any Python project
    plumb board --project . --mutation  # …and the same flag

**One command.** Loading the agent, handing it the declared entry points and then mutating are all
the launcher's job, read from the same `plumb.toml` a Python project uses. There is no script to run
first and no second configuration format.

The build only compiles. Plumb does not build your project; your build tool does, and it writes a
classpath the same way (`mvn dependency:build-classpath`).

**The suite JVM would outlive its own run.** `sample/App.java` holds a non-daemon `ExecutorService`,
so that process would not exit on its own when the last test finishes — real suites do this
constantly. The runner ends the JVM itself once the manifest is written, which is why the command
returns.

The `adapter` module also produces `build/plumb-java.jar` — the shippable half, everything the
adapter owns and nothing of the sample — and `build/plumb-boot.jar`, the probe alone, which the
agent puts on the bootstrap class path so that JDK classes can call it. That jar is what rides inside the artifact, so an adopter never
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
  `@Informs` is its counterpart for a decision or a parameter.
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
classes as they load; the listener writes the manifest. The production code reports its own
execution rather than being watched from outside, and only what the questions need is woven: a
one-store flag in each production method, a probe on each declared entry point (which test's
window it opened, and on which thread), the read primitives, and a short fixed list of dispatch
primitives.

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

**Production and test classes are told apart by where they were loaded from**, not by their
package: Maven puts `com.myapp.FooTest` in the same package tree as `com.myapp.Foo`, and the agent
excludes everything loaded from a declared test root. A production class compiled under a test root
is therefore never instrumented — and if nothing at all was, the board says so
(`observation.failed`) rather than reporting grounding it never observed.

**Following a hand-off.** Two dispatch primitives are instrumented — `Thread.start` and
`ThreadPoolExecutor.execute` — so a test whose work reaches an entry point on another thread reads
`dispatched` rather than `ungrounded`. A pooled task is wrapped so it carries the test's window to
whichever thread runs it.

## Every grounding value, including `inert` and `untouched`

Each test closes with one of: `grounded` (the test's own thread reached a declared entry point),
`dispatched` (another thread did, or work was handed off and had not arrived when the test ended),
`ungrounded` (production code ran, but not through an entry point), `inert`, `untouched`, or
`not-checked`.

`inert` is a positive claim — *the test read the production artifact and ran none of it* — and it
needs two facts:

- **Did any production method run at all?** A bit, not a count. Every instrumented production
  method sets one volatile flag, read and cleared around each test, so a test that touches
  production code pays a single store and an inert one pays nothing.
- **Was the artifact read?** The agent instruments `ClassLoader.getResourceAsStream` and
  `java.nio.file.Files` — the primitives IO libraries funnel through — and records a read whose name
  matches the declared `production` classes or packages.

Ran nothing and read it is `inert`. Ran nothing and read nothing is `untouched`, which proves nothing
and says so. Without `production` the adapter cannot tell the two apart and reports the weaker
`ungrounded`. Where the agent instrumented nothing at all, every value but `grounded` and
`dispatched` becomes `not-checked`, because it was read from an absence there was nothing to observe
with.

## Mutation — do the tests actually check the code?

    plumb board --project . --mutation

A step after the suite, because it needs what the suite produced: which tests cited which story, and
which methods ran with an entry point above them. It needs at least one declared entry point and a
single `tests` root, and refuses by name otherwise. It mutates that code, runs **every test citing
the story** against each mutant, and reports **killed out of total**. Each distinct mutant is
compiled and run once, however many stories scope it, and each story is judged by its own citing
tests.

    mutation: 4 mutants over 2 stories, 4 distinct — at least 4s (1.1s compile+JVM floor, measured here), plus the tests themselves
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

**The scope comes from the same agent.** While mutating, the agent also names each production
method that runs inside an entry point's window, so the code a story is mutated over is the code its
tests actually drove through the wired system — never the whole call tree.

**Interrupted runs are repaired.** Before each edit the original source is parked in
`.plumb-mutation-rescue`; the next board puts it back before its tests run, mutating or not. Once a
mutant has run, the original is restored and recompiled, so the class files match the source again.

## Where the two adapters genuinely differ

They are not interchangeable, and the manifest says which produced a fact (`dev07-3-1`), so a reader
can tell an instrumental difference from a real one:

- **Java is more precise on async.** It distinguishes `dispatched` from `ungrounded` by *seeing*
  the hand-off through the instrumented dispatch primitives. The Python adapter's evidence that work
  escaped is coarse — "some other thread was alive" — so it uses it only to withhold `inert`, and a
  test that runs some code locally and hands its entry-point work to another thread reads
  `ungrounded` there where Java reports `dispatched`.
- **The two `inert`s rest on different evidence.** Python's comes from its tracer and an audit hook
  on reads; Java's from a flag set by woven production methods and instrumented read primitives.
  Same value, same meaning, different instruments — which is why the manifest names the instrument.

**A project that declares no entry points** is not observed at all: citations only, grounding
reads `not-checked` — honest rather than guessed, and still a usable board at `dev07-5-1`'s lowest
input level.
