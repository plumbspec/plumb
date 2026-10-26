# dev07-5 · report it

**Last updated** 2026-10-26 v3

A sub-flow of [dev07 · run plumb](dev07-run-plumb.md). Entered from the verdicts and the
citations behind them. Exits with the board, for any tool to consume and a person to read.

```mermaid
flowchart TD
    IN([<b>START</b> · the verdicts, and the<br/>evidence behind them]):::terminal

    ROWS[<b>dev07-5-1</b> · render one row per cited story]:::process
    COND[<b>dev07-5-2</b> · surface what a check could not do]:::process
    EMIT[<b>dev07-5-3</b> · emit the board]:::process

    OUT([<b>END</b> · the board, and an exit code<br/>that reports the observation]):::good

    IN --> ROWS --> COND --> EMIT --> OUT

    classDef terminal fill:#eef0ee,stroke:#52514e,color:#0b0b0b;
    classDef process fill:#e9eef5,stroke:#2a78d6,color:#0b0b0b;
    classDef good fill:#e2f2e2,stroke:#0ca30c,color:#0b0b0b;
```

## Nodes

### dev07-5-1 · render one row per cited story

> **As a reviewer I want the citing tests and what each of them actually reached, so that I act
> on evidence rather than taking a verdict on trust.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| dev07-5-1-inf1 | In | `verdict` | yes | parent |
| dev07-5-1-inf2 | In | `citation` | yes | parent |
| dev07-5-1-inf3 | In | `scope` | optional | authored |
| dev07-5-1-inf4 | Out | `board.story` | yes | derived |
| dev07-5-1-inf5 | Out | `board.label` | yes | derived |
| dev07-5-1-inf6 | Out | `board.evidence` | yes | derived |

#### User Requirements
  * dev07-5-1-ur1 - one row per cited story: its status, the rungs its tests reached, and what its
    checks could not settle, named
  * dev07-5-1-ur2 - every word rendered above a status is a restatement of what the gate
    derived, never an addition — a rendering that overstates is indistinguishable from proof
  * dev07-5-1-ur3 - the evidence restates the citing tests with what each claimed and what
    the run found, carrying its cost and its measurement time on each entry
  * dev07-5-1-ur4 - the board totals nothing: there is no denominator to divide by, and a
    reader's arithmetic is done on figures whose scope they know because they made the run
  * dev07-5-1-ur5 - a lexicon gives a kind of subject its own word for a derived status; where
    it has no word it says the status's own name rather than inventing one
  * dev07-5-1-ur6 - a subject with aspects renders one verdict per aspect and no aggregate; a
    single-field reader is held at unproven rather than shown an average
  * dev07-5-1-ur7 - the view narrows to a namespace and never the derivation: a story reads the
    same in every scope containing it, and run-level facts survive every scope
  * dev07-5-1-ur8 - the board is derived from however much the project has declared, and says
    what is missing — a project that declares nothing gets a partial answer, never an error

#### System Requirements
  * dev07-5-1-sr1 - rows sort by the natural order of the story ids
  * dev07-5-1-sr2 - how much the project has declared is worked out inside the step and never
    emitted — a completeness number would be a status about the project rather than about a
    claim
  * dev07-5-1-sr3 - the scope filter is a prefix match over ids the run observed; a mistyped
    scope reports an empty view rather than a refusal, and says that no observed id matched it

#### Non-Functional Requirements
  * dev07-5-1-nfr1 - the board is evidence a person acts on; it renders no opinion

#### Unknowns


---

### dev07-5-2 · surface what a check could not do

> **As an adopter I want to be told what was skipped and what I would get by fixing it, so that
> nothing about my setup is silently absent.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| dev07-5-2-inf1 | In | `verdict.conditions` | yes | parent |
| dev07-5-2-inf2 | In | `manifest.extent` | optional | parent |
| dev07-5-2-inf3 | Out | `condition` | optional | derived |
| dev07-5-2-inf4 | Out | `run_condition` | optional | derived |
| dev07-5-2-inf5 | Out | `unlock` | optional | derived |

#### User Requirements
  * dev07-5-2-ur01 - nothing is silently skipped: what a check could not do is surfaced with
    what would make it possible
  * dev07-5-2-ur02 - every condition carries a stable code beside its prose, from a finite set;
    a consumer branches on the code and never on a sentence somebody will improve
  * dev07-5-2-ur03 - the prose is three separately-renderable parts — the diagnosis, the
    instruction, the example — and an example is the part advice cannot act without
  * dev07-5-2-ur04 - every code resolves to its prose locally, wherever it was defined — a
    board explains itself where there is no network
  * dev07-5-2-ur05 - a code this build has never seen still emits rather than vanishing
  * dev07-5-2-ur06 - a passing citation that still did not prove says which of the three
    reasons: never reached the wired system, executed nothing at all, or executed what a
    structural claim needed read
  * dev07-5-2-ur07 - the advice says which branch advances the story and which only ends the
    complaint
  * dev07-5-2-ur08 - a run that observed nothing is its own run-level condition, never a board
    with no stories, because an empty board is also what a correct first run looks like
  * dev07-5-2-ur09 - a run that saw tests and read no citation is its own condition; it does
    not guess which cause, and it does not fail the run — a project between init and its first
    citation is doing the tutorial in order
  * dev07-5-2-ur10 - an internal error of the runner is never reported as the project's fault
  * dev07-5-2-ur11 - an unlock is counted from the run's own output and withdrawn once the
    source already carries the fact; an empty run advertises nothing

#### System Requirements
  * dev07-5-2-sr1 - every code a build can emit resolves to its prose; what is guaranteed is that
    it resolves, never that all three parts are written
  * dev07-5-2-sr2 - every condition code and every exit code the board can emit is documented

#### Non-Functional Requirements

#### Unknowns


---

### dev07-5-3 · emit the board

> **As somebody building on plumb's output I want to read the board without knowing plumb's
> internals, so that consuming it is a parse rather than an integration.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| dev07-5-3-inf1 | In | `board.story` | yes | dev07-5-1 |
| dev07-5-3-inf2 | In | `condition` | optional | dev07-5-2 |
| dev07-5-3-inf3 | In | `run_condition` | optional | dev07-5-2 |
| dev07-5-3-inf4 | In | `absent_adapter` | optional | parent |
| dev07-5-3-inf5 | In | `emit_format` | optional | authored |
| dev07-5-3-inf6 | Out | `board` | yes | derived |
| dev07-5-3-inf7 | Out | `board.version` | yes | generated |
| dev07-5-3-inf8 | Out | `exit_code` | yes | derived |
| dev07-5-3-inf9 | Out | `rendering` | yes | derived |

#### User Requirements
  * dev07-5-3-ur1 - a consumer reading the board reads the board and nothing else; the runner's
    own messages never mix into it
  * dev07-5-3-ur2 - the board versions apart from the manifest — an internal refactor never
    reaches a consumer who pinned
  * dev07-5-3-ur3 - a breaking change is a new version and never a silent shift, symmetric
    with the inbound edge
  * dev07-5-3-ur4 - the board stamps what rendered it and when — render time, and never a
    measurement time, which stays on each fact
  * dev07-5-3-ur5 - the exit code reports whether a board was derived, never whether it is
    proven: an all-unproven board exits zero, and the runner's own failing suite is the
    runner's exit to give
  * dev07-5-3-ur6 - an aborted run cannot board — a run that never finished is not a run that
    observed nothing

#### System Requirements
  * dev07-5-3-sr1 - the page a person reads is what a run gives by default; the machine-readable
    format is given when it is asked for
  * dev07-5-3-sr2 - a translation into a platform's own envelope is given only when asked for,
    sits outside the core, and never changes the format it translates

#### Non-Functional Requirements
  * dev07-5-3-nfr1 - no shape the board can take is lost from the page a person reads — a person
    is that page's only reader, and a shape can vanish from it while the machine-readable board
    stays identical

#### Unknowns
  * dev07-5-3-u1 - whether and how the board is published beyond the desk — a dashboard, a
    shared place — without making CI the gate is a distribution question, opt-in


## Glossary

| Term | Meaning |
|---|---|
| Rendering | The page a person reads — a view of the board's machine-readable format, and the only view no other check reads. |
| Condition code | The stable identifier on a surfaced gap or unlock. The prose beside it may be reworded; the code may not. |
| Unlock | What this run earned the right to suggest next — counted from its own output, withdrawn once the source carries the fact. |
| Run-level condition | A condition about the run itself, because what it names leaves no story to attach to. |
| Exit code | Whether a board was derived from an observation — never whether it is proven. |
| Lexicon | A kind of subject's own words for derived statuses — a view, never a second place standing is authored. |
| Scope | A namespace asked for at the boundary, narrowing the view and never a status. |

---
