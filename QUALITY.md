# Checking the documentation is true

Whether the pages still describe the tool. Run it when a change alters what they assert; a release
is when that gets remembered, not what it is for.

## 1 · Build it from the page

Three to five agents, each in a fresh context, each given a made-up subject and told to produce what
the product produces — a chapter that passes the gate, a project whose board comes back green.

- They may not read `src/` or `tests/`.
- At least one may not read the worked example.
- They draft to completion, run the gate **once**, and keep that output. That run is the
  measurement. Iterating to green afterwards is not.
- Every finding carries a quotation: file, line, the words followed. Or "not documented", and where
  they looked.
- Conditions differ between them: default configuration and an awkward one, the common path and the
  least-travelled, entry at the README and entry at the tutorial.

Record the first-run fault count for each, and what the pages told them.

## 2 · Page against tool

Three directions:

- documented and gone
- present and undocumented
- documented and changed — transcripts, version numbers, output samples

Where a claim has one home in the source, it belongs in the suite rather than in this pass.
`tests/test_docs_match_the_tool.py` and goldspec's `tests/test_docs.py` hold flags, subcommands,
condition and exit codes, the Maven recipe, the board's status strings and the schema numbers. Read
those first; what they cover is done.

By hand: prose with nothing in the source to pin against.

## 3 · Adversarial pass

One agent, with source access. Extract every checkable claim — the tool does this, refuses that,
accepts this spelling — and run each one against a scratch fixture. Read the source to form the
hypothesis, run the tool to confirm it, and label a claim that was only reasoned about.

Aim it at sentences claiming to be exhaustive: *this is the whole list*, *every flag*, *checked by*.
Enumerate the source against each.

This pass is what finds a check that cannot fail. The other two cannot: a writer never trips one,
and a comparison against the source sees a setting that is read.

## Acting on it

- Reproduce each finding before fixing it.
- **Every finding a test could hold becomes a test in the same change.** Bite it against the
  unfixed source first.
- Rounds stop when findings stop blocking — when a writer reports a fact obtained by analogy rather
  than a chapter that failed.

## When to run it

A floor moves · a format or vocabulary changes · a command is added, renamed or removed · a default
moves · a check's answer changes.

Not for a refactor, a performance fix or a dependency bump.

Product-neutral: it reads the same for goldspec as for Plumb.
