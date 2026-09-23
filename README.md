# Plumb

**Capture requirements as a line you can check — top to bottom.** Plumb is a language-agnostic
method and toolkit for capturing what a system must do — as **process flow and IPO**
(Input → Process → Output) — and keeping that capture **traceable all the way to the code that
implements it**. Every role, from analyst to programmer to QA, works from one source of truth, and
"done" means *provably* done. For humans or AI.

The name is the thesis. A plumb line is the reference of *true*, dropped the full height of a wall to
check it is straight top to bottom. Plumb does that from requirement to code: real requirements in —
elicited, not imagined — provably faithful code out, with no way to fake the middle.

## One artifact, every role

Requirements captured as process flow + IPO become a shared artifact each role hands cleanly to the
next — and feedback flows back up:

| Role | Works from | Hands to |
|---|---|---|
| PM / BA | the process flow + IPO, in the business's own language | Engineers |
| Engineer | synthesises those into user stories | Programmers |
| Programmer | writes the code the stories describe | QA + the pipeline |
| QA / Test | proves it works *as specified* — and reverses that into "is the *spec* right?" | back to the BA → users |

The PM runs a closed, agile loop that still keeps a schedule.

## Getting it

    curl -fsSL https://plumbspec.org/install.sh | sh
    plumb board

**New here?** [Getting started](docs/getting-started.md) walks from install to your first
proven story in about fifteen minutes. [All the documentation](docs/README.md) is organised
by what you are trying to do, and says who each page is for.

**Already installed?** [CHANGELOG.md](CHANGELOG.md) says what each release changed and whether
taking it asks anything of you.

One file, both language adapters inside it, no package index and no account. Needs **Python 3.9+**
on the machine — the same one your tests run under, so a Python project needs one interpreter and
not two. A Java project needs **Java 8+** for its own tests and a Python anywhere for Plumb, where
nothing else about the build changes. The whole of it is a table in
[installing](docs/installing.md#what-you-need). Releases are signed by
`208B C127 9656 FEEA 7C2F  9A1D 8306 04D5 1CA7 D4FB`
(on keys.openpgp.org) — the same key that signs the
commits here from 2026-08-18 onward; the key was rotated on that date and the previous one is
revoked. Verification and its honest limits: [SECURITY.md](SECURITY.md).

## Proof the capture is real

A captured requirement is only worth the guarantee that the code actually honors it. So Plumb makes
the link **mechanical** — a story is proven by **two checks**:

1. **It ran** — a test citing the story passed in the same run, not a `skip`-with-a-message.
2. **It reached wired code** — the test's execution ran *through* a declared *production entry point*,
   so it drove the real system, not an isolated method.

Pass both and the story is proven; fail either and it isn't. Beyond the gate, two things that never
fail the build:

- **Does the test *check* the code?** — a free, opt-in mutation pass (chapter 4) mutates the code the
  story grounded into and expects a citing test to *fail*; a survivor is *advisory*, not a red build.
  Turn it on with `plumb board --mutation`, or `mutation = true` in `plumb.toml`.
- **Residue, named not hidden** — execution proves the code ran, not that an *assertion* is
  meaningful. That last sliver is human review.

This is also what lets an **AI** build the right thing: given requirements captured well enough to
become unambiguous user stories, and a spec that fails loudly the moment code drifts, an agent can
implement a system whose complexity would otherwise exceed what it can hold at once. That is the bet
this method makes.

## Writing the thing that gets proven

Plumb never asks you for a spec. `plumb init` writes none, there is no `plumb spec` command, and a
project with nothing but citations in its test suite gets a complete, correct board. How you capture
requirements — or whether you write them down at all — stays yours, and nothing here will ever
check.

If you would rather not start from a blank page, the methodology is a **separate product**, and it is
the one we recommend:

**[goldspec](https://plumbspec.org/gold/)** — process flows with IPO, data definitions, stories,
decisions and unknowns, and the gates that keep them honest. Installed separately, run as `goldspec`,
and what Plumb uses for its own specification.

Recommended is not required, and it is not a one-way door. Its conventions are settings rather than a
format — a project whose ids read `REQ` or `sh`, whose flows live somewhere else, says so in a
`goldspec.toml` and is checked just the same. Adopting it later costs nothing you did today, because
citations are the only thing you write by hand for Plumb and goldspec neither replaces nor rewrites
them.

Why the two are separate products, what each one answers, and how the boundary is enforced rather
than promised: [the tool and the method](docs/the-tool-and-the-method.md).

## Done is a vector, not a bit

Each test declares its **depth**; each rung states what it verifies and what it *assumes*, and every
assumption is discharged by exactly one other place — which is what keeps a run fast (verify Postgres
once at the floor, assume it everywhere above).

| rung | verifies | assumes | discharged by |
|---|---|---|---|
| unit | a chunk's input→output in isolation | its collaborators work | component / wiring |
| component | branching, looping, error paths (spies assert the interaction) | the doubles mirror the real collaborators | wiring / standards-integration |
| wiring | the code is actually integrated, not orphaned | the component rung is already proven | — (ordered; the rung below) |
| standards-integration | works against the real resource — embedded, fresh, standards-only | standard conformance; the platform is ops' choice | smoke / e2e |
| smoke / e2e | everything real, assembled artifact, end to end | nothing | — (the floor) |

A story proven only at the unit rung is shown as unit-only — never silently "done".

*Rung*, never *layer*: a layer is a spec's architectural strata, which is a different axis.

## Shape: core + adapters + consumers

- **Core (language-neutral):** the spec model (opaque story ids, canonical status, depth), the
  **manifest** (per story → tests × depth × result × grounding × mutation-survival), and the **gates**
  over it. Knows nothing about any language.
- **Adapters (one per language):** produce the manifest from a test run — the runner's own
  pass/skip/fail *is* the status signal in every language (JUnit `abort`, pytest `skip`, xUnit
  `Skip`). Contract in [`docs/adapter-contract.md`](docs/adapter-contract.md). **First: Python /
  pytest**, so Plumb can trace itself; **Java / JUnit** second.
- **Consumers:** real projects. Capturing a complex system's requirements the Plumb way is what
  keeps its build correct and within an AI's reach as the system grows.

Plumb also traces **itself** with its own gates, so it cannot claim a capability its own board does
not back.

