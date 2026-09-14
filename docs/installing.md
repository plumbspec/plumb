---
kind: how-to
role: [programmer, devops]
summary: Install Plumb, verify what you installed, pin a version or a channel, or remove it.
---

# Installing Plumb

**For programmers and DevOps.** One command, one file, nothing added to your project.

    curl -fsSL https://plumbspec.org/install.sh | sh

Then, in a project that has a `plumb.toml`:

    plumb board

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

---

## What you need

**Python 3.11 or newer, somewhere on the machine.** That is true even when your project is Java —
Plumb is written in Python and runs alongside your build rather than inside it. Nothing about your
Java build changes.

Ubuntu 22.04 and RHEL 9 still ship something older as `python3`. Installing a newer one is the
whole fix, and the installer tells you if this applies to you:

    apt install python3.11      # Debian / Ubuntu
    dnf install python3.11      # RHEL / Fedora

**Java projects need a JVM of 17 or newer to run a board.** Plumb's adapter runs inside the JVM
that runs your tests, so that is the version it has to load on — not the version that built it, and
not the version your project targets.

**Your own project's Java level is not affected.** The annotation your tests compile against is
built for Java 8 and imports nothing, so adding it does not raise the floor of your build. The two
are separate on purpose: what you compile against is a kilobyte of annotations, and what needs 17 is
the adapter Plumb supplies and runs.

So a project targeting Java 8 can cite stories and compile normally; what it needs is a 17+ JVM
available to run the test suite Plumb observes.

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

## Pinning a version

Plumb is alpha. Interfaces, the manifest format and the command line may change between versions
without notice, so pin if you depend on one:

    curl -fsSL https://plumbspec.org/install.sh | PLUMB_VERSION=0.5.0 sh

Every published version stays reachable at its own path, with its checksums and its documentation
frozen as they were at the cut. Releases are browsable at [/channels/](/channels/), where each channel names the version it currently points at.

Pinning means deciding when to move. The [changelog](/changelog.html) says what each release
changed and whether it asks anything of you; it lives outside the version tree, so the copy you
read is always the current one whatever version you are on.

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

      plumb: edge is 0.5.0rc4 — could be broken, a candidate, published so it can be tested

- **The install remembers which channel answered**, because one build can be named by both at once
  and the version alone cannot say:

      $ plumb --version
      plumb 0.5.1.dev12+a1b2c3d (edge)

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

Delete the two files:

    rm ~/.local/bin/plumb ~/.local/bin/plumb.pyz

Nothing else was touched. Plumb writes no system configuration and installs nothing into your
project, so removing it leaves your build exactly as it was. Any `plumb.toml` you created is yours
and stays put.

---

## See also

- [Getting started](getting-started.md) — configuration to your first proven story
- [The command line](command-line.md) — every command and option
- [Time per story](time-per-story.md) — what Plumb adds to a run of your suite
