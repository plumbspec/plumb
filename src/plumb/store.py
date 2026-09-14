"""The contributor's own store, and the outbox behind it (``ch6-6``, ``ch6-7``, ``ch6-9``).

A record is one file, which is what makes withdrawal an operation rather than an excavation. The
outbox is a directory of marker files rather than an in-memory list, because ``ch6-7``'s promise
that an unreachable endpoint costs the contributor nothing is empty if the queue dies with the
process.
"""

import re
from datetime import datetime, timezone
from pathlib import Path

import json

from plumb.support import (SCHEMA_VERSION, SupportRecord, InvalidRecord,
                             Unreadable, load_all)

MAX_ID_LENGTH = 72


class SupportStore:
    """Records under ``root``; anything awaiting transmission marked in ``root/outbox``."""

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.outbox = self.root / "outbox"

    def _ensure(self) -> None:
        self.outbox.mkdir(parents=True, exist_ok=True)

    def file(self, record: SupportRecord, *, queue: bool = False) -> Path:
        """Write a record, optionally marking it to be sent. Validation already happened at
        construction (``ch6-4``), so nothing invalid can reach the disk."""
        self._ensure()
        path = record.write_to(self.root)
        if queue:
            self.enqueue(record.id)
        return path

    def all(self) -> tuple[list[SupportRecord], list[Unreadable]]:
        """Every record that parses, and every file that does not (``ch6-16``). The caller gets
        both because it has to surface both — see `load_all`."""
        return load_all(self.root) if self.root.is_dir() else ([], [])

    def migrate(self) -> tuple[list[str], list[Unreadable]]:
        """Rewrite every record below the current schema, in place (``ch6-23``).

        Reading already migrates in memory, so nothing depends on this having been run — it exists
        so the climb happens once rather than on every load, and so a step can be retired once no
        record still needs it. Records already current are not touched, which makes it idempotent
        and cheap to run again.
        """
        upgraded: list[str] = []
        failed: list[Unreadable] = []
        for path in sorted(self.root.glob("*.json")) if self.root.is_dir() else []:
            try:
                text = path.read_text()
                if int(json.loads(text).get("version", 0)) >= SCHEMA_VERSION:
                    continue
                SupportRecord.from_json(text).write_to(self.root)
            except (InvalidRecord, ValueError, OSError) as bad:
                failed.append(Unreadable(path, str(bad)))
                continue
            upgraded.append(path.stem)
        return upgraded, failed

    def get(self, record_id: str) -> SupportRecord:
        path = self.root / f"{record_id}.json"
        if not path.is_file():
            raise KeyError(record_id)
        return SupportRecord.from_json(path.read_text())

    def withdraw(self, record_id: str) -> bool:
        """Remove the record and anything pending for it (``ch6-9``). Idempotent: withdrawing
        what is already gone is not an error, because a contributor should never have to know
        whether their first attempt landed."""
        removed = False
        path = self.root / f"{record_id}.json"
        if path.is_file():
            path.unlink()
            removed = True
        self.dequeue(record_id)
        return removed

    # ── the outbox (ch6-7) ────────────────────────────────────────────────────

    def enqueue(self, record_id: str) -> None:
        self._ensure()
        (self.outbox / record_id).touch()

    def dequeue(self, record_id: str) -> None:
        marker = self.outbox / record_id
        if marker.exists():
            marker.unlink()

    def queued(self) -> list[str]:
        if not self.outbox.is_dir():
            return []
        return sorted(p.name for p in self.outbox.iterdir() if p.is_file())

    def queued_since(self) -> float | None:
        """When the oldest thing still waiting was queued, or ``None`` if nothing is.

        **Correct behaviour and invisible behaviour are the same behaviour here**, which is the
        whole reason this exists. `ch6-7` queues rather than erroring so a holder being down never
        fails an adopter's run — and the cost is that a channel which stopped working looks exactly
        like a channel with nothing to send. A count does not separate them: *3 awaiting
        transmission* reads the same on the first day and the ninetieth.

        Taken from the marker's mtime rather than from a field, because the marker already records
        the moment it was written and a second copy of that fact is a second thing to keep true.
        """
        marks = [p.stat().st_mtime for p in self.outbox.iterdir() if p.is_file()] \
            if self.outbox.is_dir() else []
        return min(marks) if marks else None


def mint_id(observation: str, *, now: datetime | None = None) -> str:
    """A stable, human-meaningful id fixed at capture (``ch6-11``).

    Date plus a slug of the observation's opening sentence: readable in a directory listing,
    sortable by when it was seen, and derived from the record rather than from a counter that
    would need somewhere to live.
    """
    stamp = (now or datetime.now(timezone.utc)).date().isoformat()
    opening = re.split(r"(?<=[.!?])\s", observation.strip(), maxsplit=1)[0]
    slug = re.sub(r"[^a-z0-9]+", "-", opening.lower().replace("'", "")).strip("-")
    if not slug:
        raise ValueError("cannot mint an id from an observation with no words in it")
    return f"{stamp}-{slug}"[:MAX_ID_LENGTH].rstrip("-")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
