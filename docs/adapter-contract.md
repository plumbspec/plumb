---
kind: reference
role: [programmer]
summary: What a language adapter must produce for the core to read it.
---

# The adapter contract

**For programmers writing a language adapter.** Not needed to use Plumb.

An adapter binds one language's test toolchain to `plumb`'s language-neutral core. Its twin,
[the module contract](module-contract.md), governs the other seam — what consumes the core's
derived surfaces.

An adapter binds one language's test toolchain to `plumb`'s language-neutral core. It exists to
produce **the manifest** — nothing else. The core reads the manifest and runs the gates; it never
touches a test framework.

The seam is a package boundary, not a convention:

    src/plumb/core/              the manifest, the gate, the board — imports nothing else
    src/plumb/adapters/python/   the trace, the surface, grounding, the pytest plugin

`tests/test_core_is_policy_free.py` asserts it by inspection: no module under `core/` may import
anything outside `core/`, and the dependency runs one way only. A new language is a new directory
beside `python/` and no change under `core/` — if that ever stops being true, the check goes red
before anyone notices the seam has moved.

## The unifying observation (why this is tractable across languages)

Every gold-spec sibling encodes status the same way, in its own runner's native result:

| language | build tool / runner | "built" (realized) | "unproven" (specified, unbuilt) | story citation |
|---|---|---|---|---|
| Python | pytest | test **passes** | `pytest.skip("UNPROVEN[…]")` → **skipped** | `@pytest.mark.proves("dev07-4-2", depth="wiring")` |
| Java | JUnit | `@Test` **passes** | `Assumptions.abort("UNPROVEN[…]")` → **aborted** | `@Proves("dev07-4-2", depth="wiring")`, repeatable |
| C#/.NET | xUnit | `[Fact]` **passes** | `[Fact(Skip="UNPROVEN[…]")]` → **skipped** | tag in name / `Skip` reason |

So the **runner's own pass / skip(abort) / fail is already the status signal** in every language.
The core does not invent a status model; it *normalizes* the runner's result:

    passed        → realized (built)
    skipped/aborted → unproven (specified, not built)
    failed        → broken (a claimed-done story regressed — a red build)

Story ids stay **opaque strings** — `dev07-5-1`, `2P11`, whatever the project's scheme is. The core
never parses them; only the project's own spec and the adapter's extractor know the shape.

## What an adapter must provide

Six capabilities. Each is a pure function from a test run (or a static read) to manifest
data. An adapter is "done" (by Plumb's own gates) when each is proven against a real consumer.

1. **`collect_citations()` → [(test_id, story_id, depth, ref)]**
   Read the native citation mechanism (pytest mark, JUnit `@DisplayName`/annotation, xUnit
   attribute) and the declared **depth** (unit | component | wiring | standards-integration | smoke/e2e). Depth is a
   second tag alongside the story; a test with no declared depth is a hard error, not a default —
   an untagged test is an unplaceable one.

   The list is one entry **per (test, story) pair**, so a test citing several stories is already
   expressible — stacked markers, repeated annotations — with each story carrying its own depth
   rather than one smeared across all of them.

   **`ref` is optional and belongs to the consumer, not to Plumb** (`dev07-3-1`). It carries whatever
   external key the project already uses — a ticket id, a spreadsheet row — so their own systems can
   join against a citation. Plumb mints no value, enforces no uniqueness and never parses it: the
   foreign system owns that namespace and already has an identity rule. Absent is the normal case, and
   an adapter reports it as absent rather than inventing one. Because it rides the citation rather than
   the test, one test citing two stories may carry two different refs, which is the point.

2. **`collect_archetypes()` → [(story_id, archetype)]** where archetype ∈ {behavioral, structural},
   **defaulting to behavioral.**
   The one capability that reads the **spec**, not the run. It reports what kind of claim each story
   makes (`dev07-4-2`), which selects the gate's second check: a behavioral story must ground, a
   structural one must be inert. It is deliberately *not* part of `collect_citations` — the citation
   is what a **test** claims, and the archetype is the one thing a test must not get to claim about
   the story judging it. An adapter for a spec that declares no archetypes returns nothing and
   everything is behavioral, which is why this is backward-compatible by construction.

3. **`run(testset) → [(test_id, result)]`** where result ∈ {passed, skipped, aborted, failed}.
   Runs the tests and reports the native result verbatim. This is what closes "a citing test ran and
   passed" — a test that is absent, skipped or aborted cannot report `passed`.

   **Collapsing a multi-phase runner.** `dev07-3-1` requires the runner's own signal without translation
   loss and is silent on runners that report a test more than once; pytest reports setup, call and
   teardown separately, and JUnit has before/after equivalents. Two rules, both adapter-side:

   - **Only the phase that runs the body may report `passed`.** A green setup whose test never ran
     has proved nothing, so it normalizes to `skipped`, not `passed`. Getting this wrong is not
     cosmetic — it manufactures exactly the fake `dev07-4-2` exists to catch, and it is easy to write
     by accident because the runner did emit a "passed" for that phase.
   - **Worst-wins across phases.** A test that passes its body and then errors in teardown is a
     failure. Anything else lets a story read proven off a run that did not complete.

   **Run the suite the build runs, or refuse to observe it** (`dev07-1-1`). Everything this contract
   produces is derived from watching one execution, so a runtime you *reconstruct* is only evidence
   about the project to the extent it matches the one their build tool uses. Ask each build tool the
   question in its own terms: the JVM adapter reads a Maven reactor's `target/classes` and
   `target/test-classes` out of the POMs, and a Gradle build's `build/classes/*/{main,test}` **and**
   `build/resources/{main,test}` out of `settings.gradle`, because Gradle keeps resources in their
   own output directory and Maven copies them in beside the code. One list for both build tools
   would be wrong for whichever one it was not written from. Where it does not, each
   difference arrives as a test that fails under Plumb and passes under the build — which reads as a
   defect in their code and is a defect in your adapter. Borrow the build's own execution where you
   can. Where you cannot, compare what you are about to run against what the build declares, before
   you launch it, and **refuse by name** rather than observing and reporting: a run that is narrower
   than the build's manufactures failures the build does not have, and nothing in the output would
   tell the reader to doubt it.

   **If your observer dies, finish the suite anyway** (`dev07-1-3`). The tests still answered; only the
   grounding question went unasked, and `not-checked` is what says so. Killing the run because the
   instrument failed costs the reader a whole board for a reason that is not theirs — and say which
   silence it is, because "you declared no entry points" sends a project that already did to exactly
   the wrong place.

4. **`per_test_trace() → {test_id: <call tree>}`**
   A **language-native per-test execution trace** — the runtime's own tracing (e.g. Python's
   `sys.settrace`) yielding the test's **call tree**, **not a third-party coverage tool**. Coverage is
   their space; taking one on means tracking its versions and surface. Plumb needs only enough to answer
   *grounding* the way chapter 3 defines it — did execution run *under* a declared entry point — with no
   coverage dependency and no story→code map.

   **Degrading is not symmetric, and getting that backwards is expensive.** `inert` and
   `ungrounded` are both answers you might not be entitled to, and being wrong about them costs
   opposite things. `inert` is a *positive* proof — it is what a structural story needs — so an
   adapter that reports it on partial evidence **grants a pass nobody earned**, and must withhold
   to `dispatched` the moment it cannot account for every thread. `ungrounded` only ever
   *withholds* status, and it is `dev07-1-4`, the orphaned-"done" check the whole tool exists for — so
   degrading it on weak evidence trades the headline capability for a narrower correction.

   The rule that falls out: **withhold a positive claim on partial evidence; do not withhold a
   negative one.** Report `dispatched` in place of `ungrounded` only when you *saw* the hand-off —
   an observed `Executor.submit`, not merely a thread that happened to be alive.

   The same tree answers the prior question `inert` (`dev07-1-4`): whether the test invoked **any**
   production code. It is asked first and needs no entry points, so a structural spec still gets a
   real fact rather than `not-checked`. What exactly counts as a production frame — import-time and
   class-loading machinery are the awkward cases — is the adapter's to settle (`dev07-1-4`).

5. **`entry_points() → {file: {line ranges}}`**
   The declared production surface (HTTP routes, top-level use-case functions, `main()`s). Small,
   authored per project. A story is grounded only if, in a citing test's call tree, execution runs *under*
   one — the entry point is an ancestor of the code the test ran (chapter 3).

6. **`mutate(scope) → (total, killed)`** — **opt-in, default-off.**
   A **minimal in-house AST mutation** over the code a story's tests drove *under a declared entry
   point* — **no PIT / mutmut / Stryker dependency**. Each mutant runs against **every test citing
   that story**, and the result is a **score**, never a word: a story's tests routinely run far
   more code than they check, so "did any mutant survive" is `yes` almost everywhere and separates
   nothing. It is **advisory** (equivalent mutants are false positives), never a core gate
   (chapter 4). Expect it to cost minutes on a small project and hours on a real one — an adapter
   should be able to report the mutant count *before* running, so a caller can decide.

   **Use the language's own parser.** Python's `ast` and Java's `com.sun.source` are both already
   installed and are what the two shipped adapters use; a mutation engine answers a hundred
   questions where one is needed, and arrives as a version to track. Mind the type system: `return
   null` from an `int` does not compile, and a mutant that will not build has told you nothing
   about the test — skip it rather than scoring it as killed, or every score inflates by the number
   you got wrong.

## The manifest it must produce

This is the whole contract. An adapter's only obligation is to emit this document; everything
downstream — the gate, the status, the board — is the core's, and reads nothing else (`dev07-3-3`).

    {
      "schema_version": "9.0",
      "observed_tests": null | <int>,
      "stories": {
        "<opaque story id>": {
          "archetype": "behavioral" | "structural",
          "mutation":  null | {"total": <int>, "killed": <int>,
                               "survivors": [{"operator": <str>, "where": <str>,
                                              "file": <str>, "line": <int>,
                                              "reached": null | <bool>}]},
          "citations": [
            {
              "test":      "<adapter-native test id>",
              "depth":     "unit" | "component" | "wiring" | "standards-integration" | "smoke",
              "result":    "passed" | "skipped" | "failed",
              "grounding": "grounded" | "ungrounded" | "inert" | "not-checked" | "dispatched"
                             | "untouched",
              "ref":       null | "<the consumer's own external key>",
              "reached_outside_entry": null | true | false,
              "entered_through": null | ["<declared entry point>", ...]
            }
          ]
        }
      }
    }

Notes an adapter author needs and the field names do not carry:

- **The story id is opaque.** `dev07-4-2`, `CM-101`, a spreadsheet row — the core never parses it and
  needs no catalog to accept it (`dev07-3-2`).
- **`archetype` is per story and comes from the spec, not the run.** It is the one field read off
  the requirement rather than the execution, and the one thing a *test* must not get to claim about
  the story judging it (`dev07-3-2`, `dev07-4-2`). Absent means `behavioral`.
- **`grounding` is a fact, never a verdict.** Report what the trace showed and let the gate decide.
- **`inert` is a positive claim from major 8 on, and `untouched` is what it used to hide.** `inert`
  means the test **read** the production artifact and ran none of it — the mirror `dev07-4-2` asks
  for, and the only fact that proves a structural story. `untouched` means it did neither, which is
  what `assert True` does. Emit `inert` only if you can actually see the read: an adapter that
  watches execution alone cannot tell the two apart, and saying `inert` anyway hands a passing
  grade to a test that touched nothing. **If you cannot see reads, emit major 7**, where `inert`
  means *ran none of it* and claims nothing about reading — which is what Plumb's own Java adapter
  does today.
  `inert` is not a weaker `ungrounded`: it means no production code ran at all, which is what
  inspecting an artifact looks like, and it is the positive proof a structural story needs.
  `not-checked` means the question could not be asked — no entry points, or no production roots.
- **`ref` is the consumer's, not ours.** Plumb mints nothing, enforces no uniqueness and never
  parses it (`dev07-3-1`). Absent is the ordinary case; report absence rather than inventing a value.
- **One entry per (test, story) pair.** A test citing two stories produces two citations, each with
  its own depth and ref.

**`observed_tests` is how many tests your run saw — cited or not — and it is the one field here
that is about the run rather than about a test.** Report the count your runner discovered, whether
or not any of them carried a citation. It exists because every other field describes a test that
*was* seen, so without it these two runs produce the same document:

- a healthy suite of 38 tests that has not cited a story yet, and
- a run that discovered no tests at all, because the classpath or the test path was wrong.

Both have no stories, and the second is a broken run wearing the first one's clothes. With the
count, the core can say so and `plumb board` can exit non-zero on it (`dev07-5-2`, `dev07-5-3`).

**`null` means you could not tell, and `0` means you looked and there was nothing.** These are
different claims and Plumb treats them differently: it raises the alarm on `0` and stays silent on
`null`, because an adapter's silence is not evidence of an empty run (`dev07-3-3`). Report `null` if
your runner cannot tell you, and set the count only once discovery has actually happened — a run
that died before it could look should not report that it looked and found none.

Counting *citations* instead is the mistake to avoid: it would make every project's first run
report zero, and put the alarm in front of exactly the people who have done nothing wrong.

**`survivors` is optional, and empty is not a clean sheet.** Name the mutants no test noticed —
operator, `Class#method`, source file, line — because the reader's next move is to strengthen the
test that missed one, and a count cannot tell twenty-seven work items apart (`dev07-2-4`). An adapter
that reports a shortfall without naming it is *older than this field*, not reporting that nothing
survived, so `total - killed` stays the authority on how many there were. More names than shortfall
is a contradiction and is refused.

**`reached` on a survivor separates two very different findings.** A method is scoped whole, so a
story's mutants include lines its tests never enter — and one of those cannot be killed however good
the assertions are. Report `false` where you can tell the mutated expression never evaluated, `true`
where it did, and omit the field if you cannot observe it: `null` is *not reported*, never a claim
that the line was unreachable (`dev07-3-3`). This is not `dev07-2-4`'s equivalence, which is undecidable;
it is a fact a run can watch for.

**`entered_through` is optional and names the door, where `grounding` names only that there was
one.** `entry_points` is a single flat set for the whole project, so a door declared for one subject
is open to every subject — and without the identity nothing downstream can tell a test that came in
at the front from one that entered at a subsystem door somebody declared for another chapter
(`dev07-1-4`). Report the entry points the test entered **from outside any open window**: a test that
enters at the front and reaches a second declared door on the way names the first one only, so
declaring another door never rewrites the fact for a test that did not change. Ordinarily one; a test
driving two entrances reports both. `[]` means it entered by none, `null` means you cannot say.

**`reached_outside_entry` is optional and reports a limit rather than a fact about depth.**
Grounding is a property of the *test* (`dev07-1-4`), so a test that drives an entry point and then
calls unreachable code still grounds. If you can tell that a citing test also executed production
code no entry point reached, report `true` and the board says so (`dev07-1-4`). If you cannot observe
it, report nothing. `null` is *not reported*, and is different from `false`.

**A version behind is fine.** An adapter emitting an older schema than the core reads still renders
unchanged. That asymmetry is the point of `dev07-3-2`: an adapter that cannot observe a newer field
simply omits it, rather than being locked out or inventing a value. Ask the tool which versions it
reads rather than trusting a number written here — a refusal names the supported set, and this
sentence would go stale the next time one is added.

**Versioning, and what happens when you get it wrong.** `schema_version` is required and is the
shape your document claims (`dev07-3-2`). The core reads the versions it knows and refuses the rest,
and the asymmetry is deliberate: a manifest *older* than the core still reads, because the core
knows that shape; a *newer* one does not, because nothing can be inferred from a description that
has not been written yet. Within a declared version the field set is fixed — an unrecognised key
means you changed shape without changing the number, so it is refused by name rather than ignored.
That applies to **stories as well as citations**: a typo'd `archetypes` silently dropped would
leave the story quietly behavioral, and the archetype decides which check the gate applies.

Refusals are checked against **the version your document declared**, not against whatever the
current Plumb happens to define, so the field list in the message is the one you were writing to.

**`schema_version` is `major.minor`.** A **minor** bump is additive and readable by any reader of
the same major; a **major** bump is structural and is not. So you can tell from the number alone
whether a document is readable, instead of consulting a changelog.

**Stay within one major of the latest — that is the recommendation, and the window a run accepts.**
Below it a run refuses and says how to come forward.

**The migration chain reaches one major deeper than that.** `plumb manifest migrate` reads **two**
majors back, so the advice you are given is deliberately softer than the floor you can fall to and
nobody is stranded until they are three behind. The two sets are not the same set, and the
difference is the whole reason the command exists: the shapes it parses are exactly the ones a run
will not accept. Below the chain there is no path, and the refusal says so rather than naming a
command that cannot help.

Migration is **offered, never automatic**: a manifest is derived from a run and
Plumb deletes any previous one before every run, so the first answer to a stale manifest is always
*re-run your suite*. `plumb manifest migrate` is for the case where that run cannot be reproduced —
an archived CI artifact, a decommissioned system, a handover. A migration may fill a field only
with a value meaning *"this was not reported"* (`dev07-3-3`), so a carried-forward document can never
gain a fact your adapter did not report.

**Major 7 lets a citation name the aspect it is about.** A subject may declare more than one aspect
— `"aspects": ["levers", "outcome", "falsifier"]` on the story — and a citation may carry
`"about": "falsifier"` to say which one it bears on. A story has exactly one, declares none and
names none, so every document written against major 6 reads unchanged and the climb has nothing to
guess.

Both are opaque strings the core never interprets. It routes evidence to a derivation and asserts
nothing about the aspect itself — *whether* your falsifier is a good one, or your control sound, is
yours to judge and not something Plumb reports on. A citation naming an aspect its subject does not
declare is refused, because a dropped one would attach it to nothing and the subject would read
unevidenced for a reason no reader could see.

**A citation may say when it was measured.** `"when": "2026-08-02T15:04:05Z"` — RFC 3339 in UTC,
on the **fact** for the same reason the instrument is: a merged board carries several runs, so one
document-level time would be a false claim about facts that were not measured together. Stamp it
once per run rather than per citation; every fact in one run was measured by one run, and re-reading
the clock would make them disagree about when they happened.

Absent is legal and means *not reported*. It is never read as *now* — an adapter that cannot say
when it measured says nothing, which is strictly weaker than a time it made up. A wrong **shape** is
refused rather than coerced, because a time is the axis a series gets ordered on and one that parses
differently in two languages orders differently in two languages.

**Major 6 moved the instrument onto the fact.** Up to major 5 one `observer` described the whole
document, which was true while one run meant one adapter. A board may now carry facts from several
adapters at once, and `dev07-3-1` says two facts are comparable only when the same kind of observer
produced them — so each citation names its own (`dev07-3-1`). Climbing a major-5 document is lossless:
its single observer is attached to every fact in it.

Every refusal tells you what this Plumb reads:

    schema_version 99 is newer than this Plumb understands (reads: 6.x, 7.x). Upgrade Plumb,
    or emit an older version — a newer shape cannot be guessed at

    S-1: citation: field(s) ['confidence'] are not defined by schema_version 6.0 — it defines
    ['depth', 'grounding', 'observer', 'reached_outside_entry', 'ref', 'result', 'test']

`mutation` sits on the **story**, not the citation: a mutant is run against every test citing the
story, so the result is one fact about the story rather than the same number repeated per
citation. Versions 1-3 put a bare `"killed"`/`"survived"` on the citation; no adapter ever filled
it, so an empty slot carries forward and a filled one is refused rather than given an invented
denominator.

Only `test`, `depth` and `result` are required in a citation. The rest carry defaults, so a first
adapter can be small and still conform: report what you have, and the board degrades honestly
around the rest rather than refusing you.

**Check yourself against it without writing an adapter.** Hand-write a manifest and run:

    plumb board --manifest your.json

That path never touches a runner, so a board coming out of it is the core accepting your document.
Going the other way, `plumb board --emit-manifest out.json` shows what the Python adapter produces
for a real run — the reference output to compare against.

## What the adapter must NOT do

- It must not define the story-id scheme, the status vocabulary, or the gates. Those are the core.
- It must not *infer* a story's archetype — from the test, from naming, from what the trace turned out
  to show, or from a spec it went looking for. It reports what the launcher handed it from
  `[archetypes]`, or the default. An inferred archetype is a gate choosing the check that the
  evidence already passes.
- It must not decide *which* code implements a story (that story→code map rots). It supplies
  trace and mutation *facts*; the gates reason over them via the entry-point join.

## Build order

**Python / pytest first.** The core is Python, so the first adapter is the one that lets Plumb
**trace itself** — the tightest possible loop, on code we own, with no second language in the way.
It is what turns the gold-spec's own UNPROVEN stories into proven ones, and no capability here is
designed without a consumer exercising it.

**Java / JUnit second**, proven against a large, genuinely complex codebase rather than against
this one. Capturing a system's requirements this way — unambiguous user stories a gate can check —
is what keeps its build correct and within an agent's reach as it grows. That target exercises all
five capabilities on hard code the adapter's author did not write, which is the part self-tracing
cannot prove.

A third adapter only when a project actually adopts `plumb` — never speculatively. A real consumer is
what proves the abstraction is an abstraction.
