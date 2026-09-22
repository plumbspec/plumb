"""The support channel: a correspondence, not a drop box (``ch6-30``).

A record used to travel one way. The support service held it, the operator read it somewhere else, and
anything they needed to ask went by whatever route they could find — which is how a support channel
becomes an inbox nobody can track. This is the other half: a case is opened by filing, and then both
sides add **turns** to it until it is done.

**Why the shape is unusual.** The parties are ordinarily two agents, not a person and a form. The
filer's side can read the project; the support service's cannot and must not. So the traffic is questions
and answers rather than a description — *what depth is that story cited at*, answered from the code
by something standing next to it. No source crosses this wire, and the record's ``excerpt`` stays
`withheld` by default because of it.

**Three things are the support service's to say, and this client never sends them.** The case's `state`,
who authored a turn, and the id of a question. A client that could type its own state would be
typing its own verdict (`dev07-4-3-nfr3`), and a client that proposes an ask id will eventually propose one
that collides — which happened, cost a rewrite, and is why the field is gone rather than validated.

**`after` is the whole of how concurrency stays legible.** Every turn carries the number of turns its
author had read when composing, so a reader knows what a reply could possibly be answering instead of
inferring it from position. Adjacency is not causality once both sides compose at once, and both
sides do. It is also the cursor for reading: you read at *n* and you post with ``after=n``, one
number doing both jobs.

**Nothing here ever raises into a caller.** A support channel being unreachable must never fail the
thing an adopter was doing (`ch6-7`), so every function returns an `Answer` and a refusal is data.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

#: What this client speaks. Sent on every request; a support service that does not speak it answers 426 and
#: names what it does, so a client retries at a named version rather than discarding the case.
VERSION = "2"
VERSION_HEADER = "Plumb-Support-Version"

#: Refusals a caller must never retry, and the reason each is terminal is different — which is why
#: the support service names which kind rather than leaving a client to parse prose. A malformed record is
#: fixed by editing it; a reached bound by withdrawing something; an oversized body by sending less.
#: Telling a client to "try again later" for any of them is telling it to loop forever.
TERMINAL = {"content", "quota", "size", "version", "credential", "absent", "duplicate"}


@dataclass(frozen=True)
class Answer:
    """What came back. ``ok`` is the only thing most callers need; the rest is for a refusal.

    ``retryable`` is the distinction the outbox turns on and it is not derivable from the status
    code alone: 429 and 5xx clear by waiting, and a 422 never does however long anybody waits.
    """

    ok: bool
    status: int = 0
    body: dict = field(default_factory=dict)
    reason: str = ""
    retryable: bool = False

    @property
    def refused(self) -> str:
        """Which kind of refusal, in the support service's vocabulary, or ``""``."""
        return str(self.body.get("refused", ""))


class Channel:
    """One support service, one credential. Cheap to construct and holding no connection.

    Deliberately not a session: the process this runs in is a CLI that exits, and a held connection
    would be state nothing is around to keep. What replaces it is the cursor — every request carries
    its own position, so a dropped read costs nothing and a restarted service costs nothing.
    """

    def __init__(self, endpoint: str, credential: str, timeout: float = 15.0):
        self.endpoint = endpoint.rstrip("/")
        self.credential = credential
        self.timeout = timeout

    # -- the four things a filer does ------------------------------------------------------

    def open(self, record: dict) -> Answer:
        """File a record, which opens the case it becomes.

        A second arrival under one id is the same case sent twice — an id is fixed at capture
        (`ch6-11`) and `ch6-7` retries an unacknowledged send, so that is the ordinary path rather
        than an error. It answers 409 and the outbox clears, which is the outcome both sides want.
        """
        return self._request("POST", "/support", record)

    def mine(self, waiting_on: str = "") -> Answer:
        """Cases this credential may see. ``waiting_on='filer'`` is *what needs me*."""
        query = f"?waiting_on={waiting_on}" if waiting_on else ""
        return self._request("GET", f"/support/mine{query}")

    def case(self, case_id: str, since: int | None = None) -> Answer:
        """One case, whole — or only what is new, given the cursor from last time.

        ``since`` is not an optimisation. It is why a dropped read costs nothing: the position
        travels with the request, so reconnecting after a support service restart returns what arrived in
        the gap rather than waiting for it a second time.
        """
        query = f"?since={since}" if since is not None else ""
        return self._request("GET", f"/support/{case_id}{query}")

    def say(self, case_id: str, says: str = "", asks=(), answers=(), after: int = 0) -> Answer:
        """Add a turn: answer, ask, or both.

        ``asks`` carry a question and what they expect, **never an id** — the support service assigns
        those. ``answers`` name the ``ask_id`` they respond to and carry exactly one of ``value`` or
        ``absence``, because *I may not tell you* and *I do not know* route differently: one needs a
        different question, the other needs somebody's permission.
        """
        body = {"says": says, "asks": list(asks), "answers": list(answers), "after": after}
        return self._request("POST", f"/support/{case_id}/turn", body)

    def close(self, case_id: str, after: int) -> Answer:
        """Say this is finished, and stop being asked about it.

        **Not withdrawal.** Closing removes nothing — it is a statement about wanting to be left
        alone, and a later turn reopens it, because a state nobody can move is one somebody typed
        once. Withdrawal is the other act and takes the words back.

        Declared with ``after`` because it is a state declaration, and a declaration that cannot say
        what its author had read cannot be checked at all.
        """
        return self._request("POST", f"/support/{case_id}/turn",
                             {"sets_state": "closed", "after": after, "says": ""})

    def withdraw(self, case_id: str) -> Answer:
        """Take the words back (`ch6-9`). Returns them, and leaves the bare fact.

        Idempotent: withdrawing what is already withdrawn answers 200, because a contributor should
        never have to know whether their first attempt landed.
        """
        return self._request("DELETE", f"/support/{case_id}")

    # -- one place a request is made ---------------------------------------------------------

    def _request(self, method: str, path: str, body: dict | None = None) -> Answer:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            f"{self.endpoint}{path}", method=method, data=data,
            headers={"Authorization": f"Bearer {self.credential}",
                     VERSION_HEADER: VERSION,
                     **({"Content-Type": "application/json"} if data else {})})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as answered:
                raw = answered.read()
                return Answer(True, answered.status, json.loads(raw) if raw else {})
        except urllib.error.HTTPError as refused:
            return self._refusal(refused)
        except urllib.error.URLError as unreachable:
            # The support service is not there. Different from being busy, and the same outcome for a
            # caller: keep what you were sending and try later. Never a traceback into a run.
            return Answer(False, 0, reason=f"cannot reach {self.endpoint}: {unreachable.reason}",
                          retryable=True)
        except (TimeoutError, OSError) as broke:
            return Answer(False, 0, reason=f"cannot reach {self.endpoint}: {broke}", retryable=True)

    def _refusal(self, refused: urllib.error.HTTPError) -> Answer:
        try:
            body = json.loads(refused.read() or b"{}")
        except ValueError:
            body = {}
        kind = str(body.get("refused", ""))
        # **The kind decides, and the status code only fills in.** A support service naming the kind is
        # telling a client what to do about it, and that is not recoverable from 422 alone — the
        # same code carries a malformed record and a full account, which need opposite responses.
        if kind:
            retryable = kind not in TERMINAL
        else:
            retryable = refused.code == 429 or refused.code >= 500
        return Answer(False, refused.code, body,
                      reason=str(body.get("error", refused.reason or "")), retryable=retryable)


def from_enrolment(enrolment_path: Path | None = None, root=None) -> tuple[Channel | None, str]:
    """A channel from this machine's enrolment, or ``None`` and why not.

    **No endpoint is the ordinary state, not a fault.** The tool is complete with nothing
    configured: records are filed locally and stay there, which is what an adopter who has arranged
    no channel should get. So the absence is reported as a plain fact rather than an error, and
    every caller prints it and carries on.
    """
    from plumb.enrolment import NotEnrolled, load

    try:
        enrolment = load(enrolment_path, root=root)
    except NotEnrolled as why:
        return None, str(why)
    if not enrolment.endpoint:
        return None, "no endpoint configured — records stay local"
    return Channel(enrolment.endpoint, enrolment.credential), ""
