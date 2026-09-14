---
kind: how-to
role: [exec, pm-ba, engineer, programmer]
summary: Record a choice with the condition that would make it wrong, so its standing is derived rather than typed by whoever wrote it down.
---

# Recording a decision

**For anyone whose choices are written down somewhere that nothing checks.**

## What this solves

You have decisions recorded — in a document, a table, the results of a formal decision process.
Every one of them says `accepted`, or `locked`, or nothing at all, and that word was typed by a
person on the day it was written. Since then: no one has evaluated any of them.

A decision is a claim about the *future* — this choice will keep being the right one — so it can
go wrong quietly, long after the reasoning that produced it stopped being fresh. From outside the
record, the healthy case and the two failures are the same word:

| what your record says | what is actually true |
|---|---|
| `accepted` | the condition was checked, and holds |
| `accepted` | the condition fired in March; nobody noticed |
| `accepted` | nobody has ever checked it |

Plumb derives a decision's standing from something that ran, the same way it derives a story's —
and says it in words that fit a claim about the future instead of borrowing *proven*.

## What the board says

| word | what happened |
|---|---|
| **holding** | the condition was evaluated and has not fired |
| **breached** | a citing test ran and did not pass — the condition has fired |
| **silent** | nothing cites it at all. Nobody is watching, and that *is* the finding |
| **unwatched** | cited, and nothing ran |

A subject with several aspects gets **one line per aspect and no overall status**. That is
deliberate: the three close at different times for different reasons, and a single word for all of
them loses exactly what you asked for.

## What you need first

One thing, and it is the thing that is usually missing: **the condition that would make the choice
wrong**, written at the moment you decide, when the reasoning is freshest and nobody yet knows the
answer. Without it there is nothing to derive from and the record is a note.

## Declare the subject

A decision is declared in your [story feed](command-line.md) like any other subject — the same CSV
or JSON, pointed at by `stories` in `plumb.toml` — with three columns doing the work:

    id,lexicon,reduce,aspects
    D27,decision,worst,levers|outcome|falsifier

| column | why |
|---|---|
| `lexicon: decision` | picks the vocabulary above. The default, `story`, would say *proven* |
| `reduce: worst` | one fired condition breaches the decision whatever else holds. Stories reduce `best` — one qualifying citation is enough — and that is the wrong way round here |
| `aspects` | a decision makes several claims and each gets its own verdict. List them separated by a vertical bar, as above |

`reduce: worst` is the one people miss. Left at the default, a decision with one clause holding
and one fired reads as **holding**, because best-of picked the clause that passed.

## Cite it from a test

With `informs`, not `proves` — a decision is never *done*:

    @pytest.mark.informs("D27", about="falsifier")
    def test_no_free_input_level_breaches_the_budget():
        ...

In Java:

    @Informs(value = "D27", about = "falsifier")

`about` names which aspect the test bears on. There is **no depth** on an `informs` citation:
depth is a claim your run can refute, and a depth claim about a decision would be authored and
uncheckable.

## What it will not do

- **It never fails your build.** A breached decision informs. What a breach costs you is yours to
  decide, exactly as an unproven story is.
- **It never types a status.** If nothing cites a decision, the board says **silent** — it does
  not say fine, and it does not stay quiet.

## A decision with a number in it

A threshold, a window, a limit is a decision too, and where you can state a model connecting the
value to something measurable it earns a vocabulary of its own. See
[Tracking a parameter](tracking-a-parameter.md).
