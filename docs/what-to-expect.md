---
kind: explanation
role: [programmer, engineer]
summary: Why Plumb reports less than you expect, and what each surprise means.
---

# What to expect the first time

**For programmers and engineers** whose board said something unexpected.

Plumb reports less than you expect at first, on purpose. Almost everything surprising about a
first run is the tool refusing to claim something it has not established. This page says what
each surprise is, so you can tell *working correctly* from *broken*.

The single rule underneath all of it: **Plumb runs at whatever input level you have, degrades,
and says what it could not do** (`dev07-5-1`). It never fails for missing input, and it never
quietly skips a check either.

---

## "My whole spec is green, but nothing is proven"

Correct, and it is the intended starting state.

A story declares only that it exists. Its status is *derived* from a test that cites it, and the
run is **green** before any citing test exists, because **skipped is not failed**. You are not in
debt on day one.

> **What the board is, and is not.** It is built from what you have **given** Plumb — your
> citations. So a story you have written down somewhere and not yet cited is **absent** from the
> board, not UNPROVEN: with two stories declared and none cited, `plumb board` prints an empty
> board and exits 0.
>
> **Plumb is not your backlog.** It is the done-ness check over the part of your backlog you have
> handed it. That is a boundary rather than a gap: your requirements live in your project, and the
> ones nobody has written down are exactly the ones no tool can find — a backlog guessed at would
> read authoritative while missing things, which is worse than not offering one. Chapter 10 states
> the boundary; `dev07-4-3` states the matching one about proof.
>
> The practical consequence on day one: an empty board means *you have cited nothing yet*, which is
> the correct answer and a green one.

The corollary matters more: a proof that later breaks **un-proves** its story. There is no
stored "done" to go stale, because there is no stored "done" at all.

## "Everything passes, but it says PASSED — WIRING NOT VERIFIED, not PROVEN"

This is the one that surprises everyone, and it is the tool being careful rather than the tool
being broken.

A passing test is not proof. A test can pass against code that nothing in your real system ever
calls — the orphaned-"done" fake, which is the specific lie Plumb exists to catch. To rule it
out, Plumb checks that your test's execution actually ran **under a declared production entry
point**: a CLI command, an HTTP route, a handler, a job.

Until you declare those entry points, that check has nothing to run against. So the grounding
fact is `not-checked` (`dev07-1-4`), and a story that ran and passed lands on the middle status
rather than the top one (`dev07-4-3`):

| what happened | status |
|---|---|
| no citing test, or it skipped or failed | **UNPROVEN** |
| ran and passed, no entry points declared | **PASSED — WIRING NOT VERIFIED** |
| ran and passed, and grounded under an entry point | **PROVEN** |

The board tells you exactly this, under the stable code `grounding.not-checked`:

    declare entry points to catch orphaned code

Declare them and the same tests start reading PROVEN, with no change to the tests themselves.
Nothing was wrong; you had reached a level and the tool said so instead of rounding up.

**Why not just call it proven?** Because then the first thing you would learn about Plumb is
that its top status is available for free — and everything after that is worth less.

Here is Plumb's own first board, run on itself with no entry points declared. Every story its
tests cite reads the middle status, and the run is green:

    ══════ BOARD ══════
      PASSED-WIRING-NOT-VERIFIED   dev07-3-1  [component · unit]
      PASSED-WIRING-NOT-VERIFIED   dev07-5-3  [unit]
      …

      36 stories  [grounding.not-checked]
        declare entry points to catch orphaned code
        "module.path:function", e.g. "myapp.cli:main"

      passed-wiring-not-verified: 36
    ═══════════════════

That is a working tool reporting honestly, not a tool with nothing built.

## "I declared entry points and most of my board went red"

Expected, and it is the single most useful thing Plumb will tell you.

Before you declared them, grounding could not run and everything that passed sat on the middle
status. Now the check is live, and it is asking a harder question than "did the test pass": did
this test's execution actually run **under** one of your entry points? A test that calls a
function directly never does, however green it is.

So the board splits your suite into two kinds of test you probably never distinguished:

- tests that drive the wired system, which now read **PROVEN**;
- tests that exercise a unit in isolation, which now read **UNPROVEN** — because a behavioral
  story is not proven by proving its parts (`dev07-4-2`).

Plumb's own board did exactly this the first time: **5 proven, 41 unproven**. The five were the
tests that go through its CLI. Everything else tests the library directly, and no amount of
passing changes what those tests did or did not reach.

**This is not a signal to add entry points until it goes green.** Widening the declared surface
until unit tests happen to land under it is how you turn the check off while appearing to pass
it, and it is the exact fake the whole tool exists to catch. The honest readings are: write a
test that drives the real path, accept that the story is not yet proven at depth, or conclude the
code really is unreachable — which is itself the finding.

Your achieved vector still shows the rungs you *did* reach, so unit-only reads as unit-only
rather than as nothing.

## "One story has five tests. Which one decides?"

All of them, in two different ways, and they do not fight.

**Status** is decided by the best citation: a story is proven as soon as **one** citing test passes
and grounds. A second test that passes but does not ground takes nothing away — it simply proves
less, and proving less is not evidence against.

**The achieved vector** is the union: every rung any passing citation reached. So a story with a unit
test and a wiring test reads `[unit · wiring]`, and one with three unit tests still reads `[unit]`.
Three tests at the same rung are three tests, not more depth.

The consequence worth internalising: **adding tests at a rung you already have moves nothing on the
board.** That is deliberate. The board answers "how deep is this proven", and the honest way to move
it is to prove it somewhere new.

## "Will this slow my test run down?"

Some. How much depends on something less obvious than the size of your codebase.

Tracing is scoped to each citing test's **body** — setup, teardown and collection are outside the
window. So the cost tracks **what your tests do**, not how much code you have. A test doing
arithmetic costs almost nothing to trace. A test that spawns a subprocess, starts a server, or runs a
nested test session puts all of that work inside a traced window, and it costs accordingly.

For scale: on this project — about 1,700 lines — the whole board takes a few seconds, and tracing
adds roughly double the untraced run. **Do not read that as a promise.** It is one codebase, measured
by the authors of both it and the tracer, and it is recorded as an open question (`dev07-1-3`)
rather than a claim precisely because one measurement is not a property. If your suite is shaped
differently, yours will be too.

If a particular test is pathologically slow under the board and fast without it, that is worth
reporting — it is the measurement the open question is waiting for.

## "A test that runs nothing can still prove something"

Most stories are **behavioral** — they claim the system *does* something, so proving one means
running it, and the gate demands grounding. Some stories are not like that. "No module in the
storage layer imports the web layer" is a claim about **shape**, and the way you check it is to read
the artifact rather than run it: parse the source, walk the imports, inspect the bytecode.

Declare those `structural` in your `plumb.toml`, keyed by the id your tests cite:

    [archetypes]
    "dev07-4-3" = "structural"

Silence means behavioral, so you only name the exceptions, and an entry for an id nothing cites is
simply inert. It lives here rather than in your spec because Plumb reads no spec — that is what
lets the same declaration work whether your suite is pytest, JUnit or anything after them.

The gate then asks the **mirror** question. A behavioral story must be **grounded**; a structural one
must be **inert** — its call tree holds no production frames at all, because it read the artifact
instead of invoking it.

Two things follow, and both are deliberate:

- **Structural is not an exemption from grounding.** It is a different positive check over the same
  fact. A test declared structural whose execution *did* run your production code **fails** — it was
  not inspecting a shape.
- **Mis-declaring costs you.** A story declared structural can never be proved by executing anything,
  so stamping `structural` on a behavioral story does not buy a free pass; it forfeits the behavioral
  proof instead. That asymmetry is why the declaration lives in your config rather than on the test —
  the thing being judged does not get to pick its own gate.

If a structural test surprises you by reading `ungrounded`, the usual cause is that it *imported and
called* something rather than reading it. Read the file; don't invoke the module.

## "The board is suggesting things. Is it selling me something?"

No — and you can check, which is the point.

Alongside status, the board emits **unlocks**: what this run has earned the right to suggest, with
the count that earned it. *"21 stories passed but their wiring was never checked — declare entry
points and those get gated on real wiring."* That number came out of your run. With nothing to
improve, the board says nothing.

Every unlock and every gap carries a **stable code** — `unlock.grounding`, `grounding.not-checked` —
and the full set is finite and enumerable. So what the board can ever say to you is a list you can
read in advance, not an open-ended channel. Branch on the codes; the prose beside them may be
reworded.

The board also carries its **evidence**: per story, which test cited it, at what depth, what its
grounding fact was, and — where mutation was turned on — whether the citing test noticed the code
being broken. You are never asked to take a verdict on trust — the reasoning is in the output, and
if you disagree with a status you can see exactly which citation produced it.

## What mutation costs

Mutation is the check that asks whether your tests would *notice* the code being broken. Grounding
proves the code ran; this is the only thing that looks at whether anything was checked. It earns its
place: it finds tests that cannot fail and code no test reaches, in work a fully green suite has
already signed off.

It is also slow, and the shape of the cost is worth understanding before you start one.

**One mutant costs one test run.** A mutant is a one-line change to your code — a comparison
flipped, a branch negated, a return swapped — and the only way to find out whether your tests notice
is to run them against it. Plumb runs only the tests citing *that story*, not your whole suite,
which is the single thing that makes this affordable at all. Even so, starting a test process is
~0.3s before a single assertion runs, and that floor is paid by every mutant.

**The mutant count scales with the code your tests drive, not with how many tests you have.** One
end-to-end test through a real entry point drives most of your system, and every function it touches
is mutable. Measured on Plumb itself — a small project, ~5000 lines, 169 tests:

| | |
|---|---|
| the suite, mutation off | ~11 seconds |
| stories with wired tests | 32 |
| mutants generated | **3263** |
| one full pass | **45 minutes — 177× the suite** |

Scale that honestly, and scale it by the *slow* factor. Plumb's citing tests run in fractions of a
second; if yours take seconds — anything touching a database, a browser, a container — the same
mutant count costs an order of magnitude more. A real codebase with real integration tests is
**hours, and can be days**. Measured on a ~2,000-test JVM suite: 308 mutants, **~30 seconds each,
2h34m** for the pass. Same tool, same deduplication, a hundredfold the per-mutant cost — because a
mutant costs one run of the citing tests, and a test that boots an application context and a
database pays that on every mutant. Mutation is priced in test runs; your suite sets the exchange rate. Nothing about running it overnight is unusual, and nothing about it
belongs in a pre-commit hook.

**So the question is when, not whether:**

- **A story or two at a desk** — you have just written or changed something and want to know whether
  the test you wrote actually pins it down. Seconds to minutes. This is the common case, and it is
  the one that catches things.
- **A nightly or weekend pass** over everything, read as a report the next morning.
- **Never in the inner loop**, and never as a build gate. It cannot fail your build even if you want
  it to — see below.

`plumb board --mutation` prints what it is about to do before it does it — the mutant count and a
floor on the time, measured on your machine — so you can stop and pick a narrower target. Pass a path
to limit it: `plumb board --mutation tests/test_orders.py`.

## "A story says 3/40. Is that bad?"

Probably not, and this is why the result is a score rather than a pass/fail.

Your tests run far more code than they check. A test that drives an entry point and asserts one thing
about the answer has *executed* every function on the way there — and it was never trying to check
all of them. If the result were a word, almost every honest story in every honest project would read
"survived", which tells you nothing about where to look.

So read it as a proportion, and compare stories against each other:

- **0 of 40** — nothing citing this story checks anything about it. Worth opening: it is often a test
  that calls the code and asserts nothing, or asserts something that cannot fail.
- **Somewhere in the middle** — normal, and it is where nearly everything lands. Every one of
  Plumb's own 32 scored stories came back strictly between zero and full marks, 53% overall. A
  pass/fail answer would have printed the same word for all 32 and told you nothing about which
  one to open.
- **A story you believed was thoroughly tested scoring low** — that is the signal. The gap between
  what you expected and what came back is the whole value of the number.

**It never changes a status, and it never fails a build.** A mutant that survives may mean a weak
test, or it may be *equivalent* — a change that does not alter behaviour at all, which no test could
possibly catch. Telling those apart is undecidable, so a low score is a place to look and never a
verdict. Plumb will not enforce a heuristic; that is the failure mode it exists to prevent.

## "My tests aren't in Python. Is that a problem?"

Not for the part that decides anything, and not for how you run it either.

**One command, one config file, whatever language your artifact is in.**

    plumb board              # Python project
    plumb board              # Java project — the same command

`plumb.toml` sits at the root of your project and is the only thing you write:

    adapter      = "java"
    entry_points = ["com.myapp.Api#handleRequest"]
    production   = ["com.myapp.*"]
    sources      = ["src/main/java"]

    [java]
    tests          = "target/test-classes"
    classpath_file = "target/plumb-classpath.txt"

The **values** stay in your language's own spelling — `Class#method` in Java, `module:function` in
Python — because one invented notation would mean every adapter translating out of a form nobody
writes. The **file** is shared, and the **core reads it**: your adapter is handed values already
decided and never learns a config format at all. That is what stops the two languages drifting into
two tools.

### Getting it

    curl -fsSL https://plumbspec.org/install.sh | sh
    plumb board

One file. Plumb ships as a **zipapp** — Python's own single-file format, which is only viable
because the core has no dependencies. The Java adapter's jar rides inside it, so one download
covers both languages and you never compile an adapter or clone this repository.

No package index, no account, nothing added to your project's dependencies. The installer verifies
a checksum every time and a signature when it can, and **tells you which it did** —
[SECURITY.md](../SECURITY.md) states exactly what each one is worth, including what neither of them
covers. `PLUMB_REQUIRE_SIGNATURE=1` refuses to install without a verified signature and
`PLUMB_NO_SIGNATURE=1` installs without checking one;
`PLUMB_VERSION=0.5.0` pins one.

Two consequences worth knowing before you adopt:

- **Plumb runs on Python 3.9+, even when your project is Java.** It needs *a* Python 3.9 or
  newer somewhere on the machine, not in your project — which RHEL 9 and Ubuntu 22.04 both ship
  as `python3` already, and nothing about your build changes.
- **For a Python project, the adapter runs in *your* interpreter, not Plumb's** — which is why
  the two floors are the same **3.9**, and why there is one interpreter to install rather than two.
  The adapter has to import your code and your test framework. Plumb finds your virtualenv (`.venv`, `venv`, or an active
  one) and runs the adapter there, adding itself to `PYTHONPATH` — nothing is installed into your
  environment. If your interpreter lives somewhere unusual, name it:

      [python]
      interpreter = ".tox/py311/bin/python"

## "Is the manifest still the only thing the core reads?"

Yes, and that is what makes the above true rather than merely tidy. The launcher picks an adapter;
the gate never learns which one ran. You can prove it yourself — run the adapter once, keep the
manifest, and derive from it later:

    plumb board --emit-manifest run.json
    plumb board --manifest run.json     # the same board, from the file alone

Plumb is a **core** plus **adapters**. The core reads exactly one thing — a JSON document called
the manifest — and derives every status from it. The adapter is the only piece that knows what a
test framework is, and its whole job is to produce that document. So the core has no opinion about
your language, and never sees it.

Two adapters ship today — Python/pytest, and Java/JUnit under `adapters/java/`. But you do not have to wait for one in your language to
find out whether any of this is useful:

    plumb board --manifest your.json

That path never touches a runner. Write the document by hand, or emit it from a twenty-line script
in whatever you already use, and you get a real board — same gate, same statuses, same conditions.
`docs/adapter-contract.md` has the schema and the notes the field names do not carry.

Going the other way, `plumb board --emit-manifest out.json` shows exactly what the Python adapter
produces for a real run, which is the reference to compare yours against.

If Plumb refuses your document it will say what is wrong and what it supports, by name — a wrong
field, a missing one, a version it cannot read. That is deliberate: the person reading those
messages cannot see Plumb's source, so a refusal that does not name the problem is a dead end.
`docs/adapter-contract.md` has the rules those refusals enforce.

The hard part of a full adapter is not the document. It is the **per-test trace** that answers
whether execution reached a declared entry point — that is language-specific and genuinely
difficult. Everything else is reading annotations and normalizing a runner's own pass/skip/fail.

## "My structural test cites a story and it stubbornly reads UNPROVEN"

Almost certainly you cited a **behavioral** story from an **inert** test.

One execution produces exactly one grounding fact. An inert test — one that read your artifact
instead of running it — proves structural stories and *cannot* prove behavioral ones, because a
behavioral story requires the execution to have grounded. The reverse holds too: a grounded test
cannot prove a structural story.

So the rule is sharper than it first looks:

> **An inert test may only cite structural stories. A grounded test may only cite behavioral ones.**

That bites at a predictable moment. You write a rule that inspects your package boundaries, and it
plainly evidences a story about the architecture being language-blind — so you cite that story too,
and it goes UNPROVEN with no explanation. The fix is not to change the test; it is to prove that
other story the way its own claim demands, by actually running the thing.

Annoying once, and right: it forces the two kinds of evidence apart instead of letting one test
claim both.

## "I filed a friction record and it said *queued*, not *sent*"

That is usually correct, and occasionally it is the tool telling you something.

**Local by default.** An installation nobody enrolled keeps every record it makes on your own
disk and never transmits. Nothing is gathered from the general public, so if you have not enrolled
you will see `local only` — the record is filed, and that is the end of it.

If you *are* enrolled, three outcomes are possible and they mean different things:

| | what happened | what to do |
|---|---|---|
| `sent` | it arrived | nothing |
| `queued` | it has not arrived **yet** — unreachable, or the support service does not speak your record version | nothing; `plumb friction send` drains it later |
| `REFUSED` | the holder read it and would not take the content | look at it; it stays in your outbox |

The distinction between the middle and last rows is the one worth knowing. A holder running
older code than your client is a **temporary** condition — your record is kept and delivers itself
once that holder is upgraded. Only a refusal the holder positively identifies as *bad content*
is treated as final, and even then the record stays in your outbox, because removing one is
something you do deliberately and never something a failed send does on your behalf.

Filing never blocks your work and never fails your run, whichever of these happens.

## "Does Plumb want me to work test-first?"

It does not require it, and it cannot: the core enforces proof and never workflow (`dev07-4-3`). Nothing
in the tool checks when you wrote anything, and no status moves because of the order you worked in.

But it is worth saying plainly that **the loop works better test-first**, for a specific reason
rather than as a matter of taste.

Plumb binds a test to a story by **id**. That is deliberate — it means there is no second list to
keep in sync — and it has a consequence: if you rewrite what a story *claims*, its existing tests
keep passing, because they still assert what they always asserted. Nothing goes red. The story reads
proven for a claim nobody has tested (`dev07-4-3`, and `dev07-4-3` is the mechanism meant to catch it).

Working test-first closes that by hand, and cheaply:

1. the claim changes
2. you go to the tests citing it and change them **first**
3. they go red — the story un-proves itself, which is `dev07-4-3` doing exactly its job
4. you make the code true again

The board is honest at every step, including the middle where it says the story is no longer proven.
That is the state you actually want to be visible.

**Where this stops.** It only works if you notice the claim changed. It surfaces the problem for
people already following the practice; it does not detect it for anyone else. So treat it as a habit
the tool rewards rather than a guarantee it provides — the difference matters, and a tool that
implied otherwise would be claiming a check it does not run.

## "So what does PROVEN actually mean?"

Precisely this: **somebody wrote a test for this story, it ran, it passed, and its execution reached
the artifact the way the story's archetype says it should.**

It does **not** mean the test's assertions are the right ones, or that they correspond to what the
story says. Reading a claim and judging whether an assertion answers it is comprehension, and Plumb
does not do it — that is a boundary, not a missing feature (`dev07-4-3`).

Which is worth being blunt about, because the gap between those two readings is where a verification
tool would be most tempted to overclaim. What you get is *"this is really wired, and somebody really
tested it"*. What you still need a person for is *"and the test asks the right question"*.

## "Can I compare two boards?"

Only if the same kind of instrument produced them, and the board tells you which ones did — plural,
because one board can now carry facts from more than one adapter:

    "observers": [
      {
        "adapter":   "plumb-java",
        "version":   "0.1.0",
        "runtime":   "OpenJDK 64-Bit Server VM 25.0.3",
        "mechanism": "bytecode probes, in process (production surface and entry points)"
      }
    ]

Each *fact* carries its own instrument, and this list is the distinct set of them. So a board mixing
a JVM observer with a CPython tracer is readable rather than quietly incomparable — the two report
`dispatched` on different evidence, and now you can see which said what.

**`mechanism` is the field that matters**, more than the runtime. A grounding fact is a claim about
what was *observed*, so it is only as strong as the thing doing the observing — and two observers
can produce the same word from genuinely different evidence. Today's two adapters do exactly that:

- Python watches the calling thread, so its `inert` rests on a per-thread call tree. It *does*
  report `dispatched` — in place of `inert`, where it cannot account for every thread — but never
  in place of `ungrounded`, because all it can tell there is that *some* other thread was alive,
  and withholding on that would cost the orphan check its teeth.
- The JVM adapter weaves a probe into the production code itself, so its `dispatched` reports that
  an entry point was actually *reached* on another thread — a stronger fact than watching work
  depart and assuming it arrived. Where the arrival lands after the test that sent it has finished,
  it falls back to having seen the hand-off, which is what remains knowable.

Same values, same meanings, different grounds. Neither is wrong; they are not interchangeable.

**This field is also how you compare boards across a Plumb upgrade.** The JVM adapter's mechanism
changed from `JDWP breakpoints …` to `bytecode probes, in process …`, and boards made either side
of that carry the string that made them. A story whose grounding moved across that line has not
necessarily changed: read the mechanism first.

The practical readings:

- **Same adapter, same mechanism** — compare freely. Two runs, one project, one instrument.
- **Different mechanism** — read them side by side, not merged. A story `ungrounded` under one and
  `dispatched` under the other has not changed; you learned something about the observer.
- **`"observers": []`** — nothing reported an instrument. That is *not reported*, and Plumb will
  not guess it from whatever you happen to be running.

If you are wondering whether a difference between two boards is real or instrumental, this is the
field that answers it.

## "Why is there both a manifest and a board?"

The **manifest** is internal: the language-neutral record your adapter produces from a test run,
and the only thing the core reads (`dev07-3-3`). The **board** is the public contract — the derived
result, versioned, that other tools consume (`dev07-5-1`, `dev07-5-3`).

The split is what makes a new language a new adapter and nothing else. It also means the board's
shape is a promise to you, while the manifest's is ours to change.

## "Nothing I write sets a status"

Nothing can. There is no `done()`, no `mvp()`, no `realized_by()` — status is computed on every
run and never authored, which is the whole design rather than an omission.

What you *do* author is small: the story, a `proves` marker on the test that proves it, and
eventually your entry points. Everything else — the manifest, grounding, status, the board — is
derived from a run.
