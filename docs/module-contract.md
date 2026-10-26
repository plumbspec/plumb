---
kind: reference
role: [programmer]
summary: What a contributed module receives, owes, and may never do.
---

# The module contract

**For programmers contributing a module.** The twin of [the adapter contract](adapter-contract.md),
one seam over: adapters supply the manifest to the core; modules consume what the core derives
from it.

The mount is real: `plumb series` is itself a module, declared under the `plumb.modules`
entry-point group by Plumb's own distribution, and `plumb modules` lists what is mounted. Where a
clause below is not yet something the core provides, it says so. Together the two contracts are the
whole extension story — a language in, a capability out, and the core untouched by either.

## The lifecycle: absent, inert, active

A module is **absent** unless somebody installed it — nothing mounts that was not installed.
It is **inert** when it cannot reach what it needs: an unreachable service makes the module's
verbs report their own standing, and never makes the tool broken. And the core's own gates —
policy-freedom, a board complete without the network — **run with no modules mounted**, so a
hosted dependency can never become load-bearing one commit at a time while the gate stays
green. Softening that gate is the failure its own text names; this clause exists so the cheap
repair is never on the table.

## What a module receives

Three published surfaces, each with its own version — `board` 3, `series` 1 and `transport` 1 in
this release:

- **The board** — the documented, versioned, neutral format, exactly as any downstream tool
  reads it ([The board, as JSON](consuming-the-board.md)). A module declares the board version it
  speaks and an internal refactor never reaches it.
- **The series interface** — the series format and what a read refuses (`plumb.core.series`).
- **The transport** — where one capability's output goes (`plumb.transport`): a destination per
  capability, resolved from that capability's own environment variables, then the machine-wide
  `PLUMB_ENDPOINT`/`PLUMB_CREDENTIAL` pair, then the enrolment file. No destination means nothing
  of that capability leaves the machine. A credential is sent as a bearer token; nothing is signed.

And:

- **The mount** — the one CLI. A module's verbs appear under `plumb` when the package is
  installed, discovered from its entry-point declaration. Installing is the whole of enabling.
- **Configuration and state of its own** — the design gives a module its own configuration table,
  read by nobody else, and its own state home outside the repository. The core does not provide
  either yet; a module that keeps state declares where in its footprint entries, and a place that
  holds a credential is declared as one.

## What a module owes

- **A declaration** (`plumb.modules.Declaration`): its name and version, the verbs it mounts, the
  surfaces it speaks — **a version per surface, as a map**, so each refuses on its own axis —
  every place it writes, each a `plumb.footprint.Wrote` entry with a disposition so
  `plumb footprint` can name it, and **whether it reaches the network**, so the trust decision an
  install makes is over verbs, writes and reach together.
- **Its own name and version, out of its own artifact** — a defect report against a module must
  be against something.
- **Refusable versions, per surface**: a module speaking a surface the core does not publish, or a
  version other than the one it publishes, does not mount, and the refusal names both sides.
- **Install-fault honesty**: a module that cannot supply its own machinery names its own
  installation as the fault and says how to repair it — never the project, never the core.
- **A namespace, if it keeps a spec**: a module's subjects live under its own namespace and its
  citations share the board with every other spec in the repository. Keeping a spec is the
  author's choice; proving claims the method's way is what the namespace buys.

## What a module may never do

- **Read or write the manifest.** The manifest is the adapters' hub and the core's own to
  restructure without notice; a module that parsed it would break on every internal cleanup,
  and the fear of breaking it would stop the cleanup. The board exists so this never happens.
- **Move a status.** The proof graph has one set of writers and a module is not among them. A
  module reads what was proven; nothing it does can make a story more or less proven.
- **Shadow a core verb**, or mount a verb another installed module claims. A module naming a core
  verb does not mount; a name two modules claim mounts for neither. Both are said by name.
- **Write outside its declared footprint.** An undeclared write is invisible to backup and
  removal, which is how an adopter loses something they never knew they had.
- **Import the core's internals.** The documented surfaces are the contract; everything behind
  them is working state, promised to nobody.

## The mount, mechanically

A module package declares its verbs under the `plumb.modules` entry-point group. At startup the
CLI discovers installed declarations and mounts each module's verb group; the core builds the
parser from the declaration, and a module is never handed the parser. `plumb modules` lists what is
mounted, with names, versions, verbs, the surfaces each speaks, its network reach and its writes:

    series 1.0.0  verbs: series (push|show|pull)  speaks: series 1  network: yes
        writes the series file named on the command line
        writes its `.sent` mark, beside it

A module that fails to import is reported as an install fault and the rest still mount — one
broken extension never costs the tool. Discovery reads installed distributions' metadata, so a
module is found only where its distribution is installed.
