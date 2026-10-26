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

A run that changed nothing appends one line — a marker that the run happened, which is what *last
looked* is read from — and no transitions. Without `--series` nothing is written: a board that
quietly grew a store would make asking a question a mutating operation. With `--json` nothing is
appended either; add `--series` to a text board, which can be rendered from a saved manifest
(`plumb board --manifest m.json --series series.jsonl`) without running the suite again.

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
history:

    discarded 1–214 at 2026-08-01T00:00:00Z — compacted

**What compaction keeps.** A holder compacts the copy it holds (see [Running a
holder](running-a-series-holder.md)); your local file is never compacted. A compacted history keeps,
for every fact, the time it **last changed**, and keeps the **last run marker**, so *when did this
last change* and *when did anyone last look* still have their answers. What it drops is the changes
in between — so after compaction `changes` reads lower than it did, and `--subject` shows the latest
state of each test rather than every step it took to get there.

**A copy says it is a copy.** Once a holder has accepted from your series, or once you have pulled
one, `show` says so before anything else:

    cache of https://holder.example/series/acme-api, seq 1–4 — derived, not a second opinion

The point is not hierarchy, it is having something to correct *toward*: two files that both answer
*when did this break* and neither of which admits to being derived cannot be read at all.

**Your own file becomes a cache the moment a holder accepts from it.** That is what the label means:
from then on **the holder's copy is the history**, and the file you write to on every run is a local
working copy of it. Your file can still be the *longer* of the two — it carries runs you have not
pushed yet, and a holder keeping your history under a bound compacts and discards ranges your file
still holds — and it is still not a second opinion: where the two differ, the holder's is the one you
correct toward, and the extra runs in yours are history the holder has not been given yet. The banner
names the holder when the file knows it: a copy written by `plumb series pull` records where it came
from, while your own file only knows that a holder accepted from it, and says `cache of a holder that
keeps the history`.

**Each store numbers its own records.** A holder renumbers what it accepts onto its own sequence,
and compacting rewrites a store's numbering, so `seq 1–4` on your file and `seq 1–4` on the holder's
copy need not be the same records, and a `discarded` range is in the numbering the store that
discarded it had at the time. A pulled copy keeps the holder's numbering. Compare two copies by what the records say
— subject, test, when — never by sequence number. What both still hold says the same thing: the
holder appends exactly what it was sent, in the order it was sent. Where they differ it is in what
each holds — a range one has compacted, runs the other has not been given, or a repeat the holder
was sent twice (see [Committing the history](#committing-the-history)).

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

## Committing the history

**Commit the series file.** Footprint marks it irreplaceable — nothing else holds a run that was not
recorded — and `plumb session wrap-up`, when `series` is declared in `plumb.toml`, ends by naming it
among the files to commit. Committed, your repository carries it and every clone has it.

The cost is merges. The file is append-only, so two branches that each append to it conflict when
they come back together, and there is no merging two histories: every line carries a sequence
number, so a file holding both sides' lines reads without complaint, counts changes wrongly, and its
numbers no longer say what has been sent. Keep one side, and the other branch's runs are gone from
it. That is cheap when one branch writes the history — one person, sessions on the main line. Where
many branches or every CI build would append, do not commit it: git-ignore it, push it to a holder
instead (below), and point your backup at it, because a rule about tracked files will no longer
cover it.

**Keep `<series>.sent` with the series.** Beside the file, a push writes one number: how far this
file has been handed to a holder, in the file's own numbering. Commit it if you commit the series,
git-ignore it if you ignore the series, and let it survive wherever the series survives. Losing it
loses no record — the next push simply sends the whole history again — but a holder appends what it
is sent, so the repeat is stored, and `changes` on the holder's copy counts every re-sent transition
twice until the holder compacts it. A project that never pushes never writes one.

## Keep it somewhere that survives

The awkward case is CI, which is exactly where the questions matter most — it is the one machine
nobody warmed up — and exactly where a file does not survive the run. **A series is a file a run
appends to, so on an ephemeral runner there is nowhere for it to live by default.** That is a
decision you have to make before you can adopt this at all, so here it is with the costs rather
than left to you:

| where | what it costs |
|---|---|
| **commit it from CI** | every CI run writes to your repository, and parallel branches conflict on a file that is append-only by design |
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
and safe.

**Where it goes is set by the environment of the run.** A push sends to the series destination,
taken from the first of these that answers:

1. `PLUMB_SERIES_ENDPOINT` and `PLUMB_SERIES_CREDENTIAL` (and optionally `PLUMB_SERIES_SUBJECT`)
2. the machine-wide `PLUMB_ENDPOINT` and `PLUMB_CREDENTIAL` (and optionally `PLUMB_SUBJECT`)
3. an enrolment file — `--enrolment FILE`, else `$PLUMB_ENROLMENT`, else
   `~/.config/plumb/enrolment.json`.

An endpoint and a credential count only as a pair; one without the other is skipped. With none of
them, nothing is pushed and the history stays on this machine. `series pull` finds its holder the
same way, so a history is read back from where it was sent. `plumb.toml` never names an address:
an `endpoint` key there is refused by name.

The request carries one secret: the credential, as a bearer token. Nothing is signed and there is no
account key. The endpoint is the holder's **base URL**, and the client sends to
`<endpoint>/series/<subject>`. **Set the subject before the first push** — `subject = "acme-api"` in
`plumb.toml`, or `PLUMB_SERIES_SUBJECT` — or the push stops and says so; the destination's subject wins
where both are set. A holder you run yourself accepts lowercase letters, digits and hyphens. A test name describes behaviour, so what leaves on a run is the shape of
your product, and it is worth looking at before the first push.

**See it before you send it.** `--dry-run` prints what would go over the wire and sends nothing — how
many records, then each one as a line of JSON: the origin stamp, every transition with its subject,
test name, result and grounding, and the run markers. It needs no destination and no subject, so you
can read it before setting either:

    plumb series push series.jsonl --dry-run

Worth reading once before the first push from any machine.

`pull` takes the file to write, and `--subject` on it means **which store to ask for** — not the
subject id it means on `series show`. Two sibling subcommands, one flag, two meanings: check which
one you are running before you reach for it.

Without `--project`, `pull` reads the subject from the project that owns the directory it is
writing into — the nearest `plumb.toml` at or above it. `plumb series pull ../restored.jsonl` run
inside a project therefore asks under the *parent* directory's subject, or none. Pass `--project .`
when the file goes somewhere outside the project.

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
