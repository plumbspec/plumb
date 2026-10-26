# dev07-6-2-2 · hold a series

**Last updated** 2026-10-26 v2

What an IT professional does to host their team's run histories: stand a holder up on a box the
team already runs, and bound what it may spend of that box. The projects that push to it are in
[dev07-6 · append the run to the series](dev07-6-append-the-run-to-the-series.md); the endpoint
this flow stands up is the `holder` an adopter declares there.

```mermaid
flowchart TD
    IN([<b>START</b> · histories outgrowing the machines<br/>that write them, and a box the team already runs]):::terminal

    UP[<b>dev07-6-2-2-1</b> · stand the holder up]:::process
    BOUND[<b>dev07-6-2-2-2</b> · set what it may spend]:::process

    OUT([<b>END</b> · histories held and handed back —<br/>and a disk nothing on it filled]):::good

    IN --> UP --> BOUND --> OUT

    classDef terminal fill:#eef0ee,stroke:#52514e,color:#0b0b0b;
    classDef process fill:#e9eef5,stroke:#2a78d6,color:#0b0b0b;
    classDef good fill:#e2f2e2,stroke:#0ca30c,color:#0b0b0b;
```

## Nodes

### dev07-6-2-2-1 · stand the holder up

> **As an IT professional whose team's histories outgrow their machines I want one service that
> holds them and hands them back, so that custody is something we run rather than something we
> owe anybody.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| dev07-6-2-2-1-inf1 | In | `store_path` | yes | authored |
| dev07-6-2-2-1-inf2 | In | `bind_address` | yes | authored |
| dev07-6-2-2-1-inf3 | Out | `holder` | yes | derived |
| dev07-6-2-2-1-inf4 | Out | `holder.spec` | yes | derived |

#### User Requirements
  * dev07-6-2-2-1-ur1 - what the holder accepts — routes, the batch cap, which refusal means what — is
    served from the holder itself
  * dev07-6-2-2-1-ur2 - a store on storage the system clears without warning is named at startup

#### System Requirements
  * dev07-6-2-2-1-sr1 - it binds to the local interface and expects the host's own proxy for transport
    security
  * dev07-6-2-2-1-sr2 - a hand-over is appended verbatim and renumbered onto this store's own sequence
  * dev07-6-2-2-1-sr3 - a refusal says which kind it is: too large is split and resent, unreadable is
    terminal, no room is retryable
  * dev07-6-2-2-1-sr4 - two runs of one project arriving together exclude each other per series, and
    housekeeping holds the same lock

#### Non-Functional Requirements
  * dev07-6-2-2-1-nfr1 - the series surface touches no manifest, fills no slot and moves no story's
    status
  * dev07-6-2-2-1-nfr2 - it authenticates nobody; what it protects is a disk
  * dev07-6-2-2-1-nfr3 - it depends on the standard library alone — no dependency tree to keep patched,
    no build step to host
  * dev07-6-2-2-1-nfr4 - the reply never waits for housekeeping; compaction runs after it

#### Unknowns


---

### dev07-6-2-2-2 · set what it may spend

> **As an IT professional sharing a volume with things that matter more I want the bounds to be
> mine, so that holding histories can never take out what else lives on the host.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| dev07-6-2-2-2-inf1 | In | `reserve` | yes | authored |
| dev07-6-2-2-2-inf2 | In | `pool` | yes | authored |
| dev07-6-2-2-2-inf3 | In | `compact_ratio` | optional | authored |
| dev07-6-2-2-2-inf4 | Out | `startup_report` | yes | derived |

#### User Requirements
  * dev07-6-2-2-2-ur1 - the headroom left for the rest of the host is the operator's number, read from
    the disk on every write
  * dev07-6-2-2-2-ur2 - under the reserve the holder stops accepting and never starts discarding
  * dev07-6-2-2-2-ur3 - the pool is one bound over everything held; a pool at or above the whole
    filesystem is named as no bound
  * dev07-6-2-2-2-ur4 - startup says what is free, what writes are refused under, and the most it will
    hold

#### System Requirements
  * dev07-6-2-2-2-sr1 - eviction drops whole series, least-recently-retrieved first — reading a history
    is what keeps it
  * dev07-6-2-2-2-sr2 - a series already reduced to its record of discard is never an eviction
    candidate, and its bytes stay counted
  * dev07-6-2-2-2-sr3 - a discarded series is replaced by the record that it was discarded, and a
    half-written record is never read as the store
  * dev07-6-2-2-2-sr4 - compaction fires on a write once a log stores more than the ratio of what it
    says, and never fails a held record
  * dev07-6-2-2-2-sr5 - a free-space figure that cannot be read refuses nothing

#### Non-Functional Requirements
  * dev07-6-2-2-2-nfr1 - the compaction policy lives in one place, and the numbers it needs are asked of
    the holder

#### Unknowns


## Glossary

| Term | Meaning |
|---|---|
| Holder | The service this flow stands up: it keeps series for the projects that push to it and hands them back. |
| Series name | The name a project's series is held under — one series, one lock, one log. |
| Pool | The one bound over everything held, whoever it belongs to. |
| Reserve | The free space owed to whatever else lives on the host; below it, writes are refused as retryable. |
| Eviction | Dropping a whole series to bring the pool under its bound, least-recently-retrieved first. |
| Compaction | Collapsing a log to what it still says, leaving a fresh base of the same facts. |
| Record of discard | The single line a discarded series is replaced by, so *discarded* and *lost* stay different answers. |

---
