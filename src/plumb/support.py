"""Chapter 6's record: friction, captured as data (``ch6-2``, ``ch6-3``, ``ch6-4``, ``ch6-11``).

Knowledge, never evidence — nothing here touches the manifest or a story's status (``ch6-1``).

A record is **validated at write** and rejected naming what is missing, because the writer is
usually an agent still holding the context and that is the only moment a correction ever
happens. Two field classes, per ``ch6-4``:

* **required** — a record without these is not a record;
* **conditional** — carried when they apply, and otherwise marked ``INAPPLICABLE`` (it did not
  apply) or ``UNCAPTURED`` (it applied and was lost). A blank, an inapplicable field and a lost
  one are three different facts; a schema that cannot tell them apart invites a writer to invent
  a plausible value, and an importer to invent one on a record's behalf.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from pathlib import Path

MAX_EXCERPT_LINES = 40

INAPPLICABLE = "n/a"      # the field did not apply to this rub
UNCAPTURED = "unknown"    # it applied, and was never recorded — imports, mostly
#: It applied, it was captured, and the filer chose not to send it (``ch6-29``). The fourth absence,
#: and **the only one an operator can act on**: nothing can be done about a lost field, where a kept
#: one belongs to somebody who can be asked for it (``ch12-31``). Reusing `unknown` for it would put
#: those two answers behind one word, which is the collapse `ch6-4` exists to prevent.
WITHHELD = "withheld"
ABSENT = (INAPPLICABLE, UNCAPTURED, WITHHELD)

SOURCES = ("self", "trusted-tester")

#: What shape a record is (``ch6-31``).
#:
#: **`friction` is retired, with no replacement.** It was an alpha-testing practice — capture what
#: rubbed, locally, against a bar — and an open-source tool does not carry a local support desk.
#: Nothing took its place: what is left are the three shapes that address somebody else.
#:
#: A record written before the `kind` field existed reads as `report`, which is what all of them
#: turned out to be. The wire still carries whatever a service chooses to accept; this is what this
#: client will produce.
KINDS = ("question", "idea", "report")
DEFAULT_KIND = "report"

#: The kinds that must say what the rub cost the method. None does, now — `implication` was the bar
#: *friction* earned its place against, and a question has nothing to claim. It stays on the record
#: because records already carry it, and it is never required.
CLAIMS_AN_IMPLICATION = ()

#: The shape of a stored record (``ch6-15``). Stamped at write so a reader years later can tell
#: which schema produced the file it is holding, instead of inferring it from which fields happen
#: to be present. The wire protocol was already versioned (``transmit.PROTOCOL_VERSION``); the
#: durable artifact was not, which is the wrong way round — the record outlives the transport.
#:
#: A file with no ``version`` predates the stamp and is therefore version 0 by definition — not
#: "probably current", which is the guess a version exists to remove.
SCHEMA_VERSION = 5

#: `implication` left this set at v2 and became required per *kind* instead (``ch6-31``). With
#: `friction` retired no kind requires it, so it is optional on every record this client writes.
REQUIRED = ("id", "observed_at", "source", "kind", "observation")
CONDITIONAL = (
    "project", "commit", "location", "excerpt",
    "story", "depth", "condition_code", "board_status",
    # What the tool did, rather than what the adopter's code said (``ch6-32``). Conditional like
    # every other anchor: a record filed at a desk with nothing running has no observer and no
    # invocation, and says so rather than omitting the field.
    "observer", "invocation", "diagnostic",
)


class InvalidRecord(ValueError):
    """Raised at write, naming every missing field at once — a writer correcting one
    rejection at a time is a writer who stops filing."""


def _v0_to_v1(raw: dict) -> dict:
    """``layer`` became ``depth``. The rename is the whole step: same meaning, same values."""
    if "layer" in raw:
        raw["depth"] = raw.pop("layer")
    return raw


#: A ladder, not a pile of read-time special cases. Teaching the reader to understand every shape
#: that ever existed is the alternative, and it grows without bound — every future rename adds a
#: branch that can never be deleted, because some record somewhere might still need it. A step
#: chain is bounded instead: a record climbs it once, is written back at the top, and the rungs
#: below can be retired when nothing is left standing on them.
def _v1_to_v2(raw: dict) -> dict:
    """A record gained a `kind` and the support facts, and `implication` stopped being universal.

    Every v1 record was friction — it is what there was to file — so the kind is stated rather than
    guessed, and `implication` was required then, so it is already there. The support facts were
    never captured and say so with `unknown` rather than `n/a`: they applied to that run and were
    not recorded, which is a different fact from having no run at all (`ch6-4`).
    """
    raw.setdefault("kind", DEFAULT_KIND)
    for name in ("observer", "invocation", "diagnostic"):
        raw.setdefault(name, UNCAPTURED)
    return raw


def _v2_to_v3(raw: dict) -> dict:
    """A record gained the filer it is answerable to (`ch12-30`).

    `unknown` and not `n/a`: every v2 record *was* filed by somebody through a credential the
    support service resolved, and the store kept only the two-value `source` it was flattened to. The
    filer applied and was lost, which is the distinction `ch6-4` keeps two words for — and the
    reason this cannot be backfilled: `source` says *a trusted tester* and never which one.
    """
    raw.setdefault("filed_by", UNCAPTURED)
    return raw


def _v3_to_v4(raw: dict) -> dict:
    """A record gained the intake fields — what a person was actually asked (`record-contract`).

    Backfilled with the uncaptured marker, per the ratified ladder: these records came from
    clients where the fields applied and nothing wrote them down. The marker, never a value —
    *they told me unknown* and *they told me nothing* stay different facts, told apart by
    whether `unknown` was sent deliberately.
    """
    for name in ("attempting", "instead", "recurrence"):
        raw.setdefault(name, UNCAPTURED)
    return raw


def _v4_to_v5(raw: dict) -> dict:
    """A record gained the tool's own version (`record-contract`, ratified 2026-09-13).

    Backfilled with the uncaptured marker: the field applied to every v4 record — something
    filed it — and nothing wrote it down. A filer may also send it withheld, which the wire
    keeps apart from uncaptured, because declining to say is a different fact from predating
    the field.
    """
    raw.setdefault("tool_version", UNCAPTURED)
    return raw


#: One step per schema bump, keyed by the version it upgrades *from* (``ch6-23``).
MIGRATIONS = {0: _v0_to_v1, 1: _v1_to_v2, 2: _v2_to_v3, 3: _v3_to_v4, 4: _v4_to_v5}


def migrate(raw: dict) -> dict:
    """Climb a record's raw fields from the version that wrote it to the current one."""
    version = int(raw.get("version", 0))
    while version < SCHEMA_VERSION:
        step = MIGRATIONS.get(version)
        if step is None:
            raise InvalidRecord(f"no migration from schema version {version}")
        raw = step(dict(raw))
        version += 1
    raw["version"] = version
    return raw


@dataclass(frozen=True)
class SupportRecord:
    id: str
    observed_at: str
    source: str
    observation: str
    #: What shape this is (``ch6-31``). Defaulted rather than positional so a v1 record and every
    #: caller that predates the field still reads as `friction`, which is what it was.
    kind: str = DEFAULT_KIND
    #: What the rub means **for the method** — the bar a record earns its place against (`ch6-3`).
    #: Required of friction and conditional for the rest: a question has no cost to claim, and one
    #: invented to pass a validator is the value `ch6-4` exists to refuse.
    implication: str = INAPPLICABLE
    version: int = SCHEMA_VERSION
    #: Which account filed this, resolved from the credential and **never read from the payload**
    #: (``ch12-30``). Distinct from `source`, which says what *kind* of relationship filed it: two
    #: trusted testers share a `source` and are different filers, and scoping a read to *their own*
    #: needs the one that tells them apart.
    #:
    #: `n/a` until a support service stamps it, because a record on the filer's own disk has not been filed
    #: to anybody yet — that is the field not applying, not a value going missing.
    filed_by: str = INAPPLICABLE
    project: str = INAPPLICABLE
    commit: str = INAPPLICABLE
    location: str = INAPPLICABLE
    excerpt: str = INAPPLICABLE
    story: str = INAPPLICABLE
    depth: str = INAPPLICABLE
    condition_code: str = INAPPLICABLE
    board_status: str = INAPPLICABLE
    #: What the tool was and did, in Plumb's own words rather than the adopter's code (``ch6-32``).
    #: The half that is ours to publish, which is why these travel where an excerpt does not.
    observer: str = INAPPLICABLE
    invocation: str = INAPPLICABLE
    diagnostic: str = INAPPLICABLE
    #: The tool's own version (v5) — read out of the artifact, never typed. What the knowledge
    #: base grounds a versioned answer on; an answer built on it says the release was REPORTED
    #: by the client, because a receiver can refuse a malformed version and never an untrue one.
    tool_version: str = UNCAPTURED
    #: The intake fields (v4): asked of the person, apart from the machine's anchors above.
    #: `instead` and `recurrence` take the support service's published enumerations. `None` means the
    #: question was never asked — which is what lets `unknown` *answered deliberately* survive
    #: as the value it is, because a default equal to the marker word could never tell the two
    #: apart, and the whole deviation exists to keep them apart.
    attempting: str | None = None
    instead: str | None = None
    recurrence: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        self.validate()

    def validate(self) -> None:
        problems = [*self._missing_required(), *self._malformed()]
        if problems:
            raise InvalidRecord("; ".join(problems))

    def _missing_required(self) -> list[str]:
        return [
            f"{name} is required and empty"
            for name in REQUIRED
            if not str(getattr(self, name)).strip() or getattr(self, name) in ABSENT
        ]

    def _malformed(self) -> list[str]:
        problems = []
        if self.kind not in KINDS:
            problems.append(f"kind must be one of {KINDS}, got {self.kind!r}")
        # Required per kind (`ch6-31`), and with `friction` retired no kind claims one — so this
        # never fires today. It is kept rather than deleted because the rule is the schema's, not
        # friction's: a kind that needs a bar again says so by joining the set.
        if self.kind in CLAIMS_AN_IMPLICATION and (
                not str(self.implication).strip() or self.implication in ABSENT):
            problems.append("implication is required and empty — friction says what the rub cost "
                            "the method; file it as a question or an idea if there is no cost yet")
        if self.source not in SOURCES:
            problems.append(f"source must be one of {SOURCES}, got {self.source!r}")
        if not _is_utc(self.observed_at):
            problems.append(f"observed_at must be an ISO-8601 UTC instant, got {self.observed_at!r}")
        if not isinstance(self.version, int) or isinstance(self.version, bool) or self.version < 1:
            problems.append(f"version must be a positive integer, got {self.version!r}")
        # REQUIRED excluded: `_missing_required` already names those, and one fault reported twice
        # reads as two faults.
        blank = [f.name for f in fields(self)
                 if getattr(self, f.name) == "" and f.name not in REQUIRED]
        if blank:
            problems.append(
                f"blank is not a value — use {INAPPLICABLE!r} (did not apply), "
                f"{UNCAPTURED!r} (applied, not recorded) or {WITHHELD!r} (applied, kept): {blank}"
            )
        return problems

    @property
    def anchors(self) -> dict[str, str]:
        """The conditional fields that actually apply — what makes the rub resolvable later."""
        return {
            name: getattr(self, name)
            for name in CONDITIONAL
            if getattr(self, name) not in ABSENT
        }

    def to_json(self) -> str:
        """The disk shape: every field present, markers and all. The record outlives the wire."""
        return json.dumps(asdict(self), indent=2, ensure_ascii=False) + "\n"

    def to_wire(self) -> str:
        """The wire shape (`record-contract`, and the round-trip case's correction of 2026-09-13).

        A marker is never sent: absence on the wire is what produces the marker at the support service,
        each field defaulting to the absence that is true of it — and a marker word sent as text
        is stored as an *answer*, which asserts a reply the filer never gave. So a field whose
        value is a marker, or an intake question never asked, is omitted; `implication` off
        friction is omitted for the same ratified reason null would be accepted — there is
        nothing for it to say. What survives is what somebody actually supplied, `unknown`
        answered deliberately included.
        """
        raw = asdict(self)
        intake = ("attempting", "instead", "recurrence")
        for name, value in list(raw.items()):
            if value is None:
                del raw[name]
            elif value in ABSENT and name not in intake:
                # An intake value equal to a marker word is a deliberate answer — `unknown` is in
                # the published enumerations — and only the None default means never-asked. Every
                # other field's deliberate values are never marker words, so the word is safe to
                # treat as the absence it is.
                del raw[name]
        # Carried when it has real text, whatever the kind. This dropped it off every kind that
        # did not CLAIM one, which was right while only friction did: an implication on a question
        # was a validator's leftover rather than something anybody wrote. With no kind claiming
        # one, the same rule silently discards what a writer typed on purpose — and a record that
        # loses a sentence between the disk and the wire is the worst shape this can take.
        if not str(self.implication).strip() or self.implication in ABSENT:
            raw.pop("implication", None)
        return json.dumps(raw, ensure_ascii=False)

    @classmethod
    def from_json(cls, text: str) -> "SupportRecord":
        raw = json.loads(text)
        raw["tags"] = tuple(raw.get("tags", ()))
        # Before the unknown-field check, not after: a field this schema retired is not unknown,
        # it is old, and the two get told apart by the version rather than by the reader guessing.
        raw = migrate(raw)
        known = {f.name for f in fields(cls)}
        unknown = set(raw) - known
        if unknown:
            raise InvalidRecord(f"unknown field(s): {sorted(unknown)}")
        # **Filled rather than refused here**, so validation answers once with everything (`ch6-4`).
        # Raising on the absent set first meant a payload missing two required fields never reached
        # the per-kind rules, and a writer fixed the two, resubmitted, and was told about a third.
        for name in REQUIRED:
            raw.setdefault(name, "")
        return cls(**raw)

    def write_to(self, directory: Path) -> Path:
        """One record, one file — which is what makes ``ch6-9`` removal an operation
        rather than an excavation."""
        path = Path(directory) / f"{self.id}.json"
        path.write_text(self.to_json())
        return path


def _is_utc(stamp: str) -> bool:
    """Whether ``stamp`` is an ISO-8601 instant that is actually UTC.

    ``Z`` is spelled out as ``+00:00`` before parsing because `fromisoformat` learned to read the
    military suffix at 3.11, and every stamp this module *writes* carries it. Below that the
    parser refused its own output, so a project on the floor this tool declares could not file a
    support record at all — the one shape of floor defect a version matrix never catches, because
    it lives in the agreement between a writer and a reader that are the same module.
    """
    try:
        parsed = datetime.fromisoformat(stamp[:-1] + "+00:00" if stamp.endswith("Z") else stamp)
    except (TypeError, ValueError, AttributeError):
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() == timezone.utc.utcoffset(None)


@dataclass(frozen=True)
class Unreadable:
    """A file in the store that did not parse (``ch6-16``).

    Named, not skipped. Silently dropping it shortens the list without saying so, which reads as
    an answer and is worse than the crash it replaced — the contributor would have no way to tell
    a store of 69 records from a store of 76 with 7 it can no longer read.
    """

    path: Path
    reason: str

    @property
    def id(self) -> str:
        return self.path.stem


def load_all(directory: Path) -> tuple[list[SupportRecord], list[Unreadable]]:
    """Read the store per record (``ch6-16``): what parses is returned, what does not is named,
    and the caller still gets an answer.

    This was one comprehension, so the first unreadable file raised and took every good record
    with it — a one-record defect became a total outage of the knowledge base, at the moment a
    contributor was checking that filing had worked.
    """
    records: list[SupportRecord] = []
    unreadable: list[Unreadable] = []
    for path in sorted(Path(directory).glob("*.json")):
        try:
            records.append(SupportRecord.from_json(path.read_text()))
        except (InvalidRecord, ValueError, OSError) as bad:
            unreadable.append(Unreadable(path, str(bad)))
    return records, unreadable


def excerpt(path: Path | str, start: int, end: int, *, root: Path | str | None = None) -> tuple[str, str]:
    """``(location, excerpt)`` for the lines that rubbed — read-only, and bounded.

    The record carries the code rather than a reference to it (``ch6-2``), so a reader a year
    later needs neither the repository nor permission to write to it (``ch6-12``). Lines are
    numbered, so the excerpt locates itself even quoted out of context.

    Bounded on purpose: an excerpt that needs the whole file is not pointing at the rub. That is
    the same bar ``ch6-3`` sets against volume, applied to code instead of prose.
    """
    path = Path(path)
    if start < 1 or end < start:
        raise ValueError(f"not a line range: {start}-{end}")
    if end - start + 1 > MAX_EXCERPT_LINES:
        raise ValueError(
            f"{end - start + 1} lines exceeds the {MAX_EXCERPT_LINES}-line bar — an excerpt that "
            "large is not pointing at the rub; narrow it, or file more than one record"
        )
    lines = path.read_text().splitlines()
    if end > len(lines):
        raise ValueError(f"{path} has {len(lines)} lines, so {start}-{end} does not exist")

    width = len(str(end))
    body = "\n".join(f"{n:>{width}}  {lines[n - 1]}" for n in range(start, end + 1))
    where = path.resolve().relative_to(Path(root).resolve()) if root else path
    return f"{where}:{start}-{end}", body
