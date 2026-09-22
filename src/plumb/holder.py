"""What a holder can be asked, in terms a directory and a database can both answer (``dev07-6-2``).

Retention is `dev07-6-2`'s bound, and it was written in ``stat``: a pool summed from file sizes, an
eviction order read from the mtime-shaped contents of a marker file beside each log. Those are not
policies about files. They are policies about *histories* that happen to be spelled in the only
vocabulary the first implementation had, and a second implementation is not a port until they are
restated in terms both can answer.

**This is the vocabulary, and it is deliberately small.** Every question here is one a directory
answers by walking itself and a database answers with a query. What is *not* here is as much of the
point: no paths, no globs, no file handles, and no notion that a subject is a file. A caller that
needs one of those has found a policy that has not been restated yet.

**Keyed by subject and nothing above it.** A holder used to key everything by an owning account,
because a holder authenticated one. This one does not: it is a place an adopter puts their own
histories, and there is no second party to be told apart from. What is left is the question that was
always the real one — *which histories are here, how big are they, and did anybody come back for
them* — with the party dropped out of it.

**The policy does not live here.** *When* to compact, *what order* to evict in and *how much* is too
much are the holder's answers, and they are the same answers whichever backend is underneath — so
they stay with the holder that reads them. What lives here is the facts those policies are computed
from and the operations they invoke. Splitting it the other way would give each backend its own copy
of the bound, which is how two implementations come to disagree about what they are enforcing.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Holder(Protocol):
    """The questions retention asks, and nothing else.

    Named for chapter 11's word: a holder is the one place a history lives, and what it promises is
    the wire rather than the shape it keeps behind it (``dev07-6-2``).
    """

    def subjects(self) -> list[str]:
        """Every series held, in a stable order."""

    def bytes_held(self, subject: str | None = None) -> int:
        """Bytes held: for one series, or — with nothing named — for the whole pool.

        A count of bytes rather than of records because that is what the bound is written in: disk
        is what an operator provisions, and a record count is not something anybody buys it by.
        """

    def last_retrieved(self, subject: str) -> str:
        """When somebody last came for this, or ``""`` if nobody has.

        Sorts as a string on purpose — the stored form is an ISO-8601 UTC instant, so lexical order
        *is* chronological order, and never-retrieved sorts first because the empty string does.
        That is the eviction order falling out of the representation rather than being computed.
        """

    def mark_retrieved(self, subject: str) -> None:
        """Note that somebody came for this, which is what keeps it."""

    def is_tombstone(self, subject: str) -> bool:
        """Is this nothing but the record that it was discarded?

        Asked because discarding one again reclaims nothing, and a loop that does not ask walks
        past a live series to do it — measured once, on a busy adopter's history.
        """

    def churn(self, subject: str) -> tuple[int, int]:
        """``(records, facts)`` — how much is stored against how much it says.

        The ratio compaction fires on, handed over as its two numbers rather than as a verdict. A
        holder can count both cheaply and neither is a property of files; whether the ratio warrants
        compacting is the holder's to decide, once, for every backend.
        """

    def compact(self, subject: str, reason: str) -> None:
        """Collapse everything but the last record into a fresh base, recording what went."""

    def discard(self, subject: str, reason: str) -> int:
        """Replace a whole series with the record that it was discarded. Returns bytes reclaimed.

        **A tombstone, not a deletion** (``dev07-6-2``): a subject deleted outright has nowhere left to
        record that it went, and a reader would meet *never held* — the flattering answer, from the
        one operation that knows better.
        """


class FileHolder:
    """The layout that exists: ``series/<subject>.jsonl`` with sidecar markers.

    `dev07-6-2` is what makes this layout safe to keep private: it is working state, promised to
    nobody, and it changed twice in one day without either change touching the wire.
    """

    #: A tombstone is one short line, so anything larger is answered by its size without opening it.
    TOMBSTONE_CEILING = 4096

    def __init__(self, root, lock=None, log=None):
        from pathlib import Path

        self.root = Path(root) / "series"
        # The holder's per-subject lock, so a discard and an append never interleave. Passed in
        # rather than owned: the append path is still the holder's, and two lock tables keyed the
        # same way would be two locks that do not exclude each other.
        self._lock = lock or _no_lock
        self._log = log or (lambda *a: None)

    # ── what is held ──────────────────────────────────────────────────────────────────────

    def subjects(self) -> list[str]:
        return sorted(p.stem for p in self.root.glob("*.jsonl")) if self.root.is_dir() else []

    def bytes_held(self, subject: str | None = None) -> int:
        if not self.root.is_dir():
            return 0
        if subject is None:
            return sum(log.stat().st_size for log in self.root.glob("*.jsonl"))
        one = self._log_of(subject)
        return one.stat().st_size if one.is_file() else 0

    # ── whether anybody came for it ───────────────────────────────────────────────────────

    def last_retrieved(self, subject: str) -> str:
        marker = self._log_of(subject).with_suffix(".retrieved")
        return marker.read_text().strip() if marker.is_file() else ""

    def mark_retrieved(self, subject: str) -> None:
        from datetime import datetime, timezone

        marker = self._log_of(subject).with_suffix(".retrieved")
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

    # ── what it says ──────────────────────────────────────────────────────────────────────

    def is_tombstone(self, subject: str) -> bool:
        log = self._log_of(subject)
        if not log.is_file() or log.stat().st_size > self.TOMBSTONE_CEILING:
            return False
        lines = [line for line in log.read_text().splitlines() if line.strip()]
        return len(lines) == 1 and "discarded_from" in lines[0]

    def churn(self, subject: str) -> tuple[int, int]:
        from plumb.core.series import read, state

        records = read(self._log_of(subject))
        return len(records), len(state(records))

    # ── what it does about it ─────────────────────────────────────────────────────────────

    def compact(self, subject: str, reason: str) -> None:
        from datetime import datetime, timezone

        from plumb.core.series import compact, read

        log = self._log_of(subject)
        with self._lock(subject):
            records = read(log)
            if len(records) < 2:
                return  # nothing but a base: compaction reclaims churn, and there is none
            compact(log, through=records[-1].seq - 1, reason=reason,
                    when=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))

    def discard(self, subject: str, reason: str) -> int:
        """Staged and renamed rather than truncated in place, because housekeeping runs after the
        response is flushed so a reader can arrive mid-rewrite, and a truncate-then-write leaves a
        window in which the log is empty."""
        import json
        from datetime import datetime, timezone

        from plumb.core.series import Discarded, last_seq

        log = self._log_of(subject)
        with self._lock(subject):
            before, through = log.stat().st_size, last_seq(log)
            note = Discarded(seq=1, discarded_from=1, discarded_through=through,
                             when=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                             reason=reason)
            staging = log.with_suffix(".evicting")
            staging.write_text(json.dumps(note.__dict__, separators=(",", ":")) + "\n")
            staging.replace(log)
            reclaimed = before - log.stat().st_size
        self._log("series: discarded %s (%d bytes) — %s", subject, reclaimed, reason)
        return reclaimed

    # ── the one place a path is spelled ───────────────────────────────────────────────────

    def _log_of(self, subject: str):
        return self.root / f"{subject}.jsonl"


class _no_lock:
    """For a caller with no lock table — a test, or a holder nothing else is writing to."""

    def __init__(self, _key): pass
    def __enter__(self): return self
    def __exit__(self, *_): return False
