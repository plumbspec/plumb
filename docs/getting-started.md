---
kind: tutorial
role: [programmer, devops]
summary: Configuration to your first proven story, one step at a time.
---

# Getting started

**For programmers and DevOps** setting Plumb up on a real project for the first time.

You have installed Plumb. This walks you from there to your first proven story.

Four steps:

1. **Configure** — tell Plumb where your code is
2. **Cite** — mark one test with the requirement it proves
3. **Run the board** — see what Plumb makes of it
4. **Read what it says** — and do the one thing it asks

If you have not installed it yet, that is one command: see [Installing Plumb](installing.md).
If something surprises you along the way, [What to expect the first time](what-to-expect.md)
answers the common surprises.

---

## Step 1 — Configure

Run this in your project:

    plumb init

It writes one file, `plumb.toml`, and guesses what it can from your layout. Nothing else in your
project is touched. It asks you nothing: it ends by printing what is still to do — on a fresh project,
that `entry_points` is empty — and how to cite a first story.

**Read what it guessed.** The guesses are usually close and occasionally wrong, and a wrong guess
is much easier to fix now than to debug later.

### If your project is Python

    adapter      = "python"
    production   = ["src/orders"]      # your code, not your tests
    sources      = ["src/orders"]
    entry_points = []                  # you fill this in
    mutation     = false

### If your project is Java

    adapter      = "java"
    production   = ["com.acme.orders.*"]   # a package pattern, not a path
    sources      = ["src/main/java"]
    entry_points = []
    mutation     = false

    [java]
    classpath_file = "target/plumb-classpath.txt"
    tests          = "target/test-classes"

### What each setting means

**`production`** — the code you are trying to prove. Not your tests, not your libraries.

Get this one right. Plumb watches this code while your tests run, and if the pattern is too wide it
watches everything, which is slow and produces confusing answers. On Java it is a **package
pattern**, and Maven puts tests in the same package tree as the code they test — so
`com.acme.orders.*` will also match `com.acme.orders.OrdersTest`. Plumb knows to skip test classes,
but keep the pattern as narrow as the truth allows.

**`sources`** — where that code's source files live. Only Java mutation reads it, and mutation is
off by default.

**`entry_points`** — *this is the one that matters.* `plumb init` leaves it empty and names it among
what is still to do; if you already know where requests enter your system you can fill it in now. This page leaves it empty until
Step 4, because it is easier to understand once you have seen what the board says without it.

`init` does not write `specs`, the list of your story-id prefixes; it is optional, and
[Configuration](configuration.md) has it with every other key.

### Python: make your code importable the way your tests import it

Plumb runs your suite under pytest, in your interpreter, so **it imports what pytest imports** —
your code is found the way your tests find it. Get plain `pytest` green first; a suite pytest cannot
collect gives Plumb no board either. For a `src` layout that usually means telling pytest where the
package lives, in `pytest.ini` (or the `[tool.pytest.ini_options]` table of `pyproject.toml`):

    [pytest]
    pythonpath = src

— or an editable install (`pip install -e .`). Name entry points by the same module name your tests
import (`orders.api:handle`, not `src.orders.api:handle`). Plumb also puts the parent of each
`production` package on the path for its own run, so it can collect a suite plain `pytest` cannot;
if the two disagree, that is the difference to look at.

### One extra step for Java

Java needs two things Python does not.

**The annotation, so your test compiles.** Add it to the module that holds your tests:

    <dependency>
      <groupId>org.plumbspec</groupId>
      <artifactId>plumb-annotations</artifactId>
      <version>0.2.0</version>
      <scope>test</scope>
    </dependency>

It is the citation vocabulary and nothing else — `@Proves` for a story, `@Informs` for a decision or
a parameter — with no dependencies of its own, so nothing it carries lands on your compile path.

**A classpath file, so Plumb can run your tests.** Your build already knows your classpath; Plumb
needs it written down:

**With Maven:**

    mvn -q test-compile dependency:build-classpath -Dmdep.outputFile=target/plumb-deps.txt
    { printf '%s:' 'target/test-classes:target/classes'; cat target/plumb-deps.txt; } \
        > target/plumb-classpath.txt

The second line is not optional. `build-classpath` lists your *dependencies* and leaves out your own
compiled code, so without it Plumb finds no tests at all.

**Test outputs first, then main outputs, then the dependencies — Surefire's own order**, which is
why this line prepends rather than appends. Maven copies `src/test/resources` into
`target/test-classes` and `src/main/resources` into `target/classes`, so a project holding
`application.properties` in both loads whichever comes first. Put main ahead of test and the run
Plumb observes silently uses your production configuration — a different run from the one your
build performs, reported as your tests failing. Plumb refuses a classpath in that order and prints
this same line back to you, built from the directories your project actually writes.

**If your build has more than one module, append every module's output, not just this one's.**
`build-classpath` resolves a sibling module to whatever is installed in `~/.m2`; your build uses the
classes it has just compiled. Those are different bytes whenever the sibling has changed and has not
been installed, which is the ordinary state of a working tree — and it is how a resource your build
resolves stops existing for the run Plumb observes.

**With Gradle**, don't rebuild the classpath — hand over the one Gradle already runs tests on:

    // build.gradle
    tasks.register('plumbClasspath') {
        doLast { file('build/plumb-classpath.txt').text = sourceSets.test.runtimeClasspath.asPath }
    }

    gradle test plumbClasspath

`sourceSets.test.runtimeClasspath` **is** what Gradle's own `test` task uses, so nothing assembled
by hand can be short of it — which matters most for resources. Gradle keeps `build/resources/main`
and `build/resources/test` *out* of the compiled-class directories rather than copying them in
beside the code, so a classpath listing only `build/classes/java/*` silently loses every migration,
fixture and property file your suite loads. That is the default outcome on a conventional project,
not an edge case.

**Either way, Plumb checks before it launches anything** and **refuses** rather than observing a run
your build does not perform; the refusal names each directory that is missing. A divergence would
otherwise arrive as a test that fails under Plumb and passes under your build — which reads as a
defect in your code and is not one. Turn the check off with `check_classpath = false` under `[java]`
if it is wrong for your project.

If Plumb later says it cannot find `TestExecutionListener`, add
`org.junit.platform:junit-platform-launcher` as a test dependency. Maven's Surefire supplies that
internally, so a normal project never declares it — and it is missing from the classpath file for
exactly that reason.

---

## Step 2 — Cite one test

Pick a test that already passes and already exercises something real. Mark it with the requirement
it proves.

**Python:**

    import pytest

    @pytest.mark.proves("ORD-1", depth="wiring")
    def test_an_order_gets_a_queue():
        assert main("A-1")["queue"] == "standard"

**Java:**

    import org.plumbspec.Proves;

    @Test
    @Proves(value = "ORD-1", depth = "wiring")
    void anOrderGetsAQueue() { ... }

### The id is yours

`ORD-1` is whatever your team already calls that requirement — a ticket number, a spreadsheet row,
a chapter in a document. Plumb never invents ids and keeps no list of them. If your tracker calls it
`JIRA-4417`, use that.

### `depth` is a claim, and the run either backs it up or does not

`depth` says how far the test reached:

| depth | means |
|---|---|
| `unit` | one unit's input and output, in isolation |
| `component` | how the unit behaves — its branches, loops and error paths — with its collaborators doubled |
| `wiring` | the code is actually integrated: the test came in through an entry point, the way a request would |
| `standards-integration` | it works against a **real** resource — a real database, broker or filesystem, embedded and fresh — through a standard interface |
| `smoke`, `smoke/e2e` or `e2e` | everything real: the assembled artifact, end to end |

`wiring` and everything below it in this table are **wired** rungs — the run checks the test really
went through an entry point. `unit` and `component` claim isolation, which no trace can refute, so
they are taken at your word. [Testing depth](testing-depth.md) has the full ladder.

Claiming `wiring` when the test only called a function directly does **not** quietly downgrade to
`unit`. The story stays UNPROVEN and the board says why. That is the point: the claim has to survive
contact with what actually ran.

Start with one citation. Not ten.

---

## Step 3 — Run the board

    plumb board

Plumb runs your test suite, watches what your production code actually does, and prints what it
found. On a Python project its first line says which Python is running your tests — `python: /path/to/python`. That is
the `[python] interpreter` you declared, else an active virtualenv, else `.venv` or `venv` in your
project, else the Python running Plumb; if it is the wrong one, declare it. Then your runner's own
output, then the board:

    ══════ BOARD ══════
      PASSED-WIRING-NOT-VERIFIED   ORD-1  [wiring]

      1 story  [grounding.not-checked]  ORD-1
           what · grounding did not run — no production entry points are declared
           next · declare where the wired system begins, to catch orphaned code
        example · in plumb.toml — Python:  entry_points = ["myapp.cli:main"]   ·  Java:  entry_points = ["com.acme.Api#handle"]

      unlock  [unlock.grounding]
           what · 1 stories passed but their wiring was never checked
           next · declare production entry points, and those stories get gated on real wiring

      passed-wiring-not-verified: 1
      answering for the 1 subject(s) this run's tests cited, and nothing else — …
    ═══════════════════

This is not a failure. Your test passed. Plumb is telling you it could not *check* the part you
claimed, because you have not told it where your system begins yet.

Each condition is printed once, with the stories it is about after its code, and has the same three
lines. They are worth learning:

- **what** — what Plumb found
- **next** — the one thing to do about it
- **example** — that thing, written out

---

## Step 4 — From PASSED to PROVEN

Fill in `entry_points`. These are the few places a real request enters your system — a CLI command,
an HTTP handler, a queue consumer. Not every public method. The handful of front doors.

**Python** uses `module:function`:

    entry_points = ["orders.cli:main"]

**Java** uses `Class#method`:

    entry_points = ["com.acme.orders.Api#handleRequest"]

Run `plumb board` again:

    ══════ BOARD ══════
      PROVEN                       ORD-1  [wiring]

      unlock  [unlock.mutation]
           what · 1 stories are proven, and nothing has checked that their tests assert anything
           next · run mutation over them to find a test that runs the code without checking it

      proven: 1
      answering for the 1 subject(s) this run's tests cited, and nothing else — …
    ═══════════════════

An `unlock` is the board pointing at the next check you could turn on. It is never a failure.

That is a proven story. It means: a test cited it, that test passed, and the test's execution went
**through** a declared entry point into your real code. Not a comment, not a checkbox — something
ran.

---

## When a story says UNPROVEN

UNPROVEN is not an error and not a failure. It means *not proven yet*. A fresh project is entirely
UNPROVEN, and that is the correct starting state.

Three things have to be true, and missing any one of them leaves the story unproven:

![What makes a story PROVEN](proven.svg)

The usual first cause looks like this:

    ══════ BOARD ══════
      PROVEN                       ORD-1  [wiring]
      UNPROVEN                     ORD-2

      1 story  [depth.unsupported]  ORD-2
           what · a citation claims it reached the wired system, and its execution never did
           next · drive the story through a declared entry point, which is what a wired claim needs
                  to hold — or lower the claimed depth, which ends this complaint and moves the
                  verdict no further on its own
        example · at depth="unit" the claim is one the execution supports; the status stays
                  whatever the grounding already earned, and the board says why separately

      1 story  [grounding.not-wired]  ORD-2
           what · the citations that passed reached nothing wired — what ran was the implementation
                  on its own, which is not evidence the story holds where it is used
           next · drive it through a declared entry point, or leave it at the depth it reaches and
                  let the board say so
        example · a test calling the class directly proves the class; the story is about the system
                  that calls it

`ORD-2` claimed `wiring`, but the test called the function directly instead of going in through the
front door. Plumb watched, saw it never pass an entry point, and refused the claim — which is why
`ORD-2` has no bracket. **The bracket lists the depths claimed by citations that passed and that the
run did not refute**; a refuted `wiring` is not one of them.

(The board prints each line unwrapped; it is wrapped here to fit the page.)

You have two honest moves. They are not interchangeable:

1. **Lower the claim.** Change `depth="wiring"` to `depth="unit"`. This makes the claim true, and
   the `depth.unsupported` message goes away; the row now reads `UNPROVEN  ORD-2  [unit]`. **It does
   not make the story proven.** A test that never enters through a declared entry point leaves the
   story UNPROVEN, and `grounding.not-wired` stays on the board to say so.
2. **Raise the test.** Rewrite it to go in through an entry point, so it really does exercise the
   wired system. **This is the only one of the two that reaches PROVEN.**

Use (1) when the story genuinely is a unit-level claim and you want the board to stop carrying a
claim the run refutes. Use (2) when you want the story proven.

**Lowering a depth never manufactures proof.** Nothing does — which is the entire point.

**There is no third option.** Nothing you can write marks a story proven. No flag, no config, no
comment. That is deliberate: if a status could be typed, it would be, and the whole point is that it
cannot.

---

## What next

- **Cite a second test.** The loop is the same, and it is one line.
- **Learn what else a citation can say.** [Writing a citation](writing-a-citation.md) covers one
  test proving several stories, several tests proving one, and the mistakes that pass silently.
- **Put it in CI.** [Integrating with your tooling](integrating-with-your-tooling.md#2-run-it-in-ci-and-gate-on-the-right-thing)
  is the whole recipe.
- **Read the messages.** Every condition code has a `what`, a `next` and an `example`. They are the
  documentation for the situation you are actually in.
- **Leave mutation off** until the basics are steady. It is a deeper check and it is slow —
  [What to expect](what-to-expect.md#what-mutation-costs) has the numbers.
- **Surprised by something?** [What to expect the first time](what-to-expect.md) is a list of the
  things that surprise people, with the reason for each.
- **Running this suite all day?** [Time per story](time-per-story.md) measures what Plumb adds to a
  run, what governs it, and the three levers that bring it down.
