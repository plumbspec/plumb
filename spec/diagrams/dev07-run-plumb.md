# dev07 · run plumb — the proving pipeline

**Last updated** 2026-09-13 v17

A sub-flow of [A developer's workflow](developer-day.md). Entered from `dev06 · do the work`,
carrying the configuration, the annotations and the working tree. Exits to the claims, carrying a
board — one command returned it.

```mermaid
flowchart TD
    IN([<b>START</b> · one command, a cited suite,<br/>and a working tree]):::terminal

    OBS[[<b>dev07-1</b> · run the suite under observation<br/>▸ drills down]]:::subroutine
    REFUSED[/<b>REFUSED</b> · the mismatch is named, and nothing is<br/>called evidence — fix it and run again/]:::bad
    MUTQ{mutation asked for?}:::question
    MUT[[<b>dev07-2</b> · check the tests bite<br/>▸ drills down]]:::subroutine
    COL[[<b>dev07-3</b> · collect what the run did<br/>▸ drills down]]:::subroutine
    DEC[[<b>dev07-4</b> · decide whether it is proven<br/>▸ drills down]]:::subroutine
    REP[[<b>dev07-5</b> · report it<br/>▸ drills down]]:::subroutine
    SERQ{does the project keep a series?}:::question
    KEEP[[<b>dev07-6</b> · append the run to the series<br/>▸ drills down]]:::subroutine

    OUT([<b>END</b> · a board — and, where a series is kept,<br/>the run in the history]):::good

    IN --> OBS
    OBS -->|"the runtimes do not match"| REFUSED
    OBS -->|"the runtimes match"| MUTQ
    MUTQ -->|yes| MUT --> COL
    MUTQ -->|no| COL
    COL --> DEC --> REP --> SERQ
    SERQ -->|yes| KEEP --> OUT
    SERQ -->|no| OUT

    classDef terminal fill:#eef0ee,stroke:#52514e,color:#0b0b0b;
    classDef process fill:#e9eef5,stroke:#2a78d6,color:#0b0b0b;
    classDef subroutine fill:#e9eef5,stroke:#2a78d6,color:#0b0b0b;
    classDef question fill:#fdf3d8,stroke:#b8860b,color:#0b0b0b;
    classDef bad fill:#f7e4e4,stroke:#b02a2a,color:#0b0b0b;
    classDef good fill:#e2f2e2,stroke:#0ca30c,color:#0b0b0b;
```

## Nodes

### dev07-1 · run the suite under observation

Drills down into [dev07-1 · run the suite under observation](dev07-1-run-the-suite-under-observation.md).

> **As a developer whose test proves a behaviour I want the run to record what each test drove,
> so that a passing test is evidence of doneness.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| dev07-1-inf01 | In | `config` | yes | parent |
| dev07-1-inf02 | In | `working_tree` | yes | parent |
| dev07-1-inf03 | In | `annotation` | yes | parent |
| dev07-1-inf04 | Out | `run` | yes | observed |
| dev07-1-inf05 | Out | `trace` | yes | observed |
| dev07-1-inf06 | Out | `runtime_report` | optional | derived |
| dev07-1-inf07 | Out | `citation.grounding` | yes | derived |
| dev07-1-inf08 | Out | `citation.entered_through` | yes | observed |
| dev07-1-inf09 | Out | `citation.reached_outside_entry` | yes | observed |
| dev07-1-inf10 | Out | `citation.elapsed` | optional | observed |
| dev07-1-inf11 | Out | `run_condition` | optional | derived |

#### User Requirements

#### System Requirements
  * dev07-1-sr1 - observing is the adapter's, in the language's own tooling
  * dev07-1-sr2 - the launcher picks the adapter from the configuration (`adapter`) and the core
    never learns which; an unknown adapter fails as a launch, never as a verdict
  * dev07-1-sr3 - the launcher resolves the declarations once and hands whichever adapter runs
    the same resolved answers, as a file — answers, never questions, because an adapter may not
    run in this process

#### Non-Functional Requirements

#### Unknowns


---

### dev07-2 · check the tests bite

Drills down into [dev07-2 · check the tests bite](dev07-2-check-the-tests-bite.md).

> **As a developer whose suite is green I want to know which of my tests run the code without
> checking it, so that *passing* and *checking* stop being the same word.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| dev07-2-inf2 | In | `trace` | yes | dev07-1 |
| dev07-2-inf3 | Out | `story.mutation` | yes | derived |
| dev07-2-inf4 | In | `story.id` | yes | parent |
| dev07-2-inf5 | In | `annotation` | yes | parent |
| dev07-2-inf6 | In | `citation.elapsed` | optional | dev07-1 |

#### User Requirements
  * dev07-2-ur1 - only code the story's tests drove beneath a declared entry point is mutated
  * dev07-2-ur2 - every test citing the story runs against each mutant

#### System Requirements
  * dev07-2-sr1 - the proof is only as complete as the mutations implemented
  * dev07-2-sr2 - the implemented set is `flip-comparison`, `negate-branch` and `swap-return`,
    applied to the language's own parse tree, and nothing outside it is ever applied

#### Non-Functional Requirements
  * dev07-2-nfr1 - off by default because it is slow, not because it is optional; the
    configuration (`mutation`) or the command (`plumb board --mutation`) turns it on

#### Unknowns


---

### dev07-3 · collect what the run did

Drills down into [dev07-3 · collect what the run did](dev07-3-collect-what-the-run-did.md).

> **As a developer I want the record of the run to carry facts and
> never verdicts, so that the claims can be re-derived and checked rather than taken on trust.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| dev07-3-inf01 | In | `run` | yes | dev07-1 |
| dev07-3-inf08 | In | `annotation` | yes | parent |
| dev07-3-inf09 | In | `story.id` | yes | parent |
| dev07-3-inf10 | In | `citation.elapsed` | optional | dev07-1 |
| dev07-3-inf03 | In | `story.mutation` | optional | dev07-2 |
| dev07-3-inf05 | In | `citation.grounding` | yes | dev07-1 |
| dev07-3-inf06 | In | `citation.entered_through` | yes | dev07-1 |
| dev07-3-inf07 | In | `citation.reached_outside_entry` | yes | dev07-1 |
| dev07-3-inf04 | Out | `manifest` | yes | generated |
| dev07-3-inf11 | Out | `citation` | yes | derived |
| dev07-3-inf12 | Out | `absent_adapter` | optional | derived |

#### User Requirements
  * dev07-3-ur1 - one record per citing test

#### System Requirements

#### Non-Functional Requirements

#### Unknowns


---

### dev07-4 · decide whether it is proven

Drills down into [dev07-4 · decide whether it is proven](dev07-4-decide-whether-it-is-proven.md).

> **As a developer I want *done* derived from the recorded facts — the test ran, passed, and
> matched the kind of claim the story makes — so that I can rely on it.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| dev07-4-inf1 | In | `manifest` | yes | dev07-3 |
| dev07-4-inf2 | In | `story.id` | yes | parent |
| dev07-4-inf4 | In | `citation` | yes | dev07-3 |
| dev07-4-inf3 | Out | `verdict` | yes | derived |

#### User Requirements

#### System Requirements
  * dev07-4-sr1 - the core reads the manifest schema versions it knows and refuses a newer one by
    name rather than guessing

#### Non-Functional Requirements

#### Unknowns


---

### dev07-5 · report it

Drills down into [dev07-5 · report it](dev07-5-report-it.md).

> **As a developer about to act on the result I want one board naming each story's status, depth
> and residue, so that what I do next comes from what was proven.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| dev07-5-inf1 | In | `verdict` | yes | dev07-4 |
| dev07-5-inf2 | In | `manifest` | yes | dev07-3 |
| dev07-5-inf4 | In | `citation` | yes | dev07-3 |
| dev07-5-inf5 | In | `absent_adapter` | optional | dev07-3 |
| dev07-5-inf3 | Out | `board` | yes | derived |

#### User Requirements

#### System Requirements
  * dev07-5-sr1 - `plumb board --json` emits the documented, versioned neutral format for tools
    downstream

#### Non-Functional Requirements

#### Unknowns


---

### dev07-6 · append the run to the series

Drills down into [dev07-6 · append the run to the series](dev07-6-append-the-run-to-the-series.md).

> **As a developer asking when this broke I want every run to leave its mark in a history kept in
> my own tree, so that the history shows test status over the time dimension.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| dev07-6-inf1 | In | `config.series` | yes | parent |
| dev07-6-inf2 | In | `verdict` | yes | dev07-4 |
| dev07-6-inf3 | Out | `series` | yes | derived |

#### User Requirements

#### System Requirements

#### Non-Functional Requirements
  * dev07-6-nfr1 - appending locally and transmitting to its holder stay separate
  * dev07-6-nfr2 - a project that declares no series skips this step, and nothing downstream may
    come to depend on it

#### Unknowns


## Glossary

| Term | Meaning |
|---|---|
| Run | One execution of the suite, observed. |
| Trace | The runtime's own per-test record of what the test drove. |
| Mutation | Deliberate small changes to driven code, to see whether the citing tests notice. |
| Manifest | The one document the core reads: facts about the run, never verdicts. |
| Annotation | The marker on a test naming the story it evidences — what a person writes. |
| Citation | One citing test's recorded facts for a story, minted at collect from the annotation and the run. |
| Verdict | The core's derived answer per story: proven or not, and how far. |
| Board | What plumb emits: per story, whether it is proven and how far. Not the sprint backlog. |
| Series | The append-only history of runs a project chooses to keep. |
| Provenance | The fifth column of an Information table: where an input came from, or how an output was made. |
| Authored | Written by a person. An input nothing produces, or an output somebody typed. |
| Derived | Computed by this step from what it took in. |
| Observed | Read off a run, a tree or the world as it stands. |
| Generated | Made by a tool rather than by a person. |
| Parent | On a sub-flow's input: handed in by the chapter this one drills into. |

---

## Working notes — not part of the chapter

`ch0-3` in chapter-03-observing.md is the source of the refusal claim, and the operator reads it
as a story that entered from classpath and backwards-compatibility trouble, phrased so awkwardly
it obscures its own point. When ch3 is converted it should say what dev07-1-ur1 now says: the
adapter's runtime matches the project's own. The pre-launch detection, the wider-run allowance
and the measured multi-module case are that chapter's material, not this altitude's.

*Grounding* (operator, 2026-09-11): the word reads as jargon and both senses leave the corpus.
The pipeline sense converts to plain english when ch3 and the gate chapter do — say what it is:
the test drove production code beneath a declared entry point. The session sense is already gone
from dev03.
