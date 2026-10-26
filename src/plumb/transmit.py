"""Sending a record, and not caring much whether it arrives (``dev07-6-2-1-2``, ``dev07-6-2-1-4-ur3``).

Capture never blocks the work. An unreachable endpoint is not an error the contributor should
ever see: the record is already safe on their disk, it is marked in the outbox, and the next
attempt drains it. Nothing here raises into a caller's workflow — the return value says what
happened and the work carries on either way.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

from plumb.enrolment import Enrolment, NotEnrolled, load

TIMEOUT_SECONDS = 10

#: The conversation this client speaks, announced on every request. Deliberately NOT
#: any artifact's schema version: sending a record's number in a version header is the exact
#: confusion that forced a contract to be written to settle it. A durable artifact says its own
#: version where that belongs — stamped in the body, by the schema that wrote it.
#:
#: The header keeps its name. It is what a holder already matches on, and renaming a wire field to
#: tidy up a word is a break for every deployed service in exchange for nothing.
PROTOCOL_VERSION = 2
VERSION_HEADER = "Plumb-Support-Version"

#: What an attempt came to. Three outcomes rather than two, because "it arrived" and "stop
#: trying" are different facts and collapsing them is how a refused record got reported as sent.
ACCEPTED, RETRY, REFUSED = "accepted", "retry", "refused"

#: The support service positively identified the *content* as unusable, and no retry changes that.
#: Everything else non-2xx is retried: a version the support service does not know yet becomes
#: deliverable when it is upgraded, and discarding is irreversible where a retry costs a request
#: (``dev07-6-2-ur3``). Until a support service speaks the versioned protocol, drift arrives as a bare 400 and
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
    """The series name this project pushes under (`dev07-6-2-ur7`).

    It was previously required to arrive *with the credential*, and nothing issued it — which is
    what blocked the first consumer to wire this into CI. The repair is not to make issuance fill it in. Once a store is keyed by whoever
    wrote to it, a subject names a series **inside** that store and grants nothing, so it is the
    project's own to choose and belongs with the rest of its configuration rather than in a secret.

    **Two places to read it and never a third.** What was asked for, or what owns the series. The
    process's working directory used to be the last resort, and it is the one answer that can be
    confidently wrong: run from anywhere else, a push resolved the *standing* directory's subject
    and wrote one project's history into another project's series. Measured — pushing a series out
    of a project declaring `acme-api`, from a checkout declaring `plumb`, sent it as `plumb`, and
    the pull that followed asked for `plumb` too. Both succeeded.

    Nothing about the credential prevents this: a store is keyed by whoever wrote to it,
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
    board red for a reason that has nothing to do with the project. That is `dev07-6-2-1-4-ur3`.

    The mark advances **only on acceptance**, and now once **per accepted batch**: a high-water
    sequence can already express a partial hand-over, so an outage halfway through leaves exactly
    the tail that did not arrive rather than making the whole run's history owed again. Sending
    nothing is a success: an unchanged project has nothing to say, which is the ordinary case.
    """
    from plumb.core.series import InvalidSeries, mark_sent, unsent

    from plumb.transport import for_capability, variables

    # This capability's own destination, so a team self-hosting a holder is not thereby choosing
    # who answers its support (`dev07-6-2-1-D1`). An enrolment still answers where nothing more specific
    # is named, so a project that had one keeps pushing exactly where it did.
    destination = for_capability("series", enrolment_path=enrolment_path,
                                 root=project or Path(store).parent)
    if destination is None:
        endpoint_var, credential_var, _ = variables("series")
        return Outcome(reason=(
            f"no destination named for series — set {endpoint_var} and {credential_var}, or "
            f"enrol. A history stays on this machine, which is the default and not a fault"))
    subject = destination.subject or _configured_subject(store, project)
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

    url = f"{destination.url.rstrip('/')}/series/{subject}"
    sent: list[str] = []
    # Read here rather than defaulted into the signature: a default binds at import, which makes
    # the budget unchangeable for the life of the process and — worse — makes a test that sets it
    # pass while never splitting anything. That is how the first version of this was proven.
    for batch in _batches(pending, CHUNK_BYTES):
        verdict, detail = _deliver_batch(url, batch, destination)
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
    return records, "sent under a credential"


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
            # what `dev07-6-2-ur3` refuses.
            return REFUSED, f"support service refused ({refused.code}) at seq {batch[0].seq}"
        return RETRY, f"support service said {refused.code}"
    except (urllib.error.URLError, OSError, TimeoutError) as unreachable:
        return RETRY, f"support service unreachable: {unreachable}"












