"""Sending a record, and not caring much whether it arrives (``ch6-6``, ``ch6-7``).

Capture never blocks the work. An unreachable endpoint is not an error the contributor should
ever see: the record is already safe on their disk, it is marked in the outbox, and the next
attempt drains it. Nothing here raises into a caller's workflow — the return value says what
happened and the work carries on either way.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from plumb.enrolment import Enrolment, NotEnrolled, load
from plumb.support import SupportRecord
from plumb.store import SupportStore

TIMEOUT_SECONDS = 10

#: The conversation this client speaks, announced on every request (``ch6-13``,
#: ``record-contract``). Deliberately NOT the record's schema version: the ratification of
#: 2026-09-12 deferred a record-version header out of the contract until a change moves the
#: record and not the wire — and sending the record's number in a version header is the exact
#: confusion that forced the contract to be written. The record still says its own version where
#: a version of a durable artifact belongs: stamped in the body, by the schema that wrote it.
PROTOCOL_VERSION = 2
VERSION_HEADER = "Plumb-Support-Version"

#: What an attempt came to. Three outcomes rather than two, because "it arrived" and "stop
#: trying" are different facts and collapsing them is how a refused record got reported as sent.
ACCEPTED, RETRY, REFUSED = "accepted", "retry", "refused"

#: The support service refused a counter and said which to use, and the client took it. Its own verdict
#: rather than a `RETRY` the caller has to recognise by its wording: it is the one refusal that
#: repairs itself, and the caller's response — send the same batch again — is not what it does with
#: any other. Matching on the detail string would have made a reworded sentence a hang.
RESYNCED = "resynced"

#: How many times one batch may be re-sent after a counter re-synchronisation.
#:
#: **One, because the second attempt is the diagnosis.** A single client that has lost its place
#: corrects and goes through. Two clients sharing a key — an ordinary CI matrix, two legs pushing
#: in parallel, which is what any adopter with a matrix has on their first attempt — correct
#: *against each other*, and an unbounded loop would let them thrash for as long as both keep
#: trying. Bounded, the second refusal is evidence: the counter moved again while this request was
#: in flight, and only another client can have moved it.
RESYNC_RETRIES = 1

#: The support service positively identified the *content* as unusable, and no retry changes that.
#: Everything else non-2xx is retried: a version the support service does not know yet becomes
#: deliverable when it is upgraded, and discarding is irreversible where a retry costs a request
#: (``ch6-13``). Until a support service speaks the versioned protocol, drift arrives as a bare 400 and
#: is indistinguishable from bad content — so 400 is retried, and 422 is what a versioned
#: support service uses to say the content itself is wrong.
TERMINAL = frozenset({413, 422})


@dataclass(frozen=True)
class Outcome:
    """What became of an attempt. Never an exception — see the module docstring."""

    sent: tuple[str, ...] = ()
    queued: tuple[str, ...] = ()
    refused: tuple[str, ...] = ()
    reason: str = ""

    @property
    def ok(self) -> bool:
        return not self.queued and not self.refused and not self.reason


def deliver(record: SupportRecord, enrolment: Enrolment) -> tuple[bool, str]:
    """One attempt. Returns ``(verdict, detail)`` — never raises for a network condition.

    The verdict is one of :data:`ACCEPTED`, :data:`RETRY` or :data:`REFUSED`. It was a boolean
    once, where ``True`` meant "stop trying" and was read as "arrived", so a refused record was
    dequeued and reported as sent (``ch6-13``).
    """
    request = urllib.request.Request(
        url=enrolment.endpoint.rstrip("/") + "/support",
        data=record.to_wire().encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {enrolment.credential}",
            VERSION_HEADER: str(PROTOCOL_VERSION),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            if response.status in (200, 201, 409):  # 409 = already held; it did arrive
                return ACCEPTED, f"HTTP {response.status}"
            return RETRY, f"HTTP {response.status}"
    except urllib.error.HTTPError as refused:
        # Read the body **first**, and carry what it says. A bare "the service said 507" is a number a
        # user can neither infer nor fix, and the older bearer transport has always explained itself
        # better than this one — which is what happens when the explaining is retrofitted onto the
        # first path and not carried into the second. It is worse than annoying here: the support service
        # distinguishes *I do not know this key* from *that signature does not verify*, and swallowing
        # the body left even the maintainer unable to tell which one a filer had hit.
        detail = ""
        raw = b""
        try:
            raw = refused.read()
            # `HTTPError.read()` answers once; anything downstream that wants the body — and
            # `_accepts` does — gets this copy or gets nothing.
            refused._plumb_body = raw
            said = json.loads(raw.decode())
            detail = said.get("error") or ""
            for extra in ("receiver", "hint", "grants", "use"):
                if said.get(extra) is not None:
                    detail += f" [{extra}: {said[extra]}]"
        except (ValueError, OSError):
            detail = raw.decode("utf-8", "replace")[:200]
        if refused.code == 409:
            return ACCEPTED, "HTTP 409 — already held"
        if refused.code == 426:
            # The support service named a version mismatch. Temporary by nature: it becomes deliverable
            # the moment that support service is upgraded (`ch6-13`).
            return RETRY, f"HTTP 426 — {_accepts(refused)}, will retry"
        if refused.code in TERMINAL:
            return REFUSED, f"HTTP {refused.code} — refused, not retried"
        return RETRY, f"HTTP {refused.code} — will retry"
    except (urllib.error.URLError, OSError, TimeoutError) as unreachable:
        return RETRY, f"unreachable: {unreachable}"


#: How much of a series goes in one request (`dev07-6-2`). Deliberately **below** any holder's
#: limit rather than equal to it: this is the producer's own policy, the support service publishes its
#: cap at `/spec` as `series.max_body_bytes`, and the two are versioned separately and will drift
#: (`dev07-3-2`). Sizing to the cap exactly would mean every future tightening of it lands as a
#: terminal refusal on a live client. A test holds the invariant that this stays under it.
CHUNK_BYTES = 128 * 1024

#: The envelope a batch travels in, allowed for when measuring a chunk. Small, fixed, and counted
#: rather than assumed — the failure it prevents is a chunk that fits by the record bytes alone
#: and goes over once wrapped.
ENVELOPE_BYTES = 64


def _batches(records: list, budget: int) -> list[list]:
    """Split into requests that fit, keeping order. Never returns an empty batch.

    Order is preserved and batches are sent in order, because a sequence says *where in the log*
    and the support service renumbers onto its own — records arriving out of order would be held in an
    order the producer never had.

    A single record over budget gets a batch to itself rather than being dropped or silently
    joined to another. It is the one thing splitting cannot help, so it is handed to the support service
    to answer for: whatever it says is a fact about that record, where a client-side refusal would
    be a guess.
    """
    batches, current, size = [], [], ENVELOPE_BYTES
    for record in records:
        measured = len(json.dumps(asdict(record), separators=(",", ":")).encode("utf-8")) + 1
        if current and size + measured > budget:
            batches.append(current)
            current, size = [], ENVELOPE_BYTES
        current.append(record)
        size += measured
    if current:
        batches.append(current)
    return batches


def _signing(project=None):
    """The account this project pushes as, or ``None`` (`ch12-6`).

    Preferred over the bearer credential wherever one is configured, because a signature is over
    the *content* rather than presented beside it: it survives every hop, binds the body and the
    support service, and is worth nothing to whoever captures it. ``None`` — not an error — where no
    account or no passphrase is set, so the credential route keeps working unchanged and an
    installation that never adopted an account notices nothing (`ch12-5`: two doors, one model).
    """
    from plumb import account_client

    try:
        config = account_client.load()
    except (account_client.NoAccount, OSError, ValueError):
        # No file is not no account: the file holds the endpoint, the public half and a counter,
        # and every one of those is configuration or derivable from the one secret.
        return _derived_account(project)
    try:
        account_client.root()
    except (account_client.NoAccount, OSError, ValueError):
        return None
    return config


def _derived_account(project=None):
    """The same account, rebuilt from the passphrase where no file was left behind (`ch12-13`).

    An identity is **one generated string** — that is the claim, and it is what an ephemeral host
    can be handed. The file beside it holds the endpoint, the public half and a counter, none of
    which is a secret and all of which is either configuration or derivable, so requiring it made
    the claim false for exactly the case it was written for: a runner. Measured on this project's
    own CI recipe and on the printed one — both set `PLUMB_PASSPHRASE` and nothing
    else, both would fall silently back to the bearer route, find no credential either, and report
    *not pushed* on a green build.

    The endpoint comes from `plumb.toml`, where it is reviewable (`ch12-22`). The counter starts at
    zero and is corrected by the support service, which is `ch12-6`'s rule already: a client that has lost
    its place asks and is told, and a runner that keeps nothing has lost its place every time.
    """
    from plumb import account_client, identity
    from plumb.config import Config

    endpoint = Config.find(project or ".").endpoint
    if not endpoint:
        return None
    try:
        secret = account_client.root()
    except (account_client.NoAccount, ValueError, OSError):
        return None
    try:
        public = identity.Identity(secret, account_client.key_label()).public
    except Exception:            # noqa: BLE001 — a missing signing back end is not an account
        return None
    return account_client.AccountConfig(endpoint, public)


def _owning_project(path: Path) -> Path | None:
    """The project a file we were handed belongs to, found by walking up from the file itself.

    ``Config.find`` refuses to search upward and is right to: asked about a *directory*, walking
    parents eventually finds somebody's config and answers with a project the caller never named.
    This is the other question. We were handed a **file** and need to know whose it is, and that is
    not a guess — the nearest ``plumb.toml`` above a series is the project that wrote it.
    """
    from plumb.config import CONFIG_NAME

    here = Path(path).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / CONFIG_NAME).is_file():
            return candidate
    return None


def _configured_subject(store: Path, project: str | None = None) -> str:
    """The series name this project pushes under (`ch12-21`, `ch12-22`).

    It was previously required to arrive *with the credential*, and nothing issued it — which is
    what blocked the first consumer to wire this into CI, and is `ch12-8`'s phantom grant met from
    the outside. The repair is not to make issuance fill it in. Once a store is keyed by whoever
    wrote to it, a subject names a series **inside** that store and grants nothing, so it is the
    project's own to choose and belongs with the rest of its configuration rather than in a secret.

    **Two places to read it and never a third.** What was asked for, or what owns the series. The
    process's working directory used to be the last resort, and it is the one answer that can be
    confidently wrong: run from anywhere else, a push resolved the *standing* directory's subject
    and wrote one project's history into another project's series. Measured — pushing a series out
    of a project declaring `acme-api`, from a checkout declaring `plumb`, sent it as `plumb`, and
    the pull that followed asked for `plumb` too. Both succeeded.

    Nothing about the credential prevents this: a store is keyed by whoever wrote to it (`ch12-21`),
    so the request is properly authenticated and lands in the writer's own store — under the wrong
    name, silently, which is worse than a refusal. Guessing is refused for the reason the push
    already gives when it has nothing to guess from: it would put somebody's history in a
    stranger's file.
    """
    from plumb.config import Config

    # `project` first, because `--project` says which project this command is about and the two
    # halves of one command must not disagree about that. They did: the board read its config from
    # the named directory and the push read its own from the working directory, so a repository
    # whose spec lives in a subdirectory got "no subject to push under" while pointing at a file
    # that said exactly that — the most expensive kind of wrong error, because it sends somebody to
    # edit something already correct.
    owner = _owning_project(Path(store).parent)
    for start in ([Path(project)] if project else []) + ([owner] if owner else []):
        found = Config.find(start)
        if found.subject:
            return found.subject
    return ""


def push_series(store: Path, enrolment_path: Path | None = None,
                project: str | None = None) -> Outcome:
    """Send what the support service has not been given yet (`dev07-6-2`), in batches that fit (`dev07-6-2`),
    and never raise into a caller.

    A board is derived from a run and is **complete without the network**, so a support service being down
    must defer rather than fail the thing that produced the data — otherwise an outage turns every
    board red for a reason that has nothing to do with the project. That is the same posture the
    rest of this module takes for friction (`ch6-7`), for the same reason.

    The mark advances **only on acceptance**, and now once **per accepted batch**: a high-water
    sequence can already express a partial hand-over, so an outage halfway through leaves exactly
    the tail that did not arrive rather than making the whole run's history owed again. Sending
    nothing is a success: an unchanged project has nothing to say, which is the ordinary case.
    """
    from plumb.core.series import InvalidSeries, mark_sent, unsent

    from plumb.transport import for_capability, variables

    account = _signing(project) if enrolment_path is None else None
    destination = None
    if account is None:
        # This capability's own destination, so a team self-hosting a holder is not thereby choosing
        # who answers its support (`snd-D1`). An enrolment still answers where nothing more specific
        # is named, so a project that had one keeps pushing exactly where it did.
        destination = for_capability("series", enrolment_path=enrolment_path,
                                     root=project or Path(store).parent)
        if destination is None:
            endpoint_var, credential_var, _ = variables("series")
            return Outcome(reason=(
                f"no destination named for series — set {endpoint_var} and {credential_var}, or "
                f"enrol. A history stays on this machine, which is the default and not a fault"))
    endpoint = account.endpoint if account else destination.url
    subject = (destination.subject if destination else "") or _configured_subject(store, project)
    if not subject:
        return Outcome(reason=(
            "no subject to push under: name one with `subject = \"…\"` in plumb.toml. It names a "
            "series inside the store your credential owns, so it is yours to choose"))

    try:
        through, pending = unsent(store)
    except InvalidSeries as bad:
        # This module never raises into a caller's workflow, so an unreadable store is an outcome
        # like any other — and a named one, rather than a dataclass constructor's TypeError
        # arriving as a traceback out of a push.
        return Outcome(reason=str(bad))
    if not pending:
        return Outcome()

    url = f"{endpoint.rstrip('/')}/series/{subject}"
    sent: list[str] = []
    # Read here rather than defaulted into the signature: a default binds at import, which makes
    # the budget unchangeable for the life of the process and — worse — makes a test that sets it
    # pass while never splitting anything. That is how the first version of this was proven.
    for batch in _batches(pending, CHUNK_BYTES):
        for attempt in range(RESYNC_RETRIES + 1):
            if account is not None:
                verdict, detail, account = _deliver_signed(endpoint, subject, batch, account)
            else:
                verdict, detail = _deliver_batch(url, batch, destination)
            if verdict != RESYNCED:
                break
            if attempt == RESYNC_RETRIES:
                # Took the value we were told to use and were refused on it too. Nothing this
                # client did can explain that — it is holding the counter the support service named
                # moments ago — so the cause is another client signing with the same key, and
                # saying which is the whole difference between a wait and a rewrite of the CI job.
                verdict = RETRY
                detail = (
                    "the counter moved again while this push was in flight, so something else is "
                    "signing with this key — a build matrix pushing from two legs at once is the "
                    "usual cause. A counter is kept per KEY, and an account holds a set of them "
                    "(`ch12-6`, `ch12-16`), so the repair is a key per concurrent writer rather "
                    "than an account per leg: `plumb account add-key`. Nothing is lost — the "
                    "unsent records stay unsent")
        if verdict == ACCEPTED:
            # Per batch, not at the end: this is what makes a half-finished push worth the part
            # that got through, and it is safe because the mark only ever moves forward.
            mark_sent(store, batch[-1].seq)
            sent.extend(str(record.seq) for record in batch)
            continue
        # Stop at the first failure rather than trying the rest. The batches are ordered and the
        # support service appends in the order it receives, so skipping past a failed one would hand it a
        # history with a hole that later arrivals would be numbered in front of.
        if verdict == REFUSED:
            return Outcome(sent=tuple(sent), refused=(str(store),), reason=detail)
        return Outcome(sent=tuple(sent), queued=(str(store),), reason=detail)
    return Outcome(sent=tuple(sent))


#: Which fields carry the adopter's own words rather than facts about a run (`dev07-6-2`). A test node
#: id and an aspect are written in the adopter's language and describe behaviour; a subject is a
#: story id they already publish, a result and a timestamp describe the run. Only the first two are
#: replaced.
PSEUDONYMISED = ("test", "about")


def pseudonymise(records: list[dict], key: bytes, account: str) -> list[dict]:
    """Replace the adopter's own names with a keyed token, keeping identity (`dev07-6-2`).

    The same name gives the same token run after run, so *which subject changes most often* survives
    — which omitting the field would have destroyed. `None` is left alone: an aspect that is absent
    is a fact about the citation and pseudonymising it would invent one.
    """
    from plumb import identity

    out = []
    for record in records:
        copy = dict(record)
        for field in PSEUDONYMISED:
            if copy.get(field):
                copy[field] = identity.token(key, str(copy[field]), account)
        out.append(copy)
    return out


def wire_form(store: Path, enrolment_path: Path | None = None,
              project: str | None = None) -> tuple[list[dict], str]:
    """Exactly what a push would send, and nothing sent (`dev07-6-2`).

    Built by the same path the push uses rather than described beside it, because a preview assembled
    separately is a second answer that is free to disagree with the real one — and the whole point is
    that an adopter can *see* what leaves rather than read source to find out.
    """
    from dataclasses import asdict

    from plumb.core.series import unsent

    _, pending = unsent(store)
    records = [asdict(r) for r in pending]
    account = _signing() if enrolment_path is None else None
    if account is None:
        return records, "sent under a credential, with your own names carried as written"
    try:
        key = _digest_key()
    except Exception:
        return records, "sent signed; names would be replaced but the passphrase is not set"
    return (pseudonymise(records, key, account.public[:16]),
            "sent signed, with test and about replaced by a keyed token")


def _digest_key() -> bytes:
    """The key this account's names are replaced under — **read, not recomputed** (``ch12-24``).

    Derived once when the account was made and carried on the account since. Recomputing it from
    whatever root is current would mean that replacing a lost root silently renames every subject an
    adopter already holds, which is the one thing a pseudonym must not do to the person it belongs
    to. Falling back to deriving is for an account written before the field existed, and it
    reproduces exactly what that account was already using.
    """
    from plumb import account_client, identity

    secret = account_client.root()
    try:
        carried = account_client.load().digest_key
    except account_client.NoAccount:
        carried = ""
    return bytes.fromhex(carried) if carried else identity.digest_key(secret)


def _deliver_signed(endpoint: str, subject: str, batch: list, config):
    """One signed request, and the counter advances whatever the answer is (`ch12-6`).

    A counter is a *place in this key's sequence*, not a record of success: reusing one after a
    refusal is a replay by construction, and the support service cannot tell an honest retry from one. So
    it is saved before the outcome is known, and the returned config carries the value the next
    batch must use. A refusal that says which value to use is answered by taking it, which is what
    makes a client that has lost its place correct itself rather than stall.
    """
    from plumb import account_client

    path = f"/series/{subject}"
    # Pseudonymised on the signed route only, because that is the route with a root to key from
    # (`ch12-24`). A bearer credential carries no secret of the adopter's, so there is nothing to
    # key with and the names travel as written — stated rather than left to be discovered.
    records = [asdict(r) for r in batch]
    try:
        records = pseudonymise(records, _digest_key(), config.public[:16])
    except Exception:
        pass
    body = json.dumps({"records": records}).encode("utf-8")
    try:
        headers, advanced = account_client.signed(config, "POST", path, body)
    except Exception as unusable:  # a missing back end or a refused passphrase, named not swallowed
        return RETRY, f"cannot sign: {unusable}", config
    account_client.save(advanced)
    headers.update({"Content-Type": "application/json", VERSION_HEADER: str(PROTOCOL_VERSION)})
    request = urllib.request.Request(url=f"{endpoint.rstrip('/')}{path}", data=body,
                                     method="POST", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS):
            return ACCEPTED, "", advanced
    except urllib.error.HTTPError as refused:
        # Read the body **first**, and carry what it says. A bare "the service said 507" is a number a
        # user can neither infer nor fix, and the older bearer transport has always explained itself
        # better than this one — which is what happens when the explaining is retrofitted onto the
        # first path and not carried into the second. It is worse than annoying here: the support service
        # distinguishes *I do not know this key* from *that signature does not verify*, and swallowing
        # the body left even the maintainer unable to tell which one a filer had hit.
        detail = ""
        raw = b""
        try:
            raw = refused.read()
            # `HTTPError.read()` answers once; anything downstream that wants the body — and
            # `_accepts` does — gets this copy or gets nothing.
            refused._plumb_body = raw
            said = json.loads(raw.decode())
            detail = said.get("error") or ""
            for extra in ("receiver", "hint", "grants", "use"):
                if said.get(extra) is not None:
                    detail += f" [{extra}: {said[extra]}]"
        except (ValueError, OSError):
            detail = raw.decode("utf-8", "replace")[:200]
        if refused.code == 409:
            # The support service told us the value to use. Take it rather than reporting a failure a
            # person has to interpret — this is the one refusal that repairs itself.
            try:
                use = json.loads(raw.decode()).get("use")
            except (ValueError, OSError):
                use = None
            if use is not None:
                # `replace`, never a fresh AccountConfig: rebuilding it from three fields silently
                # dropped every field added since, and one of them records that this account has
                # ever been proved — so a re-synchronised push would have un-recorded it.
                return (RESYNCED, "counter re-synchronised with the support service",
                        replace(advanced, counter=use - 1))
        if refused.code in TERMINAL:
            return REFUSED, f"support service refused ({refused.code}) at seq {batch[0].seq}: {detail}", advanced
        return RETRY, f"support service said {refused.code}: {detail}", advanced
    except (urllib.error.URLError, TimeoutError, OSError) as unreachable:
        return RETRY, f"support service unreachable: {unreachable}", advanced


def _deliver_batch(url: str, batch: list, sending_as) -> tuple[str, str]:
    """One request. Same three verdicts as :func:`deliver`, and never raises for a network
    condition — see the module docstring."""
    request = urllib.request.Request(
        url=url,
        data=json.dumps({"records": [asdict(r) for r in batch]}).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {sending_as.credential}",
                 VERSION_HEADER: str(PROTOCOL_VERSION)})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS):
            return ACCEPTED, ""
    except urllib.error.HTTPError as refused:
        if refused.code in TERMINAL:
            # Positively identified as unusable, and no retry changes it. The mark still does not
            # move — a refused batch is not a sent one, and treating "stop trying" as "arrived" is
            # the bug `ch6-13` already records against friction.
            return REFUSED, f"support service refused ({refused.code}) at seq {batch[0].seq}"
        return RETRY, f"support service said {refused.code}"
    except (urllib.error.URLError, OSError, TimeoutError) as unreachable:
        return RETRY, f"support service unreachable: {unreachable}"


def _accepts(refused: urllib.error.HTTPError) -> str:
    """What the other end said it speaks. A refusal that names nothing is a dead end.

    Reads the body it is handed rather than reaching for the stream: `HTTPError.read()` answers
    once, and this function's caller is not always first — which is how a refusal that named
    everything (`accepts`, `sent`) got reported as naming nothing, on 2026-09-12, while the
    service's 426 was exemplary the whole time.
    """
    try:
        body = getattr(refused, "_plumb_body", None)
        if body is None:
            body = refused.read()
        said = json.loads(body.decode("utf-8"))
        accepts = said.get("accepts")
        sent = said.get("sent")
        return (f"support service accepts {accepts}, this request sent {sent}, "
                f"this client speaks {PROTOCOL_VERSION}")
    except Exception:
        return f"version mismatch; this client speaks {PROTOCOL_VERSION}"


def _sending_as(enrolment_path: Path | None = None, root: Path | str = ".") -> Enrolment:
    """Where support sends, resolved the way every capability resolves (`snd1-ur1`).

    Support used `load()` directly, which reads the machine-wide pair and the enrolment file and
    knows nothing of a capability's own variables. So `PLUMB_SUPPORT_ENDPOINT` — documented as
    where records go — moved `poll`, `turn` and `case`, which go through `transport`, and did not
    move `file` or `send`, which came through here. An adopter who set it was told their records
    were staying local while the tool reported the endpoint configured.

    `transport.for_capability` already falls back to the machine-wide pair and then to the
    enrolment file, so nothing that resolved before stops resolving: this widens what is read and
    narrows nothing.

    The relationship is `self` because a locally assembled one is a claim by the filer that the
    service overwrites from the credential it authenticated (`ch12-19`).
    """
    from plumb.transport import for_capability

    found = for_capability("support", enrolment_path=enrolment_path, root=root)
    if found is None:
        # Deferred to `load`, which is the one place that explains an absence, and absence is the
        # ordinary state rather than a failure (`snd2-sr1`).
        return load(enrolment_path, root)
    return Enrolment("self", found.credential, found.url, found.subject)


def pull_friction(destination: Path, enrolment_path: Path | None = None) -> Outcome:
    """Fetch what the support service holds into a directory (`ch6-17`).

    The evidence for this story was a corpus review that took `ssh`, `sudo` and `tar` against a
    path read out of a deploy script — and found that no store held the whole thing. A read that
    needs shell access to the host is a read only its host's owner has, which makes the store
    write-only for every other purpose it was built for.

    Additive on purpose. A record already present is left exactly as it is rather than refetched:
    `ch6-20` makes the received copy the authority, so a local file that differs is a divergence to
    look at rather than something to quietly overwrite while pulling.
    """
    try:
        enrolment = _sending_as(enrolment_path)
    except NotEnrolled as why:
        return Outcome(reason=str(why))
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    try:
        index = _get_json(f"{enrolment.endpoint.rstrip('/')}/support", enrolment)
    except urllib.error.HTTPError as refused:
        if refused.code == 403:
            return Outcome(reason="the support service holds this store for its operator, and this "
                                  "credential is not theirs")
        return Outcome(reason=f"the support service answered {refused.code}")
    except (urllib.error.URLError, TimeoutError) as unreachable:
        return Outcome(reason=f"support service unreachable: {unreachable}")

    fetched, kept, unreadable = 0, 0, []
    for entry in index.get("records", []):
        record_id = entry.get("id")
        if entry.get("unreadable"):
            # The support service could not read it either. Named rather than skipped silently
            # (`ch6-16`), because a pull that is quietly short reads exactly like a small corpus.
            unreadable.append(record_id)
            continue
        landing = destination / f"{record_id}.json"
        if landing.exists():
            kept += 1
            continue
        try:
            whole = _get_json(f"{enrolment.endpoint.rstrip('/')}/support/{record_id}", enrolment)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as failed:
            # One record the support service will not hand over must not take the other hundred with it —
            # `ch6-16`'s posture, which the *index* already held and the pull did not. Measured: a
            # state file dropped into the record directory was indexed with a null id, the fetch
            # answered 422, and the whole pull died in a traceback after writing 146 records it
            # then did not report. Named here rather than swallowed, so a short pull says it is
            # short.
            unreadable.append(f"{record_id}: {failed}")
            continue
        landing.write_text(json.dumps(whole, indent=2) + "\n")
        fetched += 1

    landed = {e.get("id") for e in index.get("records", [])} - {u.split(":")[0] for u in unreadable}
    pulled = tuple(sorted(str(destination / f"{e}.json") for e in landed if e))
    if unreadable:
        # Named, never dropped silently: a pull that is quietly short reads exactly like a small
        # corpus (`ch6-16`).
        return Outcome(sent=pulled, refused=tuple(sorted(unreadable)),
                       reason="unreadable on the support service")
    return Outcome(sent=pulled)


def _get_json(url: str, enrolment: Enrolment) -> dict:
    request = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {enrolment.credential}",
        VERSION_HEADER: str(PROTOCOL_VERSION)})
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as answer:
        return json.loads(answer.read().decode("utf-8"))


def send_one(record: SupportRecord, store: SupportStore, enrolment_path: Path | None = None) -> Outcome:
    """File-and-forget: deliver if enrolled and reachable, otherwise leave it queued."""
    try:
        enrolment = _sending_as(enrolment_path)
    except (NotEnrolled, ValueError, json.JSONDecodeError) as not_enrolled:
        return Outcome(reason=str(not_enrolled))  # local by default (ch6-6) — not a failure

    verdict, detail = deliver(record, enrolment)
    if verdict == ACCEPTED:
        store.dequeue(record.id)
        return Outcome(sent=(record.id,), reason=detail)
    # Refused or retryable, the record stays in the outbox either way. A refusal is the record a
    # human should look at, and quietly clearing it from the outbox is how it gets forgotten —
    # removal is an operation somebody performs (`ch6-9`), never a side effect of a rejection.
    store.enqueue(record.id)
    if verdict == REFUSED:
        return Outcome(refused=(record.id,), reason=detail)
    return Outcome(queued=(record.id,), reason=detail)


def drain(store: SupportStore, enrolment_path: Path | None = None) -> Outcome:
    """Retry everything in the outbox. Stops at the first unreachable attempt rather than
    hammering a down endpoint once per queued record."""
    try:
        enrolment = _sending_as(enrolment_path)
    except (NotEnrolled, ValueError, json.JSONDecodeError) as not_enrolled:
        return Outcome(reason=str(not_enrolled))

    sent, still_queued, refused, reason = [], [], [], ""
    for record_id in store.queued():
        if reason:
            still_queued.append(record_id)
            continue
        try:
            record = store.get(record_id)
        except KeyError:
            store.dequeue(record_id)  # withdrawn while queued (ch6-9); nothing to send
            continue
        verdict, detail = deliver(record, enrolment)
        if verdict == ACCEPTED:
            store.dequeue(record_id)
            sent.append(record_id)
        elif verdict == REFUSED:
            # Refused on content: keep it, name it, and carry on draining the rest. One bad
            # record must not stall the queue behind it, and must not vanish from it either.
            refused.append(record_id)
        else:
            still_queued.append(record_id)
            reason = detail  # a retryable condition stops the drain; the rest stay queued
    return Outcome(sent=tuple(sent), queued=tuple(still_queued),
                   refused=tuple(refused), reason=reason)
