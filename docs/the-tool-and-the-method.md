---
kind: explanation
role: [exec, pm-ba, engineer, programmer]
summary: Why Plumb requires no spec and no methodology, and what to install if you want one.
---

# The tool and the method

**For anyone deciding whether adopting Plumb means adopting a way of working.**

It does not. Plumb observes a test run and derives a board from what it saw. It has no opinion about
how you plan, what you call a requirement, whether you draw process flows, or whether you keep a
specification at all. A project with nothing but citations in its test suite gets a complete,
correct board.

The clearest evidence is what `plumb init` refuses to do. It detects your language, writes a
`plumb.toml`, and deliberately writes **no spec** — no claim vocabulary, no first chapter, no
diagrams. There is no `plumb spec` command to run afterwards, because there is no artifact Plumb
expects you to produce.

## Why the tool cannot hold the method

The temptation is obvious: check that every story is described, placed on a process flow, and that
no open question is recorded in only one place. Those are good checks. They are also impossible to
ship, because to run them a tool must first decide **what a story is, where it lives, and in what
format** — and a tool that decides those things has chosen your method for you.

The same goes for any list of subjects handed to the tool as data so that the board could report
what is left to do. Such a list is a second home for subjects your own spec or tracker already
owns, it desynchronises the moment either moves, and nothing could detect that it had. So a board
answers for the subjects a run's tests cited, and for nothing else — a subject nothing cites is
absent rather than unproven, and what is left to do lives with your project.

So the rule is not *never read a file*. It is that **no artifact may be a copy of another**, and
that the tool must not require artifacts it did not observe a run produce.

## If you want a methodology, there is one

Some projects want the opposite of a blank page — particularly those that have accumulated years of
architecture decision records, design notes and half-current documents that no longer agree with
each other. For those, the methodology exists as its own product:

**[goldspec](https://plumbspec.org/gold/)** — process flows whose every step is a person's story, with what it
moves, its requirements, decisions and unknowns, and the gates that keep them honest. Installed separately, run as
`goldspec`, and entirely optional.

The two are not layered products or tiers of one thing. They answer different questions:

| | Plumb | goldspec |
|---|---|---|
| Question it answers | is this claim actually proven? | is what we wrote down still coherent? |
| Needs | a test run | a spec, in its conventions |
| Opinions about your workflow | none | many, and you opted into them |

## How the separation is kept honest

A promise in a document is worth little, so the boundary is enforced by a test in Plumb's own suite.
It reads every shipped module as source data and fails if a single one imports `goldspec`. The
methodology's own gates are delivered as **tests** you run in your suite — so Plumb observes a test
that ran and passed, exactly as it observes any other, and never learns the test was a methodology
gate. No new interface was needed for any of this, which is the sense in which the separation is
real rather than declared.

Plumb uses goldspec for its own specification. That is dogfooding across the boundary rather than
inside it: if the split were fictional, the gate would be the thing that noticed.

## What this means for you

- Adopt Plumb alone and nothing will ever ask you for a spec.
- Adopt goldspec as well and you have chosen its conventions — the checks are then yours, not
  something imposed.
- Adopting the methodology later costs nothing you did today. Citations are the only thing you write
  by hand for Plumb, and goldspec neither replaces nor rewrites them.
