# A developer's workflow

**Last updated** 2026-09-15 v10

What a developer does, from picking up work to closing it.  This is framed as an agile process, but plumb does not require any specific methodology.

```mermaid
flowchart TD
    START([<b>dev00</b> · I want to close a story]):::terminal

    TAKE[<b>dev01</b> · take a story from the sprint backlog]:::process
    ASK[<b>dev02</b> · clarify what the story means]:::process
    OPENQ{work in sessions?}:::question
    OPEN[[<b>dev03</b> · open a session<br/>▸ drills down]]:::subroutine
    PULL[<b>dev04</b> · pull the working branch]:::process
    TEST[<b>dev05</b> · annotate and write the tests]:::process
    WORK[<b>dev06</b> · do the work]:::process

    RUN[[<b>dev07</b> · run plumb — the proving pipeline]]:::subroutine
    JUDGE{is the proof what the story needs?}:::question
    CONF[<b>dev08</b> · update the plumb configuration]:::process
    COMMIT[<b>dev09</b> · commit, naming the story]:::process
    MORE{more to do on this story?}:::question

    CLOSEQ{is a session open?}:::question
    CLOSE[[<b>dev10</b> · close the session<br/>▸ drills down]]:::subroutine
    PUSH[<b>dev11</b> · push and open a pull request, naming the story]:::process

    DONE([<b>END</b> · the story closes with derived proof rather than on authored status]):::good

    START --> TAKE --> ASK --> OPENQ
    OPENQ -->|yes| OPEN --> PULL
    OPENQ -->|no| PULL
    PULL --> TEST --> WORK --> RUN --> JUDGE
    JUDGE -->|"the depth or the type is wrong"| CONF --> RUN
    JUDGE -->|"not proven yet"| WORK
    JUDGE -->|yes| COMMIT --> MORE
    MORE -->|yes| TEST
    MORE -->|no| CLOSEQ
    CLOSEQ -->|yes| CLOSE --> PUSH
    CLOSEQ -->|no| PUSH
    PUSH --> DONE

    classDef terminal fill:#eef0ee,stroke:#52514e,color:#0b0b0b;
    classDef process fill:#e9eef5,stroke:#2a78d6,color:#0b0b0b;
    classDef subroutine fill:#e9eef5,stroke:#2a78d6,color:#0b0b0b;
    classDef question fill:#fdf3d8,stroke:#b8860b,color:#0b0b0b;
    classDef good fill:#e2f2e2,stroke:#0ca30c,color:#0b0b0b;
```

The story's status should not be typed anywhere. It is named in the commit, the pull request and the
merge, and whatever holds the backlog reads it from there.

## Nodes

### dev00 · I want to close a story

> **As a developer I want to finish a piece of work and have it shown to be finished, so that what
> I hand over is complete rather than asserted.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| dev00-inf1 | In | The team's list of what is in flight — a sprint backlog, a story board, whatever the team keeps | yes | authored |
| dev00-inf2 | In | A repository the team works in | yes | authored |
| dev00-inf3 | Out | A merged change, and a board showing the story proven | yes | derived |

#### User Requirements

  * dev00-ur1 - A story with an identifier the team already uses
  * dev00-ur2 - Somewhere the team records what is in flight
  * dev00-ur3 - Somewhere to ask what a story means

#### System Requirements

  * dev00-sr1 - A version control system with branches and pull requests
  * dev00-sr2 - A test runner the language supports
  * dev00-sr3 - Plumb installed, and its adapter for that language

#### Non-Functional Requirements

  * dev00-nfr1 - Running plumb costs about what running the tests already costs
  * dev00-nfr2 - Nothing in the flow writes a status anybody could have typed

#### Unknowns

---

### dev01 · take a story from the sprint backlog

> **As a developer starting work I want to take the next thing the team agreed on, so that what I
> build is what was asked for rather than what I noticed.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| dev01-inf1 | In | `sprint_backlog` | yes | authored |
| dev01-inf2 | Out | `story.id` | yes | derived |

#### User Requirements
  * dev01-ur1 - A story id from the team's own list

#### System Requirements

#### Non-Functional Requirements
  * dev01-nfr1 - Plumb does NOT decide what is on that list or the order.

#### Unknowns

---

### dev02 · clarify what the story means

> **As a developer holding a story I want its ambiguities settled before I write anything, so that I
> am not building my own reading of it.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| dev02-inf1 | In | `story.id` | yes | dev01 |
| dev02-inf2 | Out | `clarified story` | yes | authored |

#### User Requirements
  * dev02-ur1 - Stories will split, merge, be inserted, and renumbered.
  * dev02-ur2 - Automatically update identifiers.

#### System Requirements

#### Non-Functional Requirements
  * dev02-nfr1 - An identifier opens with its flow's sigil and number; node segments are
    bare numbers, because position already says *node*; row segments carry their kind —
    inf, ur, sr, nfr, u
  * dev02-nfr2 - Each number is left-padded to the width its own largest member needs, so a plain sort
    puts them in order without tooling. A series numbered no higher than 9 uses one digit; adding a
    tenth member takes the whole series to two digits and rewrites every one of them. The key stays
    as short as it can be.
  * dev02-nfr3 - An identifier written as an example is spelled without a prefix, so that a rewrite
    of real identifiers cannot reach it

#### Unknowns
  * dev02-u1 - Amending a shared specification is not something one developer does alone, and nothing
    here says who agrees to it

---

### dev03 · open a session

> **As a developer returning to work I want to be told where the last session stopped and whether the
> ground moved, so that I am not re-reading my own repository to work out what I was doing.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| dev03-inf1 | In | `config.cursor` | yes | authored |
| dev03-inf2 | In | `config.repos` | yes | authored |
| dev03-inf3 | In | `story.id` | yes | dev01 |
| dev03-inf4 | In | `board` | optional | dev07 |
| dev03-inf5 | Out | `cursor` | yes | derived |
| dev03-inf6 | Out | `tree_state` | yes | derived |
| dev03-inf7 | Out | `reading` | optional | observed |
| dev03-inf8 | In | `config.series` | optional | authored |

#### User Requirements
  * dev03-ur1 - the loop is optional, and nothing else may come to depend on it
  * dev03-ur2 - an absent cursor is reported, never reconstructed from the commit log

#### System Requirements
  * dev03-sr1 - the mechanism ships; where the cursor lives and which trees a session spans are the
    project's own declaration

#### Non-Functional Requirements
  * dev03-nfr1 - opening reports and refuses nothing — a dirty tree is an ordinary way to leave a
    machine mid-thought

#### Unknowns


---

### dev04 · pull the working branch

> **As a developer about to write code I want the branch current, so that what I prove is proven
> against what everybody else already has.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| dev04-inf1 | In | `clarified story` | yes | dev02 |
| dev04-inf2 | Out | `working_tree` | yes | derived |

#### User Requirements
  * dev04-ur1 - reconcile changes to story citations

#### System Requirements
  * dev04-sr1 - plumb needs a working directory

#### Non-Functional Requirements
  * dev04-nfr1 - plumb only writes the configuration; the session cursor; and a series, if the project keeps one; into the repository
  * dev04-nfr2 - plumb reduces developer workload
    * dev04-nfr2.1 - No more than a single annotation
    * dev04-nfr2.2 - Configuration that is self-descriptive

#### Unknowns

---

### dev05 · annotate and write the tests

> **As a developer I want the tests to exist before the code does, so that the work is aimed at
> something rather than described afterwards.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| dev05-inf1 | In | `story.id` | yes | dev01 |
| dev05-inf2 | In | `working_tree` | yes | dev04 |
| dev05-inf3 | Out | `test_suite` | yes | authored |
| dev05-inf4 | Out | `annotation` | yes | authored |

#### User Requirements
  * dev05-ur1 - the annotation cites a story
  * dev05-ur2 - the cited story exists
  * dev05-ur3 - an annotated test shows derived status in the board even if the test body is empty
  * dev05-ur4 - an annotation cites an id, and the id's namespace is what places it in one
    specification rather than another — which is how several specifications co-exist in one
    repository, how a typo'd id fails rather than landing beside a real one, and what a reader
    narrows a board by

#### System Requirements

#### Non-Functional Requirements

#### Unknowns

---

### dev06 · do the work

> **As a developer I want to build the thing the story asks for, so that the end-user gets their functionality.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| dev06-inf1 | In | `story.id` | yes | dev01 |
| dev06-inf2 | In | `test_suite` | yes | dev05 |
| dev06-inf3 | Out | `working_tree` | yes | authored |

#### User Requirements
  * dev06-ur1 - the work is aimed at tests that already exist

#### System Requirements

#### Non-Functional Requirements

#### Unknowns


---

### dev07 · run plumb

> **As a developer who thinks the work is finished I want the tool to say whether it is proven, so
> that *done* informs my own judgement.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| dev07-inf1 | In | `config` | yes | authored |
| dev07-inf2 | In | `annotation` | yes | dev05 |
| dev07-inf3 | In | `working_tree` | yes | dev06 |
| dev07-inf4 | Out | `board` | yes | derived |
| dev07-inf5 | Out | `manifest` | yes | generated |
| dev07-inf6 | In | `story.id` | yes | dev01 |
| dev07-inf7 | Out | `series` | optional | derived |
| dev07-inf8 | Out | `run_condition` | optional | derived |

#### User Requirements
  * dev07-ur1 - one command returns a board

#### System Requirements
  * dev07-sr1 - the proving pipeline, which this step drills into

#### Non-Functional Requirements

#### Unknowns


---

### dev08 · update the plumb configuration

> **As a developer whose proof came back at the wrong depth I want to correct what the tool was told,
> so that the answer is about my work rather than about my setup.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| dev08-inf1 | In | `board` | yes | dev07 |
| dev08-inf2 | Out | `config` | yes | authored |

#### User Requirements
  * dev08-ur1 - the board names what to correct

#### System Requirements

#### Non-Functional Requirements
  * dev08-nfr1 - an annotation alone is enough to begin; configuring is an enhancement

#### Unknowns


---

### dev09 · commit, naming the story

> **As a developer whose work is proven I want the commit to name the story, so that the proof, the
> code and the claim travel together.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| dev09-inf1 | In | `working_tree` | yes | dev06 |
| dev09-inf2 | In | `board` | yes | dev07 |
| dev09-inf3 | In | `story.id` | yes | dev01 |
| dev09-inf4 | Out | `commit` | yes | authored |

#### User Requirements
  * dev09-ur1 - the commit names the story

#### System Requirements

#### Non-Functional Requirements
  * dev09-nfr1 - the commit follows the board rather than preceding it
  * dev09-nfr2 - committing is frequent, so a working session is a sequence of proven steps

#### Unknowns


---

### dev10 · close the session

> **As a developer returning to work I want the last session to have left a cursor and committed
> its work, so that it is easy to resume where I left off.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| dev10-inf1 | In | `cursor` | yes | dev03 |
| dev10-inf2 | In | `board` | yes | dev07 |
| dev10-inf3 | In | `reading` | optional | dev03 |
| dev10-inf4 | In | `commit` | yes | dev09 |
| dev10-inf5 | In | `tree_state` | yes | dev03 |
| dev10-inf6 | In | `manifest` | yes | dev07 |
| dev10-inf7 | In | `story.id` | yes | dev01 |
| dev10-inf8 | Out | `delta` | optional | derived |
| dev10-inf9 | Out | `cursor` | yes | derived |
| dev10-inf10 | Out | `bracketed_transition` | optional | derived |

#### User Requirements
  * dev10-ur1 - the session is measured as the change in what is proven, and by nothing else
  * dev10-ur2 - a negative delta is a result, never a fault

#### System Requirements
  * dev10-sr1 - where the project keeps a history, the session is bracketed by sequence number
    rather than by differencing two summaries

#### Non-Functional Requirements
  * dev10-nfr1 - the gate is held before anything is spent or written, so a refusal costs only the
    time it takes to read it
  * dev10-nfr2 - the gate checks that work is committed and the cursor is set, never that the
    session went well

#### Unknowns


---

### dev11 · push and open a pull request, naming the story

> **As a developer who has finished I want the story named where the team will see it, so that its
> standing is read from what happened rather than typed by somebody.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| dev11-inf1 | In | `commit` | yes | dev09 |
| dev11-inf2 | In | `story.id` | yes | dev01 |
| dev11-inf3 | Out | `pull_request` | yes | authored |

#### User Requirements
  * dev11-ur1 - the story id travels in the commit, the pull request and the merge

#### System Requirements

#### Non-Functional Requirements
  * dev11-nfr1 - this flow derives status
  * dev11-nfr2 - integration with a team's story management tool is not part of plumb

#### Unknowns
  


## Glossary

| Term | Meaning |
|---|---|
| Sprint backlog | The team's own list of what is in flight. |
| Board | What plumb emits: per story, whether it is proven and how far. Not the sprint backlog. |
| Working tree | The branch as it stands on the developer's machine. |
| Annotation | The marker on a test naming the story it evidences. The whole of what plumb needs to begin. |
| Proven | Derived and checked by a run, never has to be typed. |
| Provenance | The fifth column of an Information table: where an input came from, or how an output was made. |
| Authored | Written by a person. An input nothing produces, or an output somebody typed. |
| Derived | Computed by this step from what it took in. |
| Observed | Read off a run, a tree or the world as it stands. |
| Generated | Made by a tool rather than by a person. |
| Parent | On a sub-flow's input: handed in by the chapter this one drills into. |

---

## Working notes — not part of the chapter

**Lower — inside `run plumb`, not beside it.** Everything today's chapter 0 draws as a sibling:
Observing the run · Collecting what the run did · Deciding whether it is proven · Reporting it ·
Checking the tests bite · Keeping the history. At this altitude they are one step, and they need a
parent chapter — which is today's chapter 0 minus its first three nodes.

**Same level, and therefore a duplicate.** `Working in sessions` is this flow, differing only in
carrying state between days.

**Higher — the two crossings.** The specification arrives from goldspec at `take a story`; the board
leaves at `commit` and `push`, to whatever holds the backlog.

**Not in this flow at all.** `Adoption`, `Accounts`, `The support API` — the support process.

**Steps that exist nowhere in the corpus:** take a story · pull · clarify · write the tests · do the
work · commit · push. Seven of the eleven.

**Does not survive here:** `rewrite every citation to one story` — spec maintenance, not something
done between pulling and pushing.
