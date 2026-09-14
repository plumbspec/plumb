---
kind: reference
role: [programmer, devops]
summary: The JSON document `plumb board --json` emits, field by field, for the tooling that parses it.
---

# The board, as JSON

`plumb board --json` emits one JSON document on stdout and nothing else. This page is its shape.

If you are wiring Plumb into a tracker or a pipeline rather than looking up a field, start at
[Integrating with your tooling](integrating-with-your-tooling.md) and come back here for the exact
names.

## The document

    {
      "board_version": 3,
      "rendered_by": "0.6.0",
      "rendered_at": "2026-08-30T17:04:12Z",
      "observers": [
        {"adapter": "plumb-python", "version": "0.6.0",
         "runtime": "CPython 3.13.5", "mechanism": "sys.settrace (per-thread call tree)"}
      ],
      "observed_tests": 11,
      "conditions": [],
      "stories": { "...": {} },
      "unlocks": []
    }

| Field | Type | Meaning |
|---|---|---|
| `board_version` | int | The shape of **this document**. Read it before anything else and refuse a number you do not know. It is versioned apart from the manifest, because the two change for different reasons |
| `rendered_by` | string \| null | The Plumb that wrote **this document**. `board_version` says the shape and nothing about the producer, so this is what dates a file you are holding. `null` where the caller did not supply one — the core is handed its version rather than reading one, so it stays language-blind |
| `rendered_at` | timestamp \| null | When the document was written. **This is render time, not measurement time** — see `when` on each piece of evidence for the second |
| `observers` | list | Which instruments produced the facts — `adapter`, `version`, `runtime`, `mechanism`. A board may carry several: two facts are comparable only when the same kind of observer made them. Empty means none was reported |
| `observed_tests` | int \| null | How many tests the run saw, whether or not any cited anything. **`null` is *not reported* and must not be read as none** |
| `conditions` | list | What the **run** says about itself, as condition objects. This is where *nothing was observed* lives — there is no story to hang it on |
| `stories` | object | One entry per cited subject, keyed by story id |
| `unlocks` | list | What this run has earned the right to suggest next. Derived from the run, not advertised |

## A story

| Field | Type | Meaning |
|---|---|---|
| `status` | string | `proven`, `unproven`, or `passed — wiring not verified` |
| `label` | string | The word a reader sees. Derived from `status` plus a condition already carried — never a second status |
| `achieved` | list | The depth rungs this subject actually reached |
| `conditions` | list | Why it reads as it does, as condition objects |
| `aspects` | object \| null | Per-aspect verdicts where a subject has more than one. **`null` means the only one there is**, which is every ordinary story |
| `mutation` | object \| null | `total`, `killed`, `survived`, `unreached`, and `survivors`. **`null` means the opt-in was off** — *not asked*, never a pass |
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
| `entered_through` | **Which declared entry points this test came in through**, outermost — the door it arrived at, where `grounding` says only that it reached the wired system. A test that enters at your front door and reaches a subsystem door on the way names the front one. `null` is *not reported* (an adapter below manifest major 9); `[]` means it entered by none |
| `when` | When **this fact was measured**, which is not when the board was rendered. A board can carry facts from several runs, so a document-level time would be a false claim for all but one of them. `null` is *not reported* and must not be read as now |
| `ref` | **Your own key, carried untouched.** Plumb mints it, owns it and reads it never. `null` if the citation set none |
| `about` | Which aspect this citation is about. `null` means the only one |

## Exit codes

| Code | Meaning |
|---|---|
| `0` | A board was derived |
| `2` | It could not be derived |
| `3` | The run observed nothing |

**The exit code is about whether the observation happened, never about whether anything is proven.**
A correct spec whose stories are all unproven on the day it is written exits `0`. If your pipeline
fails on unproven, it will go red on that day and stay red, and the fix people reach for is to stop
running it.
