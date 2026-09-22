"""The client half of the account loop (``ch12-1`` … ``ch12-6``).

What an install offers has to be a route it can actually perform (``ch12-1``). This is the
self-provisioned one: make an identity here, claim an account with it, and sign what is sent
afterwards. Nothing here needs an operator, a page, an email or a person on the other end.

The account file holds the **endpoint and the public key** and never the passphrase. A secret this
process was handed is not a secret this process writes down: the passphrase arrives from the
environment or the command line on every run, because an unattended runner has nobody to prompt
(``ch12-2``), and the identity is rebuilt from it rather than stored (``ch12-13``).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, replace
from pathlib import Path

from plumb import identity as identity_mod

DEFAULT_ACCOUNT = Path(
    os.environ.get("PLUMB_ACCOUNT")
    or Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "plumb" / "account.json")

#: Where a runner is expected to put the one secret it was handed (``ch12-13``).
ROOT_ENV = "PLUMB_ROOT"

#: The secret's own home, beside the configuration and never inside it (``ch12-22``). A file rather
#: than a field, so an adopter who wants the machine to hold nothing can delete it and supply the
#: root from the environment instead — which is the posture this replaced, kept as a choice
#: (``ch12-2``).
DEFAULT_ROOT = Path(
    os.environ.get("PLUMB_ROOT_FILE")
    or Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "plumb" / "root")

#: Which signing key this writer uses (``ch12-24``). A counter is per key, so concurrent writers
#: sharing one account need one key each — and they derive it from the same single secret rather
#: than being handed one apiece. A build matrix sets this to its leg.
KEY_LABEL_ENV = "PLUMB_KEY_LABEL"


class NoAccount(Exception):
    """No account configured. Ordinary, not a failure — the tool works without one."""


@dataclass(frozen=True)
class AccountConfig:
    endpoint: str
    public: str
    #: This key's place in its own sequence. Strictly increasing, kept per key rather than per
    #: account, and not a secret — a client that has lost its place asks and is told (``ch12-6``).
    counter: int = 0
    #: The key this account's history is pseudonymised under (``dev07-6-2``), derived from the root
    #: **once** and carried thereafter (``ch12-24``). Carried rather than recomputed because
    #: replacing a lost root is a different event from rotating a compromised one, and only the
    #: second should rename every subject an adopter already holds.
    digest_key: str = ""
    #: Where this was read from, so anything that writes it back does not have to be told again.
    #: Never serialised — a file that records its own path is a file that lies the moment it moves.
    #: It exists because a fact recorded at the point of proof has no other way to know which
    #: account it proved, and defaulting to the well-known path would write the wrong file for
    #: every caller that passed `--account`.
    source: Path | None = None

    def to_json(self) -> str:
        written = {"endpoint": self.endpoint, "public": self.public, "counter": self.counter}
        # Omitted when it has never been recorded rather than written null, so a file this version
        # wrote and a file that predates the field are the same bytes when they say the same thing.
        if self.digest_key:
            written["digest_key"] = self.digest_key
        return json.dumps(written, indent=2) + "\n"


def load(path: Path | None = None) -> AccountConfig:
    """The account this install holds, or ``NoAccount`` — which every unusable state answers with.

    Absent, unreadable and incomplete are three ways of having no account to work from, and the
    repair for all three is the same command. Only the first two were answered that way: a file
    holding something that is not an account reached ``json.loads`` and left as a ``JSONDecodeError``
    through every caller that had been told to expect ``NoAccount``, so ``plumb account claim``
    ended at a traceback naming a line in the json module. Reported by an adopter who had made the
    file by hand, believing ``create`` had not written one (`ch12-26`) — the two defects in one
    sitting, the second reachable only because of the first.
    """
    path = Path(path or DEFAULT_ACCOUNT)
    if not path.is_file():
        raise NoAccount(f"no account at {path}; run `plumb account create`")
    try:
        raw = json.loads(path.read_text())
    except ValueError as unreadable:
        raise NoAccount(
            f"{path} is not an account this tool can read ({unreadable}). It is written by "
            f"`plumb account create`, so running that again replaces it — nothing is lost unless "
            f"the root is gone") from unreadable
    if not isinstance(raw, dict):
        raise NoAccount(f"{path} holds {type(raw).__name__}, not an account; "
                        f"run `plumb account create` to write one")
    missing = {"endpoint", "public"} - set(raw)
    if missing:
        raise NoAccount(f"{path} is missing {sorted(missing)}")
    return AccountConfig(raw["endpoint"], raw["public"], raw.get("counter", 0),
                         raw.get("digest_key", ""), path)


def save(config: AccountConfig, path: Path | None = None) -> Path:
    # Where it came from, before the well-known path: a caller that passed `--account` said which
    # account it meant, and writing the default one back would answer a different question.
    path = Path(path or config.source or DEFAULT_ACCOUNT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(config.to_json())
    return path


def root(supplied: str | None = None, path: Path | None = None) -> bytes:
    """The root this install signs with: given, else the environment, else the file beside the
    account. Never prompted.

    Three sources in that order and not one, because they answer different situations. A runner is
    handed the secret and has nowhere to keep it. A workstation kept it here when the account was
    made. And a caller that names one is answering for itself — a test, or somebody signing as an
    account this machine does not otherwise hold.
    """
    given = supplied or os.environ.get(ROOT_ENV, "")
    if given.strip():
        try:
            return identity_mod.decode_root(given)
        except ValueError as malformed:
            raise NoAccount(f"the root supplied is not one: {malformed}") from malformed
    kept = Path(path or DEFAULT_ROOT)
    if kept.is_file():
        try:
            return identity_mod.decode_root(kept.read_text())
        except ValueError as malformed:
            raise NoAccount(f"{kept} is not a root: {malformed}") from malformed
    raise NoAccount(
        f"no root: set {ROOT_ENV}, or run `plumb account create` on this machine. It is the whole "
        f"of the identity, so it is never prompted for")


def save_root(raw: bytes, path: Path | None = None) -> Path:
    """Write the secret where only this account can read it (``ch12-22``, ``ch12-2``).

    ``0600`` before anything is in it, not after: a file created world-readable and narrowed a
    moment later is readable for that moment, and the moment is the whole of the exposure.
    """
    kept = Path(path or DEFAULT_ROOT)
    kept.parent.mkdir(parents=True, exist_ok=True)
    kept.touch(mode=0o600, exist_ok=True)
    kept.chmod(0o600)
    kept.write_text(identity_mod.encode_root(raw) + "\n")
    return kept


def _call(url: str, body: bytes | None = None, headers: dict | None = None, method: str = "GET"):
    request = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as answer:
            return answer.status, json.loads(answer.read().decode() or "{}")
    except urllib.error.HTTPError as refused:
        try:
            return refused.code, json.loads(refused.read().decode() or "{}")
        except ValueError:
            return refused.code, {}


def key_label() -> str:
    return os.environ.get(KEY_LABEL_ENV, "").strip() or identity_mod.DEFAULT_LABEL


class KeyMismatch(Exception):
    """The account file names a key this passphrase does not derive (``ch12-13``).

    The file records a public key and the passphrase derives one, and nothing compared them — so a
    claim registered the *stored* key while every signed request afterwards presented the *derived*
    one, and the holder answered `unrecognised key` to an account it had just created seconds
    before. Measured: claim reporting grants and the next command 401ing, which reads as
    a holder that does not implement the route rather than as a client with two ideas of its own
    identity.

    Refused rather than silently re-derived, because the two causes need different answers: an
    account file from an older derivation is a re-claim, and a passphrase pointed at the wrong
    secret is a mistake that silent re-derivation would turn into a second account.
    """


def check_identity(config: AccountConfig, supplied_passphrase: str | None = None,
                   label: str | None = None) -> str:
    """The key this root actually derives, or ``KeyMismatch``."""
    derived = identity_mod.Identity(root(supplied_passphrase), label or key_label()).public
    if config.public and derived != config.public:
        raise KeyMismatch(
            f"this root derives {derived[:16]}… and the account file names "
            f"{config.public[:16]}…, so one key would be registered and every request after it "
            f"would present another.\n"
            f"  Either the root is not the one this account was made with, or the file was written "
            f"by a version that derived keys differently.\n"
            f"  If it is the second: `plumb account create` again — nothing is lost, because "
            f"nothing was held under a key that never worked.")
    return derived


@dataclass(frozen=True)
class Signable:
    """Whether this install can still rebuild the key the account is named by (``ch12-25``).

    ``said`` carries the reason when it cannot, in the words of whatever refused — a missing
    passphrase, a weak one, a mismatch, or a back end this install does not have. They are different
    repairs, so the answer keeps them apart rather than flattening them to ``no``.
    """

    can_sign: bool
    said: str
    derived: str = ""


def can_sign(config: AccountConfig, supplied_passphrase: str | None = None,
             label: str | None = None) -> Signable:
    """Derive, compare, and answer — offline, sending nothing (``ch12-25``).

    Every failure here is an *answer* rather than an exception, because the state this exists to
    report is exactly the state where there is no passphrase to work from: raising there would refuse
    the question instead of answering it, which is the position an account whose secret is gone was
    already in.
    """
    try:
        derived = check_identity(config, supplied_passphrase, label)
    except (NoAccount, KeyMismatch, identity_mod.WeakPassphrase,
            identity_mod.Unavailable) as why:
        return Signable(False, str(why))
    return Signable(True, f"{derived[:16]}… derives from the passphrase this install was given",
                    derived)


def signed_wire2(who, method: str, path: str, body: bytes = b"") -> dict:
    """Headers for the support service's account routes (wire v2).

    A different contract from `signed` below, and deliberately a second function rather than a
    flag: the series wire signs `method·path·endpoint·counter·body` and the support wire signs
    `METHOD\nPATH\nTIMESTAMP\nsha256(body)` with a 300-second window. One function wearing two
    schemes is how a request comes to carry the wrong one and read as an attack.
    """
    import datetime
    import hashlib
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    message = f"{method}\n{path}\n{stamp}\n{hashlib.sha256(body).hexdigest()}".encode()
    return {"Plumb-Timestamp": stamp,
            "Plumb-Signature": f"{who.public}.{who.sign(message)}"}


def signed(config: AccountConfig, method: str, path: str, body: bytes = b"",
           supplied_passphrase: str | None = None,
           label: str | None = None) -> tuple[dict, AccountConfig]:
    """Headers proving who sent this, bound to this body, this holder and this counter."""
    check_identity(config, supplied_passphrase, label)
    identity = identity_mod.Identity(passphrase(supplied_passphrase), label or key_label())
    counter = config.counter + 1
    message = identity_mod.canonical(method, path, config.endpoint.rstrip("/"), counter, body)
    headers = {
        "Plumb-Key": identity.public,
        "Plumb-Counter": str(counter),
        "Plumb-Signature": identity.sign(message),
    }
    # `replace`, never a fresh AccountConfig. Rebuilt from three fields, this dropped every field
    # added after those three — so signing a request un-recorded whether the account had ever been
    # proved, on every request. The 409 re-synchronisation had the same shape and the same bug.
    return headers, replace(config, counter=counter)
