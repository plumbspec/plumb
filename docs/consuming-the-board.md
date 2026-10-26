---
kind: reference
role: [programmer, devops]
summary: The JSON document `plumb board --json` emits, field by field, for the tooling that parses it.
---

# The board, as JSON

`plumb board` prints the text board for a person to read. `plumb board --json` emits instead one
JSON document on stdout and nothing else — the runner's own output goes to stderr — and that
document is the documented, versioned format for tooling. This page is its shape.

If you are wiring Plumb into a tracker or a pipeline rather than looking up a field, start at
[Integrating with your tooling](integrating-with-your-tooling.md) and come back here for the exact
names.

## The document

    {
      "board_version": 3,
      "rendered_by": "0.8.1",
      "rendered_at": "2026-10-26T18:44:15Z",
      "observers": [
        {"adapter": "plumb-python", "version": "0.8.1",
         "runtime": "CPython 3.13.5", "mechanism": "sys.settrace (per-thread call tree)"}
      ],
      "observed_tests": 4,
      "conditions": [],
      "stories": {
        "APP-1": {
          "status": "proven",
          "label": "proven",
          "achieved": ["e2e"],
          "conditions": [],
          "aspects": null,
          "mutation": null,
          "evidence": [
            {"test": "tests/test_a.py::test_main", "depth": "e2e", "result": "passed",
             "grounding": "grounded", "entered_through": ["myapp.cli:main"],
             "reached_outside_entry": false,
             "when": "2026-10-26T18:44:15Z", "ref": null, "about": null}
          ]
        }
      },
      "unlocks": [
        {"code": "unlock.mutation",
         "what": "1 stories are proven, and nothing has checked that their tests assert anything",
         "next_step": "run mutation over them to find a test that runs the code without checking it",
         "example": "plumb board --mutation — off by default because it is slow, …"}
      ]
    }

| Field | Type | Meaning |
|---|---|---|
| `board_version` | int | The shape of **this document**. Read it before anything else and refuse a number you do not know. It is versioned apart from the manifest, because the two change for different reasons |
| `rendered_by` | string \| null | The Plumb that wrote **this document**. `board_version` says the shape and nothing about the producer, so this is what dates a file you are holding. `null` where the caller did not supply one — the core is handed its version rather than reading one, so it stays language-blind |
| `rendered_at` | timestamp \| null | When the document was written. **This is render time, not measurement time** — see `when` on each piece of evidence for the second |
| `observers` | list | Which instruments produced the facts — `adapter`, `version`, `runtime`, `mechanism`. A board may carry several: two facts are comparable only when the same kind of observer made them. Empty means none was reported |
| `observed_tests` | int \| null | How many tests the run collected, whether or not any cited anything — counted before your own `-k` or `-m` filters, so a run filtered down to nothing still reports what it collected, exits `0`, and reads `evidence.not-observed` on each cited story. **`null` is *not reported* and must not be read as none** |
| `conditions` | list | What the **run** says about itself, as condition objects. This is where *nothing was observed* lives — there is no story to hang it on. `spec.orphan` appears here once when any story id is outside `specs`, and also on each such story |
| `stories` | object | One entry per cited subject, keyed by story id |
| `unlocks` | list | What this run has earned the right to suggest next. Derived from the run, not advertised |

## A story

| Field | Type | Meaning |
|---|---|---|
| `status` | string | `proven`, `passed-wiring-not-verified` or `unproven` — spelled exactly like that, hyphenated and lower case, never the prose form a reader sees. A fourth value, `not-passed`, is the outcome of a single citation that did not pass; the gate uses it when it combines citations and turns it into `unproven` with `evidence.failed` before anything is emitted, so no subject carries it today. Accept it rather than failing on it. A subject with aspects is **always** `unproven` here — see `aspects` |
| `label` | string | The word a reader sees. Derived from `status` plus a condition already carried — never a second status. For an ordinary story it is the status itself; a subject declared `decision` in `[lexicon]` reads `holding`, `silent`, `breached` or `unwatched`, and one declared `parameter` reads `supported`, `unvalidated`, `refuted` or `unmeasured`. Where the vocabulary has no word for a state, the label is the status |
| `achieved` | list | The depths claimed by citations that **passed** and that the run **did not refute**. A `wiring` claim whose test never reached an entry point (`depth.unsupported`) is left out; an unrecognised depth such as `wirring` is not a wired rung, so nothing refutes it and it is listed as written. Not the status: a story can read `unproven` with `["unit"]` |
| `conditions` | list | Why it reads as it does, as condition objects |
| `aspects` | object \| null | Per-aspect verdicts where a subject has more than one, keyed by aspect name; each carries `status`, `label` and `conditions`. **This is where such a subject's answer is.** It has no overall status, so its own `status` is held at `unproven` with `aspects.per-aspect` — a consumer that reads only `status` is never shown a green no aspect earned. **`null` means the only one there is**, which is every ordinary story |
| `mutation` | object \| null | `total`, `killed`, `survived`, `unreached`, and `survivors` — one `{operator, where, file, line, reached}` per mutant no citing test noticed; `reached` is `null` from the Python adapter. **`unreached` is `null` — not reported — whenever any survivor's `reached` is `null`** (every Python run with a survivor) or a survivor went unnamed; `0` would claim every survivor was reached. **`mutation: null` means not asked** — the opt-in was off, or the story is not proven and so was not mutated. Never a pass |
| `evidence` | list | The citations behind the verdict |

## A condition

Conditions appear on the run and on each story, and have the same shape:

| Field | Meaning |
|---|---|
| `code` | Stable, and **the only part that is a promise**. Key your tooling off this |
| `what` | The diagnosis. May be reworded between versions |
| `next_step` | What to do about it. May be reworded |
| `example` | What that looks like. May be reworded |

## A piece of evidence

| Field | Meaning |
|---|---|
| `test` | The test, spelled the way its runner spells it. **Not a join key** — it is built from a path and a name, so it moves when a test is renamed |
| `depth` | The rung this citation claims at |
| `result` | `passed`, `skipped`, or `failed` |
| `grounding` | `grounded`, `ungrounded`, `inert`, `untouched`, `not-checked`, or `dispatched` |
| `reached_outside_entry` | `true` when this test also ran production code no entry point reaches, `false` when it did not, `null` when the adapter did not report it. Set on **every** piece of evidence, grounded or not; it is what explains `grounding.reached-outside` only on **grounded** evidence (and only from a test that passed). On ungrounded evidence it is no news: the test's own `grounding` already says it never came in through an entry point |
| `entered_through` | **Which declared entry points this test came in through**, outermost — where it arrived, where `grounding` says only that it reached the wired system. A test that enters at your outermost entry point and reaches a subsystem entry point on the way names the outer one. `null` is *not reported* (an adapter below manifest major 9); `[]` means it entered by none |
| `when` | When **this fact was measured**, which is not when the board was rendered. A board can carry facts from several runs, so a document-level time would be a false claim for all but one of them. `null` is *not reported* and must not be read as now |
| `ref` | **Your own key, carried untouched.** You mint it, you own it, you join on it; Plumb neither mints nor parses one. `null` if the citation set none |
| `about` | Which aspect this citation is about. `null` means the only one |

## Exit codes

| Code | Meaning |
|---|---|
| `0` | A board was derived |
| `2` | It could not be derived |
| `3` | The run observed nothing |

**The exit code is about whether the observation happened, never about whether anything is proven**
— and never about whether a test failed. [Integrating with your
tooling](integrating-with-your-tooling.md#2-run-it-in-ci-and-gate-on-the-right-thing) has the CI
recipe built on it.
A correct spec whose stories are all unproven on the day it is written exits `0`. If your pipeline
fails on unproven, it will go red on that day and stay red, and the fix people reach for is to stop
running it.
