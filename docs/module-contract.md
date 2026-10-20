---
kind: reference
role: [programmer]
summary: What a contributed module receives, owes, and may never do.
---

# The module contract

**For programmers contributing a module.** The twin of [the adapter contract](adapter-contract.md),
one seam over: adapters supply the manifest to the core; modules consume what the core derives
from it.

**Read this as the design and not as a surface you can build against today.** Nothing in the
shipped tool declares the `plumb.modules` entry-point group, there is no `plumb modules` command,
and no module has been mounted — so what follows is what a module *would* receive and owe, written
down so the first one does not invent it. Every other page here describes something you can run. Together they are the whole extension story — a language in, a capability out, and the
core untouched by either.

## The lifecycle: absent, inert, active

A module is **absent** unless somebody installed it — nothing mounts that was not installed.
It is **inert** when it cannot reach what it needs: an unreachable service makes the module's
verbs report their own standing, and never makes the tool broken. And the core's own gates —
policy-freedom, a board complete without the network — **run with no modules mounted**, so a
hosted dependency can never become load-bearing one commit at a time while the gate stays
green. Softening that gate is the failure its own text names; this clause exists so the cheap
repair is never on the table.

## What a module receives

- **The board** — the documented, versioned, neutral format, exactly as any downstream tool
  reads it. A module pins a board version and an internal refactor never reaches it.
- **The series interface** — `plumb series` read and write, local or against a holder, behind
  the same answers whichever implementation is declared.
- **The mount** — the one CLI. A module's verbs appear under `plumb` when the package is
  installed, discovered from its entry-point declaration. Installing is the whole of enabling.
- **Its own configuration table** — named for the module, read by nobody else. The core's own
  keys are read-only to it. A configuration table is not where a secret belongs.
- **Its own state home, outside the repository** — granted by the mount, named for the module.
  Where a bearer credential or a private key rests, its footprint entry carries the
  disposition *carries a credential*.

## What a module owes

- **A declaration**: its name, the verbs it mounts, the surfaces it speaks — **a version per
  surface, as a map**, because one number cannot refuse on three axes (a conversation, a
  record body and a tier ladder each version apart) — every place it writes, each write a
  footprint entry with a disposition, and **whether it reaches the network**, so the trust
  decision an install makes is over verbs, writes and reach together.
- **Its own name and version, out of its own artifact** — a defect report against a module must
  be against something.
- **Refusable versions, per surface**: each named surface in the map refuses independently and
  by name, with what each side speaks.
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
  module reads what was proven; nothing it does can make a story more or less proven — the
  same line the support channel holds, generalized to every extension.
- **Shadow a core verb**, or mount a verb another installed module claims. Both refuse by name.
- **Write outside its declared footprint.** An undeclared write is invisible to backup and
  removal, which is how an adopter loses something they never knew they had.
- **Import the core's internals.** The documented surfaces are the contract; everything behind
  them is working state, promised to nobody.

## The mount, mechanically

A module package declares its verbs under the `plumb.modules` entry-point group. At startup the
CLI discovers installed declarations and mounts each module's verb group. `plumb modules` lists
what is mounted, with names and versions. A module that fails to import is reported as an
install fault and the rest still mount — one broken extension never costs the tool.
