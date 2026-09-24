# lex · say it in the reader's words

**Last updated** 2026-09-24 v2

What somebody implementing a story does about the gap between the words it is written in and the
words the code will use. A story is in its audience's language, because it is their process. An
implementation needs names that survive a second audience arriving with different ones. Both are
right, and the mapping between them is the work — it is why one programs to an interface, and it
is why the label on a field is not the field.

Entered from [dev06 · do the work](developer-day.md); the words the chapter itself uses are settled
in goldspec's [sha · share a word across owners](../../goldspec/spec/diagrams/sha-share-a-word-across-owners.md),
which is the other half and is about two specs rather than a spec and its code.

```mermaid
flowchart TD
    IN([<b>START</b> · a story in its audience's words, and a<br/>technology that will serve more than one]):::terminal

    NAME[<b>lex1</b> · name the thing in words<br/>that outlive any one audience]:::process
    BORROWED{<b>lex2</b> · is that name<br/>one audience's word?}:::question
    LEAK[/<b>REFUSED</b> · the core speaks one audience's language,<br/>and the next one renames it/]:::bad

    EDGE[<b>lex3</b> · carry each audience's<br/>word at the boundary]:::process
    FIND[<b>lex4</b> · keep the story findable<br/>from the code that serves it]:::process

    OUT([<b>END</b> · one implementation, each audience reading<br/>its own words, and a trace through both]):::good

    IN --> NAME --> BORROWED
    BORROWED -->|it is theirs| LEAK
    BORROWED -->|it outlives them| EDGE --> FIND --> OUT

    classDef terminal fill:#eef0ee,stroke:#52514e,color:#0b0b0b;
    classDef process fill:#e9eef5,stroke:#2a78d6,color:#0b0b0b;
    classDef question fill:#fdf3d8,stroke:#b8860b,color:#0b0b0b;
    classDef good fill:#e2f2e2,stroke:#0ca30c,color:#0b0b0b;
    classDef bad fill:#f7e4e4,stroke:#b02a2a,color:#0b0b0b;
```

**Decision `lex-D1` — the durable name goes inside and the audience's word goes at the edge.**
Renaming a concept in an implementation costs every call site, every test and every neighbouring
system that reads it; renaming a label costs one string. The asymmetry decides which of the two
words is allowed to be wrong later, and it is the one that is cheap to change.

## Nodes

### lex1 · name the thing in words that outlive any one audience

> **As somebody implementing a story I want the names inside the code chosen for how long they will
> be true, so that a second business unit arriving with its own vocabulary is a day's work at the
> edge rather than a rename of everything.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| lex1-inf1 | In | `story.wording` | yes | authored |
| lex1-inf2 | In | `audience` | yes | authored |
| lex1-inf3 | Out | `implementation_name` | yes | derived |

#### User Requirements
  * lex1-ur1 - the name is chosen for how long it stays true, and not for who asked for the work
    first
  * lex1-ur2 - one name is used at every call site inside, so changing it later is one decision
    rather than a negotiation

#### System Requirements
  * lex1-sr1 - the implementation keeps one vocabulary across its own modules; a name that differs
    between two of them is two concepts or one mistake, and nothing downstream can tell which

#### Non-Functional Requirements
  * lex1-nfr1 - renaming a concept inside costs every call site, every test and every neighbouring
    system that reads it, where renaming a label costs one string — which decides which of the two
    is allowed to turn out wrong
  * lex1-nfr2 - the story is still the authority on what the thing *is*; this is a naming decision
    and never a licence to implement something the story did not describe

#### Unknowns
  * lex1-u1 - how anybody recognises a name that will outlive its audiences before the second one
    arrives is undecided; the ones that failed were obvious only afterwards

---

### lex2 · is that name one audience's word?

> **As somebody implementing a story I want a name borrowed from whoever asked first to be caught
> before anything is built on it, so that the cost of the borrowing does not fall on whoever
> arrives second.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| lex2-inf1 | In | `implementation_name` | yes | lex1 |
| lex2-inf2 | In | `audience.words` | yes | observed |
| lex2-inf3 | Out | `durable_name` | optional | derived |
| lex2-inf4 | Out | `borrowed` | optional | derived |

#### User Requirements
  * lex2-ur1 - a name that is one audience's own word is named as such before code is written
    against it
  * lex2-ur2 - a word the audience happens to share with the trade is not a borrowing; what makes
    one is that the audience could change theirs and the code would then be wrong

#### System Requirements
  * lex2-sr1 - the comparison is against the words that audience actually uses, gathered from them,
    and never against a list of terms somebody believes are domain-specific

#### Non-Functional Requirements
  * lex2-nfr1 - a borrowed word is discovered when the second business unit arrives, which is the
    most expensive moment available: the code is written, the tests cite it, neighbouring systems
    read it, and the rename has become a negotiation between two customers rather than a decision
  * lex2-nfr2 - the same word meaning two things in two business units is the harder case and looks
    like agreement — *done*, *closed*, *approved* — so it is read fluently and wrongly by both

#### Unknowns

---

### lex3 · carry each audience's word at the boundary

> **As somebody who reads what this system produces I want it to say what I would say, so that I
> can act on it without translating out of somebody else's trade.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| lex3-inf1 | In | `durable_name` | yes | lex2 |
| lex3-inf2 | In | `audience.words` | yes | observed |
| lex3-inf3 | Out | `boundary_word` | yes | derived |

#### User Requirements
  * lex3-ur1 - each audience meets its own word where it meets the system — the label, the
    description, the field a consumer reads — and never the implementation's
  * lex3-ur2 - adding an audience adds words at the boundary and changes nothing inside, which is
    the whole return on having named the inside durably
  * lex3-ur3 - two audiences may give one implementation name two different words, and that is
    ordinary

#### System Requirements
  * lex3-sr1 - one boundary word stands for exactly one implementation name: an audience may not
    be shown one word for two things, because it leaves them unable to say which they mean
  * lex3-sr2 - the boundary is the only place an audience's word appears; a core that reads one has
    taken the borrowing back

#### Non-Functional Requirements
  * lex3-nfr1 - an audience reading the implementation's words translates on every reading, and the
    ones who get fastest at it stop noticing — which is when they begin reporting the technology's
    word back as their own and the two vocabularies quietly merge
  * lex3-nfr2 - the boundary is where a mistake is visible and cheap; a wrong label is argued with
    by whoever reads it, and a wrong internal name is argued with by nobody

#### Unknowns
  * lex3-u1 - whether a boundary word belongs to the interface's version or moves independently of
    it is undecided; a renamed label is not a breaking change to a program and may be one to a
    person

---

### lex4 · keep the story findable from the code that serves it

> **As anybody reviewing whether this was built I want to get from the story to the code and back
> without either of them being renamed to match, so that two vocabularies do not cost us the
> trace.**

#### Information

| Information | IO | Description | Required | Provenance |
|---|---|---|---|---|
| lex4-inf1 | In | `boundary_word` | yes | lex3 |
| lex4-inf2 | In | `story.id` | yes | authored |
| lex4-inf3 | Out | `traceable_implementation` | yes | derived |

#### User Requirements
  * lex4-ur1 - the code serving a story can be reached from the story, and the story from the code,
    while the two go on using different words for the same thing
  * lex4-ur2 - nothing is renamed to make the trace work — that is the failure this flow exists to
    avoid, arriving from the other direction

#### System Requirements
  * lex4-sr1 - the link is the citation a test already carries; no second document is written to
    hold the mapping

#### Non-Functional Requirements
  * lex4-nfr1 - a mapping kept as its own document is a third home for a fact that already has two,
    and it drifts from whichever of them moves first — usually the code, silently
  * lex4-nfr2 - without the trace, a reviewer holding a story and a file cannot tell a faithful
    implementation under a different name from an unfaithful one, and the safe-looking response is
    to make the names match

#### Unknowns
  * lex4-u1 - whether a boundary should also say which story it serves is undecided; it would make
    the trace readable at the edge and would put a spec identifier into shipped surface

## Glossary

| Term | Meaning |
|---|---|
| Audience | A group who reads what the system produces and shares a working vocabulary. Not a department: the unit is shared language |
| Implementation name | What a thing is called inside, chosen to outlive any one audience. The name every call site uses |
| Boundary | Where the system meets an audience — a label, a description, a transfer object's field. The only place an audience's word appears |
| Boundary word | What one audience calls a thing, at the boundary that serves them. Two audiences may have two for one implementation name |
| Borrowing | An implementation name taken from one audience's vocabulary. Works until a second audience arrives, and then costs a rename of everything |
| Provenance | The fifth column of an Information table: where an input came from, or how an output was made |
| Authored | Written by a person. An input nothing produces, or an output somebody typed |
| Derived | Computed by this step from what it took in |
| Observed | Read off a run, a tree or the world as it stands |
