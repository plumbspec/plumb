"""The session loop — opening from a cursor and measuring what a session moved (``ch13``).

Adoption happens once (``ch9``); this happens every working day. The shape was in the field twice
before it was written down, in two projects sharing no policy at all, and what they had written
identically is what ships here: read the cursor, confirm the ground, take a reading, difference it,
hold the gate.

**Nothing else in the tool reads any of this** (``dev03``). A project that never runs a session
command has every capability it had before, which is what makes recommending the loop honest rather
than a lock-in dressed as advice.

**The cursor's fields are three, and the rest ride along.** ``NEXT_TASK``, ``REF`` and ``CONTEXT``
are the mechanism's; every other key is carried untouched, because one of the two field examples
keeps a ``BRANCH`` there and a tool that dropped unknown keys would silently eat somebody's policy
(``dev03``).
"""

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from plumb import __version__

#: What the mechanism requires. ``CONTEXT`` is the field that earns the file — the other two can be
#: re-derived from the repository, and that one is what stops the project being re-interpreted.
REQUIRED = ("NEXT_TASK", "REF", "CONTEXT")

#: ``key="value"``, one per line. A *pattern*, deliberately — the ergonomic way to read this in a
#: shell is to source it, and sourcing executes every backtick and ``$(...)`` in what is a sentence
#: somebody wrote in English (``dev03-1``).
_FIELD = re.compile(r'^([A-Z_][A-Z0-9_]*)="(.*)"$', re.S)

#: Session state rather than a record of anything: it is what the close differences against, and
#: nothing derives a status from it.
READING_NAME = "session-reading.json"


def reading_path(project: Path) -> Path:
    """Where the opening reading is kept — **outside the repository**, deliberately.

    Written beside the cursor it would be uncommitted work at the moment the gate looks for
    uncommitted work, so the tool's own scratch file would fail the tool's own gate (``dev10-1``);
    the escape hatches from there are a `.gitignore` the tool is not allowed to write (``ado2``) or
    a gate that skips a path it recognises, which is a hole cut in a check to fit its author. The
    honest split is that the *cursor* is a handoff between two sessions and belongs in the
    repository, and a *reading* is within-session scratch on one machine and never travels.
    """
    import hashlib
    import os

    state = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    key = hashlib.blake2b(str(Path(project).resolve()).encode(), digest_size=8).hexdigest()
    return state / "plumb" / key / READING_NAME


class NotWrapped(Exception):
    """The gate refused. Carries the reasons, already in the words a person can act on."""

    def __init__(self, reasons: list[str]):
        super().__init__("; ".join(reasons))
        self.reasons = reasons


@dataclass(frozen=True)
class Cursor:
    """The handoff between two sessions. Data, and reading it never runs it (``dev03-1``)."""

    fields: dict[str, str] = field(default_factory=dict)
    path: Path | None = None

    def get(self, name: str) -> str:
        return self.fields.get(name, "")

    @property
    def missing(self) -> list[str]:
        return [name for name in REQUIRED if not self.fields.get(name, "").strip()]

    def to_text(self) -> str:
        # Stamped, because this is a file the tool writes into somebody's repository and *behind*
        # and *edited by hand* are otherwise the same bytes from the outside (`ado2`).
        lines = [f"# written by plumb {__version__} — data, not shell: parsed, never sourced"]
        ordered = list(REQUIRED) + [k for k in self.fields if k not in REQUIRED]
        lines += [f'{key}="{self.fields[key]}"' for key in ordered if key in self.fields]
        return "\n".join(lines) + "\n"


def read_cursor(path: Path) -> Cursor | None:
    """Parse ``key="value"`` lines. Returns ``None`` where there is no cursor at all.

    Absence is an answer rather than an error: the two causes — a first session, and a session that
    did not wrap — are different situations with identical evidence, so both get named and neither
    gets guessed at (``dev03-1``).
    """
    path = Path(path)
    if not path.is_file():
        return None
    found: dict[str, str] = {}
    for line in path.read_text().splitlines():
        matched = _FIELD.match(line.strip())
        if matched:
            found[matched.group(1)] = matched.group(2)
    return Cursor(found, path)


def write_cursor(path: Path, fields: dict[str, str]) -> Path:
    from plumb import statefile

    return statefile.replace(Path(path), Cursor(dict(fields)).to_text())


@dataclass(frozen=True)
class Reading:
    """What a run found at one moment. A measurement, and never a status (``dev03-3``).

    It records what the board said and when, so a close can difference it. Nothing derives *proven*
    from this file — a stored reading that could vote on status would be the authored verdict the
    whole method refuses, wearing a timestamp to look respectable.
    """

    statuses: dict[str, str] = field(default_factory=dict)
    when: str = ""
    version: str = ""
    #: Where the project's history stood when this was taken, so the close can bracket exactly the
    #: transitions the session produced (``dev10-3``). ``-1`` where no history is kept.
    series_seq: int = -1

    @property
    def proven(self) -> int:
        from plumb.core.gate import PROVEN

        return sum(1 for status in self.statuses.values() if status == PROVEN)

    @property
    def total(self) -> int:
        return len(self.statuses)

    def to_json(self) -> str:
        return json.dumps({"when": self.when, "version": self.version,
                           "series_seq": self.series_seq, "statuses": self.statuses}, indent=2)

    @classmethod
    def from_json(cls, text: str) -> "Reading":
        raw = json.loads(text)
        return cls(dict(raw.get("statuses", {})), raw.get("when", ""), raw.get("version", ""),
                   int(raw.get("series_seq", -1)))


@dataclass(frozen=True)
class Delta:
    """The difference between two readings — the whole of what a session is reported as having
    moved (``dev10-2``). A negative one is a result and not a fault."""

    became: tuple[str, ...] = ()
    lost: tuple[str, ...] = ()
    opened: int = 0
    closed: int = 0

    @property
    def moved(self) -> int:
        return len(self.became) - len(self.lost)


def difference(before: Reading, after: Reading) -> Delta:
    """Which stories became proven and which stopped being (``dev10-2``, ``dev07-4-3``).

    A story the closing reading no longer carries is **not** counted as a loss: deleting a story is
    not the same event as breaking one, and a session that tidied the spec would otherwise report
    a regression it did not cause.
    """
    from plumb.core.gate import PROVEN

    was = {sid for sid, status in before.statuses.items() if status == PROVEN}
    now = {sid for sid, status in after.statuses.items() if status == PROVEN}
    lost = {sid for sid in was - now if sid in after.statuses}
    return Delta(tuple(sorted(now - was)), tuple(sorted(lost)), before.proven, after.proven)


def take_reading(config, project: Path):
    """Run the project's own board and record what it found (``dev03-2``, ``dev03-3``).

    The board *is* the ground: producing it runs the project's suite, so confirming the ground and
    taking the reading are one action rather than two runs of the same tests.
    """
    import contextlib
    import sys
    from datetime import datetime, timezone

    from plumb.core.board import Board
    from plumb.launch import produce

    with contextlib.redirect_stdout(sys.stderr):
        manifest, absent, blind = produce(config, report=lambda line: None)
    board = Board.render(manifest, config.specs, absent, blind, rendered_by=__version__)
    statuses = {sid: verdict.status for sid, verdict in board.verdicts.items()}
    return Reading(statuses, datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   __version__, _series_seq(config, project)), manifest


def _series_path(config, project: Path) -> Path | None:
    return (Path(project) / config.series) if config.series else None


def _series_seq(config, project: Path) -> int:
    from plumb.core import series

    path = _series_path(config, project)
    if path is None or not path.exists():
        return -1
    return series.last_seq(path)


def since(config, project: Path, seq: int) -> list:
    """The transitions a history recorded after ``seq`` — exactly this session's (``dev10-3``)."""
    from plumb.core import series

    path = _series_path(config, project)
    if path is None or not path.exists() or seq < 0:
        return []
    return [entry for entry in series.read(path) if getattr(entry, "seq", 0) > seq]


def volatile(config, project: Path, limit: int = 3) -> list:
    """Which subjects this history has moved most — *whether today was typical* (``dev10-3``).

    The history answers a question the delta cannot: a story that has flickered for a fortnight and
    one that moved for the first time today are the same single transition to a session, and only
    the record of the other runs tells them apart.
    """
    from plumb.core import series

    path = _series_path(config, project)
    if path is None or not path.exists():
        return []
    standing = [row for row in series.overview(series.read(path)) if row.changes > 1]
    return sorted(standing, key=lambda row: -row.changes)[:limit]


def dirty(project: Path, repos, ignoring=()) -> list[str]:
    """Which of the declared trees have uncommitted work (``dev03-2``, ``dev03``).

    ``ignoring`` names paths this run wrote itself. Exactly one thing is ever passed here — the
    cursor, on the run that just wrote it — because a command cannot both write a file and require
    it to have been committed already, and refusing on it would make the gate unsatisfiable in one
    pass (``dev10-1``). It is not a general exemption: a cursor left uncommitted by an *earlier* run
    is uncommitted work like any other, and is caught by the next close.
    """
    unclean = []
    # Compared as paths rather than strings: `git status` collapses a newly created directory to
    # `?? .plumb/` instead of naming the file inside it, so the cursor's own directory has to
    # count as the cursor. Normalising with `removeprefix` and not `lstrip`, which strips a set of
    # characters and would turn `.plumb/…` into `plumb/…`.
    skip = {str(p).removeprefix("./") for p in ignoring}
    covered = lambda reported: any(
        entry == reported or entry.startswith(reported.rstrip("/") + "/") for entry in skip)
    for name in repos:
        where = (Path(project) / name).resolve()
        if not (where / ".git").exists():
            continue
        try:
            said = subprocess.run(["git", "-C", str(where), "status", "--porcelain"],
                                  capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            continue
        if said.returncode != 0:
            continue
        remaining = [line for line in said.stdout.splitlines()
                     if line.strip() and not covered(line[3:].strip().strip('"'))]
        if remaining:
            unclean.append(name)
    return unclean

