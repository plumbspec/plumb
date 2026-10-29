---
kind: reference
role: [programmer, devops]
summary: Every key `plumb.toml` is read for, what it does and what it defaults to.
---

# Configuration

**For programmers and DevOps** who need to know what a `plumb.toml` key does.

`plumb.toml` is the one file Plumb reads about your project, whatever its language. `plumb init`
writes a first one; this page is every key it can hold.

**Where it is read from.** The directory you run in, or the one `--project DIR` names. Plumb does not
search parent directories. Every relative path in the file is relative to the file's own directory,
not to where you ran the command. With no `plumb.toml` at all, a run still happens with every
default below. A `[tool.plumb]` table in `pyproject.toml` is not read; the run names it, tells you to
move it here, and carries on.

**Top-level keys go above the first `[table]`.** In TOML a key written after a `[header]` belongs to
that table, so `specs = […]` appended at the end of a file that ends in `[python]` is a setting of
`[python]`. When `specs`, `production`, `sources`, `entry_points`, `mutation`, `subject` or `adapter`
is written inside a table, Plumb names the key and runs without it — the board carries
`config.ignored` and says which. A key this page does not list is not read.

**Nothing in this file stops a run except a file that cannot be read at all**: invalid TOML, an
unknown `adapter`, `adapter` beside `[[adapters]]` blocks, or a list key given something other than a
list of strings. Those leave no board (exit `2`). Everything else that cannot be used is named on
the board, and the run carries on.

## Top-level keys

| Key | Default | What it is |
|---|---|---|
| `adapter` | `"python"` | which language adapter runs your tests: `"python"`, `"java"` or `"dotnet"`. Not allowed beside `[[adapters]]` blocks |
| `production` | `[]` | the code you are proving — not your tests, not your libraries. Python: paths to the directories (or files) holding it. Java: package patterns such as `"com.acme.orders.*"`. .NET: assembly names such as `"Acme.Orders"` or `"Acme.*"`. With none declared, grounding cannot run and passing stories read `passed-wiring-not-verified` |
| `entry_points` | `[]` | the few places a real request enters your system. Python: `"module:function"`, the module named as your code imports it. Java: `"com.acme.Api#handle"`. .NET: `"Acme.Orders.Api.Handle"`. With none declared, grounding cannot run |
| `sources` | same as `production` | where the source files behind `production` live. Read only by Java mutation, which mutates the `.java` files under the first entry. The Python adapter ignores it |
| `mutation` | `false` | run mutation on every board. `--mutation` turns it on for one run; nothing turns it off for one run |
| `specs` | `[]` | your story-id namespaces — see [below](#specs) |
| `subject` | none | the name your run history is pushed and pulled under. Needed before the first `plumb series push`, unless `PLUMB_SERIES_SUBJECT` or `PLUMB_SUBJECT` is set. A self-run holder accepts lowercase letters, digits and hyphens |
| `series` | none | the history file `plumb session` brackets and appends to. `plumb board` does not read it — it takes `--series FILE` |
| `cursor` | `".plumb/next-session.txt"` | where `plumb session` keeps the handoff between two sessions |
| `repos` | `["."]` | which working trees `plumb session` checks are committed |

`endpoint` is **not read**: the run names it on the board (`config.ignored`) and carries on. Where
history is sent is named in the environment of the run —
`PLUMB_SERIES_ENDPOINT`, `PLUMB_ENDPOINT` or an enrolment file — never in the project. See
[Environment](command-line.md#environment).

### `production` and `entry_points`, side by side

They answer different questions and are spelled differently, and mixing them up is the commonest
first-run mistake:

| | `production` | `entry_points` |
|---|---|---|
| answers | *which code is mine?* | *where does a request come in?* |
| how many | all of it | a handful |
| Python | a **path**: `["src/orders"]` | a **module and function**: `["orders.cli:main"]` — not `src.orders.cli` |
| Java | a **package pattern**: `["com.acme.orders.*"]` | a **class and method**: `["com.acme.orders.Api#handleRequest"]` |
| .NET | an **assembly name**: `["Acme.Orders"]` | a **type and method**: `["Acme.Orders.Api.Handle"]`, a nested type as `Outer+Inner` |

A test **grounds** when its execution runs under one of the entry points; production code is what
Plumb watches for. Declaring a function as an entry point because a test calls it makes that test
ground without proving anything — [Testing depth](testing-depth.md#choosing-a-depth-honestly)
says why the list should stay short.

### `specs`

    specs = ["ORD", "OPS"]

The prefixes your story ids start with. A story id that starts with none of them carries
`spec.orphan`, on its own row and once for the run, so a mistyped namespace — `PAY-1` in a project
whose ids are all `ORD-…` — is named rather than read as a real story.

- **It is a prefix match on the id as written.** `"ORD"` also matches `ORDER-7`, and a typo *inside*
  the namespace — `ORD-1O5` for `ORD-105` — matches and is not caught.
- **`plumb init` does not write it.** With no `specs`, no id is ever an orphan.
- **An id you declare in `[aspects]`, `[reduce]` or `[lexicon]` is never an orphan.** Those are
  usually your decisions and parameters — `D27`, `RETRIES` — whose ids follow no story namespace.
  Naming one in a table is the project declaring it, which is what the check asks for, so it is not
  read as a typo. An id cited and declared nowhere still is.
- **A board rendered from a saved manifest checks this only when told the project** —
  `plumb board --manifest FILE --project DIR`. See [the command line](command-line.md#how-they-intersect).
- **It changes no status.** An orphan is still derived like any other story; the condition is there
  so you look at the id.

`--scope NS` on `plumb board` uses the same prefix match to narrow the view.

## `[python]`

| Key | Default | What it is |
|---|---|---|
| `interpreter` | discovered | the Python your tests run under, relative to the project or absolute. Without it Plumb uses, in order: an active virtualenv (`$VIRTUAL_ENV`), `.venv/bin/python` in the project, `venv/bin/python` in the project, and finally the Python running Plumb. Each run prints the one it chose on stderr: `python: /path/to/python` |
| `marker` | `"proves"` | the pytest marker name your citations use, for a project that already cites requirements under its own name. `informs` is always read too. When no test cites the configured marker but tests carry other markers with a string argument, the run names them and suggests this key |

## `[java]`

| Key | Default | What it is |
|---|---|---|
| `tests` | **required** | the compiled test classes to discover tests from, e.g. `"target/test-classes"`. A list for modules that compile separately |
| `classpath_file` | none | a file holding your test classpath, written by your build — see [Getting started](getting-started.md#one-extra-step-for-java) |
| `classpath` | none | the classpath itself, as `java -cp` takes it. Joined ahead of `classpath_file`, then `$PLUMB_JAVA_CLASSPATH`. Your test classpath has to come from one of the three |
| `check_classpath` | `true` | compare the classpath against what your build declares and refuse a run that differs. `false` turns the check off |
| `plumb_classpath` | none | where Plumb's own Java classes are, for running from a source checkout. An installed Plumb supplies them itself |
| `work` | Plumb's cache | the directory for the run's own scratch files. Defaults to the per-project directory under `~/.cache/plumb/runs/` |

## `[dotnet]`

| Key | Default | What it is |
|---|---|---|
| `tests` | **required** | the test project's built assembly, as `dotnet build` leaves it, e.g. `"tests/Acme.Tests/bin/Debug/net8.0/Acme.Tests.dll"`. Plumb runs it where it is and never writes there |
| `check_runtime` | `true` | refuse a run whose output is missing an assembly its `deps.json` declares, or holds an older build of a project it references. `false` turns the check off |

The .NET adapter observes through the CLR Instrumentation Engine your test SDK already restores, so
it runs where Microsoft ships that engine: Windows x86, x64 and arm64, Linux x64 and macOS x64.

## Tables keyed by story id

These four say how to judge a subject — something no run can observe. Each is keyed by the id your
tests cite, and silent about every id it does not mention. An entry for an id nothing cites does
nothing. Every run prints, on stderr, each entry that changed what it would otherwise have reported:

    stories: D27 declares reduce='worst' in plumb.toml, overriding 'best' from the run

| Table | Values | Default | What it is |
|---|---|---|---|
| `[archetypes]` | `"behavioral"`, `"structural"` | `"behavioral"` | how the story is proved — by running the code, or by reading it. See [What to expect](what-to-expect.md#a-test-that-runs-nothing-can-still-prove-something) |
| `[aspects]` | a list of names | none | the parts of a decision or parameter that are judged separately. A subject with aspects has no single status |
| `[reduce]` | `"best"`, `"worst"` | `"best"` | how several citations combine. `best`: one qualifying citation is enough, which is right for a story. `worst`: one failure decides, which is right for a decision |
| `[lexicon]` | `"story"`, `"decision"`, `"parameter"` | `"story"` | the words the board says the status in |

An id holding anything but letters, digits, `-` and `_` is quoted: `"REQ.4" = "structural"`. [Recording a
decision](recording-a-decision.md) puts the last three together.

## More than one language: `[[adapters]]`

    specs = ["APP"]

    [[adapters]]
    adapter      = "python"
    production   = ["src/app"]
    entry_points = ["app.cli:main"]

    [[adapters]]
    adapter      = "java"
    production   = ["com.example.app.*"]
    sources      = ["src/main/java"]

    [adapters.java]
    tests          = "target/test-classes"
    classpath_file = "target/plumb-classpath.txt"

Each block takes `adapter`, `production`, `entry_points` and `sources`. Its language table goes
**under the block** as `[adapters.python]` or `[adapters.java]`; a top-level `[java]` is not read
once you use blocks. Everything else — `specs`, `mutation`, `subject` and the tables keyed by
story id — stays at the top level and applies to the whole project. A top-level `adapter` line beside
blocks is refused. [The command line](command-line.md#more-than-one-language-in-one-repository) says
how the two runs combine.

## See also

- [Getting started](getting-started.md) — the keys you need first, in order
- [The command line](command-line.md) — the options that sit beside these
- [Writing a citation](writing-a-citation.md) — the other thing you write
