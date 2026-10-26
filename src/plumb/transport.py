"""Where one capability's output goes (`dev07-6-2-1`).

**A destination belongs to a capability, not to the machine** (`dev07-6-2-1-D1`). One credential and one
base URL for everything the tool sends made a person choose between self-hosting a holder and being
answered by a support service, because both hung off the same address — which is not configuration,
it is a choice between two products. A capability names its own, and a project names as many as it
uses.

**Absence is the ordinary state and never an error** (`dev07-6-2-1-2-sr1`). With no destination named for a
capability, what that capability produced stays on this machine. That is what makes *nothing leaves
without being told where* a guarantee rather than a promise about somebody's configuration: there is
no default address to forget to change.

**A destination is not a relationship.** It says where to send, what to send with, and which store
there it owns — and nothing about who the sender is to whoever runs it. That is the service's to
decide from the credential it authenticated (`dev07-6-2-1-1-sr2`), and the enrolment this replaces said so
itself: the client's claim was overwritten on arrival. A field nobody downstream trusts is one the
core has no business carrying.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

#: The version of the transport surface, which is what a module declares it speaks (`dev08-1-1-ur2`).
#:
#: **1 is this shape as it stands**: a destination per capability, resolved from the environment
#: first and a file second. Published because the series module already reaches through this and
#: the support client will, and a surface two modules build on with no version is one neither can
#: be refused against.
TRANSPORT_VERSION = 1

#: Every field of a destination is readable from the environment (`dev07-6-2-1-1-ur3`). A runner can set a
#: variable; not every runner can mount a file, and a file in a working tree is collectable by an
#: artifact upload or a cache step written for something else.
_MACHINE_WIDE = ("PLUMB_ENDPOINT", "PLUMB_CREDENTIAL", "PLUMB_SUBJECT")


@dataclass(frozen=True)
class Destination:
    """Where one capability sends, what it sends with, and which store there it owns."""

    capability: str
    url: str
    credential: str
    #: Which store at that address this credential owns. Issued with the credential, because a
    #: credential owns exactly one store and the pairing is decided at issuance.
    subject: str = ""

    def __post_init__(self):
        if not self.capability.strip():
            raise ValueError("a destination belongs to a capability, and none was named")
        if not self.url.startswith(("http://", "https://")):
            raise ValueError(f"endpoint must be an absolute http(s) URL, got {self.url!r}")
        if not self.credential.strip():
            raise ValueError("a destination with no credential cannot send anything")

    def at(self, path: str) -> str:
        """One address under this destination, joined the one way."""
        return self.url.rstrip("/") + path


def variables(capability: str) -> tuple:
    """The three variables a runner sets for one capability.

    The capability's own name, upper-cased, with anything that is not a letter or a digit becoming
    an underscore — because `run-history` is a capability and `PLUMB_RUN-HISTORY_ENDPOINT` is not a
    variable anybody's shell will set.
    """
    stem = re.sub(r"[^A-Za-z0-9]+", "_", capability).strip("_").upper()
    return (f"PLUMB_{stem}_ENDPOINT", f"PLUMB_{stem}_CREDENTIAL", f"PLUMB_{stem}_SUBJECT")


def for_capability(capability: str, *, enrolment_path: Path | None = None,
                   root: Path | str = ".") -> Destination | None:
    """Where this capability sends, or ``None`` because nowhere was named.

    Three places, most specific first, and the first that answers wins:

    1. **the capability's own variables** — what a project sets to send two things to two hosts
    2. **the machine-wide pair** — one address for everything, which stays workable and stops being
       the only thing expressible
    3. **the enrolment file** — one relationship with one service, the shape this replaces. A file
       that already exists keeps answering for every capability that has nothing more specific.

    ``None`` is a state and not a failure: nothing was named, so nothing of this capability's
    leaves (`dev07-6-2-1-2-ur1`).
    """
    endpoint, credential, subject = variables(capability)
    found = _from_env(capability, (endpoint, credential, subject))
    if found is not None:
        return found
    found = _from_env(capability, _MACHINE_WIDE)
    if found is not None:
        return found
    return _from_enrolment(capability, enrolment_path, root)


def _from_env(capability: str, names: tuple) -> Destination | None:
    """A destination from three variables, or ``None`` where the pair is not both set.

    Both halves or neither: an endpoint with no credential is somebody half-way through configuring
    a runner, and answering with it would send unauthenticated and report the refusal as the
    service's.
    """
    url, credential, subject = (os.environ.get(name, "") for name in names)
    if not url.strip() or not credential.strip():
        return None
    return Destination(capability, url.strip(), credential.strip(), subject.strip())


def _from_enrolment(capability: str, path: Path | None, root: Path | str) -> Destination | None:
    """The enrolment file read as a destination for everything that named none of its own.

    Imported here rather than at module scope: `enrolment` is the older shape and this is the
    newer one, so the dependency points backwards on purpose and is worth being able to see.
    """
    from plumb.enrolment import NotEnrolled, load

    # Which file, resolved when asked rather than when imported. `enrolment.DEFAULT_ENROLMENT` is a
    # module-level constant, so a `PLUMB_ENROLMENT` set after import is not seen — which is every
    # caller that sets it for one invocation rather than for the whole process.
    if path is None:
        named = os.environ.get("PLUMB_ENROLMENT")
        path = Path(named) if named else None
    try:
        enrolled = load(path, root=root)
    except (NotEnrolled, OSError, ValueError):
        return None
    return Destination(capability, enrolled.endpoint, enrolled.credential, enrolled.subject)
