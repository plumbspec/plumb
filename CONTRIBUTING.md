# Contributing to Plumb

Thanks for helping keep requirements true to the code.

## Sign your commits (DCO)

Plumb accepts contributions under the [Developer Certificate of Origin](https://developercertificate.org/)
— a lightweight affirmation that you wrote the patch or otherwise have the right to submit it under
the project's license. There is **no CLA to sign.**

Add a `Signed-off-by:` line to every commit by committing with `-s`:

```
git commit -s -m "your message"
```

This appends a line like `Signed-off-by: Your Name <you@example.com>` using your `git config`
name and email. A PR whose commits are not signed off cannot be merged.

## Ground rules

- **The spec is the authority.** `spec/` is Plumb's own gold-spec — the chapter modules plus
  `diagrams/`, run with `pytest`. Behavior changes land with the story and tests that prove them —
  Plumb traces itself with its own gates.
- **No core feature without a real consumer.** The core grows only when an actual project needs it;
  a second adapter lands only when a second project adopts Plumb. That discipline is what proves
  the abstraction rather than guessing at it.
- **Adapters follow the contract.** New language adapters implement
  [`docs/adapter-contract.md`](docs/adapter-contract.md) and produce the manifest from a real test
  run.

## Scope

Plumb keeps its scope tight on purpose. Before a large change, open an issue so we can agree it
fits before you build it.
