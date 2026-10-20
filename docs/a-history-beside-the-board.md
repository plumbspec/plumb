---
kind: how-to
role: [engineer, programmer, devops]
summary: Keep a history alongside the board, so you can answer when something broke, how often it moves, and when anyone last looked.
---

# A history beside the board

**For anyone who has looked at a red row and wondered how long it had been red.**

## What this solves

A board is a snapshot of one run, and it is built that way on purpose: the manifest is unlinked
before every run so that a stale one can never answer for a run that failed. That is the right
trade, and it costs you every question with a *when* in it.

| question | a board | a series |
|---|---|---|
| is this proven **now**? | yes | — |
| **when** did it stop being proven? | no | yes |
| how **often** does it move? | no | yes |
| when did anyone last **look** at it? | no | yes |

The last one is the one people are surprised by. *Last changed* and *last looked at* are
different facts, and a subject nobody has run in six months is not the same as one that has been
steady for six months — but they read identically on a board.

## Keep one

A series is opt-in and is never a side effect of asking for a board:

    plumb board --series series.jsonl

Nothing is written when nothing changed, which is the ordinary case. A board that quietly grew a
store would make asking a question a mutating operation.

## What it shows you

    plumb series show series.jsonl

    subject                     last changed          last looked           changes
    ORD-2                       2026-08-26T19:03:41Z  2026-08-26T19:03:41Z        3
    ORD-1                       2026-08-26T19:03:30Z  2026-08-26T19:03:41Z        1
    ORD-3                       2026-08-26T19:03:41Z  2026-08-26T19:03:41Z        1

Ordered by **changes**, most-moved first, because that is the column you came for. Each row answers
a different question and the three are independent:

- **last changed** — when this subject's fact last became something new. Silence here is stability.
- **last looked** — when a run last *observed* it at all. Silence here is not stability, it is
  absence: nobody has asked. A subject whose *looked* is old is not steady, it is unwatched.
- **changes** — how many transitions this subject has ever had. `1` means one observation and no
  movement since. Reading the two timestamps together is what makes the number mean anything.

Read the three rows above as a reader would:

- **ORD-2, changes 3** — it has moved three times, most recently just now. Something about this
  claim is unsettled.
- **ORD-1, changes 1, changed earlier than looked** — seen in every run since and never moved.
  This is what settled looks like, and it is the only row here you can stop thinking about.
- **ORD-3, changes 1, changed and looked at the same moment** — brand new. It has one observation
  because it has only ever had one run, not because it is stable.

**ORD-1 and ORD-3 both read `changes: 1` and mean opposite things.** The timestamps are what tell
them apart, which is why both columns are printed rather than a single "last seen".

If part of the history has been compacted away, `show` prints the discarded range **before the
table and never as a footnote** — a reader who scrolls past it would read the rest as the whole
history.

**A copy says it is a copy.** Once a holder has accepted from your series, or once you have pulled
one, `show` says so before anything else:

    cache of https://holder.example/series/acme-api, seq 1–4 — derived, not a second opinion

The point is not hierarchy, it is having something to correct *toward*: two files that both answer
*when did this break* and neither of which admits to being derived cannot be read at all. A cache is
not necessarily the shorter one — a holder keeping your history under a bound discards ranges it
once held, so your local file can be the longer of the two without being a second opinion. They
never disagree about a range they both hold.

**A history that cannot show where it began says so, above the count:**

    history of UNKNOWN EXTENT — this file carries no origin stamp, so it cannot show whether it
      is the whole history. A count below is a floor, never a total.

A series is stamped once at creation, so a file carrying no stamp was not created by a board — it
was restored from a partial copy, cut by a hand-edit, or written before stamping existed. None of
those is a short history, and reporting one as short is how a lost fortnight becomes a confident
`changes: 1`.

## Reading one subject

    plumb series show series.jsonl --subject ORD-2

      2026-08-26T19:03:30Z  passed · grounded         tests/test_orders.py::test_refunds
      2026-08-26T19:03:41Z  failed · grounded         tests/test_orders.py::test_refunds
      2026-08-26T19:03:41Z  passed · ungrounded       tests/test_orders.py::test_refunds

Oldest first, one line per transition, each carrying the **result** and the **grounding** together.
That pairing is the point. This subject broke, came back — and came back `ungrounded`: the test
passes again, and on the way it stopped driving the wired system. The claim is passing and is now
being proven of less than it was.

The board does say `UNPROVEN` for it today. What the board **cannot** say is that this is a
regression: a story that was never wired and one that lost its wiring on Tuesday read identically on
a snapshot, because a snapshot only ever shows you the last line. *When it changed* is the whole
question a board is built not to answer.

A transition reading `gone` means the fact disappeared — no test cites this subject any more:

      2026-08-26T19:03:41Z  passed · grounded         tests/test_orders.py::test_places_twice
      when unknown          gone                      tests/test_orders.py::test_places_twice

A recorded event rather than a silent stop, so a deleted test cannot leave a subject reading forever
as whatever it last said. It carries no time of its own, because nothing observed it — what is known
is the run that first did not find it.

## What the shapes mean

| what you see | what it usually is | what to do |
|---|---|---|
| high **changes**, still moving | a flaky test, or a claim nobody has settled | look at the transitions — alternating pass/fail is flake, a slide in grounding is scope drift |
| high **changes**, quiet for a long time | it thrashed and then settled | nothing; the number is history, not a warning |
| `changes: 1`, **looked** long ago | nobody is running it | find out why it left the suite before trusting the row |
| `changes: 1`, **looked** just now | brand new — or a replacement for a history that was lost | check the origin stamp against the holder's; a fresh file is honestly stamped fresh |
| result steady, grounding sliding | the test still passes and reaches less of the system | the more expensive of the two, and the one a board hides |

`plumb session start` reads the same history for you and prints the subjects that have moved more
than once, so a story that has flickered for a fortnight is not read as one that just moved.

## Keep it somewhere that survives

The awkward case is CI, which is exactly where the questions matter most — it is the one machine
nobody warmed up — and exactly where a file does not survive the run. **A series is a file a run
appends to, so on an ephemeral runner there is nowhere for it to live by default.** That is a
decision you have to make before you can adopt this at all, so here it is with the costs rather
than left to you:

| where | what it costs |
|---|---|
| **commit it to the repo** | every CI run writes to your repository, and parallel branches conflict on a file that is append-only by design |
| **a CI cache** | best-effort by definition — an eviction loses the history, and the next run cannot tell that it did |
| **a build artifact** | has a retention window, and the *next* run cannot read it back, so it accumulates nothing |
| **push it to a holder** | needs credentials on the runner, and a push failure deliberately does not fail your board — so it can stop accumulating quietly |

**The last one is what this was built for**, and its failure mode is the one to set up against: check
that the history is still arriving rather than assuming it is. The first three all work, and each
trades something you should choose on purpose.

Hand it to a holder:

    plumb board --series series.jsonl --push
    plumb series push series.jsonl            # the same work, on its own
    plumb series pull restored.jsonl          # write the holder's copy to a file

Only what the holder has not already been given goes over the wire, so pushing repeatedly is cheap
and safe. Which store a run joins comes from the enrolment where it carries one, and otherwise from
`subject` in `plumb.toml`.

A **credential** — `PLUMB_CREDENTIAL` in the environment, with `endpoint` in `plumb.toml` — is
presented beside the body. A test name describes behaviour, so what leaves on a run is the shape
of your product, and it is worth looking at before the first push.

**See it before you send it.** `--dry-run` prints what would go over the wire and sends nothing:

    plumb series push series.jsonl --dry-run

Worth reading once before the first push from any machine.

`pull` takes the file to write, and `--subject` on it means **which store to ask for** — not the
subject id it means on `series show`. Two sibling subcommands, one flag, two meanings: check which
one you are running before you reach for it.

## What it will not do

- **A push failure never fails your board.** A board is derived from a run and is complete
  without the network, so an outage must not turn a build red for a reason that has nothing to
  do with your project. The consequence is worth knowing: a runner that has silently stopped
  reaching the holder looks exactly like a project that has stopped changing. If a series
  matters to you, check that it is still arriving.
- **It never computes a verdict.** A history answers *when*; it never grades. The board derives
  status from a run, and a second source of truth about done-ness is the thing this whole method
  exists to remove.
- **A history it cannot vouch for is reported as unknown, not as short.** A series is stamped once
  when it is created, and one that carries no stamp says so before it shows you any count. What it
  still cannot do on its own is notice that *your* history was evicted and replaced: a fresh file
  gets a fresh stamp, honestly, because it really is a new series. Comparing your stamp against the
  holder's is what catches that, which is why pushing is the answer to the CI case above rather
  than a cache — and why a pulled copy names the holder it came from.
