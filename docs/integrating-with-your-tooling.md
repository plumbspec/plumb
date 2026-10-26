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

Each step below is set up once.

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

The whole recipe, as one job. It runs every step whatever the one before it said, and decides at
the end — so a red test still gets you a board:

    # 0. Start clean. A reused workspace must not publish an earlier run's files as this one's.
    rm -rf artifacts && mkdir artifacts

    # 1. Your test runner, for the red/green build. Plumb does not give you this.
    pytest && tests=0 || tests=$?             # or: mvn test, gradle test

    # 2. Plumb: one run, the JSON for your tooling and the manifest it was derived from.
    plumb board --json --emit-manifest artifacts/manifest.json > artifacts/board.json \
        && board=0 || board=$?

    # 3. Only if step 2 derived a board: a text board for the log, from the saved manifest. No
    #    second run. --project . so it checks ids against your `specs` exactly as step 2 did.
    if [ "$board" -eq 0 ]; then
        plumb board --manifest artifacts/manifest.json --project .
    fi

    # 4. Only if step 2 derived a board: keep artifacts/board.json and artifacts/manifest.json
    #    as build artifacts (your CI's upload step, conditioned on board == 0).

    # 5. Now decide. Red tests fail the build; so does a board that could not be derived.
    [ "$tests" -eq 0 ] && [ "$board" -eq 0 ]

The `&& x=0 || x=$?` form records an exit code without stopping the script, including under the
`set -e` most CI shells run with. On GitHub Actions, the same shape is two steps with
`continue-on-error: true` and a last step that checks both outcomes; on GitLab, `after_script` or a
final job reading both.

What each step is for:

- **Your runner gives the red/green.** `plumb board` exits `0` when a test fails — a failed test is
  a complete observation whose answer is no, and it shows up on the board as `evidence.failed`. So
  the build's pass/fail comes from your runner's own exit code, not from Plumb's.
- **`--json` and `--emit-manifest` combine.** The JSON goes to stdout and nothing else does; the
  runner's output, the `python: …` line and `manifest → …` go to stderr. Redirect stdout only.
- **Gate on Plumb's exit code, never on `status`.** `0` means a board was derived, `2` that it could
  not be — bad configuration, or a test session that never finished, such as a module that fails to
  import — and `3` that the run observed no tests at all. Fail the build on `2` and `3`, which is
  what step 5 does.
- **Clear the artifacts first, and publish only on `0`.** On `2` there is no board: `board.json` is
  empty, and Plumb removes any file at the `--emit-manifest` path before it starts, so a failed run
  leaves no manifest rather than the last one. On `3` the JSON is a board of nothing. Neither is
  worth uploading as this run's answer.
- **Re-rendering is free.** `--manifest` reads the file and runs nothing, so the text board in the
  log, and any later `--json` you need, costs no second test run. On its own it needs no
  `plumb.toml` and no checkout; with `--project .` it reads your `plumb.toml` for `specs`, so the log
  board names an id outside your namespaces (`spec.orphan`) exactly as the run's JSON does. Without
  it, the two would disagree.
- **Read `board_version` before anything else** in whatever parses `board.json`, and refuse a number
  you do not know — see step 3.

**Your suite runs twice** — once under your runner, once under Plumb's observer — and Plumb has no
way to give you the first run's answer, because its exit code deliberately ignores test failures. If
the second run costs more than you want on every push, run step 2 on fewer triggers (the main branch,
or nightly) rather than dropping step 1.

**Do not fail the build on unproven.** It sounds like rigour and behaves like a broken window: a
spec whose stories are all unproven on the day it is written is correct and exits `0`, so a gate on
status goes red the day the spec lands, stays red while the work is done, and the team's fix is to
stop running it. What you want red is `2` and `3` — the build could not answer, which is a real
failure and one nobody can see any other way.

If you want a regression gate — *this was proven last week and is not now* — that is a question about
history, and the board cannot answer it. See step 4.

## 3. Read the board into your tracker

Parse [the JSON](consuming-the-board.md). Per story you get `status`, a human `label`, the depth rungs
it `achieved`, and `conditions` explaining why.

`entered_through` on each piece of evidence names the entry point a test came in through. It is
worth reading if you declare entry points at more than one altitude: `entry_points` is a single flat
set, so an entry point you declare for one subject counts for every subject, and this is what tells a
test that came in at your outermost entry point from one that entered at a subsystem entry point
declared for something else.

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
- **`mutation` may be `null`**, meaning *not asked* — the opt-in was off, or the story was not
  proven and so was not mutated. Never a pass.
- **A subject with aspects reads `status: unproven` whatever its aspects say.** It has no single
  status, and the field is held there so a consumer reading only `status` is never shown a green
  nobody earned. Read its `aspects` instead.

## 4. Keep a series for the questions a board cannot answer

A board is one run and is amnesiac on purpose. *When did this break, what keeps moving, when did
anyone last look* need a history:

    plumb board --series history.jsonl

It records what **changed**, so an unchanged run appends only a one-line marker that it happened.
That is what keeps it small and what makes a regression gate cheap — you are reading transitions,
not diffing snapshots. `--series` is written with the text board and not with `--json`, so in the
recipe above put it on step 3: `plumb board --manifest artifacts/manifest.json --project . --series
history.jsonl` records the same run.

**Where to keep it in CI.** A CI runner usually starts empty, and a series is a file each run
appends to, so it needs a home that outlives the runner. The default we recommend:

- **Record the history from one place only — your main branch** — not from every branch and pull
  request. Branch runs are previews; a history fed by all of them interleaves runs of different
  code and conflicts on every merge.
- **If you run a holder, let it be the history.** Keep the series file *and* its `.sent` mark
  between main-branch runs wherever your CI keeps state, and add `--push`. A CI cache is enough
  here: losing it loses nothing the holder has, and costs one full re-send — the holder stores the
  repeat, so `changes` on its copy reads high until it compacts. The holder is then the
  copy that matters, and `plumb series pull` reads it back anywhere.
- **If you do not, commit it from the main branch** — the one place the append-only file does not
  conflict — or keep it at your desk with [sessions](command-line.md#plumb-session) and leave CI
  without one.

[A history beside the board](a-history-beside-the-board.md#keep-it-somewhere-that-survives) weighs
every option and what each costs, and has the shapes a history takes and what they mean.

## 5. Re-run after you upgrade Plumb

A board is derived from a run, and a saved board or manifest is a record of the Plumb that made it —
`rendered_by` on the board, `version` on each observer. After an upgrade, derive a fresh board rather
than comparing against one the previous version wrote; if the instrument changed, its `mechanism`
says so. Plumb's own cache is kept per version (`plumb footprint` shows where), so nothing it keeps
carries across an upgrade.

## What this will not do

- **It will not close your tickets.** Plumb answers whether the code does what a story says; whether
  that means *done* is a judgement your process owns.
- **It will not tell you what to work on next.** The board says what is proven, not what is
  important.
- **It will not accept a status you want to set.** There is nowhere to write one. That is the point:
  a status nobody can type is a status nobody has to trust.
