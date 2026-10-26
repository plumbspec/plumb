"""Who is filing, and whether their records may leave (``dev07-6-2-1-2``).

Consent is established **once, at enrolment**, never re-asked per record. An installation nobody
enrolled keeps everything local and never transmits — the core ships to anyone, so that is the
default case and it is what makes "nothing phones home" a guarantee rather than a promise.

Never from local config: the *client* cannot be the authority on who it is —
anything on this disk is a claim by the filer. So the client states a relationship and the
**holder overwrites it** from the credential it authenticated. Local records are ``self``
because you are the only authority over your own store; transmitted ones are stamped by whoever
accepted them.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

RELATIONSHIPS = ("self", "trusted-tester")

#: The one field of an enrolment that is a secret, carried as an opaque string.
#: Every runner can set a variable; not every runner can mount a file, and a file in a working tree
#: is collectable by an artifact upload or a cache action written for an unrelated purpose.
CREDENTIAL_ENV = "PLUMB_CREDENTIAL"

#: The address, which is configuration and wants reviewing. Read from ``plumb.toml`` when it is not
#: given here, so "which service is this CI pushing to?" is answerable from the repository.
ENDPOINT_ENV = "PLUMB_ENDPOINT"

DEFAULT_ENROLMENT = Path(
    os.environ.get("PLUMB_ENROLMENT")
    or Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "plumb" / "enrolment.json"
)


class NotEnrolled(Exception):
    """No enrolment, so nothing transmits. Not an error — the default (``dev07-6-2-1-2``)."""


@dataclass(frozen=True)
class Enrolment:
    relationship: str
    credential: str
    endpoint: str
    #: Which store this credential owns. Issued *with* the credential, because a credential
    #: owns exactly one store and the pairing is decided at issuance rather than chosen later.
    #:
    #: Deliberately **not** the subject id, which is unbuilt. That one is a measurement identity
    #: generated into `plumb.toml`, and reaching for it here would mean writing to an adopter's
    #: config as a side effect of a board run — and would give the subject a second job as an access
    #: boundary, which is the failure the owned store exists to avoid. Absent where an enrolment predates
    #: series support, and friction does not use it.
    subject: str = ""

    def __post_init__(self):
        if self.relationship not in RELATIONSHIPS:
            raise ValueError(f"relationship must be one of {RELATIONSHIPS}, got {self.relationship!r}")
        if not self.credential.strip():
            raise ValueError("an enrolment without a credential cannot carry consent")
        if not self.endpoint.startswith(("http://", "https://")):
            raise ValueError(f"endpoint must be an absolute http(s) URL, got {self.endpoint!r}")

    @property
    def may_transmit(self) -> bool:
        """Enrolment *is* the consent (``dev07-6-2-1-2``); there is no per-record question to ask."""
        return True

    def to_json(self) -> str:
        written = {"relationship": self.relationship, "credential": self.credential,
                   "endpoint": self.endpoint}
        # Omitted when absent rather than written empty: an enrolment that carries no store is one
        # that predates series support, and a blank field would read as a store named "".
        if self.subject:
            written["subject"] = self.subject
        return json.dumps(written, indent=2) + "\n"


def from_environment(root: Path | str = ".") -> Enrolment | None:
    """An enrolment assembled from the environment of the run: the credential and the address
    beside it (`dev07-6-2-1-1-sr4`).

    ``None`` when no credential is set, so the file form below stays the escape hatch for setups
    that deliver secrets as files.
    """
    credential = os.environ.get(CREDENTIAL_ENV, "").strip()
    if not credential:
        return None
    endpoint = os.environ.get(ENDPOINT_ENV, "").strip()
    if not endpoint:
        raise NotEnrolled(
            f"{CREDENTIAL_ENV} is set and {ENDPOINT_ENV} is not: name the address beside the "
            f"credential, in the environment of the run")
    # `self`, because a locally assembled relationship is a claim by the sender and the receiver
    # overwrites it from the credential it authenticated anyway.
    return Enrolment("self", credential, endpoint)


def load(path: Path | None = None, root: Path | str = ".") -> Enrolment:
    """The enrolment, or ``NotEnrolled`` — which is the ordinary case, not a failure.

    `root` is the project this command is *about*, which is not always the directory it is run
    from: `--project` exists precisely so a board can be derived for a project you are not standing
    in. It was honoured for the board and not for the endpoint, so one invocation read its
    configuration from two roots and the same command pushed or did not depending on where it was
    typed — observed where a wrapper passes an absolute `--project` from the repository
    root, which is the shape the Java setup instructions lead you to write.

    What made it expensive is that a developer machine has an enrolment file whose endpoint answers
    first, so it cannot be reproduced locally at all: it appears only where there is none, which is
    CI, where it lands as a silent non-push that can never fail a build.
    """
    if path is None:
        from_env = from_environment(root)
        if from_env is not None:
            return from_env
    path = Path(path or DEFAULT_ENROLMENT)
    if not path.is_file():
        raise NotEnrolled(
            f"no enrolment at {path} and {CREDENTIAL_ENV} is not set; records stay local")
    raw = json.loads(path.read_text())
    missing = {"relationship", "credential", "endpoint"} - set(raw)
    if missing:
        raise NotEnrolled(f"{path} is missing {sorted(missing)}")
    return Enrolment(raw["relationship"], raw["credential"], raw["endpoint"], raw.get("subject", ""))


def is_enrolled(path: Path | None = None) -> bool:
    try:
        load(path)
        return True
    except (NotEnrolled, ValueError, json.JSONDecodeError):
        return False
