"""The run history a manifest deliberately is not (`dev07-6-1`).

A manifest is **amnesiac on purpose** (`ch2`): unlinked before every run so a stale one can never
answer for a failed one. That is right, and it means the questions people bring to a board — *when
did this break*, *which test is flaky*, *when was this last checked* — cannot be answered from it.
This is the second artifact those need.

**Transitions, not snapshots**. A fact that has not changed is not new information: measured
at 0 of 55 facts differing between two runs of an unchanged tree, and 1.3% across five real commits.
Storing a snapshot per run stores the same fact until somebody deletes it, and buries the one event
anybody is looking for — a result actually moving — under a hundred identical copies of everything
that did not.

Lossless, which is the only reason it beats simply choosing a coarser grain: base plus every change
reconstructs the history exactly. Granularity stays per test per run, because flakiness and
*which test un-proved this* are per-test questions and a coarser record cannot answer either.

**Nothing here is written as a side effect.** A board run that quietly grew a store would make
`--json` a mutating operation, and a series nobody chose to keep is a series nobody knows the shape
of. `plumb board --series FILE` is the whole of the opt-in — the same posture `plumb manifest
migrate` takes about doing something irreversible only when asked.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path

from plumb.core.manifest import Manifest


#: What to call each record type in a refusal. The class name is the tool's word for it and reads
#: as jargon in a sentence a project's author is meeting for the first time.
CALLED: dict = {}


#: How many bytes of proof a series is stamped with. Long enough that two series never collide by
#: accident, which is the whole of what it has to be — it is evidence of *which* series this is and
#: never a secret, so nothing is defended by making it longer.
ORIGIN_BYTES = 8


@dataclass(frozen=True)
class Origin:
    """Positive proof that this series began here (``dev07-6-1``).

    `dev07-6-2` makes a range *we discarded* legible and stops one step short: a history lost entirely
    leaves nothing behind to be legible about. After an eviction every subject reads ``changes: 1``,
    which is the honest reading of a single observation and a lie here, because a history existed
    and is gone. So the absences are three rather than two — *nothing happened*, *we discarded it*,
    *we lost it* — and only the third is silent.

    **A counter cannot fix it.** A counter restored from nothing reads exactly like one that has
    just started, so what is missing is not a bigger number but proof of beginning. A series is
    stamped once, at creation, with a value it can present later; one that cannot present a stamp
    is a history of *unknown extent* rather than a short one.

    The token is not a secret and defends nothing. It answers *is this the same series*, which is
    what lets a holder's copy and a local file be told apart rather than averaged (`dev07-6-3`).
    """

    seq: int
    origin: str
    #: When the series began, taken from the first run's own facts rather than from a clock — the
    #: same restraint `Run` uses, and for the same reason: this process observed nothing.
    started: str | None = None


#: What a copy of a history is to the holder that keeps it (``dev07-6-3``).
AUTHORITY, CACHE = "authority", "cache"


@dataclass(frozen=True)
class Retrieved:
    """Written into the file ``pull`` writes, so a copy says what it is (``dev07-6-3``).

    A history that may live in several places will live in several places, and they diverge. That
    is worse than being wrong: a single source consistently wrong can be read around, because a
    reader learns its bias — several plausible sources cannot be read at all. So one holder is the
    history and every local copy says it is derived, which is what gives a reader something to
    correct *toward*.

    In the file rather than worked out from configuration, because the question is about **this
    copy** and its answer must survive being moved, mailed or opened somewhere the project is not.
    """

    seq: int
    retrieved_from: str
    at: str | None = None


class InvalidSeries(ValueError):
    """A line in a series a reader cannot make a record of, named by file, line and shape.

    Its own class rather than the constructor's `TypeError`, because every caller here has a place
    to put a refusal a person can read and none of them had anything to catch.
    """


@dataclass(frozen=True)
class Discarded:
    """A range this store no longer holds, **recorded as discarded** (`dev07-6-2`).

    A series is kept under a bound, so parts of it get compacted or dropped — and the two ways a
    reader finds nothing there are *nothing happened* and *we discarded it*. Opposite readings, and
    only one is about the project. A gap nobody is told about reads as the first, which makes a
    discarded fortnight look like a quiet one.

    It also decides whether **custodial** is honest: a store that returns what it holds
    without saying what it dropped is not holding anything for anyone, it is keeping what happened
    to survive.

    ``through`` is the last sequence dropped, so a reader can tell a gap from a lost record: the
    sequences are dense (`dev07-4-3-ur06`), and a jump with no `Discarded` beside it means something was
    lost rather than released.
    """

    seq: int
    #: The first sequence no longer held, and the last. Inclusive.
    discarded_from: int
    discarded_through: int
    #: When it was dropped, and why in the store's own words — *compacted*, *evicted*. Never a
    #: judgement about the data, which is not ours to make (`dev07-4-3`).
    when: str | None
    reason: str


@dataclass(frozen=True)
class Run:
    """That a run happened, and when. **One line, whatever the run covered.**

    A log of changes cannot say *when was this last checked* — a fact that keeps holding never
    appears again, so silence means both *nothing moved* and *nobody looked*, which is `dev07-3-3`
    arriving inside the store built to answer it.

    It carries no list of what it covered, and does not need one: the covered set is the replayed
    state, because a subject enters it when its first fact appears and leaves when the last one
    goes, and both of those are already transitions. So *last checked* for a subject is the most
    recent run at which that subject was in state — derived from two things already here rather
    than a third thing written down.
    """

    seq: int
    #: When the run measured, in the adapter's own words (`dev07-3-1`). ``None`` is *not reported*.
    run: str | None
    #: How many tests it observed at all, cited or not (`dev07-3-2`) — the one fact about the run
    #: rather than about a test, and what tells a broken run from a quiet one.
    observed: int | None


@dataclass(frozen=True)
class Entry:
    """One fact changing, and when.

    ``seq`` is unique and monotonic (`dev07-4-3-ur06`) so a reader can page, resume and de-duplicate, and
    so the **store** can move — file, appendable log, embedded database — without the **contract**
    moving. Added while the store holds nothing, because retrofitting it after anything reads the
    store costs a version of the contract and every consumer's upgrade.
    """

    seq: int
    subject: str
    test: str
    #: Which of the subject's aspects this bears on (`dev07-3-1`); ``None`` where it has one.
    about: str | None
    #: ``None`` means the fact is **gone** — the test no longer cites this subject. Absence has to
    #: be a recorded transition rather than a silent stop, or a deleted test reads forever as
    #: whatever it last said (`dev07-3-3`).
    result: str | None
    grounding: str | None
    #: When the run that observed this measured it. ``None`` is *not reported* and never *now*.
    when: str | None



def _ordering(key) -> tuple:
    """A total order over fact keys.

    `None` sorts as the empty string rather than raising: `about` is absent for a subject with one
    aspect, and `sorted` over a mix of `str` and `None` is a TypeError that surfaces only once a
    project has an uncited story — which is every real project and no fixture.
    """
    return tuple("" if part is None else str(part) for part in key)


def facts(manifest: Manifest) -> dict[tuple[str, str, str | None], tuple]:
    """Every fact in a run, keyed by what makes it the same fact across runs.

    **`when` is not part of what a fact says.** It is when we looked, not what we saw, and folding
    it in makes every fact differ from itself on every run — which turns a transition log into a
    snapshot store that has forgotten it is one. Found by building this: a second identical run
    wrote 317 transitions where it should have written none.

    The cost of leaving it out is real and is `dev07-4-3-ur10`'s: a series of *changes* cannot answer *when
    was this last checked*, because a fact that keeps holding never appears again. That question
    wants a record per **run** rather than per fact, which is one line and is not this function.
    """
    found = {
        (sid, c.test, c.about): (c.result, c.grounding)
        for sid, story in manifest.stories.items()
        for c in story.citations
    }
    # A subject reaches a manifest only by being cited, so there is no declared-and-uncited case to
    # record here: a board answers for the ids a run's tests cited (`dev07-3-2`). `result=None` remains
    # the one absence this states — a test that has stopped citing a subject.
    return found


def _measured(manifest: Manifest, key) -> str | None:
    """When the run measured this fact, or ``None`` where it no longer reports one."""
    sid, test, about = key
    story = manifest.stories.get(sid)
    for c in story.citations if story else ():
        if c.test == test and c.about == about:
            return c.when
    return None


def sent_mark(path: Path) -> Path:
    """Where the last-sent sequence is kept, beside the store it belongs to."""
    return path.with_suffix(path.suffix + ".sent")


def unsent(path: Path) -> tuple[int, list]:
    """The high-water mark, and everything above it.

    **The log is its own outbox.** `dev07-4-3-ur06`'s sequence is dense and monotonic precisely so a
    reader can page and resume, and this is the resume case — so there is no queue, no outbox and
    no drain command. If the receiver is unreachable the mark does not move and the next attempt
    carries the backlog, which is `dev07-6-2-sr3`'s posture falling out of the data rather than being
    implemented a second time.

    The mark is the **local** sequence. A receiver renumbers onto its own store, so the number it
    reports back is not ours — treating it as ours would look like it worked while silently
    re-sending everything, which is the same shape as the `when`-in-the-fact-identity bug.
    """
    mark = sent_mark(path)
    through = int(mark.read_text().strip() or 0) if mark.is_file() else 0
    return through, [r for r in read(path) if r.seq > through]


def mark_sent(path: Path, through: int) -> None:
    """Advance the high-water mark, and only ever forwards.

    A mark that could move backwards would re-send records the receiver already holds. Harmless for
    it, since a store is append-only; wrong for us, because it would say we had not sent what we
    had, and a count that can go down is not a high-water mark.
    """
    mark = sent_mark(path)
    current = int(mark.read_text().strip() or 0) if mark.is_file() else 0
    mark.write_text(str(max(current, through)))


def last_seq(path: Path) -> int:
    """The highest sequence in a store, read from the end rather than by reading it all.

    Appending is the hot path — once per run per adopter — and reading a whole log to find out
    where it ends makes every write cost what the history costs. Measured at 35 MB for a large
    project after a hundred runs, which is 50 ms of pure counting before anything is written.

    The sequences are dense (`dev07-4-3-ur06`), so the last line has the answer and nothing else needs to
    be parsed.
    """
    if not path.is_file() or path.stat().st_size == 0:
        return 0
    with path.open("rb") as store:
        # Enough for one line without being enough for a whole record set. A short file is read
        # whole, which is the ordinary case for a young store.
        store.seek(max(0, store.seek(0, 2) - 4096))
        tail = store.read().decode("utf-8", "ignore").splitlines()
    for line in reversed(tail):
        if line.strip():
            return int(json.loads(line)["seq"])
    return 0


def read(path: Path) -> list:
    """Every record, oldest first — `Run` markers and `Entry` transitions in one log.

    Discriminated by shape rather than by a `kind` on every line: a fact names a subject and a run
    does not. Two record types in one append-only file is what an event log is; a second file would
    be a second thing to keep in step, and the ordering between them is the whole point.
    """
    if not path.is_file():
        return []
    found = []
    for n, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        # Refused by name, never as a traceback. A series is an append-only log a project keeps in
        # its own tree, so it is exactly the file a hand-edit, a merge or another tool's writer
        # reaches — and the reader used to answer a bad line with `TypeError: Entry.__init__() got
        # an unexpected keyword argument`, out of a dataclass constructor, at whatever command
        # happened to be reading. Which line and which field is what a reader can act on; the
        # constructor's own words are about a class they have never heard of.
        try:
            raw = json.loads(line)
        except ValueError as bad:
            raise InvalidSeries(f"{path}:{n} is not JSON — {bad}") from None
        if not isinstance(raw, dict):
            raise InvalidSeries(f"{path}:{n} is {type(raw).__name__}, and every record is an object")
        shape = (Entry if "subject" in raw
                 else Discarded if "discarded_from" in raw
                 else Origin if "origin" in raw
                 else Retrieved if "retrieved_from" in raw
                 else Run)
        try:
            found.append(shape(**raw))
        except TypeError as bad:
            expected = ", ".join(f.name for f in fields(shape))
            raise InvalidSeries(
                f"{path}:{n} does not read as {CALLED[shape]} — {bad}.\n"
                f"  {CALLED[shape]} carries: {expected}") from None
    return found


CALLED.update({Entry: "a transition", Run: "a run", Discarded: "a discarded range",
               Origin: "an origin stamp", Retrieved: "a retrieval marker"})


@dataclass(frozen=True)
class Extent:
    """The range a copy actually holds, and the gaps inside it (``dev07-6-3``).

    **No store answers a question about a range it does not hold as though it held it.** That is
    what the authority/cache hierarchy was really protecting, and it is the better statement of it:
    a holder keeping a history under a bound discards ranges it once held (`dev07-6-2`), so a local
    copy can be the *longer* of the two without being a second opinion — the two never disagree
    about a range they both hold.
    """

    role: str
    #: The lowest and highest sequence this copy carries. ``None`` where it carries nothing.
    first: int | None = None
    last: int | None = None
    #: Ranges inside it that were compacted away, oldest first (`dev07-6-2`).
    gaps: tuple = ()
    #: Whether it can show where it began (`dev07-6-1`). ``False`` is *unknown extent*, never *short*.
    whole: bool = False
    #: Where a cache came from, when the copy says so.
    holder: str | None = None


def extent(entries: list, sent_through: int = 0) -> Extent:
    """What this copy holds and what it is, derived from the copy itself.

    ``sent_through`` is the mark (`dev07-6-2`) — the highest local sequence a holder has accepted. A
    copy something has accepted from is a copy the holder is the authority for, which is `dev07-6-2`'s
    consequence rather than a new claim: it moves the mark only on acceptance, so a mark that has
    moved *is* the evidence that a holder exists.
    """
    came_from = next((r for r in entries if isinstance(r, Retrieved)), None)
    # The marker is a fact about the *file*, not a record in the history, so it is not part of the
    # range the file holds — counting it would make a pulled copy claim one record more than the
    # holder handed over.
    seqs = [r.seq for r in entries
            if not isinstance(r, Retrieved) and getattr(r, "seq", None) is not None]
    return Extent(
        role=CACHE if (came_from is not None or sent_through > 0) else AUTHORITY,
        first=min(seqs) if seqs else None,
        last=max(seqs) if seqs else None,
        gaps=tuple((g.discarded_from, g.discarded_through) for g in discarded(entries)),
        whole=began(entries) is not None,
        holder=came_from.retrieved_from if came_from else None,
    )


def began(entries: list) -> "Origin | None":
    """The stamp this history was created with, or ``None`` where it carries none.

    ``None`` is the answer that matters. It is what a file restored from a partial artifact, cut by
    a hand-edit, or written before stamping existed all look like — and none of those is a short
    history, they are histories of unknown extent.
    """
    return next((e for e in entries if isinstance(e, Origin)), None)


def state(entries: list) -> dict[tuple[str, str, str | None], tuple]:
    """What the history says is true now — base plus every change, replayed."""
    current: dict = {}
    for e in (x for x in entries if isinstance(x, Entry)):
        key = (e.subject, e.test, e.about)
        if e.result is None:
            current.pop(key, None)
        else:
            current[key] = (e.result, e.grounding)
    return current


def append(path: Path, manifest: Manifest) -> list[Entry]:
    """Record what this run changed, and return it. Nothing changed means nothing written.

    An empty append is the ordinary case on a healthy project and writes no line at all — not a
    marker, not an empty record. A run that changed nothing is not an event, and a store that noted
    every one of them would be a snapshot store wearing a log's clothes.
    """
    existing = read(path)
    was, now = state(existing), facts(manifest)
    seq = last_seq(path)

    # Stamped once, when the series is created, and never again (`dev07-6-1`). Written here rather
    # than by whoever asked for a series, because creation is the only moment at which *this file
    # began* is a fact anybody holds — a stamp added later would be an assertion about a past the
    # writer was not present for.
    stamp = None
    if not existing:
        seq += 1
        stamp = Origin(seq=seq, origin=secrets.token_hex(ORIGIN_BYTES), started=_ran_at(manifest))

    changed = []
    for key in sorted(set(was) | set(now), key=_ordering):
        if was.get(key) == now.get(key):
            continue
        seq += 1
        result, grounding = now.get(key, (None, None))
        when = _measured(manifest, key)
        subject, test, about = key
        changed.append(Entry(seq=seq, subject=subject, test=test, about=about,
                             result=result, grounding=grounding, when=when))

    # The run marker is written **whether or not anything changed** — that is its whole job. An
    # unchanged run is the ordinary case and is exactly the case a log of changes cannot otherwise
    # report, so a store that only recorded eventful runs would answer *when did we last look* with
    # the date of the last thing that broke.
    seq += 1
    marker = Run(seq=seq, run=_ran_at(manifest), observed=manifest.observed_tests)
    # The directory is made rather than assumed. A series is asked for by path — `--series
    # build/plumb/series.jsonl` — and a build directory is precisely the kind that does not exist
    # yet on a runner that was created this minute, which is where a series is most wanted. Without
    # this the board reached the end of a successful run and died in a traceback about a file it was
    # asked to create, which reads as a fault in the project rather than in what it was handed.
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as store:
        if stamp is not None:
            store.write(json.dumps(asdict(stamp), separators=(",", ":")) + "\n")
        for entry in changed:
            store.write(json.dumps(asdict(entry), separators=(",", ":")) + "\n")
        store.write(json.dumps(asdict(marker), separators=(",", ":")) + "\n")
    return changed


def _ran_at(manifest: Manifest) -> str | None:
    """When this run measured, taken from the facts rather than from our clock.

    Reading the clock here would stamp a time this process observed nothing at — the adapter did
    the measuring, and on a merged board several did (`dev07-3-1`). The earliest is taken, because a
    run began when its first observation was made.
    """
    times = sorted(c.when for s in manifest.stories.values() for c in s.citations if c.when)
    return times[0] if times else None


def compact(path: Path, through: int, reason: str, when: str | None = None) -> Discarded:
    """Collapse everything up to ``through`` into a new base, and **say so**.

    Not deletion. A transition log is lossless only as *base plus every change since*, so dropping
    the oldest records removes the base and makes everything after it unreconstructable — it would
    not free space, it would destroy the remainder (rewritten for exactly this reason). What
    is written back is the replayed state as fresh entries, which is the same size as the base it
    replaces: compaction reclaims **churn**, never the base.

    The `Discarded` record is not bookkeeping. Without it the compacted span reads as a period in
    which nothing happened, and the store would be answering a question about the project with a
    fact about itself.
    """
    records = read(path)
    kept = [r for r in records if r.seq > through]
    dropped = [r for r in records if r.seq <= through]
    if not dropped:
        raise ValueError(f"nothing at or below seq {through} to compact")

    base = state([r for r in records if r.seq <= through])
    seq = 0
    lines = []
    # **The stamp outlives the range it sits in** (`dev07-6-1`). It is written first, so it is always
    # inside the first span compacted — and rebuilding the log from replayed state kept only the
    # entries, which silently threw it away. A holder that has compacted once could then no longer
    # show where the history began, and every copy pulled from it read as one of *unknown extent*
    # while the holder knew the answer perfectly well. Compaction reclaims churn; proof of
    # beginning is not churn.
    stamp = began(records)
    if stamp is not None:
        seq += 1
        lines.append(replace(stamp, seq=seq))
    note = Discarded(seq=seq + 1, discarded_from=min(r.seq for r in dropped),
                     discarded_through=through, when=when, reason=reason)
    seq += 1
    lines.append(note)
    for key in sorted(base, key=_ordering):
        seq += 1
        subject, test, about = key
        result, grounding = base[key]
        lines.append(Entry(seq=seq, subject=subject, test=test, about=about,
                           result=result, grounding=grounding, when=None))
    # Renumbered from one: the sequence says *where in this store*, and a store that kept the old
    # numbers would claim to hold records it released. Dense either way, so a jump still means a
    # record was lost rather than let go.
    for record in kept:
        seq += 1
        lines.append(type(record)(**{**asdict(record), "seq": seq}))

    # Atomically, because a crash partway through leaves a truncated log — which is worse than a
    # full one, and unlike a full one it is not obviously wrong.
    staging = path.with_suffix(path.suffix + ".compacting")
    staging.write_text("".join(
        json.dumps(asdict(r), separators=(",", ":")) + "\n" for r in lines))
    staging.replace(path)
    return note


def last_checked(entries: list, subject: str) -> str | None:
    """When a subject was last **looked at**, which is not when it last changed (`dev07-4-3-ur10`).

    *Deriving looked rather than fine is the whole of the honesty here*: a watched decision's
    answer lives in somebody else's changelog and cannot be computed, but whether anyone has looked
    recently can be. Returns ``None`` where the subject has never been in state — never checked is
    not the same as checked long ago, and inventing a date for it would be the fabrication `dev07-3-1`
    refuses.
    """
    seen, when = False, None
    for record in entries:
        if isinstance(record, Entry) and record.subject == subject:
            seen = record.result is not None
        elif isinstance(record, Run) and seen:
            when = record.run or when
    return when


@dataclass(frozen=True)
class Standing:
    """What a history says about one subject, without saying whether it is any good (`dev07-6-3`).

    Deliberately four facts and no verdict. A board derives status from a run (`dev07-4-3`); a history
    that started grading would be a second source of truth about the same thing, and the two would
    disagree the first time somebody read an old file.
    """

    subject: str
    changed: str | None
    checked: str | None
    #: How many **runs** moved this subject, not how many records mention it. The difference is
    #: not cosmetic: the first append writes one record per citation, so counting records made a
    #: subject with sixteen citing tests the most volatile thing in a project where nothing had
    #: ever changed. Runs is the question anybody actually asks — *what keeps breaking* — and on
    #: a fresh history every answer is 1, which is the honest reading of one observation.
    changes: int
    #: Where it stands now, replayed from the history — ``None`` where the last thing that happened
    #: to it was disappearing, which is a fact and not an absence (`dev07-3-3`).
    result: str | None = None


def overview(entries: list) -> list[Standing]:
    """One row per subject the history knows, in the order they first appear.

    *When it last changed* and *when it was last looked at* are different questions and the whole
    reason a series exists beside a manifest: an unchanged subject is not an unexamined one, and
    `dev07-4-3-ur10` turns on exactly that difference.
    """
    changed: dict[str, str | None] = {}
    changes: dict[str, int] = {}
    moved_this_run: set[str] = set()
    for record in entries:
        if isinstance(record, Entry):
            moved_this_run.add(record.subject)
            # The measurement time, not our clock — the run did the observing (`dev07-3-1`). A
            # transition carrying none leaves the previous answer standing rather than blanking it.
            changed[record.subject] = record.when or changed.get(record.subject)
        elif isinstance(record, Run):
            # A run marker closes the run its transitions belong to: they are written first and
            # the marker last, so this is where a run becomes countable.
            for subject in moved_this_run:
                changes[subject] = changes.get(subject, 0) + 1
            moved_this_run = set()
    for subject in moved_this_run:      # transitions after the last marker, if a run was cut short
        changes[subject] = changes.get(subject, 0) + 1

    now = state(entries)
    return [
        Standing(subject=subject,
                 changed=changed[subject],
                 checked=last_checked(entries, subject),
                 changes=changes[subject],
                 result=next((result for (sid, _, _), (result, _) in now.items()
                              if sid == subject), None))
        for subject in changed
    ]


def history(entries: list, subject: str) -> list[Entry]:
    """Every transition recorded for one subject, oldest first — *when did this break*."""
    return [r for r in entries if isinstance(r, Entry) and r.subject == subject]


def discarded(entries: list) -> list[Discarded]:
    """The ranges the store no longer holds. Never inferred from a gap — only ever read from a
    record that says so (`dev07-6-2`)."""
    return [r for r in entries if isinstance(r, Discarded)]
