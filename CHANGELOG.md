# Changelog

What each release gives you, and what to change to take it.

## 0.8.3 — `--json` keeps the series

**Fixed.** `plumb board --json --series FILE` printed the board and never wrote the history, without
a word; `--push` beside it was dropped the same way. The run is now appended, and pushed if asked,
whichever way its board is printed, and stdout still carries only the JSON board. A CI step that
ran the board a second time to keep the history can drop that step and add `--series` to the one
that prints the JSON.

## 0.8.2 — where to report

**Changed.** Vulnerability reports and proposals for a large change go to
[support.plumbspec.org](https://support.plumbspec.org), not to GitHub issues. A contribution no
longer needs a `Signed-off-by:` line; the pull request is the ask. The package links to
plumbspec.org and its source.

## 0.8.1 — the series-holder page is listed

**Fixed.** "Running a series holder" carried no front matter, so the documentation index left it
out. It is listed again, and every page is now held to the front matter the index is built from.

## 0.8.0 — a report, never a halt

### An account is your address

`plumb account open --email ADDR` hands the address to the support service, which mails you a
link; `plumb account redeem TOKEN` stores the credential it answers with. Nothing is generated on
your machine first, and there is no key to keep.

**What to change.** `plumb account create`, `export` and `show` are gone, and so are `--account`,
`--root`, `PLUMB_ROOT`, `PLUMB_PASSPHRASE`, `PLUMB_ACCOUNT` and `PLUMB_KEY_LABEL`. A push goes with
the credential its destination names, as it already did wherever no account was set up. The
`plumbspec[account]` extra is gone; nothing else needs `cryptography`. A `~/.config/plumb/account.json`
or `root` left from before is no longer read, and is yours to delete.

### An address is named where the run is

`plumb.toml` never names a destination. An `endpoint` key there is not read: the run names it and
the variable to set instead, and carries on, rather than being read on one path and ignored on
another. `series pull` now finds its holder exactly as `push` does, `PLUMB_SERIES_*` first, so a
history is read back from where it was sent.

**What to change.** Move an `endpoint` from `plumb.toml` to `PLUMB_ENDPOINT`, or
`PLUMB_SERIES_ENDPOINT` for the series alone.

**A run never halts on a setting it cannot use.** A top-level key written inside a section, an
`endpoint`, or a leftover `[tool.plumb]` in `pyproject.toml` used to stop the run with exit 2. Each
is now named on the board as `config.ignored`, and the run carries on without it.

**Fixed.** A board read with `--manifest` and `--series` no longer crashes after appending. An
unreachable service is a message from `plumb account`, and an unreadable `plumb.toml` one from
`series pull`, not a traceback. A copy pulled from one holder and pushed to another no longer
carries the first holder's *fetched from* note, so the second holder's history does not read as a
cache. `evidence.not-observed` prints its explanation and next step. `python -m plumb.series_holder`
runs the holder. Push messages name the destination rather than a support service.

## 0.7.0 — one Python, and Java 8

**One Python, not two.** Plumb needed 3.11 while your tests ran on whatever they ran on. It needs
3.9 now, so you keep one interpreter. On RHEL 9 and Ubuntu 22.04 the `python3` you already have is
enough, and you can drop the `apt install python3.11` step. `pip install plumbspec` succeeds on 3.9,
where it refused.

**Java 8.** Run a board on the JVM your tests already use, down from 17. Mutation comes with it. If
you are holding at Java 8, stay on the JUnit 5 line — JUnit 6 requires 17.

### Upgrade and carry on

Same command, same `plumb.toml`, same citations.

### Your board may read differently

**Your mutation scores can move.** Plumb now names a story's wired code for the source definition it
belongs to, so work done inside a lambda or a comprehension counts toward the function or method
holding it. A story whose tests drive that kind of code may come back with a different score.

### `plumb series` is the first module

**The one CLI can be extended without touching the core.** An installed package declaring the
`plumb.modules` entry point has its verbs mounted into `plumb`, and `plumb series` is now the first
thing to arrive that way — `plumb.cli` names none of its commands. `plumb series push` works
exactly as it did.

`plumb modules` lists what is mounted, what each one adds, which surfaces it speaks and whether it
reaches the network, so trusting a module is a decision about a list. A module that names a verb
the core owns, speaks a surface the core publishes no version of, or fails to import is named and
refused — and every other module still mounts.

**What this asks of you.** A module is discoverable only where its distribution is installed.
`pip install plumbspec` has `plumb series` as before. A source checkout run from `PYTHONPATH`, or a
zipapp run against an interpreter nothing was installed into, has no modules and `plumb series` is
absent rather than broken. Running the suite now needs `pip install -e ".[dev]"` for the same
reason.

The core publishes two versioned surfaces for a module to build against: the board, and the series
interface — which now carries a version at all, where it published none.

### `plumb support` has left the core

**It is a module now, not a core verb.** Filing, reading and answering a support case are gone
from this tool. What answers that name is a package you install like any other, mounted through
the `plumb.modules` entry point — the same mechanism `plumb series` arrived by.

An open-source tool does not carry a support desk. A core that kept shipping the verb would keep
claiming the capability, and the surviving name would go on telling adopters this project supports
them. So nothing was kept behind and there is no alias: with no support module installed, `plumb
support` is not a command this tool has, and `plumb modules` says what is mounted.

**Your records are exactly where they were.** This release moves nothing and deletes nothing — a
conversion run by the half that is leaving is one nobody could run a second time. The core no
longer writes to that directory and no longer lists it in `plumb footprint`, because that list is
what *this* tool writes. It is yours to keep or remove.

**What stayed is what a module builds on**: the transport surface, the enrolment it resolves
through, and the account that signs. A holder you run yourself must never come to depend on the
software of whoever answers a different capability.

Gone with it: `plumb support file|list|send|show|withdraw|migrate|pull|poll|turn`, the
`PLUMB_SUPPORT_*` destination variables as far as this tool is concerned, and the record contract
reference — the record is the module's now, and so is documenting it.

### `plumb footprint` names what a module writes

A module declares the places it writes, each with a disposition — whether it rebuilds itself,
whether your repository already carries it, whether it holds a credential, whether **nothing else
holds it**. `plumb footprint` prints them under a heading of their own, last, named as the
modules' and not the core's. A module that writes nothing adds no section.

This is what keeps the list honest as capabilities move out of the core. The release that hands a
capability to a module is the release the core stops naming what that capability wrote — and the
files do not stop existing. Whoever is deciding what to protect would simply stop being told, with
no error and nothing to notice.

A module whose declared writes are not footprint entries is **refused by name**, the same as one
that mounts a core verb or speaks a surface the core publishes no version of. `plumb modules`
names the same places without the dispositions.

### A destination belongs to a capability, not to the machine

`PLUMB_ENDPOINT` and `PLUMB_CREDENTIAL` named one address for everything Plumb sends, so a team
running its own series holder had to accept whoever answered that address for support as well.
Each capability can name its own now:

    PLUMB_SERIES_ENDPOINT     where run histories go
    PLUMB_SERIES_CREDENTIAL
    PLUMB_SUPPORT_ENDPOINT    somewhere else entirely, if you want

Three places are read, most specific first: the capability's own pair, the machine-wide pair, then
an enrolment file. **Nothing you have set stops working** — one address for everything is still
one line, it is just no longer the only thing you can say.

With no destination named for a capability, what it produced stays on this machine and the run
says so. There is no default address, which is what makes that a guarantee rather than a promise
about your configuration.

`transport` joins the board and the series interface as a surface a module declares the version it
speaks of, so a contributed module can send without carrying its own credential handling.

### `plumb backup` and `plumb restore` are retired

**Plumb takes no archive.** `plumb footprint` marks what is `IRREPLACEABLE` — your series, and the
support store — and you point whatever you already back up at those paths.

Taking custody meant Plumb deciding what counts as a secret, what your repository already carries
and what a restore may overwrite. Those are three policies belonging to whoever runs the machine,
on a machine that is already being backed up somehow. The story behind those verbs only ever asked
the tool to *hold the list* so that answering *what do I back up* never meant reading the source —
and holding the list is what remains.

**If you have an archive**, unpack it with `tar`: the layout is a `project/` directory and a
`plumb-backup.json` naming what was taken and what was left.

### `friction` is retired, with no replacement

`plumb support file --kind friction` and `plumb support why` are gone. Filing what rubbed against a
bar, locally, was an alpha-testing practice, and an open-source tool does not carry a support desk.
Nothing took its place.

What is left is the three shapes that address somebody else — `question`, `idea` and `report`,
which is now the default — and **no kind requires `--implication`**. State one where it helps a
reader; a record without one is no longer refused. A record you file with one is carried on the
wire whatever its kind, where it used to be dropped for every kind but friction.

The wire itself is unchanged: a support service still holds records filed as friction and older
clients still send them, and what a service accepts is the service's to narrow.

### Fixed

- **`plumb support` works on 3.9.** The record's own timestamp parser refused the `Z` it writes, so
  on the floor this release lowers to, every record was invalid at the moment it was made.
- **`plumb init` reports on the file it kept.** Run it on a project that has already declared its
  entry points and it no longer says `entry_points is empty` above a file naming two, and no longer
  opens its numbered steps with one you have taken.
- **The Java sample builds at Java 8**, so the one example you can copy compiles on the JDK the
  install page tells you to have.
- **`pip install plumbspec[dev]` resolves on 3.9.** It pinned a pytest that does not reach it.
- **`plumb footprint` names the directory your records are actually in.** It carried its own copy
  of where the store lives, and the copy went stale — it pointed at `plumb/friction`, which the
  tool stopped writing to, and honoured only the superseded `PLUMB_FRICTION_DIR`. The one command
  whose job is to say what is irreplaceable was naming somewhere that does not exist.

### Smaller things

- Plumb names a frame the same way whichever Python or JVM observed it. If you keep a series that
  spans an interpreter upgrade, the names either side of it match — across 3.11 to 3.12 they did
  not.
- The documentation was checked against the tool. The Maven classpath recipe now puts test outputs
  ahead of main, which is the order Plumb requires and Surefire uses — the old one built a
  classpath the guard refuses, and on a project without the guard it loads production
  configuration under test. Decisions and parameters are shown as the `plumb.toml` tables that
  actually configure them. The board reference spells `passed-wiring-not-verified` the way the
  board emits it. `plumb account add-key`, `plumb modules` and a spec file that never existed are
  gone from the pages that named them.

## 0.6.0 — the debugger is gone

**If you run Plumb on Java, take this one.** A second process used to watch grounding over JDWP.
Plumb now observes it inside the process where it happens, with probes it weaves into the bytecode
as your classes load. No port, no handshake, no attach, no second process, no timing.

| | with the debugger | now |
|---|---|---|
| a pilot's 1,928-test Spring Boot board | 2.3–5.4 hours | **41 seconds** |
| that board's overhead over the bare suite | — | **+1.2%** |
| a 973-test suite, bare against observed | — | 93.8/93.8, 92.4/92.1, 92.2/91.4 |
| mutation-mode observation | ~90× | **no measurable cost** |

A malformed probe fails immediately and loudly — the JVM verifies transformed bytecode as it loads —
so you get a refusal rather than a board that is quietly wrong.

### Your board may read differently

Every movement is a **correction**, and all three run one way: toward saying less where less was
known. Nothing here makes a story proven that was not.

| you had | you may get | why |
|---|---|---|
| `inert` | `not-checked` | `inert` is the positive claim *no production code ran*, and may now only be made where a surface was declared **and** the instrument actually rewrote something. It used to be read from an absent hit, which an instrument that never attached produces just as well as a test that touched nothing. |
| `ungrounded` | `dispatched` | work handed to another thread that *reaches* an entry point is now seen arriving, rather than inferred from a hand-off going out. Measured: 142 hand-offs seen where the debugger saw 137. |
| `dispatched` | `grounded` | the same, from the other side. |

You do not have to remember a version to tell which side of the line a board came from. Every fact
carries the instrument that made it: the mechanism field reads `JDWP breakpoints …` before and
`bytecode probes, in process …` after. If a story moved, read the mechanism before reading the
story.

`observation.failed` now means the instrument was declared and never reached your code. On Java the
usual cause is a production class sitting under a declared test root.

### Mutation runs on the same instrument

- **The window follows the work across a hand-off.** A system that hands work to a pool runs almost
  all of it on a thread the entry point never opened. The window is carried by the work, so an
  unrelated thread running production code at the same moment records nothing. On a pilot whose
  front door is `CompletableFuture.supplyAsync(…)`, this took the scope from 6 classes to 33.
- **Each mutant is compiled once**, not once per story that scopes it. On that pilot: 3,877
  story-mutant pairs, **308 distinct**, 17 minutes where the same scope undeduplicated would have
  run about four hours.
- **The board tells a survivor nobody reached from one nobody noticed.** Scope is per method, so a
  story gets mutants on paths its tests never enter. On that pilot the reported kill ratio went from
  **38% to 71%**, and the list of things to go and fix from 205 to 109.
- **A mutant that changes nothing no longer counts against you.** Plumb stops generating them.
  `swap-return` on `return null;` produced byte-identical source: unkillable, counted as a survivor
  forever, capping a story below 100% however strong its tests became.

**The board names each survivor** — operator, `Class#method`, file and line — once each behind
`--survivors`, and the manifest carries them per story.

**`--mutation` tells you when you have declared no entry point**, and refuses with an explanation.
With no entry point there is no window, and every story came up clean without having been looked at.

**Expect your killed-out-of-total to move on both halves of the fraction.** Compare ratios only
within one version.

### Update your `--json` reader, and your classpath file

**`mutation.survivors` changed shape.** `mutation.survivors` was an **integer** — the shortfall —
and is now the **list** of named mutants. The integer is `mutation.survived`. Anything reading
`survivors` as a number now reads a list. There is also `mutation.unreached`, counting survivors no
citing test evaluated.

**And check the order of your Java classpath file.** The guard's own remedy used to say to *append*
your build's output directories, which yields `deps:classes:test-classes` while Maven's runtime
order is the reverse. Both directories carry the resources Maven copied into them, so the main
`application.properties` was shadowing the test one — on a pilot that lost a test-only Flyway
location, killed a shared Spring context, and made citations read *did not pass* for tests that are
green under Surefire. The guard now checks order as well as membership and will refuse a classpath
it used to run; the remedy it prints is the whole classpath, already ordered, from your own project.

### Smaller things

- **A long run says where it has got to.** `suite running, 340s — 812/1941 tests (41%), ~27m left`,
  and the mutation phase counts its own mutants.
- **The board counts the tests it observed instead of listing them.** `--tests` restores the list.

---

## 0.5.3 — 0.5.2's Java half, which 0.5.2 did not contain

**If you took 0.5.2 for the Java fix, take this one instead.** 0.5.2 is published, signed and
verifiable, and the adapter inside it is the one the fix replaced. The Java source landed; the
compiled jar the artifact bundles is gitignored, the release host already had one built two days
earlier, and it was packaged without complaint. Everything downstream agreed with itself — the
checksum matched, the signature was good, the version was right — over the wrong bytes.

The artifact refuses to build when the jar is older than the Java it ships, and names the source
that is newer.

Everything 0.5.2's notes describe is true of this release, and was not true of that one.

## 0.5.2 — a Java board finishes

**If you run Plumb on Java, take this one.** A pilot's 1,928-test Spring Boot suite ran for over
seven hours without producing a board. The same suite now boards in **43 seconds**, against 40.7
seconds for the tests alone.

- **Plumb watches the production surface only for tests that cite something.** Grounding is only
  ever recorded against a citation, so the verdict computed for an uncited test was thrown away.
  That project has three citations and was paying for 1,928.
- **The instrument matches what the test does.** A structural test reads the artifact rather than
  running it; a behavioral test runs production code immediately. The archetype you already declare
  in `plumb.toml` picks which. An ArchUnit suite that cost 242 seconds costs 6.7.

Two defects found on the way, both of which could report something false:

- A test in the **mutation scope** could be one that never reached a declared entry point, so
  chapter 4 was mutating code no test had driven through the wired system.
- `plumb init` wrote **"still to do" notes into the config it was describing**, so a project that
  named its entry points still had a file saying it had not. The notes are printed now, not kept.

### Upgrade and carry on

`inert` means exactly what it meant, no condition code changed, and no configuration moves. If your
board was correct before it is correct now, and if it was slow it is not.

## 0.5.1 — a signing key you can actually check

**The only reason this release exists is the key.** Nothing about the tool changed; if you installed
0.5.0 and it works, it still works and it is still the same code.

The key that signed 0.5.0 and every release before it has been **withdrawn and published as
revoked**. `gpg --verify` on those releases now reports the key as compromised, and
`git tag -v v0.5.0` says the same. The signature on 0.5.0 is no longer evidence of anything.

The installer served from `plumbspec.org/install.sh` pinned the withdrawn key, so anyone installing
with `PLUMB_REQUIRE_SIGNATURE=1` was having the install refused. This release replaces it.

### Fetch the new key

- **Fetch it and re-verify.** The signing identity is now
  `208BC1279656FEEA7C2F9A1D830604D51CA7D4FB`, published at keys.openpgp.org and
  keyserver.ubuntu.com. It is a primary key, not a subkey, so a routine subkey rotation will not
  break your pin again.

      gpg --keyserver hkps://keys.openpgp.org --recv-keys 208BC1279656FEEA7C2F9A1D830604D51CA7D4FB

- **Drop the old key from your keyring if you pinned it by fingerprint.** Anything still configured
  to require the previous fingerprint will refuse this release, correctly.
- **Nothing you built or pinned needs rebuilding.** 0.5.0's bytes are unchanged and still served
  under their own version directory.

## 0.5.0 — the methodology leaves, and Plumb stops reading specs

**Plumb does not read a spec, verify one, or check against one.** Everything that did has moved out
or gone. If you adopted Plumb for the board, nothing you rely on changed. If you adopted it for the
spec gates, they are still available — as a separate product you install yourself.

### What to redo before you upgrade

- **Re-create your account.** Every one made before 0.5.0 is void — Plumb derives signing keys under
  a label now, so the same passphrase produces a different key and the receiver does not recognise
  it. Run `plumb account create` and `plumb account claim` again. Running a matrix? Set
  `PLUMB_KEY_LABEL` per leg so each derives its own key from the one secret — two legs sharing a key
  race for one counter.
- **Move a top-level `adapter` into a block of its own.** Plumb refuses a `plumb.toml` carrying both
  that and `[[adapters]]` blocks. It used to drop the top-level line silently, so a project
  declaring two languages got a board covering one. If yours has both, that refusal is why, and an
  earlier board may have been quieter than it looked.
- **Keep or delete the spec files `init --spec` wrote.** `init` writes only `plumb.toml` now. Any
  `spec/` directory it wrote before is yours and is untouched. `status.py`, `conventions.py`,
  `flowcheck.py`, `test_spec_backlog.py` and `test_spec_status_guardrail.py` are yours to keep, edit
  or delete. If your project is not Python, deleting them is the point.
- **`plumb spec` is gone.** Those gates ship as **goldspec** now — a separate product, its own
  version, installed and run on its own:

      curl -fsSL https://plumbspec.org/gold/install.sh | sh
      goldspec <spec-directory>

It is optional and Plumb never asks whether you have it. If you ran `plumb spec check` against a
spec in goldspec's conventions, that is the replacement and the checks are unchanged.
- **`plumb catalogue` is gone, and nothing replaces it.** It derived what a release changed by
  diffing two story *feeds*, and the feed is gone: a set of subjects handed to us is a copy of a
  list your project already owns, stale the moment yours moves. If you used it for a changelog, that
  is yours to write now.

### New

- **Three condition codes, and two fire on stories whose tests are green.** `grounding.not-wired`
  and `grounding.inert` name a cited subject whose citations *passed* and which is still unproven —
  the first because nothing it ran reached the wired system, the second because nothing it ran
  touched the implementation at all. `structural.executed` is the same for a structural subject
  whose citing test executed production code. Nothing changed status: these were already unproven,
  and the board simply carried no reason. If you consume `--json`, a check treating an empty
  `conditions` list as *no problem here* will now see an entry, and that entry is the point.
- **Condition prose resolves offline.** `evidence.none`, `evidence.failed` and `aspects.per-aspect`
  used to be emitted with `what`, `next_step` and `example` present and empty. If you built a lookup
  table of your own, delete the workaround.
- **`plumb session`** — open from a cursor, close by measuring the session against the board.
  Opt-in; nothing else in the tool depends on it.
- **A refused `session wrap-up` changes nothing.** The gate is held before the board is run and
  before anything is written, so a refusal costs you the time it takes to read it. It used to run
  the board, append to your series and write the cursor *first*.
- **`plumb account`** — an identity nobody has to issue, derived from a passphrase rather than
  stored, so an ephemeral CI host can be handed a string instead of a file. `account show` answers
  whether it can still sign, offline.
- **Two channels.** `stable` is what an unqualified install gives you; `edge` is the candidate,
  published so it can be tested before it is recommended. Both pointers are signed.

## 0.4.1 — a spec written by `plumb init --spec` could not run

If you had:

    ModuleNotFoundError: No module named 'flowcheck'
    !!!! Interrupted: 1 error during collection !!!!

re-run `plumb init --spec`.

## 0.4.0 — the series, decisions and parameters

- **`plumb series`** — a history beside the board: when a subject last changed, when it was last
  looked at, and which subjects move most. Kept locally, and optionally pushed to a holder without
  the run depending on it.
- **Decisions** — record a choice together with the condition that would make it wrong, and its
  standing is derived rather than typed. One running past its own condition, or one nobody has
  looked at in a year, shows up instead of reading as settled.
- **Parameters** — a threshold or a window is a decision with a number in it. Where you can state a
  model and a measurement for it, its standing derives too — **supported**, **unvalidated**,
  **refuted**.
- **Subjects that are never *done*** — cite one with `informs` instead of `proves`, and it derives
  in its own words: **holding**, **breached**, **silent**, **unwatched**.
- **Aspects** — a subject may make several claims and gets a verdict for each, with no aggregate to
  collapse them.
- **`unproven` now says which kind it is** — `evidence.none` when nothing cited it,
  `evidence.failed` when a citing test ran and failed, `evidence.not-observed` when it was cited and
  nothing ran. They were one row before.
- **A declared set, handed over as data** — CSV or JSON, read by the core, so the board shows what
  is **left** beside what is proven. This is the only way to get that in a language whose spec your
  test runner does not execute.
- **`plumb board --scope`** — one board, scoped to one namespace.
- **`plumb manifest migrate`** — carries an older manifest forward; the chain reaches two majors
  back.

## 0.3.10 — two defects the suite could not see

- A test session that dies while **collecting** — an import error in one test file — used to be
  reported as a healthy run in which nothing was proven. It exits **2** now, because a board that
  could not be derived is a different thing from a board with nothing on it.
- The artifact could not ground a project that shares its own package name.

## 0.3.9 — a Java run no longer needs a Python test framework

## 0.3.8 — a run that observed nothing exits non-zero, and the codes are documented

- **A run that discovered no tests now exits 3** with `observation.none`, where it used to print an
  empty board and exit **0**. This is the difference between a CI step that passes when it saw
  nothing and one that fails, so it is worth checking before you upgrade.
- You can look the return codes up, and a check holds the documentation equal to the tool.

## 0.3.7 — the Java adapter runs on a JVM that is not the build host's

- The adapter ships at a **declared** bytecode floor, Java 17, so the JDK that built it no longer
  decides what yours must be.
- A broken Plumb install no longer presents as a broken project.
