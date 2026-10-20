# Security

## Verifying what you installed

Plumb ships as a single file, `plumb.pyz`, published beside a `SHA256SUMS` and a detached
`SHA256SUMS.asc`. The signature is over the **checksums**, so one signature
covers everything a release contains and the cheap check and the strong check read the same file.

    curl -fsSL https://plumbspec.org/install.sh | sh

The installer always verifies the checksum, verifies the signature when `gpg` is available, and
**says which of those it did**. To refuse installation unless the signature verifies:

    curl -fsSL https://plumbspec.org/install.sh | PLUMB_REQUIRE_SIGNATURE=1 sh

To install without checking a signature — the checksum is still checked:

    curl -fsSL https://plumbspec.org/install.sh | PLUMB_NO_SIGNATURE=1 sh

That is a named flag rather than something you reach by emptying `PLUMB_KEY_FINGERPRINT`. An empty
pin is a pin the installer cannot use, and it refuses and tells you the flag instead of silently
restoring its own.

To pin a version rather than take the current one:

    curl -fsSL https://plumbspec.org/install.sh | PLUMB_VERSION=0.6.0 sh

By hand, if you would rather not pipe anything to a shell:

    curl -fsSLO https://plumbspec.org/latest/plumb.pyz
    curl -fsSLO https://plumbspec.org/latest/SHA256SUMS
    curl -fsSLO https://plumbspec.org/latest/SHA256SUMS.asc
    gpg --keyserver hkps://keys.openpgp.org --recv-keys 208BC1279656FEEA7C2F9A1D830604D51CA7D4FB
    gpg --verify SHA256SUMS.asc SHA256SUMS
    sha256sum --check SHA256SUMS

## What that verification does and does not buy you

Stated plainly, because most projects shipping an installer of this shape do not.

- **The checksum** protects against a corrupted download and against a mirror that is not the
  origin. It does **not** protect against the origin being compromised: whoever served you a bad
  artifact served you the installer too, and the installer is what checks it.
- **The signature** is what closes that, and only if the public key reaches you by a route that is
  not the host serving the binary. That is the entire reason the key goes to a keyserver: it makes
  the key a different trust root from the artifact.
- **The fingerprint still has to reach you from somewhere you trust.** A keyserver will hand out
  any key claiming any identity; it authenticates distribution, not identity. If you take the
  fingerprint off the same website that served the binary, you are back where you started.

## What the release checks before you are served anything

A pinned key is only as good as the operation that publishes it, and that operation is not visible
from inside a signature. Both halves of one release can be individually correct — a signature that
verifies, a fingerprint of the right shape — and compose into an origin that works perfectly and
serves an installation nobody can complete: every machine with `gpg` refuses, correctly, because
the key the installer pins is not the key that signed or is not on the keyserver it is fetched
from.

So the cut runs the install-side check itself, against a keyring built the way yours is — empty,
one keyserver, one fingerprint — over everything an installer can reach: the channel pointers and
the checksums of every version they name. A signature that cannot verify fails the release rather
than your install, which is the only one of the two failures anybody can still act on.

## The signing key

    208B C127 9656 FEEA 7C2F  9A1D 8306 04D5 1CA7 D4FB

Published at [keys.openpgp.org](https://keys.openpgp.org/search?q=208BC1279656FEEA7C2F9A1D830604D51CA7D4FB) and
`keyserver.ubuntu.com`. The same key signs the commits in this repository from 2026-08-18 onward, so
`git log --show-signature` is a second, independent place to see it — one that does not come from
the download host. **Commits and releases before that date carry the previous key; see the rotation
below before you use them as a cross-check.**

The fingerprint above is the **primary** key, and that is deliberately what the installer pins.
`gpg --verify` reports the signing *subkey* first and the primary last; subkeys are meant to
rotate, so pinning one would break every installed copy the first time the key is rotated
routinely.

Compare the fingerprint across at least two of: this file, the README, the git commit signatures,
and the keyserver. Taking it only from the site that served you the binary defeats the purpose.

## The key was rotated on 2026-08-18, and the old one is revoked

Stated here rather than quietly, because a reader who cross-checks against this repository's
history will find a different fingerprint and is owed an explanation that is not "trust us".

The previous signing key —

    57C4 5ECD E870 35DB 5D6B  2AA9 675D DD55 F917 F71F

— was **revoked on 2026-08-18 for key compromise**, and the revocation is published on both
keyservers. Its private half must be assumed to be in someone else's hands.

What that means for what you already have:

- **Anything published before 2026-08-18 is signed by the old key.** `gpg --verify` will report a
  good signature *and* warn that the key is revoked. Both halves of that are true, and the warning
  is the part that matters: a signature from a compromised key demonstrates only that *someone*
  holding that key made it, which is no longer a statement about who.
- **The artifacts themselves were not altered.** They are committed to this repository, and git's
  hash chain — not the signature — is what protects their contents. That is why they have not been
  re-signed under the new key: re-signing would assert a vouching this project cannot honestly make
  about material that predates the rotation.
- **If you pinned an old version, take a current one.** Not because the old artifact is known bad,
  but because its signature can no longer distinguish good from bad.
- **Every version before 0.5.0 was withdrawn from the site on 2026-08-19.** They
  are gone rather than re-signed: leaving a download whose signature cannot be
  trusted is worse than not offering it, and re-signing would assert a vouching
  this project cannot honestly make about artifacts published before the new key
  existed. A pinned install of a withdrawn version will now fail to fetch, which
  is the intended outcome — it fails loudly instead of installing something whose
  provenance is unverifiable.
- **Commit signatures before 2026-08-18 carry the old key**, so `git log --show-signature` is a
  cross-check for the *new* fingerprint only on commits after that date.

## Supported versions

Plumb is pre-1.0. Only the current minor is maintained. Wire and API compatibility may break
between any two releases until 1.0.0.

| Version | Supported |
|---|---|
| 0.6.x | current; current; pre-1.0 |
| 0.5.x | superseded |
| 0.4.x | superseded |
| 0.3.x | superseded |
| 0.2.x | superseded |
| 0.1.x | superseded |
| 0.0.x | superseded |

## Dependencies

The core has **no runtime dependencies**. That is a security property as much as a design one:
there is no transitive tree to audit, nothing to resolve at install time, and the single-file
artifact is possible because of it.

- **Python 3.9+** at runtime, and nothing else — the same floor the adapter declares, so a
  project needs one interpreter rather than one for its tests and a newer one for the tool
  that watches them.
- **A JDK** only for the Java adapter, and only in the project being measured. The shipped
  adapter's bytecode floor is the `maven.compiler.release` its module declares.
- **pytest** is required only in the project being measured, which already has it — Plumb does not
  install it and does not carry it.
- The Java adapter uses **JDK-provided APIs only** (`java.lang.instrument`, `com.sun.source`, JUnit
  Platform Launcher supplied by the project under test). No PIT, no Stryker, no coverage agent.

## What Plumb does to the code it measures

Worth knowing before pointing it at anything you care about:

- **Grounding** observes and never modifies the source. Python uses `sys.settrace`; Java loads an
  agent into the process running your suite and weaves probes into classes as they load, leaving
  every class file on disk untouched.
- **Mutation edits your source in place**, one file at a time, and restores it. It is off by
  default. Before each edit the original is written to `.plumb-mutation-rescue`, and a run killed
  mid-mutant is repaired by the next run *before its tests execute*. Run it on a clean working tree
  anyway; that is what version control is for.
- **Nothing is transmitted** unless the installation is enrolled, which is a separate, explicit
  consent, and anything filed can be withdrawn.
- **`plumb session` writes a cursor into your repository** and a disposable reading outside it. The
  cursor is `key="value"` data and is parsed, never executed; nothing in the tool sources it.

`plumb footprint` prints every location Plumb writes on your machine, what each is, and which of it
is worth backing up.

## Reporting a vulnerability

Open a GitHub issue for anything already public. For anything not, use GitHub's private security
advisory reporting on the repository. There is no separate mailbox and no bounty.
