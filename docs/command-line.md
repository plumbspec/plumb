---
kind: reference
role: [programmer, devops]
summary: Every command and option, and how they cancel each other out.
---

# The command line

**For programmers and DevOps** who need the exact behaviour of a flag.

Six commands, and a handful of options. The options matter less than **how they fit together** —
most confusion comes from not knowing which ones cancel each other out.

    plumb --version
    plumb board      [--json] [--manifest FILE] [--emit-manifest FILE] [--mutation] [--survivors] [--tests] [--scope NS] [--project DIR]
                     [--series FILE [--push] [--enrolment FILE]]
    plumb series     {show|pull|push} FILE [--subject ID] [--enrolment FILE] [--dry-run]
    plumb modules                                      what is mounted, and what it reaches
    plumb init       [--project DIR]
    plumb manifest   migrate FILE
    plumb support    [--store DIR] [--enrolment FILE]  {file|list|send|show|withdraw|migrate|pull|poll|turn}
    plumb account    [--account FILE]                  {create|open|redeem|export|show}
                     create [--endpoint URL] · export [--root HEX]

---

## The shape of it

```
                        plumb
                          |
      +---------+---------+---------+---------+---------+
      |         |         |         |         |
    init      board    manifest  support   account
   set up   derive and  bring a   capture   an identity
     a         show     document    what    nobody has
   project    status    forward    rubbed    to issue

    board, in detail:

                        plumb board
                             |
                    was --manifest given?
                             |
              no  +----------+----------+  yes
                  |                     |
        run your test suite      read the manifest
        watch production code    from the file
        build a manifest                |
                  |                     |
      --mutation  |                     |   needs no project,
      --project   |                     |   no config, no run
      --emit-manifest apply             |
      ONLY here   |                     |
                  +----------+----------+
                             |
                        the gate
                  derive each story's status
                             |
                       the board
                    text, or --json
```

**The one branch that matters is `--manifest`.** Everything else on `board` hangs off which side of
it you are on.

---

## `plumb board`

Runs your tests, watches your production code, and prints what each story's status derives to.

### The options, and what each replaces

| Option | What it does |
|---|---|
| `--json` | machine-readable output instead of the text board |
| `--series FILE` | also append what this run **changed** to a series — the history a manifest deliberately is not (`ch11`). Opt-in and never a side effect: a board that quietly grew a store would make `--json` a mutating operation. Nothing is written when nothing changed, which is the ordinary case |
| `--push` | with `--series`, also send what the support service has not been given. Reports and **never fails the board** if the support service is unreachable — a board is derived from a run and complete without the network, so an outage must not turn a build red for a reason unrelated to the project. Same work as `plumb series push`, triggered here instead of separately |
| `--enrolment FILE` | with `--push`, the enrolment to send under (default `~/.config/plumb/enrolment.json`). The credential names the store it may write to, so this is also what decides *whose* series this run joins |
| `--manifest FILE` | **skip the test run** and derive from a saved manifest |
| `--emit-manifest FILE` | save the manifest this run produced |
| `--mutation` | also check the tests would notice if the code changed. In `--json`, each story's `mutation` carries `total`, `killed`, `survived`, `unreached` and a `survivors` list of `{operator, where, file, line, reached}`. **`unreached` counts survivors no citing test evaluated** — scope is per method, so a story gets mutants on paths its tests never enter, and those could not have been killed by any assertion. A ratio that mixes them answers neither question |
| `--survivors` | after the board, list the mutants no test noticed — once each, with how many stories scoped them. Off by default: a survivor sits in every story that reached its method, so printing them per story repeats one work item many times and buries the verdicts |
| `--tests` | list every test the run observed and what it grounded, instead of counting them. Off by default: on a mature suite the citing tests are a small minority, so the recital buries the verdict — the board's output should scale with the spec, not with the suite. Turn it on when a board is not what you expected and you need the per-test fact |
| `--scope NAMESPACE` | show only stories whose id begins with NAMESPACE |
| `--manifest FILE` (repeatable) | give it more than once to board several manifests together |
| `--project DIR` | read `plumb.toml` from somewhere other than here |

### How they intersect

**`--manifest` turns the run off.** With it, Plumb reads a file and renders it. No tests run, no
`plumb.toml` is read, and your project does not even have to be the current directory:

    cd /tmp && plumb board --manifest ~/saved.json     # works

That is what makes a board reproducible: the manifest is the evidence, and rendering it twice gives
the same answer twice.

**So `--manifest` cancels three other options.** `--mutation`, `--project` and `--emit-manifest`
only apply on the run path. Give `--manifest` and they do nothing.

> **Sharp edge:** `plumb board --manifest a.json --emit-manifest b.json` writes **no file** and says
> nothing about it. `--emit-manifest` is silently ignored when you are not running. If you wanted a
> copy, use `cp`.

**`--mutation` can only turn mutation *on*.** There is no `--no-mutation`. The flag is OR'd with
`mutation` in `plumb.toml`:

| `plumb.toml` | flag | result |
|---|---|---|
| `mutation = false` | — | off |
| `mutation = false` | `--mutation` | **on** |
| `mutation = true` | — | **on** |
| `mutation = true` | `--mutation` | on |

That asymmetry is deliberate. A flag that could switch mutation *off* would make the board depend on
how it was invoked, and two people running "the same" command would get different answers.

**`--scope` is a view, never a gate.** A repository can carry more than one spec — a product spec and
an operations spec, say — and `--scope OPS` shows one of them. Every story reads exactly what it reads
unscoped: scoping removes rows from your view and cannot move a status, because each story derives
from its own citations and nothing else. Narrowing to the spec that happens to look good buys you
nothing.

### More than one language in one repository

A repository can declare several adapters, each with its own production surface — a Java package
and a Python module path are not the same kind of name, so they cannot be shared:

    specs = ["APP"]

    [[adapters]]
    adapter = "python"
    production = ["src/app"]
    entry_points = ["app.cli:main"]

    [[adapters]]
    adapter = "java"
    production = ["com.example.app.*"]
    sources = ["src/main/java"]

A Java project whose modules compile separately names every root it wants boarded:

    [java]
    tests = ["scheduler/target/test-classes", "collector/target/test-classes"]

One spec can describe a system whose pieces build separately, and naming a single root would make
the board answer for part of the spec while presenting itself as answering for all of it. Each root
must also be on the `classpath` — being discovered from and being loadable are different things.

Note there is no top-level `adapter` line: once you use `[[adapters]]`, every adapter goes in a
block, including the one you started with. Writing both is **refused**, naming the conflict and what
to write — because the two forms mean different things, and a board covering one of two declared
languages reads exactly like a board covering both.

Each adapter observes its own language and produces its own manifest; the board is derived from
their **union**. Every fact carries the instrument that made it, so a board mixing a JVM adapter
with a CPython tracer is readable rather than quietly incomparable.

**A merge refuses rather than reconciles.** If two manifests carry the same story and the same test
with different facts, that is a defect in the run — not a difference to average or resolve by
order — and Plumb says so instead of picking one.

**If one adapter fails, the others still report, and the board says which language is missing**
(`adapter.absent`). A board covering two languages with one adapter down is not a smaller board; it
is a board about a different project, and it must not read as the whole answer.

**If an adapter's *instrument* never reaches your code, the suite still finishes and the board
still comes out** (`observation.failed`). The results are the results; only the wiring question went
unasked, so grounding reads `not-checked` for every citation in that language. That is not the same
silence as having declared no entry points — if you declared them, they are not the thing to go and
look at, and the code is there so the board can tell you which of the two you are in. On Java the
usual cause is a production class sitting under a declared test root, where the adapter excludes it
along with the tests.

You can do the same thing by hand with saved manifests:

    plumb board --manifest python.json --manifest java.json


### The codes it can emit

A board carries **condition codes** beside its prose. The code is the promise — a tool branches on
it, and it never changes; the sentences beside it may be reworded whenever they get clearer. The set
is finite, and this is it:

| Code | Raised when |
|---|---|
| `grounding.not-checked` | grounding could not run — no production entry points are declared |
| `grounding.dispatched` | the work went to a thread the adapter could not follow, so wiring is unknown |
| `grounding.reached-outside` | the story grounded, and the same test also ran code no entry point reaches |
| `depth.unsupported` | a citation claims it reached the wired system and its execution never did |
| `aspects.per-aspect` | it has more than one aspect, so it has no single status — read the aspects |
| `evidence.none` | nothing cites it — an absence of evidence, and the correct reading of a fresh spec |
| `evidence.failed` | something cites it, **ran**, and did not pass — the one unproven that is a *result* rather than a gap |
| `evidence.not-observed` | something cites it and **never ran** — no evidence at all, not evidence against |
| `grounding.not-wired` | every citation **passed** and none reached the wired system — proved of the implementation alone |
| `grounding.inert` | every citation **passed** without executing the implementation at all |
| `grounding.untouched` | the citing test neither ran the production artifact nor read it — `assert True` lands here |
| `structural.executed` | a structural subject's citing test ran production code, so it exercised the shape rather than reading it |
| `observation.none` | no tests were observed at all, so there was nothing to derive from |
| `observation.uncited` | tests ran and none of them cited a subject — nothing claimed yet, or citations that could not be read |
| `spec.orphan` | a story id belongs to no declared spec — outside every namespace in `specs` |
| `adapter.absent` | an adapter this project declares did not run, so a language is missing |
| `observation.failed` | the instrument was declared and never reached your code, so grounding is `not-checked` everywhere — for the instrument's reason, not yours |
| `unlock.grounding` | stories passed whose wiring was never checked — declaring entry points would gate them |
| `unlock.mutation` | stories are proven and nothing has checked their tests assert anything |

**Every code resolves to its prose in the tool itself.** A board carries `what`, `next_step` and
`example` beside each code, in the text board and in `--json` alike, and resolving them needs no
network — which matters, because a board is read most often where there is not one.

**Five reasons a subject reads `unproven`, and they want different things from you.** The status is
the same word; the code beside it is what tells you which situation you are in.

| If you see | What actually happened | What moves it |
|---|---|---|
| `evidence.none` | nothing cites it | write a citing test — or leave it, on a spec authored ahead of the work |
| `evidence.failed` | a citation ran and failed | fix the code or the claim; this is a *result*, not a gap |
| `evidence.not-observed` | a citation never ran | find out why it was skipped — no evidence is not evidence against |
| `grounding.not-wired` | the citations **passed**, and never reached the wired system | drive it through a declared entry point, or accept the depth it reaches |
| `grounding.inert` | the citations **passed** without executing the implementation at all | assert against the implementation — a test that touches nothing passes forever |

The last two are the ones worth knowing about, because the tests are green: somebody has written a
passing test and the story still does not move. An `unproven` with no reason beside it leaves the
author who has done the most work told the least, which is why the code is printed with the
status.

**A subject may say its status in its own words.** The status codes above never change — they are
what a consumer keys off (`dev07-5-2`) — but a *decision* or a *parameter* is not a story, and `proven`
is the wrong word for a claim about the future. Declare a `lexicon` in your feed and the board says
the word beside the code:

| code | `story` | `decision` | `parameter` |
|---|---|---|---|
| `proven` | proven | holding | supported |
| `unproven` + `evidence.none` | unproven | silent | unvalidated |
| `unproven` + `evidence.failed` | unproven | breached | refuted |
| `unproven` + `evidence.not-observed` | unproven | unwatched | unmeasured |

The words are derived, never authored — each comes from a status the gate computed and a condition
it carried, so nothing a lexicon says is anything the run did not. A lexicon with no word for a
state says the state's own name rather than inventing one.


**The one-liners above are for orientation, not for acting on.** Each code carries its own *what*,
*next* and *example* in the board itself, written for the situation you are actually in — read those
rather than these. What this table is for is telling you the set exists and what is in it, so a
silence you are looking at can be told from a state you have not reached.

### What it exits with

**The exit code describes the observation, never the proof.**

| Code | Means |
|---|---|
| `0` | a board was derived from a run that observed tests |
| `2` | Plumb could not produce a board at all — bad config, an unreadable `--manifest`, or **the test session never finished** (a collection error, a usage error, an interrupted run) |
| `3` | **no tests were observed**, so there was nothing to derive from |

The line worth reading twice is the first one. **Stories being UNPROVEN is exit `0`.** So is a
failing test. Proof happens at your desk, not in CI, and a spec you wrote this morning is
all-unproven and green on purpose — a tool that failed your build for that would be enforcing a
workflow rather than checking a proof.

Your test runner already has an exit code for a failing suite, and it is a better one than Plumb
could give you. Run it.

`3` exists because the other two could not tell you the difference between these:

    $ plumb board --json        # a healthy project, nothing cited yet
    { "observed_tests": 38, "stories": {}, "conditions": [] }

    $ plumb board --json        # a broken classpath, finding no tests at all
    { "observed_tests": 0, "stories": {}, "conditions": [{"code": "observation.none", ...}] }

Both print an empty board, because an empty board is exactly what a correct first run looks like.
The first is fine. The second means your runner never found your tests — and if you have wired
`plumb board` into CI, that is the one case where a green step would be lying to you.

**`2` and `3` are different failures, and the difference matters.** `3` is a run that *finished* and
honestly saw nothing. `2` includes a run that **never finished** — one bad import, a syntax error in a
test module, a missing `conftest` dependency, and your runner stops collecting. Zero tests were
observed either way, but only one of them looked:

    $ plumb board            # a test module fails to import
    the test session did not complete (pytest exit 2), so no board can be derived from it
    $ echo $?
    2

Left at `0` this is the most expensive kind of green: a story that proved yesterday reads UNPROVEN
today, which for a live spec is the ordinary state — nobody has written that test yet — so a
completely broken suite is indistinguishable from routine incompleteness.

A suite that *ran* and failed is a different thing entirely and still exits `0`. That is a complete
observation whose answer happens to be no, and it belongs to your test runner.

> **If you are putting this in CI:** the default is already right. `plumb board` fails the step when
> it could not observe — nothing collected, or a session that never finished — and passes it when it
> observed something, whatever the board then says about proof. You do not need to grep the log.

An adapter that cannot report how many tests it saw emits `observed_tests: null`, and Plumb will
**not** exit `3` on it — silence is not evidence of an empty run. Both shipped adapters report it.

### Putting them together

    plumb board                                   # the normal case
    plumb board --mutation                        # slower, deeper — see what-to-expect.md
    plumb board --emit-manifest run.json          # run, and keep the evidence
    plumb board --manifest run.json               # re-render that evidence, anywhere, instantly
    plumb board --manifest run.json --json        # …as JSON, for a tool
    plumb board --project ../other-repo           # run against a different project

**A useful pairing:** emit once, render many times.

    plumb board --emit-manifest run.json          # minutes
    plumb board --manifest run.json --json        # instant, repeatable

---

## `plumb init`

Writes your **declaration** — `plumb.toml` — guessing what it can from your layout. Nothing else, in
any language.

| Option | What it does |
|---|---|
| `--project DIR` | set up a project other than this directory |

**It never overwrites.** Run it twice and the second run reports what it kept. A file it wrote once
belongs to your project from the moment it lands.

**The declaration is the whole of it.** Which adapter, what counts as production code, where the
wired system begins. Nothing about where you write your requirements down, what you call them, or
whether you write them down at all.

**Why there is no list of subjects to point at.** Such a list is a copy of a
list you own — it goes stale the moment yours moves, and nothing here can detect that it has. So a
board answers for the subjects your tests **cite**, and says so on every run. A subject you have
written down and not cited yet is simply not on it. That is a smaller claim than the alternative,
and it is one we can keep: what is left to do lives with you, where it is current.

---


## `plumb series` — the first module

**These verbs come from a module, not from the core.** `plumb.cli` names none of them: they reach
the command line through the mount every contributed module uses, declared by the `plumb.modules`
entry point in this distribution's own metadata. Remove that entry and `plumb series` leaves the
tool without a line of the core changing.

One consequence worth knowing before it surprises you: **a module is discoverable only where its
distribution is installed.** `pip install plumbspec` has it. A source checkout on `PYTHONPATH`, or a
zipapp run against an interpreter that has not been installed into, sees no modules at all — and
`plumb series` is simply absent rather than broken. `plumb modules` says which are mounted.

The run history a manifest deliberately is not. A manifest is unlinked before every run so a stale
one can never answer for a failed one — which is right, and means *when did this break*, *which test
is flaky* and *when was this last checked* cannot be answered from it. A series is the second
artifact those need.

It records **what changed**, not what a run found. A fact that has not changed is not new
information, so an unchanged run adds no transitions at all — only a line saying the run happened.

    $ plumb board --series series.jsonl
    series: 323 transition(s) -> series.jsonl

    $ plumb board --series series.jsonl
    series: 0 transition(s) -> series.jsonl

### `plumb series show FILE`

Reads it back — the three questions above, answered from the history:

    $ plumb series show series.jsonl
    subject                     last changed          last looked           changes
    ORD-14                      2026-08-05T09:00:00Z  2026-08-05T09:00:00Z        5
    ORD-2                       2026-08-01T09:00:00Z  2026-08-05T09:00:00Z        1

**`last changed` and `last looked` are different questions**, and the difference is most of why a
series exists. `ORD-2` has not moved since the first run and was examined on the most recent one —
an unchanged subject is not an unexamined one, and a tool that conflated them would report a healthy
project as an abandoned one.

**`changes` counts runs, not records.** It is *what keeps changing* — a flakiness count stated as a
number rather than a feeling. On a fresh history every subject reads `1`, which is the honest
reading of one observation.

| Option | What it does |
|---|---|
| `--subject ID` | one subject's transitions, oldest first, instead of the summary over all of them |

    $ plumb series show series.jsonl --subject ORD-14
      2026-08-01T09:00:00Z  passed · grounded    tests/test_orders.py::test_queue
      2026-08-03T09:00:00Z  failed · grounded    tests/test_orders.py::test_queue

That is *when did this break* — a question no board can answer, because a board is one run.

**A discarded range is printed first, never as a footnote.** A reader who scrolls past it reads the
rest as the whole history:

    $ plumb series show series.jsonl
    discarded 1–214 at 2026-08-01T00:00:00Z — compacted — bounded history

**It reports and never grades.** No status, no label, no condition code. Status derives from a run,
and a history that graded anything would be a second source of truth about the same subject — the
two would disagree the first time somebody opened an old file.

### `plumb series pull FILE`

Fetches the history the holder holds for you and writes it where you say. The other half of
*custodial*: a store that cannot hand it back is holding nothing for anyone.

    $ plumb series pull recovered.jsonl
    series: pulled 324 record(s) for acme-orders -> recovered.jsonl

What lands is a series like any other, so `plumb series show` reads it.

| Option | What it does |
|---|---|
| `--subject ID` | which store to ask for; defaults to the one the enrolment names |
| `--enrolment FILE` | the enrolment to ask under (default `~/.config/plumb/enrolment.json`) |

Exits `1` when the holder has nothing for that subject, and writes no file — an empty one would read
as *nothing happened*, which is the answer this whole chapter exists to keep apart from *we no
longer hold it*.

**Retrieval is not a read-only convenience.** It is the signal eviction ranks on, so
reading your history is part of what keeps it.

### `plumb series push FILE`

Sends what the holder has not been given yet. Requires an enrolment carrying a subject — the store
that credential owns.

    $ plumb series push series.jsonl
    series: pushed 324 record(s)

| Option | What it does |
|---|---|
| `--enrolment FILE` | the enrolment to send under (default `~/.config/plumb/enrolment.json`) |

An enrolment issued before series support carries no subject, and this says so rather than guessing
one — a guessed store would file this project's history under a stranger's name.

    $ plumb series push series.jsonl
    series: not pushed — this enrolment carries no subject, so there is no store to push to

**The log is its own outbox.** Every record carries a dense, monotonic sequence, so *what has not
been sent* is a number rather than a queue. If the holder is unreachable the mark does not move
and the next push carries the backlog — nothing is lost and there is nothing to drain.

**A large backlog is split, not refused.** The first push is the biggest one a project ever makes —
it carries the whole base state, where every push after it carries a day's churn — so it is sent in
batches sized under what the holder publishes at `/spec` as `series.max_body_bytes`. Batches go in
order and the mark moves after each one, so a push interrupted halfway leaves exactly the tail that
did not arrive.

    $ plumb series push series.jsonl
    series: not pushed — holder unreachable: [Errno 111] Connection refused

Exits `0` whenever the store was readable, including when the holder was down. A board is derived
from a run and is complete without the network, so an outage must never turn a build red for a
reason that has nothing to do with the project.

---

## `plumb modules`

What is mounted, what each module adds, what surfaces it speaks and whether it reaches the network
— the list `mod2` exists to make readable, so trusting a module is a decision over what it declares
rather than a hope.

    $ plumb modules
      series 1.0.0  verbs: series (push|show|pull)  speaks: series 1  network: yes
          writes the series file named on the command line, and its `.sent` mark beside it

A module that did not mount is listed too, with the reason, rather than being missing:

    $ plumb modules
      telemetry  NOT MOUNTED — speaks `telemetry`, which the core publishes no version of

The core refuses a module that names a verb the core already owns, one that speaks a surface the
core publishes no version of or a version it cannot give, and one that will not import. **A module
that fails to import is named and every other module still mounts** — one broken extension never
costs the tool. Nothing here probes whether a module can reach what it needs: a module that cannot
is inert, and its own verbs report their own standing, because the core cannot tell a service being
down from a credential being wrong.

The surfaces the core publishes, each versioned on its own, are the **board** and the **series
interface**. A module declares the version it speaks per surface.

## `plumb manifest`

Works with a manifest a run produced. One subcommand.

### `plumb manifest migrate FILE`

Rewrites a manifest written against an older schema, in place, at the current one.

A run accepts the current major and one back — **stay within one major of the latest** is the
recommendation. This command reads **two** majors back, so the rescue path is one major deeper than
the advice and nobody is stranded until they are three behind.

**Reach for it last.** A manifest is derived from a run, and Plumb deletes any previous one before
every run, so the first answer to a stale manifest is always *re-run your suite*. This is for the
case where that run cannot be reproduced — an archived CI artifact, a decommissioned system, a
handover.

    $ plumb manifest migrate archived.json
    archived.json: schema 7 -> 9.0

Already current, and nothing is written — not one byte, so a file's timestamp keeps meaning *this
was brought forward*:

    $ plumb manifest migrate current.json
    current.json is already at schema 9.0

Below the chain there is no path, and it says so rather than naming itself:

    $ plumb manifest migrate ancient.json
    ancient.json: schema_version 3 is older than this Plumb reads (7.x, 8.x, 9.x). ...
    no migration path exists — the chain reaches back to 7.x, and a shape below it
    cannot be inferred

Exits `0` when the file is current or was brought forward, `1` when it cannot be read or has no
path forward.

---


---

## `plumb support`

Captures what rubbed while using the method. Records stay on your machine unless this installation
is enrolled.

    plumb support file --observation "…" --implication "…"
    plumb support list
    plumb support send                   # retry anything queued
    plumb support show <id>
    plumb support withdraw <id>
    plumb support migrate                # rewrite records written by an older schema
    plumb support poll                   # what the other side is waiting on from you
    plumb support turn <id> --after N    # answer, ask, or close
    plumb support pull <dir>             # operator-side: fetch what the support service holds

### A record is the start of a correspondence, not the end of one

`poll` and `turn` are the other half of filing. A record opens a **case**; after that both sides add
**turns** to it until it is done. Where the party on each end is an agent rather than a person, the
traffic is mostly questions and answers — *what depth is that story cited at* — answered from the
code by something standing next to it, so that no source ever crosses the wire.

Both are inert unless this installation is enrolled at an endpoint. With none configured they say so
and stop; nothing about the local tool depends on them.

    plumb support poll                                       # anything waiting on you
    plumb support turn <id> --after 4 --says "…"             # reply
    plumb support turn <id> --after 4 --answer q3=unit       # answer a question you were asked
    plumb support turn <id> --after 4 --answer q3=withheld   # …or decline to, which is not the same
    plumb support turn <id> --after 4 --ask "which board?"   # ask one back
    plumb support turn <id> --after 4 --close                # done; removes nothing

**`--after` is required and it is not paperwork.** It records how many turns you had read when you
composed, so a reader knows what your reply could be answering. Once both sides compose at the same
time — which is the ordinary case, not the exceptional one — two turns land next to each other
having seen different things, and position stops meaning anything. Take it from the case's `cursor`.

`--answer` takes `ASK_ID=VALUE`, and the value may be one of the absence markers. `withheld` is the
one worth knowing: it says *I have this and may not give it to you*, which routes to somebody who can
grant permission, where `unknown` routes to a different question. A blank is neither.

`--close` says you are finished and stops the other side coming back to you. **It removes nothing** —
`plumb support withdraw` is what takes the words back, and a later turn reopens a closed case.

`plumb support pull` is **operator-side**, like the support service's own `registry`. It fetches what the support service
holds into a directory, and the holder refuses it to anyone but the operator: reading the
authoritative store back is not something a contributor's credential may do. It is additive — a
record already present is left exactly as it is, because the received copy is the authority and a
local file that differs is a divergence to look at rather than something to overwrite.

> **Sharp edge — the options come *before* the subcommand.** `--store` and `--enrolment` belong to
> `support`, not to `file`:
>
>     plumb support --store /tmp/f file --observation "…"    # correct
>     plumb support file --store /tmp/f --observation "…"    # error
>

`file` requires `--observation` and nothing else. Say what shape it is with `--kind`:

    plumb support file --kind question   --observation "how do I declare an entry point in a reactor?"
    plumb support file --kind idea       --observation "the board could name the door a test came in by"
    plumb support file --kind report     --observation "the Maven classpath instructions worked first time"

**`friction` is retired, and nothing replaced it.** It was a local capture practice from alpha
testing — a list of moments to file at, and an implication to file against — and an open-source
tool does not carry a support desk. `plumb support why`, which printed that guidance, is gone with
it. No kind requires an implication now; state one where it helps a reader and leave it out where
it does not.

### The options on `plumb support file`

Everything below is optional. A record with only the two required fields is a complete record; each
of these answers a question a reader of that record would otherwise have to ask you.

| Option | What it does |
|---|---|
| `--observation` | **required** — what happened, in your words |
| `--kind` | `report` (default), `question` or `idea` — what shape this is |
| `--implication` | optional, and never required — what it means beyond what happened |
| `--story` | the story it bears on, in **your** ids (`APP-142`) — Plumb never parses it |
| `--depth` | `unit` \| `component` \| `wiring` \| `standards-integration` \| `smoke` |
| `--code` | carry the code that rubbed, as `PATH:START-END` |
| `--root` | a path root, so the location in `--code` reads relative rather than absolute |
| `--code-id` | the condition code the board surfaced, if one was |
| `--tag` | repeatable, for your own grouping |
| `--id` | override the minted id — for re-filing a record you withdrew |

`--code` is the one worth reaching for. A record carrying the lines that rubbed is resolvable a year
later; one describing them from memory usually is not.

---

### Seeing what would be sent

    plumb series push FILE --dry-run

Prints exactly what a push would put on the wire, and sends nothing. It is built by the push's own
code path, so it cannot disagree with the real thing.

Worth running once before you enable a push. On an account, the `test` and `about` fields — the two
that carry **your** names rather than facts about a run — are replaced by a keyed token before they
leave. The same test gives the same token every run, so *which subject changes most often* still
works, and the holder never holds the name. The key comes from your passphrase and never leaves
your machine; rotating a signing key does not move it, so your history stays continuous.

On a credential rather than an account there is no secret of yours to key with, so names travel as
written — and `--dry-run` says which of the two you are on.

---

## Environment

Only one value Plumb reads is a secret, and it travels on its own.

    PLUMB_CREDENTIAL   the credential every capability sends with — the only secret here
    PLUMB_PASSPHRASE   a self-provisioned account's passphrase — likewise
    PLUMB_ENDPOINT     the address every capability sends to
    PLUMB_ENROLMENT    path to an enrolment file — the escape hatch, see below

### A destination belongs to a capability, not to the machine

One address for everything is a choice between two products the moment you self-host one of them:
a team running its own series holder had to accept whoever answered that address for support as
well, because both hung off it. So each capability may name its own, and the specific wins:

    PLUMB_SERIES_ENDPOINT     where run histories go
    PLUMB_SERIES_CREDENTIAL   and what they go with
    PLUMB_SERIES_SUBJECT      which series there this credential owns

    PLUMB_SUPPORT_ENDPOINT    where records go — a different host, if you want one
    PLUMB_SUPPORT_CREDENTIAL

The name is the capability's, upper-cased, with anything that is not a letter or a digit becoming
an underscore. Three places are read, most specific first: **the capability's own pair**, then
**the machine-wide pair above**, then **an enrolment file**. One address for everything still
works and is no longer the only thing you can say.

**Both halves or neither.** An endpoint with no credential is a half-configured runner, and
answering with it would send unauthenticated and report the refusal as the service's.

**Naming none is the ordinary state.** With no destination for a capability, what that capability
produced stays on this machine and the run says so. That is what makes *nothing leaves without
being told where* a guarantee rather than a promise about your configuration: there is no default
address to forget to change.

The address is **configuration**: put `endpoint = "https://…"` in `plumb.toml` where a reviewer can
see it. Keeping it out of the secret store is what makes "which holder is this CI pushing to?"
answerable from the repository, and what lets a wrong address fail as a wrong address instead of as
a rejected credential. It also means rotating a credential does not mean re-pasting the destination.

`PLUMB_ENROLMENT` still takes a path to a JSON file, and is the right primitive where secrets
genuinely arrive as files — Kubernetes mounts, Vault templating, the `*_FILE` convention. Prefer the
variable where you have the choice: a file in the working tree can be collected by an artifact
upload, a cache action or a debug step that archives the directory, and a variable cannot.

---

## What Plumb writes, and where

So you can decide what to back up and what to carry to a new machine. Two things here are
irreplaceable; everything else is either in your repository already or rebuilt on demand.

**In your project** — your version control already carries all of it.

| Path | What it is |
|---|---|
| `plumb.toml` | your declaration — the whole of what `plumb init` may write |
| the `stories` feed | the stories you hand over, if you declared one |
| the `cursor` file | the handoff between two sessions (default `.plumb/next-session.txt`) |
| the `series` store | **irreplaceable** — every transition, losslessly. A run that was not recorded cannot be recovered from a later one |
| `<series>.sent` | how far that history has been transmitted |

**Outside your project** — the half a repository does not carry.

| Path | What it is | Keep it? |
|---|---|---|
| `~/.config/plumb/account.json` | endpoint, the public half of your account, and this key's counter. **No secret** — the identity is derived from your passphrase and is never written down | yes, but it is **shared** across every project pushing to that holder |
| `~/.config/plumb/enrolment.json` | an operator-issued enrolment, file form — **this one carries a credential** | yes; marked `SECRET` |
| `~/.local/share/plumb/support/` | support records, and an outbox of what has not reached a support service | **irreplaceable** — nothing else holds an untransmitted record |
| `~/.local/state/plumb/` | a session's opening reading, keyed by project path | no — scratch; a session that loses it is simply told its delta cannot be computed |
| `~/.cache/plumb/` | a per-version cache | no — rebuilt when missing |

Each honours its `XDG_*` variable; `PLUMB_ACCOUNT` and `PLUMB_SUPPORT_DIR` override the first and
third outright.

**The two to actually worry about** are your `series` and any untransmitted support record. The account
file matters less than it looks: everything in it except the counter rebuilds from your passphrase,
and the passphrase is the thing to keep safe — losing it loses the account, and no backup helps,
because it was never stored anywhere to be backed up.

    $ plumb footprint

prints the same list with **your** paths filled in, which this page cannot: every location honours
its `XDG_*` variable, so where your support store actually is is a property of your machine.

| Option | What it does |
|---|---|
| `--project DIR` | the project to read `plumb.toml` from |

**A mounted module adds a section of its own**, headed *added by modules*, listing what that
module says it writes. It is printed last and named as theirs, because the core stops being able to
answer for a capability the moment that capability moves out of it — and the files it wrote do not
stop existing. A module that writes nothing adds no section. `plumb modules` names the same places
without the dispositions.

This table is a view of `plumb.footprint`, which lives beside the code that does the writing. A
hand-kept list of paths stays right until somebody adds a writer, and nothing goes red when they do.

---

## Backing up — what Plumb tells you, and does not do for you

**Plumb takes no archive.** `plumb footprint` names everything it wrote and marks what is
`IRREPLACEABLE`; point whatever you already back up at those paths. That includes what mounted
modules declare, so installing one does not quietly put state outside the list.

That is a deliberate retirement. `plumb backup` and `plumb restore` existed, and taking custody of
your files meant Plumb deciding what counts as a secret, what your repository already carries and
what a restore may overwrite — three policies belonging to whoever runs the machine, on a machine
that is already being backed up somehow. Holding the list removes the reason anybody read the
source, which is all the story ever asked for.

Two things nothing else holds, so they are the two to point your backup at:

| | |
|---|---|
| your **series** | every transition, losslessly. A run that is not recorded cannot be recovered from a later one — and it commonly sits inside the project *and* is git-ignored, so a rule about tracked files will miss it |
| the **support store** | records and an outbox of what has not reached a holder yet |

A passphrase is in neither, because it is never written down: losing it loses the account, and no
backup helps.

## `plumb session`

Optional. Nothing else in the tool reads any of it, and a project that never runs these commands
loses no capability. It is worth having for one reason: it opens and closes at **the board**, so a
session is measured by what your own artifact proves rather than by what it felt like. How you spend
the time between the two readings is not something it has an opinion about.

### `plumb session start`

What the last session left, whether the ground is sound, and a reading to measure against.

    $ plumb session start
      cursor    .plumb/next-session.txt
      next      give the tool a way to answer "can this account sign?"
      ref       ado6
                CI publishes under a credential instead, so this is no longer blocking — it
                is the defect that made a day expensive.
      ground    clean
      board     117 unproven of 190
      target    ado6 is unproven

      When you are done:  plumb session wrap-up --next '…' --ref … --context '…'

It refuses nothing. A dirty tree, a missing cursor and a reference that resolves to nothing are all
*reported* — the cost of a wrong open lands on you, who can see it. There is no cursor on a first
run, and that is said plainly rather than reconstructed from the commit log: a first session and a
session that never wrapped leave identical evidence, so the tool names both instead of guessing.

### `plumb session wrap-up`

The delta since the open, and the gate.

    $ plumb session wrap-up --next 'settle ado2' --ref ado2 --context 'the JVM adapter needs it first'
      board     115 unproven of 199
      session   +2 proven since 2026-08-05T09:14:00+00:00
                + ado6
                + dev03
      cursor    set → ado2

      OK — the next session runs: plumb session start

| Option | What it does |
|---|---|
| `--project DIR` | the project to read `plumb.toml` from |
| `--next TEXT` | the single next thing (writes the cursor) |
| `--ref ID` | where it is specified — a story or an open unknown |
| `--context TEXT` | the one line the next session cannot reconstruct by reading |

The gate holds two things and no more: the work is committed, and the cursor's three fields are
filled in. It checks that they are *present*, never what they mean — `REF` is your own string and is
not resolved against anything. It does **not** require that the session went well — a delta may be negative,
because a proof that later fails un-proves its story, and a gate that demanded progress would be one
people learn to route around. Pushing is not checked either: a remote is somebody else's
availability, and a gate that fails when a network does teaches people to force past it.

Exits `1` when the gate refuses, naming each reason.

**A refused close changes nothing.** The gate is held before the board is run and before anything is
written, so a refusal costs you the time it takes to read it — no cursor written, no history
appended, no reading taken. Fix what it named and run the same command again; there is nothing to
undo first, and the board runs once rather than twice. The delta is the one thing a refusal does not
report, and it is reported by the run that actually ends the session.

### What it reads and writes

| Key in `plumb.toml` | Default | What it is |
|---|---|---|
| `cursor` | `.plumb/next-session.txt` | where the handoff between two sessions lives |
| `repos` | `["."]` | which trees a session spans — name a sibling if your work touches one |
| `series` | *(none)* | where you keep a history; declaring it is the opt-in |

The cursor is `key="value"` data. It is **parsed, never sourced** — the context field is a sentence
somebody wrote in English, and sourcing it would execute whatever punctuation that took. Keys the
tool does not know are carried through untouched, so anything your own workflow keeps there rides
along.

Where `series` is declared, the close appends the run and reports the transitions recorded since the
open — the delta says what today moved, and the history says whether today was typical. Nothing is
transmitted anywhere: appending to a local store and pushing to a holder stay separate.

---

## `plumb account`

An identity nobody has to issue you. The keypair is made here and its private half never leaves.

    plumb account create                  # generate an identity; nothing is shown to copy
    plumb account open --email ADDR       # open it at the holder; signed, never credentialled
    plumb account redeem TOKEN            # redeem a credential link; the answer comes once
    plumb account export                  # print the root, for CI or a copy of your own
    plumb account show                    # endpoint, public key, counter

`open` registers the identity at its holder: the request is **signed by the key it
registers**, because a caller with no account yet has no credential to present — that hole is
the design, not a gap in it. `--email` is the **anchor**: the address that survives losing the
machine, because it is not on the machine. `--endpoint` overrides the account file's holder.

`redeem` trades a credential link's token for the credential itself, once, and stores it where
the channel reads (`~/.config/plumb/enrolment.json`, any prior file kept beside it). The link is
spent by the answer. `--endpoint` as above. Together the two are the lost-credential path: mint a
fresh key, `open` with your anchor address, have the operator bind it to your account, `redeem`
— your cases and `filed_by` are unchanged throughout.

`create` takes no arguments and shows you nothing to write down. It generates a **root key** — 32
bytes from the operating system — writes it `0600` beside the account, and derives everything else
from it under a label: a signing key per writer, and the key your history is pseudonymised under.

**No secret crosses the terminal**, which is what lets this be one command rather than two with a
copy-and-paste between them.

`export` prints the root as one string, for `PLUMB_ROOT` in a CI secret store, or to keep a copy of
your own. Somebody who would rather this machine held nothing can export it, delete the file, and
supply it from the environment on every run — the older posture, offered as a choice rather than
imposed. Lost with no copy kept means the account is lost.

Signing needs an extra, because Plumb's runtime declares no dependencies:
`pip install 'plumbspec[account]'`. Without it, `plumb account` says so and names the repair.

> **This is being replaced.** Creation is moving to one command with no arguments, which asks for an
> address and confirms it, and the derivation is moving onto named primitives. What is documented
> here is what the tool does today.

### Running a holder

Serving is a different job, and its command belongs to whoever runs one:

    plumb-series-holder --store DIR [--reserve MIB] [--pool MIB]
                          [--compact-above RATIO] [--host HOST] [--port PORT]

**It authenticates nobody**, because it is a holder you run for yourself — there is no
second party to be told apart from, so no credential, no account, no quota per holder. What it
protects is a disk.

`--reserve` is MiB to leave free for whatever else lives on the volume. **Raise it on a shared
host.** Below the reserve the holder refuses transmissions as retryable — the producer keeps its
backlog, no board turns red, and nothing already held is discarded. Filling a shared disk is not
exceeding a quota, it is taking out the neighbours; and paying for our shortage by deleting
somebody's history would spend the custody the store exists to provide.

`--pool` is the total it may hold. `--compact-above` is how much churn a series may carry before it
is collapsed into a fresh base. See [Running a holder](running-a-series-holder.md) for what each
refusal means.

---

## `plumb --version`

    $ plumb --version
    plumb 0.5.1

A build published to `edge` between releases names the commit it was cut from — `0.5.1.dev40+5f3325a`
— so a report against one is unambiguous. A release names its version plainly.

Worth knowing because the installer resolves a channel, so you never typed a version. Include it in
any bug report or friction record — a report against an unidentifiable build costs the maintainer
the ambiguity you saved.

---

## See also

- [Getting started](getting-started.md) — install to first proven story
- [What to expect the first time](what-to-expect.md) — the surprises, with reasons
- [Running a holder](running-a-series-holder.md) — the operator's side: disk limits, refusals
- [Testing depth](testing-depth.md) — what `depth` claims mean
