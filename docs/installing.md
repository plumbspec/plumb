---
kind: how-to
role: [programmer, devops]
summary: Install Plumb, verify what you installed, pin a version or a channel, or remove it.
---

# Installing Plumb

**For programmers and DevOps.** One command, one file, nothing added to your project.

    curl -fsSL https://plumbspec.org/install.sh | sh

Then, in your project:

    plumb board

That works with no `plumb.toml` at all — a Python project gets a board from its tests' citations,
with nothing checked for wiring and the board saying so. `plumb init` writes the `plumb.toml` that
tells Plumb where your code is and where requests enter it; [Getting started](getting-started.md)
walks through it.

That is the whole installation. Everything below is for when you want more control over it.

---

## What gets installed, and where

Two files, into `~/.local/bin`:

| file | what it is |
|---|---|
| `plumb.pyz` | the whole tool, both language adapters inside it |
| `plumb` | a small launcher that runs it with the Python it found |

Nothing is added to your project's dependencies, there is no package index involved, and no account
is needed. To install somewhere else, set `PLUMB_BIN_DIR`:

    curl -fsSL https://plumbspec.org/install.sh | PLUMB_BIN_DIR=/usr/local/bin sh

The installer tells you if the directory it used is not on your `PATH`.

An install made through a channel also leaves a small marker beside them, `.plumb-install`, naming
the channel — it is what lets `plumb --version` say which one you are on.

**What the single file does not carry: modules.** Modules — `plumb series` is the first — are found
through installed package metadata, and the zipapp carries none of its own — run against an
interpreter with nothing installed into it, it mounts no modules: `plumb series` is absent rather than broken, and `plumb modules`
says what is mounted. If you want the series commands, install the package instead.

### With pip

    pip install plumbspec

This installs the `plumb` command with its `series` module mounted, and the `plumb-series-holder`
command for running a holder of your own. It does **not** carry the Java adapter, which ships only
inside the zipapp: for a Java project, use the installer above, or set `PLUMB_JAVA_CLASSPATH` to a
`plumb-java.jar` you already have.

### Which to choose

| | installer | pip |
|---|---|---|
| `plumb board`, `init`, `session`, `footprint` | yes | yes |
| the Java adapter | yes | no |
| `plumb board --series FILE --push` — record a history and send it | yes | yes |
| `plumb series show`, `pull`, `push` — read a history back | no | yes |
| `plumb-series-holder` | no | yes |

A Java project wants the installer. A Python project wants either, and pip if it will read its
history back or run a holder. `plumb modules` says what the one you have mounts.

---

## What you need

| | needs |
|---|---|
| **A Python project** | **Python 3.9 or newer** — the same one your tests run under, and nothing else |
| **A Java project** | **Java 8 or newer** for your tests, and a **Python 3.9 or newer** anywhere on the machine for Plumb itself |
| What your Java tests compile against | **Java 8 or newer** — the annotation jar, which imports nothing |
| Your test runner | **pytest**, or **JUnit 5** — whichever you already have. Plumb brings neither and pins neither |

**One Python, not two.** Plumb runs on the same floor its observer does, so a Python project
needs one interpreter rather than one for its tests and a newer one for the tool that watches
them. RHEL 9 ships 3.9 and Ubuntu 22.04 ships 3.10 as `python3`; both are enough as they come.
Ubuntu 20.04's 3.8 is not, and installing a newer one is the whole fix:

    apt install python3.9       # Debian / Ubuntu
    dnf install python3.9       # RHEL / Fedora

**Plumb is written in Python and runs alongside your build rather than inside it**, which is why a
Java project needs one available too. Nothing about your Java build changes.

**On JUnit.** JUnit 6 requires Java 17, so a project holding at Java 8 stays on the JUnit 5 line —
which is what Plumb's adapter is built against. Nothing here asks you to choose either.

**Java projects also need two more things** before `plumb board` will run — that annotation on the
compile path, and a classpath file. Both are covered in
[Getting started](getting-started.md#one-extra-step-for-java).

---

## Verifying what you install

Releases are signed. The installer always checks the artifact's checksum, checks the signature when
`gpg` is present, and tells you which of the two it did.

To refuse to install unless the signature verifies:

    curl -fsSL https://plumbspec.org/install.sh | PLUMB_REQUIRE_SIGNATURE=1 sh

To install without checking a signature at all:

    curl -fsSL https://plumbspec.org/install.sh | PLUMB_NO_SIGNATURE=1 sh

The checksum is still checked — that one needs nothing installed and is never skipped. Turning
verification off is a flag with a name because **emptying `PLUMB_KEY_FINGERPRINT` is not a way to
say it**: an empty pin is a pin the installer cannot use, and it will tell you so rather than
quietly putting its own back.

Releases are signed by this key:

    208B C127 9656 FEEA 7C2F  9A1D 8306 04D5 1CA7 D4FB

It is published on [keys.openpgp.org](https://keys.openpgp.org/search?q=208BC1279656FEEA7C2F9A1D830604D51CA7D4FB)
and on `keyserver.ubuntu.com`, so the key can reach you by a route that is not this website.

**That last point is the one that matters.** A checksum protects you against a corrupted download,
but not against this host: whoever served you a bad artifact also served you the installer that
checks it. Only the signature closes that hole, and only if you did not take the fingerprint from
here alone. Fetch it from a keyserver, or from someone who already has it.

---

## Channels: `stable` and `edge`

**Most people want `stable`, which is what you get without asking.** It is what we run, and it is
what a defect report is taken against. You do not have to do anything to be on it.

`edge` carries a **candidate**: a build published so it can be tested before it is recommended. It
may be broken, and it is where a change goes to be found wrong by somebody who is not its author.

    curl -fsSL https://plumbspec.org/install.sh | PLUMB_VERSION=edge PLUMB_REQUIRE_SIGNATURE=1 sh

A channel is a **signed pointer to a version**, not a separate download. The pointer is verified
before anything is fetched from the version it names, so choosing a channel is authenticated the
same way the artifact is — otherwise anyone able to rewrite the pointer could aim you at an older
release with a known hole and every other check would still pass.

Two things follow, and both are on purpose:

- **The channel tells you what it promises**, at install time, out of the pointer itself:

      plumb: edge is 0.8.0rc1 — could be broken, a candidate, published so it can be tested

- **The install remembers which channel answered**, because one build can be named by both at once
  and the version alone cannot say:

      $ plumb --version
      plumb 0.8.0.dev12+a1b2c3d (edge)

  Include that line in anything you report. A defect on `edge` is a different conversation from the
  same symptom on `stable`.

Pinning a literal version still works and is unaffected by either channel — a pinned install is on
neither, and says so by naming no channel.

**If you are trying a candidate for us**, `edge` is the whole of what you need to change. There is
no separate site, no unsigned artifact and no check to relax: it is the ordinary install path with
one variable set, which is the point.

---

## All the settings

Every one of these is an environment variable read by the installer:

| variable | default | what it does |
|---|---|---|
| `PLUMB_VERSION` | `stable` | a channel — `stable` or `edge` — or a literal version to pin |
| `PLUMB_BIN_DIR` | `~/.local/bin` | where the two files go |
| `PLUMB_REQUIRE_SIGNATURE` | `0` | `1` refuses to install without a verified signature |
| `PLUMB_NO_SIGNATURE` | `0` | `1` installs without checking one. The checksum is still checked |
| `PLUMB_KEY_FINGERPRINT` | the release's own pin | 40 hex characters — the key to verify against |
| `PLUMB_BASE_URL` | `https://plumbspec.org` | where to fetch from, for a mirror |
| `PLUMB_KEYSERVER` | `hkps://keys.openpgp.org` | where to fetch the signing key |

---

## Removing it

### From a project

Plumb puts very little into a project, and all of it is yours to delete:

- **`plumb.toml`** — the declaration `plumb init` wrote.
- **`.plumb/`** — the session cursor, if you used `plumb session` (or wherever `cursor` points).
- **Your series files and their `.sent` marks**, if you kept a history — `series` in `plumb.toml`, or
  whatever you passed to `--series`. Back them up first if you want the history: nothing else holds it.
- **Citations** — `@pytest.mark.proves`, `@pytest.mark.informs`, `@Proves`, `@Informs`. They do
  nothing without Plumb, so leaving them in place is harmless; removing them is a search. If you
  registered the markers in `pytest.ini` or `pyproject.toml`, take those lines out with them, and on
  Java remove the `plumb-annotations` test dependency once nothing imports it.
- **`.plumb-mutation-rescue`** — only present if a Python mutation run was killed partway; run
  `plumb board` once first, and it puts your source file back and deletes this.

Outside the project, Plumb keeps a per-project directory under `~/.cache/plumb/runs/` and a
session reading under `~/.local/state/plumb/`. Both are disposable. Run `plumb footprint` in the
project **before** deleting `plumb.toml` to see where they are on your machine.

### From your machine

Delete what the installer wrote:

    rm -f ~/.local/bin/plumb ~/.local/bin/plumb.pyz ~/.local/bin/.plumb-install

Plumb writes no system configuration and installs nothing into your project, so removing it leaves
your build exactly as it was. Using it does write a few things of its own — a cache, a session's
scratch reading, an enrolment if you made one — and `plumb footprint`, run before you remove it,
lists each of them with what losing it would cost. Any `plumb.toml` you created is yours and stays
put.

---

## See also

- [Getting started](getting-started.md) — configuration to your first proven story
- [The command line](command-line.md) — every command and option
- [Time per story](time-per-story.md) — what Plumb adds to a run of your suite
