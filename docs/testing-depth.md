---
kind: explanation
role: [qa, engineer, programmer]
summary: What a depth claim means, and which role each rung serves.
---

# Testing depth, and the roles it serves

**For QA, engineers and programmers** deciding what depth to claim.

"Done" in Plumb is a **vector over testing depth**, not a single green bit (see Plumb's own gold spec,
`spec/chapter_01_proof.py` → `dev07-4-3`). Each **rung** proves a different thing, **assumes** the rung
below it, and hands its assumption up to be **discharged** by a rung above — so a run stays fast and
non-redundant, and a story proven only at the bottom reads as *only* that deep. The same rungs map to
who does the work in an organization: each is written by a role and assures another.

> **A rung is not a layer.** *Layer* means a spec's architectural strata — the ladder of packages a
> system is decomposed into, where an edge may only point down. That is a different axis and a
> different kind of spec, proved by inspecting structure rather than by running anything. Depth is how
> far up the proof pyramid a test reached; layering is how the code is arranged. Nothing here refers to
> the latter.

Two rules frame the whole stack:

- **Proof happens at the developer's desk, not in CI.** No *coding* error should be caught by CI — if
  one is, the testing failed. CI exists to **package** on a cadence; the only thing legitimately caught
  at or after packaging is a packaging/deploy regression, guarded by the top rung.
- **Mutation is the cross-cutting honesty check.** Mutate the code a story's tests drove; whatever no
  test notices is code the suite does not actually check. It finds defects a fully green suite has
  already signed off, so the question is not whether to run it but **when** — and that is a cost
  question, because it is *not* cheap: a mutant costs a test run, and there are thousands of them.
  Scoping to one story's wired code is what makes a story affordable at a desk; the whole project is
  a nightly or a weekend. See [what to expect](what-to-expect.md#what-mutation-costs).

## Where a depth is written

Everything on this page is about one argument in the citation you already write — `depth`:

    @pytest.mark.proves("ORD-1", depth="wiring")
    def test_an_order_gets_a_queue():
        assert run("A-1")["queue"] == "standard"

The same claim in Java:

    @Test
    @Proves(value = "ORD-1", depth = "wiring")
    void anOrderGetsAQueue() {
        assertEquals("standard", api.handle("A-1").queue());
    }

`depth` is a **claim about how far that test reached**, not a label for how it is filed. The run
either supports the claim or refutes it. The rest of this page is what the values mean and how to
choose between them.

Two things worth knowing before you read the table:

- **Only the wired rungs get checked.** `wiring`, `standards-integration` and `smoke/e2e` all claim
  the test drove the real system, and grounding is the check on that claim. `unit` and `component`
  claim the opposite — isolation — which no trace can refute, so they are taken at your word. This
  is why lowering a depth quiets the tool: you have moved the claim to where nothing checks it.
- **Spell the value exactly as the table spells it.** Nothing validates the string today. A
  misspelled `wiring` is accepted as written, silently stops matching a wired rung, and the story
  simply loses its diagnostic — `wirring` and `wiring` both end up UNPROVEN on the same test, but
  only the correctly-spelled one tells you why.

## Choosing a depth honestly

There is a real pull toward claiming deep, and it is worth naming rather than pretending it away.

**A behavioural story reaches PROVEN only when its test grounds** — when execution passes through a
declared production entry point. `unit` and `component` claim isolation, so they do not ground, so a
story cited only at those rungs stays UNPROVEN however good the test is. That is by design, and it
means the board rewards depth. Anyone reading a board as a score will feel it.

**Claiming a rung you did not reach does not work, and the tool says so.** Write `depth="wiring"` on
a test that calls a function directly and grounding refutes it — `depth.unsupported`, with the
citation named. This is the check doing its job, and it is not the thing to guard against.

**The thing to guard against is `entry_points`.** That list is the one input Plumb cannot verify: it
takes your word for where the system begins. Declare the unit under test as an entry point and a
direct unit test grounds, comes out `PROVEN [wiring]`, and raises no condition at all — because
every mechanical check passed. The claim became true by moving the front door, and nothing in the
tool can tell that from a system whose front door was always there.

So the discipline lives in one place:

- **An entry point is where a request from outside enters** — a CLI command, an HTTP handler, a
  queue consumer, a scheduled job. Not every public method, and not a function a test happens to
  need.
- **The list should be short, and it should be boring.** It describes your architecture, and your
  architecture does not change because a story would not prove.
- **Watch when it grows.** A story that will not prove, followed by a new entry point, is the
  pattern worth catching in review. Treat a change to `entry_points` the way you would treat a
  change to permissions: rare, deliberate, and explained.
- **Run mutation on the stories that matter.** Grounding proves a test *reached* the code. Mutation
  is the only thing here that asks whether it *checked* anything, which is the other half of the
  same honesty question.

And the pressure releases entirely once one thing is accepted: **UNPROVEN is not a failing grade.** A
story proven at `unit` is proven at `unit`, and the achieved vector says so precisely. A board full
of honest `unit` is worth more than a board of `wiring` bought by widening a list, because only one
of them still tells you something the day it goes red.

## The rungs

| Rung | What it proves | Mocks | Assumes → discharged by | Written by | Assures |
|---|---|---|---|---|---|
| **unit** | a unit's input→output in isolation | no | its collaborators work → *component / wiring* | programmer | the logic itself is correct |
| **component** | branching, looping, error paths — how the unit *behaves* | yes (spies) | the doubles mirror the real collaborators → *wiring / standards-integration* | programmer | the engineer: the code does what the story says |
| **wiring** | the code is actually **integrated**, not orphaned | yes | *component is already proven* — ordered, because you cannot check the wiring of wrong code | programmer + engineer | that "done" is real, not dead or unwired code |
| **standards-integration** | it works against the real resource **technology** through a standard interface | no — a **real** resource, **embedded & fresh** | standard conformance; the *platform* choice is ops' → *smoke/e2e* | programmer / engineer | portability, and that it works against the resource |
| **smoke / e2e** | everything real, assembled artifact, end-to-end | no | nothing — the floor | programmers, to a QA + devops plan | QA: works as specified · devops: packaging introduced no bug |

**Grounding** underlies wiring and standards-integration: in the test's own call tree — a
language-native per-test trace, never a coverage tool — execution must run *under* a *declared
production entry point*, proof it drove the real system and not an isolated method. A test claiming
`wiring` or `standards-integration` whose execution never grounds is a lie the tool catches.

**These rungs are the pyramid for *behavioral* proof.** A **structural** story — dependency
direction, containment, format — is proved by inspecting the artifact rather than running it, so its
test executes no production code at all and grounding is the wrong question to ask of it; the gate
asks the mirror question instead (Plumb's own gold spec, `dev07-4-2`, `dev07-4-2`). Which rung such a test sits on is
genuinely unsettled — see `dev07-4-3`.

> **Read the artifact; do not import it.** A structural test must reach its subject *as data* — open
> the file, parse the bytecode, walk the tree. Importing the module to inspect it does not work, and
> it fails in the direction that costs the most to diagnose: the first import runs module-level code, so the test
> looks like it executed production code, while a later run finds the module already imported and
> touches nothing at all. Same test, same assertions, and what the board says depends on whether
> some *other* test imported it first. Plumb refuses both — a structural claim is proved only by a
> test that read the artifact — so an import-based one is simply never provable, whichever order the
> suite runs in. Note that **non-functional requirements are not a third kind**:
they are behavioral, proven at smoke/e2e against the assembled artifact, exactly as the two-track
section below describes.

## Three things that cost people time when missed

- **Mocks are not a smell.** Used correctly they are *how* you prove at the **component** rung
  (branching, looping, errors) and at **wiring** (that the code is actually called by the real system).
  The wiring mock is specifically what catches the "it reports done but it's orphaned" failure.
- **Standards-integration means embedded, fresh, and standards-only.** Use the real resource
  *technology* (real SQL semantics a mock can't fake) but instantiate it **new each run** — freshness
  *by construction*, not "remember to truncate" (a persistent shared database drifting between runs is
  a classic, real bug). Test against a **standards-only** stand-in so a developer can't reach for
  vendor-specific features: the choice of the actual platform is a **dev-ops / ops** decision, not a
  developer one. A vendor coupling is permitted only as a **declared** exception, where topology forces
  it (e.g. high WAN latency pushing computation into the database) — declared, never drifted into.
- **Ordering is a dependency, not a preference.** Wiring assumes the component rung;
  standards-integration assumes wiring. A rung proven on code whose lower rung is unproven proves
  nothing — the assumption it leans on was never discharged.

## Two tracks, one implementer

**All test code is code, written by the programmers — every rung, including smoke/e2e.** QA and
devops do not write tests; they write the **plan**. Requirements arrive on two parallel tracks:

- **Functional** requirements descend the role loop as stories — PM/BA → engineer → programmer — and
  are proven at the unit / component / wiring / standards-integration rungs.
- **Non-functional** requirements (performance, reliability, deployment, end-to-end acceptance) are a
  **parallel track**: QA and devops author the plan, and the *same programmers* implement it in code.
  **Smoke/e2e is where that track lands**, verified against the assembled artifact.

So "written by" always means the programmers; what changes hands is the rung's *plan* — a functional
story for the lower rungs, a QA/devops non-functional plan for smoke/e2e.

## How the rungs close the loop across roles

The rungs are the vertical proof; the roles are a horizontal loop around them:

- **PM / BA** own the requirement as process-flow + IPO — the spec the rungs prove against.
- **Engineers** synthesize the IPO and process flow into user stories, and work with programmers on
  the component and wiring rungs.
- **Programmers** write the code and **all** its tests, at every rung — the lower rungs from the
  functional stories, smoke/e2e from the non-functional plan.
- **DevOps** split the code into packages and deploy; they make no requirement claim, but the top
  rung **assures them the packaging introduced no bug**, the *platform* choice is theirs, and they
  co-author (with QA) the **non-functional plan** the programmers implement.
- **QA / Test** read the whole vector — *does it work as specified?* — **reverse** that into *is the
  spec correct?* back to the BA, and **author the non-functional / acceptance plan** that the
  programmers implement as smoke/e2e.
- The **PM** runs the closed loop: agile, but keeping a schedule and a cadence of improving the process.

Everything Plumb **enforces** is objective correctness — ran + passed · grounded · wired. Mutation is
reported beside that and never enforced: a surviving mutant may be a weak test or may be semantically
identical to the original, and nothing can tell those apart. *Which* rungs a story must reach — the
required depth — is **policy**, set per team, and is never imposed by the framework.
