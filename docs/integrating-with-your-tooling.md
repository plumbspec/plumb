---
kind: how-to
role: [devops, programmer, pm-ba]
summary: Wire Plumb into the tracker and pipeline you already run, so status arrives from a run instead of from somebody typing it.
---

# Integrating with your tooling

**For whoever owns the pipeline.** What you get: your tracker's own items carrying a status nobody
typed, derived from the build that just ran.

Plumb mints no identifiers, keeps no catalogue and has no database. That is what makes this an
integration rather than a migration — your tracker stays the system of record, and Plumb answers one
question about it per run.

## The loop

    your tracker  ──ids──▶  citations in tests  ──▶  CI runs plumb board --json
         ▲                                                      │
         └──────────────  your tooling reads it  ◀──────────────┘

Four decisions make it work, and they are all made once.

## 1. Decide what the join key is

You have two, and picking one now saves reconciling later.

**Use the tracker's key as the story id.** Simplest, and right when your tracker is where work is
already named:

    @pytest.mark.proves("JIRA-4417", depth="wiring")

The board comes back keyed by `JIRA-4417` and your tooling needs no mapping at all.

**Or keep your own ids and carry the tracker's key in `ref`.** Right when a story outlives the ticket
that happened to fund it, or when one subject is worked under several tickets over a year:

    @pytest.mark.proves("ORD-1", depth="wiring", ref="JIRA-4417")

`ref` is minted and owned entirely by you; Plumb carries it untouched and reads it never. It comes
back on every evidence entry, which is what lets you join a verdict to a ticket without Plumb holding
a second copy of your ids.

What you must not do is keep a mapping file. A second list of which test proves which ticket is the
thing the citation exists to replace, and it drifts from the day it is written.

## 2. Run it in CI, and gate on the right thing

    plumb board --json > board.json

**Gate on the exit code, never on `status`.** `0` means a board was derived, `2` that it could not be,
`3` that the run observed nothing. A spec whose stories are all unproven on the day it is written is
correct and exits `0`.

Failing the build on unproven sounds like rigour and behaves like a broken window: it goes red the
day the spec lands, stays red while the work is done, and the team's fix is to stop running it. What
you want red is `2` and `3` — the build could not answer, which is a real failure and one nobody can
see any other way.

If you want a regression gate — *this was proven last week and is not now* — that is a question about
history, and the board cannot answer it. See step 4.

## 3. Read the board into your tracker

Parse [the JSON](consuming-the-board.md). Per story you get `status`, a human `label`, the depth rungs
it `achieved`, and `conditions` explaining why.

`entered_through` on each piece of evidence names the door a test came in through. It is worth
reading if you declare entry points at more than one altitude: `entry_points` is a single flat set, so
a door you open for one subject is open to every subject, and this is what tells a test that came in
your front door from one that let itself in at a subsystem door declared for something else.

**Key your logic off `conditions[].code` and never off the prose.** The code is the promise; `what`,
`next_step` and `example` are written for a person and may be reworded between versions.

**Read `board_version` first and refuse a number you do not know.** It is the contract, and it is
versioned separately from the manifest because the two change for different reasons. A consumer that
ignores it will one day parse a shape it was not written for and report confidently wrong statuses,
which is worse than refusing.

`rendered_by` and `rendered_at` say which Plumb wrote the file and when — worth recording beside
whatever you write into the tracker, because a status is only as current as the run behind it, and a
board file on disk carries no other clue. They are the document's own two facts; `when` on each piece
of evidence is a different one, the moment that fact was *measured*.

Two fields stop a subtle class of wrong report:

- **`observed_tests` may be `null`**, meaning *not reported*. It does not mean none. A consumer that
  treats it as `0` will announce that a run saw no tests when nobody counted.
- **`mutation` may be `null`**, meaning the opt-in was off — *not asked*, not a pass.

## 4. Keep a series for the questions a board cannot answer

A board is one run and is amnesiac on purpose. *When did this break, what keeps moving, when did
anyone last look* need a history:

    plumb board --series history.jsonl

It records what **changed**, so an unchanged run writes nothing. That is what makes it small enough to
keep in the repository and what makes a regression gate cheap — you are reading transitions, not
diffing snapshots. [A history beside the board](a-history-beside-the-board.md) has the shapes and what
they mean.

## 5. Re-run after you upgrade Plumb

A tree carries working state from whichever version last wrote it, and a board derived over the last
version's state can be confidently wrong in ways nothing in its output suggests. After an upgrade,
clear the derived state and run again from a build the current version made.

## What this will not do

- **It will not close your tickets.** Plumb answers whether the code does what a story says; whether
  that means *done* is a judgement your process owns.
- **It will not tell you what to work on next.** The board says what is proven, not what is
  important.
- **It will not accept a status you want to set.** There is nowhere to write one. That is the point:
  a status nobody can type is a status nobody has to trust.
