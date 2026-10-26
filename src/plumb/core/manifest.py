"""Chapter 2's hub: the language-neutral contract between adapter and core.

The **one** thing the core reads (``dev07-3-3``). An adapter produces it from a test run; the gate
reasons over it. Because it is the sole interface, the core touches no runner and knows no
language — a new language is a new adapter and nothing else (``dev07-3-3``).

It carries **facts, not verdicts** (``dev07-3-1``): the adapter records what happened, and only the
gate decides proven from unproven. Nothing here computes a status, and no adapter can stamp one.

Grounding and mutation are **slots** (``dev07-3-1``) — this module fixes where they sit, never how
they are produced (chapters 3 and 4). Two fields are not facts about the run at all: a subject's
``archetype`` comes from the project's config (``dev07-3-2``), and a citation's ``ref`` is the consumer's
own external key, which Plumb carries and never parses (``dev07-3-1``).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

# The runner's own signal, normalized — the core invents no status model (`dev07-3-1`).
PASSED, SKIPPED, FAILED = "passed", "skipped", "failed"
RESULTS = (PASSED, SKIPPED, FAILED)

# The grounding slot's vocabulary (`dev07-1-4`). `not-checked` is the honest answer when no entry
# points are declared — surfaced, never silently skipped (`dev07-1-4`).
GROUNDED, UNGROUNDED, INERT, NOT_CHECKED = "grounded", "ungrounded", "inert", "not-checked"
#: The work left for a thread the adapter could not follow. Distinct from `not-checked` — that is
#: "the question could not be asked", this is "it was asked and the answer walked away" — and the
#: two need different things from the reader (`dev07-1-4`).
DISPATCHED = "dispatched"
#: The citing test **neither ran the production artifact nor read it** (`dev07-4-2`).
#:
#: `inert` was the whole of *did not execute*, and `dev07-4-2` asks for the mirror of a presence —
#: *the test read it rather than running it*. A mirror of a presence has to be another presence,
#: and an absence is satisfied by `assert True`: probed and confirmed, an empty test produced no
#: frames and no reads, read as `inert`, and proved a structural story. That is the fake the whole
#: framework exists to catch, shipping inside the framework.
#:
#: So the two are split at the point the fact is made. From major 8 an adapter that can see reads
#: emits `inert` only where the artifact was **read**, and `untouched` where it was not. A document
#: written at major 7 keeps `inert`'s older, looser meaning — the climb carries it rather than
#: re-reading it, because nothing recorded whether those runs read anything and inventing the
#: answer either way is what `dev07-3-1` forbids.
UNTOUCHED = "untouched"
GROUNDING = (GROUNDED, UNGROUNDED, INERT, NOT_CHECKED, DISPATCHED, UNTOUCHED)


# What kind of claim a story makes (`dev07-4-2`). Behavioral is the default, so a spec that never
# mentions archetypes is unchanged.
BEHAVIORAL, STRUCTURAL = "behavioral", "structural"
ARCHETYPES = (BEHAVIORAL, STRUCTURAL)

# How several citations of one aspect combine (`dev07-4-3-ur05`). **Best** is a story: one qualifying
# proof is enough, and another test failing does not un-prove what this one showed. **Worst** is a
# decision: one clause of a falsifier firing breaches it whatever the others say, and taking the
# best of them would report the flattering half of a decision already known to be wrong.
BEST, WORST = "best", "worst"
REDUCTIONS = (BEST, WORST)

# What a subject's derived statuses are **called** (`dev07-4-3-ur05`). A projection over what the gate
# already derived, never a second status — `story` is the default and every project that has not
# asked for anything else. The core carries the name only; the words live in the gate.
STORY_LEXICON = "story"

SCHEMA_MAJOR = 9
SCHEMA_MINOR = 0
#: ``major.minor`` (`dev07-3-1`). A single sequential integer answered *which shape*, never *can you
#: read it* — so compatibility lived in a changelog and an adapter author could not derive it.
#: **Minor** is additive and readable by any reader of the same major; **major** is structural and
#: is not. Majors 1-4 are retired: the window is the current major and one back, and a step retires
#: when nothing stands on it (`dev07-3-3-sr3`).
SCHEMA_VERSION = f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}"

# Each schema version's shape, stated once and in full (`dev07-3-2`). A version's entry is the whole
# truth about that version: adding a field means adding a **new entry**, never editing an old one,
# because two cores that both claim to read version 1 must agree on what version 1 is.
#
# Checking against the *declared* version rather than against whatever the current dataclass
# happens to define is what makes a refusal accurate. The looser check — "no version I know
# defines this field" — reads identically while only one version exists and starts lying the day
# a second one lands.
MANIFEST_FIELDS = {
    # Major 6 has **no document-level observer**. One observer for a whole document was right
    # while one run meant one adapter, and becomes a false claim the moment a board carries a JVM
    # observer's fact beside a CPython tracer's (`dev07-3-1`).
    7: frozenset({"schema_version", "stories", "observed_tests"}),
    # Major 8 changes no field. It widens the **grounding vocabulary**, which a major-7 reader
    # would reject outright rather than degrade — so the shape is identical and the version is
    # what says *this document may say `untouched`*.
    8: frozenset({"schema_version", "stories", "observed_tests"}),
    # Major 9 adds `citation.entered_through` — the *which* door, where major 8 and everything
    # before it carried only the *whether* (`dev07-1-4`). Document shape is unchanged; the addition is
    # on the citation, and a major-8 reader would refuse the field rather than degrade, which is
    # `dev07-3-2` working rather than a cost of it.
    9: frozenset({"schema_version", "stories", "observed_tests"}),
}
_STORY_FIELDS = frozenset({"archetype", "citations", "mutation"})
#: Major 7 lets a subject declare **its aspects** (`dev07-3-1`). A story has one and names
#: none, which is why every document written before this reads unchanged.
_V7_STORY = _STORY_FIELDS | {"aspects", "reduce", "lexicon"}
STORY_FIELDS = {7: _V7_STORY, 8: _V7_STORY, 9: _V7_STORY}

#: Retired at major 9, when the window moved past it (`dev07-3-3-sr3`). Kept as the base the later
#: shapes are stated against, because each version's entry is the whole truth about that version
#: and deriving 7 from 6 is how that stays true without restating seven fields.
#: Major 6 puts the instrument on the **fact** (`dev07-3-1`, `dev07-3-1`) — major 5 named one for the
#: whole document, and retired when the window moved past it.
_V6_CITATION = frozenset({"test", "depth", "result", "grounding", "ref",
                          "reached_outside_entry", "observer"})
#: Major 7 lets a citation say **which of its subject's aspects it is about** (`dev07-3-1`). Absent
#: means the subject has one, which is every story ever written.
_V7_CITATION = _V6_CITATION | {"about", "when"}
#: Major 9 names **which declared entry point** the test came in through (`dev07-1-4`). `dev07-1-4`'s bool
#: says one was reached; a flat project-wide `entry_points` means a door opened for one subject is
#: open to every subject, and without the identity nothing downstream can tell a test that came in
#: the front from one that let itself in at a subsystem door somebody declared for another chapter.
_V9_CITATION = _V7_CITATION | {"entered_through"}
CITATION_FIELDS = {7: _V7_CITATION, 8: _V7_CITATION, 9: _V9_CITATION}

#: A citation cannot be reconstructed without these. The rest carry defaults, so an adapter that
#: knows nothing about grounding or mutation still emits a valid document (`dev07-5-1`).
REQUIRED_CITATION_FIELDS = {7: ("test", "depth", "result"), 8: ("test", "depth", "result"),
                            9: ("test", "depth", "result")}

#: Every shape `plumb manifest migrate` can **parse** — the chain, and **two majors back**, revised. Deeper than what a run accepts on purpose: the rescue path is worth one major more
#: than the recommendation, so nobody is stranded until they are three behind.
#:
#: Derived rather than listed, so retiring a shape is deleting its entry rather than remembering
#: to. A described shape outside this range is a description nothing can reach.
PARSEABLE_VERSIONS = frozenset({SCHEMA_MAJOR - 2, SCHEMA_MAJOR - 1, SCHEMA_MAJOR}) & frozenset(CITATION_FIELDS)

#: Every shape a **run** accepts: the current major and one back, which is also the published
#: recommendation — *stay within one major of the latest*. Deliberately **narrower** than the
#: chain, and the two stopped being one set the first time a version retired.
#:
#: The original reasoning was that a short window costs nothing because *the chain ships in every
#: release anyway, since the reader needs it* — true only while every shape in the chain is also
#: in the window, and false the moment one retires. Revised to keep the chain one major deeper
#: than the window, so the advice a reader is given is softer than the floor they can fall to.
#:
#: Both refusals are honest and they differ. Too **new** cannot be guessed at, and there is
#: nothing to offer. Too **old** may still be in the chain, so the refusal says so — and where it
#: is not, it says that instead rather than naming a command that cannot help.
#: What Plumb's own shipped adapters still emit, and therefore what the window must keep reading
#: whatever policy says (`dev00-1-1`: one artifact carries every adapter, so an adapter Plumb ships is
#: Plumb's to keep readable). Empty now that the Java adapter emits the current major — it sat at
#: 5 for two majors and worked only because the window happened to still include it, which is the
#: kind of fact that should be visible rather than incidental.
#:
#: `test_no_bundled_adapter_emits_a_version_the_core_refuses` is what keeps this honest: retiring a
#: version an adapter of ours still emits does not inconvenience an adopter, it breaks every
#: project in that language, and re-running their suite reproduces the same refused document.
#:
#: **7, because the JVM observer cannot see reads.** Major 8 makes `inert` the positive half of
#: `dev07-4-2` — *read the artifact and ran none of it* — and the Java adapter watches execution
#: only, so at 8 its `inert` would assert something it never observed. It emits 7, where `inert`
#: means what it can actually establish, and the lag is recorded here rather than left incidental.
#:
#: **Closed on 2026-08-31.** The JVM adapter now observes a read — `ClassLoader.getResourceAsStream`
#: and `java.nio.file.Files`, the primitives every IO library funnels through — so it can make major
#: 8's split on evidence and emits the current major. Empty again, and for the first time because
#: nothing is behind rather than because nothing was checked.
#:
#: **What the lag cost while it lasted.** Major 9 puts the entry point a test came in through on the citation
#: (`dev07-1-4`), and a shipped adapter two majors back cannot carry it — so the fact `dev07-1-4` is
#: about is observable in Python and not in Java, which is where a flat `entry_points` set was
#: actually hit. The blocker is not this field: it is that at 8 the Java observer can make neither
#: positive claim `inert` and `untouched` split into, because it cannot see a read. Nothing here
#: is fixed by widening the window — the adapter has to be able to answer the question major 8
#: asks before it can emit anything above 7.
_SHIPPED_ADAPTER_EMITS = frozenset()

#: What the version-window policy says a run accepts: the current major and one back. The *policy*, kept apart from
#: what actually holds, because the difference between them is a fact worth being able to read.
POLICY_WINDOW = frozenset({SCHEMA_MAJOR - 1, SCHEMA_MAJOR})

#: What a run accepts in fact — the policy, widened by whatever our own adapters still emit.
SUPPORTED_VERSIONS = (POLICY_WINDOW | _SHIPPED_ADAPTER_EMITS) & PARSEABLE_VERSIONS


class InvalidManifest(ValueError):
    """The manifest is the sole interface, so a malformed one is caught at its edge rather
    than misread downstream by a core that cannot see where it came from."""


@dataclass(frozen=True)
class Provenance:
    """The instrument that made a manifest's measurements (``dev07-3-1``).

    ``mechanism`` is the load-bearing field, not ``runtime``. One runtime can offer two ways to
    watch the same thing whose visibility does not agree — CPython's ``sys.settrace`` sees one
    thread and ``settrace_all_threads`` sees them all — and a grounding fact says nothing about
    which was used. Two facts are comparable when the same kind of observer produced them, so
    this is what makes them comparable at all.
    """

    adapter: str
    version: str
    runtime: str
    mechanism: str


@dataclass(frozen=True)
class Survivor:
    """One mutant no test noticed, named (``dev07-2-4``).

    A surviving mutant is the most actionable thing mutation produces, and the reader's next move —
    strengthen the test that missed it — needs to know *what* survived and *where*. Measured on a
    measured: one story at 23/50 left twenty-seven work items with no file, no line and no operator
    recorded anywhere, to be re-derived by hand against a tool that already knew all three.

    The same reasoning as a condition code (``dev07-4-3``): the reader's next move differs per survivor,
    so a number that cannot distinguish them is not the fact they need.
    """

    #: Which mutation was applied — ``flip-comparison``, ``negate-branch``, ``swap-return``.
    operator: str
    #: ``Class#method``, spelled as the adapter's scope spells it.
    where: str
    #: The source file, relative to the project root.
    file: str
    line: int
    #: Whether any citing test actually EVALUATED the mutated expression.
    #:
    #: A survivor nobody reached is not a weak test. Scope is per method, and a method is scoped
    #: whole — so a story whose test sends one kind of event gets mutants on the guard clauses for
    #: every other kind, on lines it never enters and could not kill however good it were. The
    #: reader's next move differs completely: *not noticed* is a missing assertion, *not reached*
    #: is a path this story's tests do not drive (`dev07-4-3`'s argument, one chapter over).
    #:
    #: Unlike equivalence, which is undecidable and stays open as ``dev07-2-4``, this is observed:
    #: the mutated expression is wrapped in a probe and the run reports whether it evaluated.
    #: ``None`` is *not reported* — an adapter older than this field, never a claim it was
    #: unreachable (``dev07-3-3``).
    reached: bool | None = None

    def __post_init__(self):
        if self.line < 1:
            raise InvalidManifest(f"survivor line {self.line} — a mutant sits on a real line")


def _survivor(story_id: str, raw: object) -> Survivor:
    if not isinstance(raw, dict):
        raise InvalidManifest(f"{story_id}: a survivor must be an object, got {type(raw).__name__}")
    missing = [f for f in ("operator", "where", "file", "line") if f not in raw]
    if missing:
        raise InvalidManifest(f"{story_id}: survivor is missing {missing} — a survivor the reader "
                              "cannot locate is the count again, spelled longer")
    reached = raw.get("reached")
    if reached is not None and not isinstance(reached, bool):
        raise InvalidManifest(f"{story_id}: survivor 'reached' must be a boolean or absent, "
                              f"got {type(reached).__name__}")
    return Survivor(operator=raw["operator"], where=raw["where"],
                    file=raw["file"], line=raw["line"], reached=reached)


@dataclass(frozen=True)
class Mutation:
    """How many mutants of a story's grounded code its tests noticed (``dev07-2-4``).

    **A count, not a verdict**, and that is the whole of what a boolean got wrong. A story's tests
    typically run far more code than they check — a component test drives an entry point and
    asserts one thing about the result — so "did any mutant survive?" is ``yes`` for almost every
    real test, and a fact that is almost always the same value carries almost no information. A
    score separates the test that checks nothing from the one that checks most of what it runs,
    and those need different things from the reader.

    It stays advisory whatever the numbers say (``dev07-2-4``): an *equivalent* mutant is
    indistinguishable from a real survivor (``dev07-2-4``), so a shortfall is a place to look and
    never a verdict to act on unread.
    """

    total: int
    killed: int
    #: The mutants no test noticed, named. **Optional, and empty is not "none survived"** — an
    #: adapter that reports a shortfall without naming it is older than this field, not reporting
    #: a clean sheet, so the count stays the authority on how many there were (`dev07-5-1`).
    survivors: tuple[Survivor, ...] = ()

    def __post_init__(self):
        if self.total < 1:
            raise InvalidManifest(f"mutation total {self.total} — a run that made no mutant "
                                  "reports nothing at all, never a score out of zero")
        if not 0 <= self.killed <= self.total:
            raise InvalidManifest(f"mutation killed {self.killed} is not within 0..{self.total}")
        if len(self.survivors) > self.survived:
            raise InvalidManifest(
                f"mutation names {len(self.survivors)} survivor(s) but the score leaves only "
                f"{self.survived} — a name without a shortfall to sit in is a mutant this run "
                "counted as killed and reported as surviving, and the two cannot both be right")

    @property
    def survived(self) -> int:
        """How many mutants no test noticed. The count, which every adapter reports."""
        return self.total - self.killed

    @property
    def unreached(self) -> int:
        """Survivors no citing test ever evaluated — mutants this story could not have killed.

        Zero where the adapter does not report reach, which reads as *none known* rather than
        *none*: the count is only as strong as what was observed (``dev07-3-3``).
        """
        return sum(1 for one in self.survivors if one.reached is False)


@dataclass(frozen=True)
class Citation:
    """One citing test's facts for a story (``dev07-3-1``).

    ``test`` is opaque and adapter-native — a pytest node id, a JUnit method handle. The core
    carries it and never parses it, which is also why it cannot serve as anyone's join key: it
    is derived from a path and a name, so it moves when a test is renamed. ``ref`` exists for
    that (``dev07-3-1``).
    """

    test: str
    depth: str
    result: str
    grounding: str = NOT_CHECKED
    #: Which of the subject's aspects this evidences (`dev07-3-1`) — *informs D27 **about** its
    #: falsifier*. ``None`` is *not named*, the only honest reading for a subject with one aspect,
    #: which is every story ever written. Named for the relation rather than the set, the way a
    #: citation carries a ``depth`` while the ladder it picks from is *rungs* (`dev07-4-3`).
    about: str | None = None
    #: When this was measured, RFC 3339 in UTC — `2026-08-02T15:04:05Z`.
    #:
    #: **On the fact, for `dev07-3-1`'s reason.** That story moved the instrument onto the citation
    #: because a merged board carries several adapters, and two facts are comparable only when the
    #: same kind of observer produced them. A merged board carries several *runs* for exactly the
    #: same reason, so one document-level time would be the same false claim one field over.
    #:
    #: ``None`` is *not reported* and is never read as *now* (`dev07-3-3`): an adapter that cannot
    #: say when it measured says nothing, which is strictly weaker than a time it made up. Every
    #: document written before this carries none, and that is the honest reading of them.
    #:
    #: A manifest stays amnesiac — this is not a history. It is what a *series* is assembled from
    #: once one exists, and the field has to be here first because nothing downstream can recover
    #: a time the run never recorded.
    when: str | None = None
    ref: str | None = None
    #: Did this test also run production code that no entry point reached? Grounding is a
    #: property of the whole test (``dev07-1-4``), so a test can ground on one call and exercise
    #: unreachable code in the next; this is what stops that passing silently (``dev07-1-4``).
    #: ``None`` is *not reported* — an adapter that cannot observe it says nothing (``dev07-3-3``).
    reached_outside_entry: bool | None = None
    #: Which declared entry points this test came in through, **outermost** (`dev07-1-4`). `dev07-1-4`'s
    #: `ran_under_entry_point` says one was reached; `entry_points` is a flat project-wide set, so a
    #: door opened for one subject is open to every subject and the *whether* cannot tell a test that
    #: came in the front from one that entered at a subsystem door declared for another chapter.
    #:
    #: Outermost rather than innermost because that is the arrival, and because it is the only choice
    #: a later declaration cannot rewrite: adding a door changes nothing for a test that already
    #: entered above it.
    #:
    #: ``None`` is *not reported* and is never read as *none entered* (`dev07-3-3`) — an adapter below
    #: major 9 cannot say, which is weaker than saying no door was used.
    entered_through: tuple[str, ...] | None = None
    #: The instrument that made **this** fact (``dev07-3-1``). On the citation rather than on the
    #: document because ``dev07-3-1`` says two facts are comparable only when the same kind of
    #: observer produced them — so a document carrying two adapters' facts under one observer
    #: asserts a comparability it cannot support. ``None`` is *not reported* (``dev07-3-3``).
    observer: "Provenance | None" = None

    def __post_init__(self):
        if self.result not in RESULTS:
            raise InvalidManifest(f"{self.test}: result {self.result!r} is not one of {RESULTS}")
        if self.grounding not in GROUNDING:
            raise InvalidManifest(f"{self.test}: grounding {self.grounding!r} is not one of {GROUNDING}")

    @property
    def ran_and_passed(self) -> bool:
        """``dev07-4-2`` — a skip or an abort is a claim, not proof."""
        return self.result == PASSED


@dataclass(frozen=True)
class Story:
    """A story's entry: its declared archetype, and every test that cited it.

    Keyed in the manifest by an **opaque** id (``dev07-3-2``) — a ``chN-M``, a ticket number, a
    spreadsheet row. The core never parses it and needs no catalog to build this.
    """

    archetype: str = BEHAVIORAL
    #: The aspects this subject has, declared (`dev07-3-1`). Empty means **one, unnamed** — a story,
    #: and the shape every document before major 7 carries. Opaque strings, because a subject's
    #: aspects are its own business (`dev07-3-2`'s posture on ids) and the core knows no set. Named
    #: nowhere in the tool beyond routing: which of them an adopter's evidence bears out is theirs
    #: to judge, and we say only that something informed one (`dev07-4-3`).
    aspects: tuple[str, ...] = field(default_factory=tuple)
    #: How this subject's citations combine (`dev07-4-3-ur05`). `best` is the default and is every story
    #: ever written; `worst` is what a decision needs. Declared rather than inferred from whether
    #: aspects are present — those are two different facts and coupling them would make the second
    #: arrive by accident.
    reduce: str = BEST
    #: What this subject's statuses are called (`dev07-4-3-ur05`). `proven` is the wrong word for a claim
    #: about the future, which can only be un-falsified so far — so a decision says `holding`, and
    #: the two readings of unproven, one situation for code, are opposites for it.
    lexicon: str = STORY_LEXICON
    citations: tuple[Citation, ...] = field(default_factory=tuple)
    #: ``None`` is *not asked* (``dev07-3-3``) — mutation is opt-in and off by default (``dev07-2-2``),
    #: and an unfilled slot must never read as a story whose tests checked nothing.
    mutation: Mutation | None = None

    def __post_init__(self):
        if self.archetype not in ARCHETYPES:
            raise InvalidManifest(f"archetype {self.archetype!r} is not one of {ARCHETYPES}")
        if self.reduce not in REDUCTIONS:
            raise InvalidManifest(f"reduce {self.reduce!r} is not one of {REDUCTIONS}")
        # An aspect outside the declared set is a typo, not an aspect nobody declared — the same
        # reading `dev07-4-1` gives an id belonging to no spec. Refused rather than dropped, because
        # a dropped aspect attaches the citation to nothing and the subject reads unevidenced for
        # a reason no reader could see.
        #
        # Only where aspects *are* declared. A subject declaring none may still be waiting for
        # them: a subject's aspects and the citations naming them arrive from different adapters at
        # different moments, so as one assembles this document one half is legitimately absent. The
        # cross-channel case is caught after the merge, where both halves exist, rather than here
        # where refusing would reject every correct document that names one.
        named = {c.about for c in self.citations if c.about is not None}
        unknown = sorted(named - set(self.aspects)) if self.aspects else []
        if unknown:
            raise InvalidManifest(
                f"citation(s) are about {unknown}, which this subject does not declare — it "
                f"declares {sorted(self.aspects) or 'no aspects, meaning it has exactly one'}")


@dataclass(frozen=True)
class Manifest:
    """``story id -> {archetype, [citations]}`` — the sole thing the core reads (``dev07-3-3``)."""

    stories: dict[str, Story] = field(default_factory=dict)
    #: Absent is a legal answer and means *not reported* — never inferred from whatever the
    #: reader happens to be running (`dev07-3-1`, `dev07-3-3`).
    #: How many tests the run observed at all, cited or not (``dev07-3-2``) — the one fact here about
    #: the *run* rather than about a test. It exists because every other field describes a test
    #: that was seen, so a run that saw none produces a document indistinguishable from a healthy
    #: suite that has not cited a story yet.
    #:
    #: ``None`` is *not reported* and is never read as zero (``dev07-3-3``). The two are different
    #: claims — "I could not count" is strictly weaker than "I looked and there was nothing" — and
    #: only the second is evidence of a broken run. ``dev07-3-2`` carries what that costs an adapter
    #: which cannot count.
    observed_tests: int | None = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self):
        if self.observed_tests is None:
            return
        # `bool` is an `int` in Python, and `observed_tests=True` would sail through as 1 —
        # a count nobody measured, which is the invention `dev07-3-1` forbids.
        if isinstance(self.observed_tests, bool) or not isinstance(self.observed_tests, int):
            raise InvalidManifest(
                f"observed_tests {self.observed_tests!r} is not a count — it is how many tests the "
                "run saw, and absent is how an adapter says it could not tell")
        if self.observed_tests < 0:
            raise InvalidManifest(f"observed_tests {self.observed_tests} is negative")

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(asdict(self), indent=indent, sort_keys=True)

    @classmethod
    def migrate(cls, text: str) -> "Manifest":
        """Read a manifest at any shape in the chain, at the current one (`dev07-3-2`).

        **Offered, never automatic.** Climbing an old manifest in memory on every read would
        leave the file on disk at its old version forever, so no step would ever have nothing
        standing on it and the chain — plus its tests — would be carried permanently. That is the
        unbounded reader `dev07-3-3-ur6` refuses, moved to the migration chain and hidden.

        Reads shapes the ordinary reader has retired, which is the whole point: the population
        that needs migrating is exactly the population outside the window. A shape older than the
        chain is refused rather than guessed at — nothing here invents a fact (`dev07-3-1`).

        Not a substitute for re-running. A manifest is derived and deliberately amnesiac, so
        *re-run your suite* is the first answer and this serves only what cannot be reproduced:
        an archived CI artifact, a decommissioned system, a handover.
        """
        return cls.from_json(text, accept=PARSEABLE_VERSIONS)

    @classmethod
    def from_json(cls, text: str, accept: frozenset = None) -> "Manifest":
        """Read a manifest somebody else may have written (``dev07-3-2``).

        Every rejection names what is supported, because the reader of these messages is an
        adapter author with no view of this source. A refusal costs them one clear sentence;
        guessing would cost them a board that is subtly wrong and silent about why.
        """
        raw = json.loads(text)
        major = _check_version(raw.get("schema_version"), accept)
        _reject_unknown("manifest", raw, MANIFEST_FIELDS[major], major)
        return cls(
            stories={
                sid: _story(sid, entry, major)
                for sid, entry in raw.get("stories", {}).items()
            },
            # Absent means *not reported* and is never read as zero: filling it would make an
            # older document claim its run observed nothing, turning `dev07-5-2` into a false alarm
            # on exactly the manifests that predate the field (`dev07-3-3`).
            observed_tests=_observed(raw.get("observed_tests")),
        )

    def write(self, path: Path) -> Path:
        path.write_text(self.to_json())
        return path

    @classmethod
    def read(cls, path: Path) -> "Manifest":
        return cls.from_json(Path(path).read_text())


def _check_version(version: object, accept: frozenset = None) -> int:
    """Return the **major**, or refuse in a sentence that says what to do next.

    Both refusals matter and they are not symmetric. A manifest *newer* than this core cannot be
    guessed at — nothing can be inferred from a description that has not been written. One
    *older* than the window can be brought forward, and the message says so rather than leaving
    an adapter author to work it out.
    """
    accept = SUPPORTED_VERSIONS if accept is None else accept
    supported = ", ".join(f"{v}.x" for v in sorted(accept))
    if version is None:
        raise InvalidManifest(
            f"no schema_version — every manifest declares the shape it was written against "
            f"(this Plumb reads: {supported})"
        )
    if isinstance(version, str) and re.fullmatch(r"\d+\.\d+", version):
        major = int(version.split(".")[0])
    elif isinstance(version, int) and not isinstance(version, bool):
        major = version          # majors 1-5 predate `major.minor` and numbered sequentially
    else:
        raise InvalidManifest(
            f"schema_version {version!r} is not a version — expected `major.minor` "
            f"(this Plumb reads: {supported})"
        )
    if major in accept:
        return major
    if major > max(accept):
        raise InvalidManifest(
            f"schema_version {version} is newer than this Plumb understands (reads: {supported}). "
            "Upgrade Plumb, or emit an older version — a newer shape cannot be guessed at"
        )
    # Two different old-versions, and only one of them has a way forward. Offering `migrate` to
    # somebody whose shape is outside the **chain** sends them to run the command they may already
    # be running, and a circular instruction is worse than none: it reads like a remedy.
    remedy = ("bring the file forward with `plumb manifest migrate`" if major in PARSEABLE_VERSIONS
              else f"no migration path exists — the chain reaches back to "
                   f"{min(PARSEABLE_VERSIONS)}.x, and a shape below it cannot be inferred")
    raise InvalidManifest(
        f"schema_version {version} is older than this Plumb reads ({supported}). A manifest is "
        "derived from a run, so the first answer is to **re-run your suite**; if that run cannot "
        f"be reproduced, {remedy}"
    )


def _reject_unknown(where: str, raw: dict, allowed: frozenset[str], version: int) -> None:
    """Within a declared version the field set is fixed, so an unrecognised key means the
    producer changed shape without changing the number it claims (``dev07-3-2``).

    Applied to **stories as well as citations**. Silently dropping an unknown story field is
    worse than dropping an unknown citation field, not better: a typo like ``archetypes`` would
    leave the story quietly behavioral, and a mis-declared archetype changes which check the
    gate applies and therefore the status.
    """
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise InvalidManifest(
            f"{where}: field(s) {unknown} are not defined by schema_version {version} "
            f"— it defines {sorted(allowed)}"
        )


def _story(story_id: str, raw: object, version: int) -> Story:
    if not isinstance(raw, dict):
        raise InvalidManifest(f"{story_id}: a story must be an object, got {type(raw).__name__}")
    _reject_unknown(story_id, raw, STORY_FIELDS[version], version)
    return Story(
        archetype=raw.get("archetype", BEHAVIORAL),
        # Absent through major 6, where a subject could not have more than one aspect — so the
        # climb to 7 is lossless with nothing to guess, rather than lossless by convention.
        aspects=tuple(raw.get("aspects", ())),
        reduce=raw.get("reduce", BEST),
        lexicon=raw.get("lexicon", STORY_LEXICON),
        citations=tuple(_citation(story_id, c, version)
                        for c in raw.get("citations", ())),
        mutation=_mutation(story_id, raw.get("mutation")),
    )


def _mutation(story_id: str, raw: object) -> Mutation | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise InvalidManifest(f"{story_id}: mutation must be an object with 'total' and 'killed', "
                              f"got {type(raw).__name__}")
    missing = [f for f in ("total", "killed") if f not in raw]
    if missing:
        raise InvalidManifest(f"{story_id}: mutation is missing {missing} — a score needs both "
                              "halves, and a survivor count nobody can put in proportion is noise")
    named = raw.get("survivors", ())
    if not isinstance(named, (list, tuple)):
        raise InvalidManifest(f"{story_id}: mutation survivors must be a list, "
                              f"got {type(named).__name__}")
    return Mutation(total=raw["total"], killed=raw["killed"],
                    survivors=tuple(_survivor(story_id, one) for one in named))


def _citation(story_id: str, raw: object, version: int) -> Citation:
    if not isinstance(raw, dict):
        raise InvalidManifest(f"{story_id}: a citation must be an object, got {type(raw).__name__}")
    _reject_unknown(f"{story_id}: citation", raw, CITATION_FIELDS[version], version)
    missing = [f for f in REQUIRED_CITATION_FIELDS[version] if f not in raw]
    if missing:
        raise InvalidManifest(f"{story_id}: citation is missing required field(s) {missing}")
    fields = {k: v for k, v in raw.items() if k != "mutation"}
    fields["observer"] = _provenance(raw.get("observer"))
    fields["when"] = _when(story_id, raw.get("when"))
    # `dev07-1-4`. Absent stays None — *not reported*, which is the honest reading of every document
    # written before major 9 — while a present list becomes a tuple so the record stays hashable.
    if raw.get("entered_through") is not None:
        doors = raw["entered_through"]
        if not isinstance(doors, list) or not all(isinstance(d, str) for d in doors):
            raise InvalidManifest(
                f"{story_id}: citation entered_through must be a list of strings, "
                f"got {doors!r}")
        fields["entered_through"] = tuple(doors)
    # Versions 1-3 defined mutation on the citation as a bare outcome word. No adapter ever filled
    # it, so an empty slot carries forward exactly and a filled one is refused rather than guessed
    # at: "survived" says a mutant lived without saying how many ran, and inventing the
    # denominator would put a fabricated score in front of a reader who cannot see it was invented.
    if raw.get("mutation") is not None:
        raise InvalidManifest(
            f"{story_id}: citation carries mutation {raw['mutation']!r}, which schema_version "
            f"{version} could not put a count against. Re-run mutation and emit schema_version "
            f"{SCHEMA_VERSION}, where the score is the story's"
        )
    return Citation(**fields)


def _observed(raw: object) -> int | None:
    """``dev07-3-2`` — the count, or absence meaning *not reported*.

    A JSON document can put anything in the slot, so the type is checked at the edge where the
    producer can still be named, rather than inside the core where it would surface as a
    comparison failing on a value nobody can trace back (``dev07-3-3``).
    """
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, int):
        raise InvalidManifest(
            f"observed_tests must be a count or absent, got {type(raw).__name__} — absent means "
            "the adapter could not tell, and 0 means it looked and found none")
    return raw


#: RFC 3339 in UTC, which is the one spelling every language reads without a library argument.
_WHEN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")


def _when(story_id: str, raw: object) -> str | None:
    """A measurement time, or nothing — and never something in between.

    Refused rather than coerced when it is the wrong shape. A time is the axis a series is ordered
    on, so one that parses differently in two languages orders differently in two languages, and a
    board would disagree with itself about what happened first.
    """
    if raw is None:
        return None
    if not isinstance(raw, str) or not _WHEN.match(raw):
        raise InvalidManifest(
            f"{story_id}: citation `when` is {raw!r} — expected RFC 3339 in UTC, e.g. "
            "'2026-08-02T15:04:05Z'; absent is legal and means not reported")
    return raw


def _provenance(raw: object) -> Provenance | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise InvalidManifest(f"observer must be an object, got {type(raw).__name__}")
    missing = [f for f in ("adapter", "version", "runtime", "mechanism") if f not in raw]
    if missing:
        raise InvalidManifest(f"observer is missing {missing} — a half-named instrument names none")
    return Provenance(**{k: str(raw[k]) for k in ("adapter", "version", "runtime", "mechanism")})


def merge(*manifests: "Manifest") -> "Manifest":
    """Several adapters, one board (``dev07-3-3``).

    ``dev07-3-3`` makes the manifest the hub and ``dev07-3-3`` makes the core language-blind, so a second
    language is a second *manifest* and nothing else: the core learns no language and grows no
    branch — it gains only the ability to read more than one document.

    **It refuses rather than reconciles.** Where two documents carry the same story and the same
    test with facts that disagree, that is a defect in the run and not a difference to average,
    take the best of, or resolve by order. Silently preferring one would make the board depend on
    which adapter finished first, which is the invocation-dependence ``dev07-2-2`` refuses everywhere
    else. Refusing names the disagreement, which is the only outcome that leads anywhere.

    Provenance rides on each fact (``dev07-3-1``), so a merged document says which instrument made
    which measurement — without that, this function would be assembling a comparability
    ``dev07-3-1`` says does not exist.
    """
    stories: dict[str, Story] = {}
    for manifest in manifests:
        for sid, story in manifest.stories.items():
            if sid not in stories:
                stories[sid] = story
                continue
            stories[sid] = Story(
                archetype=_agree(sid, "archetype", stories[sid].archetype, story.archetype),
                citations=_merge_citations(sid, stories[sid].citations, story.citations),
                mutation=stories[sid].mutation or story.mutation,
            )
    extents = [m.observed_tests for m in manifests]
    return Manifest(
        stories=dict(sorted(stories.items())),
        # A total nobody can complete is not a total. One adapter that cannot count makes the sum
        # unknowable, and absent is *not reported* rather than an undercount (`dev07-3-3`, `dev07-3-2`).
        observed_tests=None if any(e is None for e in extents) else sum(extents),
    )


def _agree(sid: str, field: str, first: object, second: object) -> object:
    if first != second:
        raise InvalidManifest(
            f"{sid}: manifests disagree about {field} — {first!r} and {second!r}. That is a defect "
            f"in the run, not a difference to resolve; preferring one would make the board depend "
            f"on which adapter finished first"
        )
    return first


def _merge_citations(sid: str, first: tuple, second: tuple) -> tuple:
    by_test: dict[str, Citation] = {c.test: c for c in first}
    for citation in second:
        seen = by_test.get(citation.test)
        if seen is not None and seen != citation:
            raise InvalidManifest(
                f"{sid}: two manifests carry different facts for the same citation "
                f"{citation.test!r}. One test observed twice with two answers is a defect in the "
                f"run; the board cannot choose between them"
            )
        by_test[citation.test] = citation
    return tuple(sorted(by_test.values(), key=lambda c: c.test))
