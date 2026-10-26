"""Chapter 1's core: the proof gate, and the status derived from it.

**Status is derived, never authored** (``dev07-4-3``) — computed live from the manifest on every
run and never stored, so a proof that later fails un-proves its story and no stale "done" can
exist. Nothing here writes a status anywhere; the caller renders what it returns.

The gate is two checks in series, fail-fast (``dev07-4-2``): a citing test **ran and passed**
(``dev07-4-2``), and its execution matched what the story's archetype claims — behavioral must
**ground**, structural must be **inert**. The second check is never *waived*, only *mirrored*:
an archetype that switched grounding off would be the exemption every fake wants.

This module imports the manifest and nothing else. That is the whole of ``dev07-3-3``
in one line — the core reads only the manifest, so it touches no test framework and knows no
language.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from plumb.core.manifest import (
    BEST,
    FAILED,
    WORST,
    BEHAVIORAL,
    DISPATCHED,
    GROUNDED,
    UNGROUNDED,
    INERT,
    NOT_CHECKED,
    UNTOUCHED,
    Manifest,
    Story,
)

# The derived status vocabulary (`dev07-4-3`).
PROVEN = "proven"
UNPROVEN = "unproven"
PASSED_WIRING_NOT_VERIFIED = "passed-wiring-not-verified"

# Surfaced conditions carry a stable code beside their prose, because a consumer keys off the
# code and never off a sentence that will be reworded. `dev07-5-2` generalizes this; `dev07-1-4` is the
# one condition the gate can already raise.
NO_ENTRY_POINTS = "grounding.not-checked"

#: How to declare an entry point, in **both** spellings the tool ships an adapter for.
#:
#: The *file* is universal and the *values* are the adapter's own (`dev07-1-3`), which is what lets one
#: hint serve every language — and showing a single language's value is the thing that principle
#: forbids. Found by boarding a real Java project: the two strings that made this a defect the first
#: time were gone, and this one was still handing a Java reader a Python module path.
ENTRY_POINT_HINT = ('in plumb.toml — Python:  entry_points = ["myapp.cli:main"]   '
                    '·  Java:  entry_points = ["com.acme.Api#handle"]')
DEPTH_UNSUPPORTED = "depth.unsupported"
REACHED_OUTSIDE = "grounding.reached-outside"

#: Why a subject that **is** cited, whose citations **passed**, is still unproven (``dev07-5-2``).
#: The two easy shapes already had codes — nothing cites it, or a citation failed — and this third
#: one had none, so the board printed a verdict with an empty condition list and a reader who had
#: done more work was told less than one who had done none. One code per arm of the second check,
#: because the next move differs: reach further, assert on the implementation, or stop executing it.
NOT_WIRED = "grounding.not-wired"
CITATION_INERT = "grounding.inert"
STRUCTURAL_EXECUTED = "structural.executed"
#: The citing test touched the artifact in no way at all (`dev07-4-2`). Its own code because the
#: reader's next move is not the one `CITATION_INERT` asks for: that one has a test that read the
#: artifact and is told to run it, this one has a test that did neither.
CITATION_UNTOUCHED = "grounding.untouched"

#: The one condition that is about the **run** rather than about a story (`dev07-5-2`). There is no
#: story to hang it on — that is precisely the failure — so it cannot travel with the others.
#: A citation that did not pass. Not a status a subject can hold — it is the fourth *outcome* a
#: single citation can have, and it exists so a failing citation can take part in the reduction
#: rather than being filtered out before it. A story drops them, which is right: another test
#: failing does not un-prove what a passing one showed. A decision must not, because one clause of
#: a falsifier firing breaches it whatever the others say (`dev07-4-3-ur05`).
NOT_PASSED = "not-passed"

#: Most decisive first, per reduction (`dev07-4-3-ur05`). The gate already ranked its outcomes — as a
#: hardcoded `if` chain reading *proven beats passed-wiring beats unproven* — and naming that order
#: is what lets a second one exist. Reducing is then `min` by position in both cases rather than
#: two algorithms, and adding a subject kind is a row here rather than a branch anywhere.
RANK = {
    BEST: (PROVEN, PASSED_WIRING_NOT_VERIFIED, UNPROVEN, NOT_PASSED),
    WORST: (NOT_PASSED, UNPROVEN, PASSED_WIRING_NOT_VERIFIED, PROVEN),
}

#: A subject with several aspects has no overall status; read its aspects (`dev07-4-3-ur05`).
PER_ASPECT = "aspects.per-aspect"

#: Two reasons for one verdict, told apart (`dev07-3-3`). UNPROVEN has always meant both *nobody
#: wrote a citing test* and *the citing test ran and did not pass*, with nothing on the board to
#: say which — and the reader's next move is completely different. For code the two are at least
#: the same kind of situation; for a decision they are opposites, a silence nobody is watching
#: against a condition that has fired.
NOT_CITED = "evidence.none"
EVIDENCE_FAILED = "evidence.failed"
#: Cited, and **nothing ran**. Not evidence against — the third outcome
#: `closed-loop-frameworks.md` says a chore check needs and the derivation did not have: a
#: keyserver being down and a chore not being done produced the same word, so the recurrence
#: signal meant to nominate chores for automation was noise. It matters wherever a check runs
#: against the world rather than against the repository.
NOT_OBSERVED = "evidence.not-observed"
#: A setting written where the run cannot use it (`dev00-1-2-ur6`). The run carries on; the board
#: says what it did not use.
CONFIG_IGNORED = "config.ignored"

#: What a derived status is **called**, per kind of subject (`dev07-4-3-ur05`).
#:
#: The words are a projection and never a second status: every entry below maps a status the gate
#: already derived, plus a condition it already carries, onto a label. Nothing here can say
#: anything the derivation did not — which is `dev07-5-1` applied to the vocabulary rather than to a
#: view, and the reason a lexicon cannot quietly become a place where standing is authored.
#:
#: `story` is the default and is every project that has not asked for anything else.
#:
#: `decision` exists because **proven is the wrong word for a claim about the future**. A decision
#: can only be un-falsified *so far*, so `holding` is the strongest thing it may say — and the two
#: readings of unproven, which for code are one situation, are opposites here: nobody is watching
#: (`dev07-4-3-ur10`, where the silence is the finding) against the condition has fired (`dev07-4-3-nfr4`, which
#: informs). Splitting `evidence.none` from `evidence.failed` is what made those sayable at all.
LEXICON = {
    "story": {},
    "decision": {
        (PROVEN, None): "holding",
        (UNPROVEN, NOT_CITED): "silent",
        (UNPROVEN, EVIDENCE_FAILED): "breached",
        (UNPROVEN, NOT_OBSERVED): "unwatched",
    },
    # A parameter is a decision with a model and a measurement (`dev07-4-3-ur11`), so it derives
    # identically and reads differently. Neither *holding* nor *breached* fits: a value is not
    # held, and a hypothesis that loses to its own placebo has not been breached, it has been
    # **refuted**. `unvalidated` is the adopter's own word for the ordinary case — a corpus of 81
    # priors with a stated way to test each and no observation against any.
    "parameter": {
        (PROVEN, None): "supported",
        (UNPROVEN, NOT_CITED): "unvalidated",
        (UNPROVEN, EVIDENCE_FAILED): "refuted",
        (UNPROVEN, NOT_OBSERVED): "unmeasured",
    },
}


def label(verdict: "Verdict", lexicon: str) -> str:
    """What to call this verdict, in this subject's vocabulary. Falls back to the status itself.

    A lexicon that has no word for a state says the state's own name rather than inventing one:
    an unlabelled status is a gap in the vocabulary, and a made-up word would hide it.
    """
    words = LEXICON.get(lexicon, {})
    for condition in verdict.conditions or (None,):
        if (verdict.status, condition) in words:
            return words[(verdict.status, condition)]
    return words.get((verdict.status, None), verdict.status)

NOTHING_OBSERVED = "observation.none"
#: The run observed tests and read no citation out of any of them (`dev07-5-2`). Its own code beside
#: `observation.none`, because *the run never happened* and *the run happened and nothing it did
#: reached the board* send a reader to opposite places.
NOTHING_CITED = "observation.uncited"
ORPHAN_STORY = "spec.orphan"
ADAPTER_ABSENT = "adapter.absent"
#: The instrument died and the suite finished anyway (`dev07-1-3`). Run-level for the same reason
#: `ADAPTER_ABSENT` is: it is true of every citation at once, and hanging it on each of them would
#: say a thousand times what happened once.
OBSERVATION_FAILED = "observation.failed"

#: Rungs whose claim is *about* reaching the wired system. A citation claiming one of these whose
#: execution never grounded is lying about its depth, and grounding is the mechanical check on an
#: otherwise-trusted claim (``dev07-4-2``).
#:
#: This lives in the core rather than beside the tracer, and that placement is the whole reason it
#: works: it is a pure function of two manifest fields, but while it sat in the adapter the gate
#: could not import it (``dev07-4-3`` forbids core reaching into an adapter) — so the only caller that
#: could ever have used it was prevented by the seam, and two passing tests made it look alive.
WIRED_RUNGS = frozenset({"wiring", "standards-integration", "smoke", "smoke/e2e", "e2e"})


def contradicts_claimed_depth(depth: str, grounding: str) -> bool:
    """``dev07-4-2`` — is this citation's claimed rung refuted by what actually executed?

    Only the wired rungs make a claim grounding can check. A ``unit`` or ``component`` claim is
    about isolation and is *expected* not to ground, so it is never contradicted here — the
    remainder stays trusted and is named as the residue it is (``dev07-4-2``).
    """
    if depth not in WIRED_RUNGS:
        return False
    return grounding in (UNGROUNDED, INERT)
WORK_DISPATCHED = "grounding.dispatched"


@dataclass(frozen=True)
class Condition:
    """A surfaced gap, in three separately-addressable parts.

    They are kept apart rather than run into one sentence because they answer different
    questions and are consumed differently: a reader wants ``what``, someone fixing it wants
    ``next_step``, and someone who has never seen the syntax needs ``example``. A consumer can
    render or suppress each on its own, and only ``code`` is a promise — the prose may be
    reworded freely (``dev07-5-2``).
    """

    code: str
    what: str
    next_step: str
    example: str = ""


UNLOCK_GROUNDING = "unlock.grounding"
UNLOCK_MUTATION = "unlock.mutation"

#: Conditions about the run itself, keyed the same way and carrying the same three parts, so a
#: consumer reads them with the code it already has (`dev07-5-2`, `dev07-5-2`). Separate from
#: ``CONDITIONS`` because the two attach to different things, not because they differ in kind.
RUN_CONDITIONS = {
    PER_ASPECT: Condition(
        code=PER_ASPECT,
        what="this has more than one aspect, so it has no single status — each derives its own, "
             "and they close at different times for different reasons",
        next_step="read the aspects rather than the subject; an aggregate would hide the one that "
                  "matters behind the ones that do not",
        example="a decision whose outcome is asserted and whose falsifier nobody has evaluated is "
                "not proven, and is not unproven either — it is one of each",
    ),
    NOT_CITED: Condition(
        code=NOT_CITED,
        what="nothing cites this, so nothing has been claimed about it — an absence of evidence, "
             "not evidence against",
        next_step="write a test that cites it, or leave it: an unproven story on a fresh spec is "
                  "the correct reading and not a fault",
        example="a spec authored ahead of the work reads entirely unproven, and should",
    ),
    EVIDENCE_FAILED: Condition(
        code=EVIDENCE_FAILED,
        what="something cites this, ran, and did not pass — a failing test is evidence against, "
             "whatever the other citations show",
        next_step="read the failure itself; this is the one unproven that is a *result* rather "
                  "than an absence, and it is the only one that changed",
        # The distinction is worth a code because the two are indistinguishable on a board and
        # need opposite responses: one is work not started, the other is work that broke.
        example="a story that read proven yesterday and unproven today did not lose its test — "
                "its test started failing",
    ),
    NOT_OBSERVED: Condition(
        code=NOT_OBSERVED,
        what="something cites this and none of its citations ran, so nothing was observed either "
             "way — not evidence against, and not evidence for",
        next_step="find why the citing tests did not run — skipped, deselected, or a check that "
                  "runs against the world and could not reach it — and run them",
        example="a check that reaches a keyserver reads unobserved while the keyserver is down, "
                "rather than failed",
    ),
    CONFIG_IGNORED: Condition(
        code=CONFIG_IGNORED,
        what="a setting in the project's configuration is written where this run cannot use it, "
             "so the run went ahead without it",
        next_step="read the lines naming each one, above the board, and move or remove the "
                  "setting — the board below is what the run measured without it",
        example="`specs` written under [java] is read by nothing; above the first `[` it is read",
    ),
    NOTHING_OBSERVED: Condition(
        code=NOTHING_OBSERVED,
        what="no tests were observed at all, so nothing was derived — this board is empty because "
             "the run found nothing to look at, not because nothing is proven yet",
        next_step="check that your own test command discovers tests before reading this board; a "
                  "run that observed nothing looks exactly like a correct first run",
        # Language-neutral, for the reason `depth.unsupported` is: this fires on the runs where a
        # build system is misconfigured, and naming one language's runner would send half the
        # readers who see it to the wrong place.
        example="run your suite on its own — if it reports 0 tests, so will Plumb, and the cause "
                "is in the test path or classpath rather than in any citation",
    ),
}

#: Every condition the gate can raise about a story. The set is finite and knowable, so what the
#: board can say is a list rather than an open question (`dev07-5-2`).
CONDITIONS = {
    WORK_DISPATCHED: Condition(
        code=WORK_DISPATCHED,
        what="the work was handed to a thread this adapter could not follow, so whether it ran "
             "under an entry point is unknown",
        next_step="carry the entry-point context across that hand-off, or accept that this story "
                  "is proven no deeper than its own thread",
        example="an executor created before the entry point ran inherits nothing — wrapping it "
                "is what carries the context across",
    ),
    REACHED_OUTSIDE: Condition(
        code=REACHED_OUTSIDE,
        what="this story grounded, and the same test also ran production code that no entry "
             "point reaches — so the grounding does not vouch for all of it",
        next_step="check that what this story claims is the part that ran wired, not the part "
                  "that did not; splitting the test is the usual answer",
        example="a test that drives an entry point and then calls a helper directly grounds on "
                "the first call, and nothing here can tell the two apart",
    ),
    DEPTH_UNSUPPORTED: Condition(
        code=DEPTH_UNSUPPORTED,
        what="a citation claims it reached the wired system, and its execution never did",
        # **Which branch does what, because they do different things.** Both end this complaint and
        # only one advances the story, and the text used to offer them as equals — leading with the
        # one that does not. A reader who lowered the depth exactly as instructed watched the
        # message disappear and the story stay unproven, which reads as the advice not having
        # worked. Reaching an entry point goes first for the same reason: `dev07-5-2` makes the board
        # say what would make a check possible, and that must not open with the option that moves
        # the verdict no further.
        next_step="drive the story through a declared entry point, which is what a wired claim "
                  "needs to hold — or lower the claimed depth, which ends this complaint and "
                  "moves the verdict no further on its own",
        # Language-neutral on purpose. Every one of these is printed to whoever ran the command,
        # and the citation syntax differs per language — a Java user was being shown a pytest
        # marker, which is advice they cannot act on and cannot tell is not meant for them.
        example='at depth="unit" the claim is one the execution supports; the status stays '
                'whatever the grounding already earned, and the board says why separately',
    ),
    NO_ENTRY_POINTS: Condition(
        code=NO_ENTRY_POINTS,
        what="grounding did not run — no production entry points are declared",
        next_step="declare where the wired system begins, to catch orphaned code",
        # A form without a home is advice nobody can act on, so the example names the file. The
        # *values* stay in the adapter's own spelling (`dev07-1-3`) and the file does not, which is
        # what lets one hint serve every language.
        example=ENTRY_POINT_HINT,
    ),
    NOTHING_CITED: Condition(
        code=NOTHING_CITED,
        # **It does not say which**, because the manifest cannot tell. What it separates is this
        # board from the one a run that observed *nothing* produces — those were the same bytes,
        # and the difference is the whole finding.
        what="tests ran and not one of them cited a subject — either nothing is claimed here yet, "
             "or the citations could not be read",
        next_step="if you have written citations, check they use the marker this project declares "
                  "and the annotation Plumb ships rather than a copy of it; the run's own output "
                  "names any marker it saw and did not recognise",
        # Language-neutral, which `dev07-3-3` requires of everything the core says: the shapes are
        # named, never one adapter's spelling of them. A first draft reached for the Java case by
        # name and the standing check caught it.
        example="a citation marker this project did not declare, or a copy of the citation type "
                "compiled into the project itself, which shadows the real one and makes every "
                "citation invisible",
    ),
    ORPHAN_STORY: Condition(
        code=ORPHAN_STORY,
        what="a story id belongs to no declared spec — an id outside every namespace is not a "
             "story in a spec nobody named, it is a typo, and it lands on the board looking "
             "authoritative",
        next_step="add the namespace to `specs` in plumb.toml, or correct the id",
        example='in plumb.toml:  specs = ["APP", "OPS"]',
    ),
    NOT_WIRED: Condition(
        code=NOT_WIRED,
        what="the citations that passed reached nothing wired — what ran was the implementation "
             "on its own, which is not evidence the story holds where it is used",
        next_step="drive it through a declared entry point, or leave it at the depth it reaches "
                  "and let the board say so",
        example="a test calling the class directly proves the class; the story is about the "
                "system that calls it",
    ),
    CITATION_UNTOUCHED: Condition(
        code=CITATION_UNTOUCHED,
        what="the citing test neither ran the production artifact nor read it, so nothing it did "
             "is evidence about the subject it names",
        next_step="make the test touch the thing it claims about — run it, or read it as data if "
                  "the claim really is about its shape",
        example="`assert True` passes forever and is a claim about nothing; so is a test asserting "
                "only on values it built itself",
    ),
    CITATION_INERT: Condition(
        code=CITATION_INERT,
        what="every citation passed without executing the implementation at all, so the story is "
             "cited by a test that never reached what it claims about",
        next_step="assert against the implementation, or re-declare the subject as structural if "
                  "inspection really is the proof",
        example="a test asserting on a fixture, a constant or its own setup passes forever and "
                "moves no story",
    ),
    STRUCTURAL_EXECUTED: Condition(
        code=STRUCTURAL_EXECUTED,
        what="a structural claim is proved by inspection, and its citing test executed production "
             "code — so what passed was an exercise of the shape rather than a reading of it",
        next_step="inspect the shape without running it, or re-declare the subject as behavioral",
        example="reading an import graph proves it; importing the modules and calling them does "
                "not",
    ),
    OBSERVATION_FAILED: Condition(
        code=OBSERVATION_FAILED,
        what="the observer failed during this run, so grounding is `not-checked` everywhere — "
             "for a reason that is the instrument's and not your project's",
        next_step="read the adapter's own output above for what the observer hit; the test results "
                  "on this board are unaffected, and only the wiring question went unanswered",
        example="`not-checked` here does NOT mean you declared no entry points — if you declared "
                "them, they are not the thing to go and look at",
    ),
    ADAPTER_ABSENT: Condition(
        code=ADAPTER_ABSENT,
        what="an adapter this project declares did not run, so a language is missing from this "
             "board — what you are reading is part of the answer, not the whole one",
        next_step="fix the adapter that failed and re-run; its own output above says why",
        example="a board covering two languages with one adapter down is not a smaller board, it "
                "is a board about a different project",
    ),
}


#: What more this project could get, and what it would cost them to get it. The board markets
#: its own next step from its own output, so nobody has to be sold anything (`dev07-5-2`).
UNLOCKS = {
    UNLOCK_GROUNDING: Condition(
        code=UNLOCK_GROUNDING,
        what="{n} stories passed but their wiring was never checked",
        next_step="declare production entry points, and those stories get gated on real wiring",
        example=ENTRY_POINT_HINT,
    ),
    UNLOCK_MUTATION: Condition(
        code=UNLOCK_MUTATION,
        what="{n} stories are proven, and nothing has checked that their tests assert anything",
        next_step="run mutation over them to find a test that runs the code without checking it",
        example="plumb board --mutation — off by default because it is slow, not because it is "
                "optional; it prints what it will cost before it starts",
    ),
}

#: Everything the board is permitted to say. A consumer branches on these and never on prose.
ALL_CODES = frozenset(CONDITIONS) | frozenset(UNLOCKS) | frozenset(RUN_CONDITIONS)

#: Every code's prose, in one place, because a code is one vocabulary and the registries above
#: only record *what a code can attach to* (``dev07-5-2``). Reading a story's condition out of
#: ``CONDITIONS`` alone is what shipped `evidence.none` with an empty `what` and `next_step`: the
#: three commonest conditions a story can carry are defined beside the run-level ones, so the
#: lookup that knew about only one registry found nothing and emitted the code bare. The parts are
#: authored once and resolved from anywhere, so where a code is *defined* can never again decide
#: whether a reader is told what it means.
PROSE = {**CONDITIONS, **RUN_CONDITIONS, **UNLOCKS}


def prose(code: str) -> Condition | None:
    """The three parts behind a code, wherever it was defined. ``None`` for a code this build
    does not know, which a consumer must still be able to receive (``dev07-5-2``)."""
    return PROSE.get(code)


def orphaned(sid: str, namespaces=(), declared=()) -> bool:
    """Whether an id lies outside every declared namespace and was named nowhere else (``dev07-4-1``).

    ``declared`` is the ids the project named in its own configuration — a decision or a parameter
    in the tables that say how a subject is judged. The project has already named those, which is
    the whole of what the check asks (``dev07-4-1-ur5``), so they are never orphans.
    """
    return bool(namespaces) and sid not in declared and not sid.startswith(tuple(namespaces))


def run_conditions(manifest: Manifest, namespaces=(), absent_adapters=(),
                   blind_adapters=(), declared=(), ignored=()) -> tuple[str, ...]:
    """What this run has to say about *itself*, before any story is derived (``dev07-5-2``).

    Only one thing so far, and it is the one the rest of the gate structurally cannot notice: a run
    that observed no tests derives an empty board, and an empty board is exactly what a correct
    first run produces. ``derive_all`` iterates the stories, so with no stories it has nothing to
    iterate and nothing to say — the silence is not a bug in the loop, it is the loop working on an
    input that never arrived.

    ``None`` raises nothing. An adapter that did not report the extent has not claimed there was
    none, and inventing the stronger claim from its silence is what ``dev07-3-3`` forbids — the cost
    of that restraint is ``dev07-3-2``.
    """
    codes = []
    if manifest.observed_tests == 0:
        codes.append(NOTHING_OBSERVED)
    # `dev07-5-2`, and the same argument as `NOTHING_OBSERVED` one step along: a run that read no
    # citation emits the identical bytes as a healthy suite nobody has cited yet, and the method's
    # own doctrine is what hides it — an empty board is what a correct first run looks like.
    #
    # **Only where tests were actually seen.** `None` is *not reported* (`dev07-3-3`) and 0 is already
    # `NOTHING_OBSERVED`; claiming this on either would be reporting a second condition for one
    # fact, and on `None` it would be inventing the count the adapter said it could not take.
    elif manifest.observed_tests and not manifest.stories:
        codes.append(NOTHING_CITED)
    if namespaces:
        # An id outside every declared namespace (`dev07-4-1`). Only asked when the project declared
        # namespaces at all — silence means it carries one spec and the question does not arise.
        if any(orphaned(sid, namespaces, declared) for sid in manifest.stories):
            codes.append(ORPHAN_STORY)
    if absent_adapters:
        codes.append(ADAPTER_ABSENT)
    if blind_adapters:
        # Told apart from `absent` deliberately. An adapter that did not run has said nothing; one
        # that ran blind has said everything except one thing, and a reader who cannot tell those
        # apart does not know whether the results above are worth anything (`dev07-1-3`).
        codes.append(OBSERVATION_FAILED)
    if ignored:
        codes.append(CONFIG_IGNORED)
    return tuple(codes)


def unlocks(verdicts: dict[str, "Verdict"], manifest: Manifest) -> dict[str, int]:
    """Which next steps this run has earned the right to suggest, and how many stories each
    would move. Derived from the run — never a standing advertisement (`dev07-5-2`).

    The manifest is read as well as the verdicts because a suggestion must not outlive its own
    answer: a story whose citations already carry a mutation fact has had the question asked, and
    telling that project to turn mutation on is the board asserting a gap its own source does not
    show (`dev07-5-1`).
    """
    found: dict[str, int] = {}
    partial = sum(1 for v in verdicts.values() if v.status == PASSED_WIRING_NOT_VERIFIED)
    if partial:
        found[UNLOCK_GROUNDING] = partial
    unchecked = sum(1 for sid, v in verdicts.items()
                    if v.status == PROVEN and not _mutation_checked(manifest.stories[sid]))
    if unchecked:
        found[UNLOCK_MUTATION] = unchecked
    return found


def _mutation_checked(story: Story) -> bool:
    """Has the question been asked of this story at all? An unfilled slot is *not asked*
    (`dev07-3-3`), which is exactly when the next step is still available."""
    return story.mutation is not None


@dataclass(frozen=True)
class Verdict:
    """What the gate derived for one story — the output, computed each run (``dev07-4-3``)."""

    story: str
    status: str
    achieved: tuple[str, ...] = ()
    conditions: tuple[str, ...] = ()
    #: One verdict per declared aspect (`dev07-3-1`, `dev07-4-3-ur05`), empty for a subject with one.
    #: A subject with several has **no overall status** — the aspects close at different times
    #: for different reasons, and an aggregate would re-collapse exactly what declaring them
    #: separates. `status` is held at `unproven` in that case so a consumer reading only that
    #: field can never be shown a green it did not earn (`dev07-5-1`).
    aspects: dict[str, "Verdict"] = field(default_factory=dict)

    @property
    def proven(self) -> bool:
        return self.status == PROVEN


def _second_check(archetype: str, grounding: str) -> str:
    """The archetype selects a check over the *same* per-test fact (``dev07-4-2``).

    Every arm of both branches is handled deliberately. An unhandled arm is exactly where a case
    falls silently through a gate, and this framework already shipped that bug once — its
    structural branch had no arm for one of the grounding facts.
    """
    if archetype == BEHAVIORAL:
        if grounding == GROUNDED:
            return PROVEN
        if grounding == UNTOUCHED:
            # Never partial credit. `not-checked` and `dispatched` are questions that could not be
            # answered; this is an answer — the test did nothing to the artifact — and it is the
            # weakest evidence there is (`dev07-4-2`).
            return UNPROVEN
        if grounding in (NOT_CHECKED, DISPATCHED):
            # Two different reasons for the same verdict. `not-checked`: nothing declared where
            # the real system begins. `dispatched`: it was declared, the check ran, and the work
            # left for a thread the adapter could not follow. Neither is a failure and neither is
            # a pass — degrade and surface (`dev07-1-4`, `dev07-5-1`). They are told apart by the
            # condition the board carries, because the reader's next move differs.
            return PASSED_WIRING_NOT_VERIFIED
        # `ungrounded` is the orphaned-"done" fake; `inert` never ran the code at all.
        return UNPROVEN

    # Structural: proved by inspection, so the citing test must be inert (`dev07-4-2`). Anything
    # that executed production code was not inspecting the shape — including `not-checked`,
    # which means production code *did* run, merely without a declared surface to judge it by.
    #
    # `inert` is the **positive** half of that claim from major 8 on: the test read the artifact
    # and ran none of it. `untouched` is the case this branch used to accept and must not — a test
    # that did neither is not inspecting anything, and `assert True` is its cheapest form.
    return PROVEN if grounding == INERT else UNPROVEN


def derive(story_id: str, story: Story) -> Verdict:
    """Run the gate over one subject's citations and return what it derived.

    A subject with one aspect gets one verdict, which is every story ever written. One with
    several gets a verdict **per aspect** and no aggregate (`dev07-4-3-ur05`): a decision's aspects —
    its levers measured, its outcome observed, the condition that would make it wrong not fired —
    close at different times and for different reasons, and a single word for all three is not a
    simplification but a loss of the finding.
    """
    if story.aspects:
        return _per_aspect(story_id, story)
    if not story.citations:
        # An absence of evidence, not evidence against — and the correct reading of a spec
        # written ahead of the work.
        return Verdict(story_id, UNPROVEN, conditions=(NOT_CITED,))

    # Every citation gets an outcome, including the ones that did not pass. Filtering those out
    # first is what made a story's reduction the only one expressible: a decision needs them, and
    # `worst` cannot see what was removed before it ran.
    rank = RANK[story.reduce]
    outcomes = [_second_check(story.archetype, c.grounding) if c.ran_and_passed else NOT_PASSED
                for c in story.citations]
    decided = min(outcomes, key=rank.index)

    passing = [c for c in story.citations if c.ran_and_passed]
    if decided == NOT_PASSED or not passing:
        # Cited and not proven, and *why* is what a reader acts on. A citation that ran and failed
        # is evidence against; one that never ran is no evidence at all, and calling the second a
        # failure is how a flaky third party gets counted as a broken claim.
        ran = any(c.result == FAILED for c in story.citations)
        return Verdict(story_id, UNPROVEN,
                       conditions=(EVIDENCE_FAILED,) if ran else (NOT_OBSERVED,))
    status = decided

    # The achieved vector is the rungs a story is *actually* proven at (`dev07-4-3`) — derived and
    # shown, so unit-only reads as unit-only.
    # A rung the run refuted is surfaced below as `depth.unsupported` and is not also reached
    # (`dev07-4-3-ur04`).
    achieved = tuple(sorted({c.depth for c in passing
                             if c.depth and not contradicts_claimed_depth(c.depth, c.grounding)}))
    conditions = ()
    # dev07-4-2: a claimed rung the execution refutes is surfaced whatever the status — a story can be
    # proven by one citation while another lies about how deep it reached.
    if any(contradicts_claimed_depth(c.depth, c.grounding) for c in passing):
        conditions += (DEPTH_UNSUPPORTED,)
    # dev07-1-4's stated limit, made visible rather than left to be discovered: grounded on the
    # strength of one call, while another went somewhere no entry point reaches.
    if any(c.grounding == GROUNDED and c.reached_outside_entry for c in passing):
        conditions += (REACHED_OUTSIDE,)
    if status == PASSED_WIRING_NOT_VERIFIED:
        # Name the reason, not just the verdict: "declare entry points" is useless advice to a
        # project that already did, and told only that, they would go looking in the wrong place.
        reasons = {c.grounding for c in passing}
        conditions += tuple(sorted(
            ({WORK_DISPATCHED} if DISPATCHED in reasons else set())
            | ({NO_ENTRY_POINTS} if NOT_CHECKED in reasons else set())
        ))
    if status == UNPROVEN:
        # The same obligation, for the verdict that had none (`dev07-5-2`). Cited and failed is
        # `evidence.failed` and cited by nothing is `evidence.none`; this is the third shape,
        # where the tests did their job and what they executed does not support the claim. Read
        # off the citations that actually derived it rather than off all of them, so a story
        # proven nowhere by one arm is not explained by another arm's grounding.
        refused = {c.grounding for c in passing
                   if _second_check(story.archetype, c.grounding) == UNPROVEN}
        if story.archetype == BEHAVIORAL:
            conditions += tuple(sorted(
                ({CITATION_UNTOUCHED} if UNTOUCHED in refused else set())
                | ({NOT_WIRED} if UNGROUNDED in refused else set())
                | ({CITATION_INERT} if INERT in refused else set())
            ))
        elif refused:
            # Two ways a structural claim fails and they are opposite mistakes. `structural.executed`
            # is a test that ran the artifact when it should have read it — too much contact.
            # `grounding.untouched` is a test that did neither — none at all. Telling somebody who
            # wrote `assert True` that their test executed production code sends them to delete
            # something that is not there.
            conditions += tuple(sorted(
                ({CITATION_UNTOUCHED} if UNTOUCHED in refused else set())
                | ({STRUCTURAL_EXECUTED} if refused - {UNTOUCHED} else set())
            ))
    if any(c.result == FAILED for c in story.citations):
        # A red test is never hidden behind the reason another citation fell short
        # (`dev07-4-3-ur12`): told only that nothing reached the wired system, a reader goes
        # looking for an entry point while a test is failing.
        conditions = (EVIDENCE_FAILED,) + conditions
    return Verdict(story_id, status, achieved, conditions)


def _per_aspect(story_id: str, story: Story) -> Verdict:
    """One verdict per declared aspect, and deliberately none for the subject.

    A citation naming no aspect is **not** spread across them. Attributing it to all would let one
    test speak for three aspects it never mentioned, and attributing it to a guessed one would
    invent a fact — so it is counted nowhere, and every aspect it might have served reads as the
    silence it actually is (`dev07-3-3`, `dev07-4-3-ur10`).
    """
    derived = {}
    for aspect in story.aspects:
        # The name is stripped on the way down: inside one aspect's view it is implicit, and a
        # citation still carrying it would name an aspect that view no longer declares.
        cited = tuple(replace(c, about=None) for c in story.citations if c.about == aspect)
        derived[aspect] = derive(f"{story_id}#{aspect}",
                                 replace(story, aspects=(), citations=cited))
    # Never a status of its own — held unproven so a consumer reading only this field cannot be
    # shown a green that no single aspect earned.
    return Verdict(story_id, UNPROVEN, conditions=(PER_ASPECT,), aspects=derived)


def derive_all(manifest: Manifest) -> dict[str, Verdict]:
    """Derive every story's status from the manifest — the core's whole job."""
    return {sid: derive(sid, story) for sid, story in manifest.stories.items()}
