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

If you have not installed it yet, that is one command: see the [README](../README.md).
If something surprises you along the way, [What to expect the first time](what-to-expect.md)
answers the common surprises.

---

## Step 1 — Configure

Run this in your project:

    plumb init

It writes one file, `plumb.toml`, and guesses what it can from your layout. Nothing else in your
project is touched.

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

**`sources`** — where that code's source files live. Only used by mutation, which is off by default.

**`entry_points`** — *this is the one that matters.* Leave it for Step 4; it is easier to
understand once you have seen the board complain about it.

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

    mvn -q test-compile dependency:build-classpath -Dmdep.outputFile=target/plumb-classpath.txt
    printf ':target/classes:target/test-classes' >> target/plumb-classpath.txt

The second line is not optional. `build-classpath` lists your *dependencies* and leaves out your own
compiled code, so without it Plumb finds no tests at all.

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
| `unit` | it exercised a piece in isolation |
| `component` | it exercised a few pieces together |
| `wiring` | it went through the real system, the way a request would |
| `standards-integration` | it crossed a boundary you do not own |
| `smoke` | it touched the deployed thing |

Claiming `wiring` when the test only called a function directly does **not** quietly downgrade to
`unit`. It fails the story. That is the point: the claim has to survive contact with what actually
ran.

Start with one citation. Not ten.

---

## Step 3 — Run the board

    plumb board

Plumb runs your test suite, watches what your production code actually does, and prints what it
found. The first run says something like:

    ══════ BOARD ══════
      PASSED-WIRING-NOT-VERIFIED   ORD-1  [wiring]

      1 stories  [grounding.not-checked]
           what · grounding did not run — no production entry points are declared
           next · declare where the wired system begins, to catch orphaned code
        example · in plumb.toml — Python:  entry_points = ["myapp.cli:main"]   ·  Java:  entry_points = ["com.acme.Api#handle"]

      passed-wiring-not-verified: 1
    ═══════════════════

This is not a failure. Your test passed. Plumb is telling you it could not *check* the part you
claimed, because you have not told it where your system begins yet.

Every message has the same three lines, and they are worth learning:

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
      PROVEN   ORD-1  [wiring]

      proven: 1
    ═══════════════════

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
      UNPROVEN                     ORD-2  [wiring]

      1 stories  [depth.unsupported]
           what · a citation claims it reached the wired system, and its execution never did
           next · lower the claimed depth to what the test actually reaches, or drive the story
                  through a declared entry point
        example · cite it at depth="unit" instead — a claim the execution supports

`ORD-2` claimed `wiring`, but the test called the function directly instead of going in through the
front door. Plumb watched, saw it never pass an entry point, and refused the claim.

You have two honest moves. They are not interchangeable, and the board's suggestion is only one of
them:

1. **Lower the claim.** Change `depth="wiring"` to `depth="unit"`. This makes the claim true, and
   the `depth.unsupported` message goes away. **It does not make the story proven.** A test that
   never enters through a declared entry point leaves the story UNPROVEN — and once the claim is
   honest the board has nothing left to say, so it goes quiet while the story stays unproven.
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
  test proving several stories, several tests proving one, and the two ways a citation silently
  does nothing.
- **Read the messages.** Every condition code has a `what`, a `next` and an `example`. They are the
  documentation for the situation you are actually in.
- **Leave mutation off** until the basics are steady. It is a deeper check and it is slow —
  [What to expect](what-to-expect.md#what-mutation-costs) has the numbers.
- **Surprised by something?** [What to expect the first time](what-to-expect.md) is a list of the
  things that surprise people, with the reason for each.
- **Running this suite all day?** [Time per story](time-per-story.md) measures what Plumb adds to a
  run, what governs it, and the three levers that bring it down.
