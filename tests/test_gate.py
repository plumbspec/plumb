"""The proof gate and the status it derives (chapter 1).

The gate is a pure function of the manifest, so every case here is built by hand rather than
run — which is the point of `dev07-3-3`: the core can be exercised with no runner in sight.
"""

import pytest

from plumb.core.gate import (
    NO_ENTRY_POINTS,
    PASSED_WIRING_NOT_VERIFIED,
    PROVEN,
    UNPROVEN,
    derive,
    derive_all,
)
from plumb.core.manifest import (
    FAILED,
    GROUNDED,
    INERT,
    NOT_CHECKED,
    PASSED,
    SKIPPED,
    STRUCTURAL,
    UNGROUNDED,
    Citation,
    Manifest,
    Story,
)


def story(*citations, archetype=None) -> Story:
    kw = {"archetype": archetype} if archetype else {}
    return Story(citations=tuple(citations), **kw)


def cite(result=PASSED, grounding=GROUNDED, depth="wiring", test="t::a",
         about=None) -> Citation:
    return Citation(test=test, depth=depth, result=result, grounding=grounding, about=about)


@pytest.mark.proves("dev07-4-2", depth="unit")
def test_no_citing_test_at_all_is_a_claim_not_a_proof():
    assert derive("s", story()).status == UNPROVEN


@pytest.mark.proves("dev07-4-2", depth="unit")
@pytest.mark.parametrize("result", [SKIPPED, FAILED])
def test_a_skip_or_a_failure_never_proves(result):
    assert derive("s", story(cite(result=result))).status == UNPROVEN


@pytest.mark.proves("dev07-5-2", depth="unit")
@pytest.mark.parametrize("reduce, expected", [("best", PROVEN), ("worst", UNPROVEN)])
def test_the_same_citations_reduce_two_ways_and_the_rank_is_the_only_difference(reduce, expected):
    """`dev07-4-3-ur05`. One claim holds and one fired; which of them the verdict reports is the whole
    difference between a story and a decision.

    **Best** is right for a story: another test failing does not un-prove what a passing one
    showed. **Worst** is right for a decision: one clause of a falsifier firing breaches it
    whatever the others say. Confirmed on a real board before this existed — the tier-count falsifier
    read PROVEN while that falsifier had fired, because best-of picked the clause that held, and
    it was wrong in the flattering direction.

    The two are one algorithm over two orderings rather than two algorithms, which is what makes a
    third subject kind a row in the table rather than a branch in here.
    """
    verdict = derive("s", Story(archetype="structural", reduce=reduce, citations=(
        cite(grounding=INERT, depth="unit"),
        cite(grounding=INERT, depth="unit", result=FAILED))))

    assert verdict.status == expected


@pytest.mark.proves("dev07-5-2", depth="unit")
def test_a_failing_citation_takes_part_in_the_reduction_rather_than_being_removed_from_it():
    """The mechanical reason a story's reduction was the only one expressible. Failing citations
    were filtered out before anything ranked them, so `worst` could not see what was already
    gone — the fix is that every citation gets an outcome and the ordering decides, not the
    filter."""
    from plumb.core.gate import NOT_PASSED, RANK

    assert NOT_PASSED in RANK["worst"] and NOT_PASSED in RANK["best"]
    assert RANK["worst"].index(NOT_PASSED) == 0, "most decisive for a decision"
    assert RANK["best"].index(NOT_PASSED) == len(RANK["best"]) - 1, "least, for a story"
    assert set(RANK["best"]) == set(RANK["worst"]), "same outcomes, different order"


@pytest.mark.proves("dev07-3-1", depth="component")
@pytest.mark.proves("dev07-5-1", depth="component")
def test_a_subject_with_several_aspects_derives_one_verdict_each_and_no_overall():
    """`dev07-4-3-ur05`. The legs close at different times for different reasons, so a single word for
    all of them is not a simplification but a loss of the finding — and the corpus shows both
    failure directions at once. A decision whose *outcome* is asserted reads fully proven while
    its *falsifier* has never been evaluated; one whose falsifier has already **fired** reads
    identically to one nobody has ever examined.

    The subject keeps no status of its own. It is held unproven rather than left blank so a
    consumer reading only that field can never be shown a green no claim earned (`dev07-5-1`).
    """
    verdict = derive("D27", Story(
        archetype="structural", aspects=("levers", "outcome", "falsifier"),
        citations=(cite(about="outcome", grounding=INERT, depth="unit"),
                   cite(about="falsifier", result=FAILED, grounding=INERT, depth="unit"))))

    assert verdict.status == UNPROVEN and "aspects.per-aspect" in verdict.conditions
    assert verdict.aspects["outcome"].status == PROVEN
    assert "evidence.failed" in verdict.aspects["falsifier"].conditions, "cited, and it fired"
    assert "evidence.none" in verdict.aspects["levers"].conditions, "nobody measured them"


@pytest.mark.proves("dev07-3-1", depth="unit")
def test_a_citation_naming_no_aspect_is_counted_nowhere_rather_than_everywhere():
    """Spreading it across the legs would let one test prove three claims it never made;
    attributing it to a guessed one would invent a fact. Counted nowhere, so every leg it might
    have served reads as the silence it actually is (`dev07-3-3`)."""
    verdict = derive("D27", Story(
        archetype="structural", aspects=("outcome", "falsifier"),
        citations=(cite(grounding=INERT, depth="unit"),)))

    assert all("evidence.none" in leg.conditions for leg in verdict.aspects.values())


@pytest.mark.proves("dev07-5-2", depth="unit")
@pytest.mark.parametrize("citations, expected", [
    ((), "evidence.none"),
    ((cite(result=FAILED),), "evidence.failed"),
    ((cite(result=SKIPPED),), "evidence.not-observed"),
])
def test_unproven_says_which_of_its_three_reasons_it_is(citations, expected):
    """One verdict, three situations, three different next moves.

    *Nothing cites this* is an absence of evidence and the correct reading of a spec written ahead
    of the work. *The citation ran and did not pass* is evidence against — the only unproven that
    is a **result** rather than a gap, and a story that read proven yesterday did not lose its
    test, its test started failing. *The citation never ran* is neither: no evidence at all.

    The third matters most where a check runs against the world rather than the repository — a
    keyserver down and a chore not done were the same word, so a recurrence count meant to nominate
    chores for automation counted third-party flakiness as broken claims. All three were sharing a
    spelling, which is `dev07-3-3`'s rule one level up: absent is not zero, twice over.
    """
    verdict = derive("s", story(*citations))

    assert verdict.status == UNPROVEN, "the verdict is the same word — the condition is not"
    assert expected in verdict.conditions


@pytest.mark.proves("dev07-4-2", depth="component")
def test_one_passing_citation_is_enough_even_beside_a_failing_one():
    """Stories are commonly cited more than once; one real proof is a proof."""
    verdict = derive("s", story(cite(result=FAILED, test="t::a"), cite(test="t::b")))
    assert verdict.status == PROVEN


@pytest.mark.proves("dev07-4-2", depth="component")
def test_the_gate_is_two_checks_in_series_and_fails_fast():
    """The second check never rescues a failure of the first: a citation that did not pass
    reads unproven even when its grounding fact is perfect."""
    assert derive("s", story(cite(result=FAILED, grounding=GROUNDED))).status == UNPROVEN
    assert derive("s", story(cite(result=SKIPPED, grounding=GROUNDED))).status == UNPROVEN
    # And a first check that passes hands over to the second rather than short-circuiting green.
    assert derive("s", story(cite(result=PASSED, grounding=UNGROUNDED))).status == UNPROVEN


@pytest.mark.proves("dev07-4-3", depth="component")
def test_the_status_vocabulary_is_exactly_three_values():
    assert derive("s", story(cite(grounding=GROUNDED))).status == PROVEN
    assert derive("s", story(cite(grounding=UNGROUNDED))).status == UNPROVEN
    assert derive("s", story(cite(grounding=NOT_CHECKED))).status == PASSED_WIRING_NOT_VERIFIED


@pytest.mark.proves("dev07-4-3", depth="component")
def test_status_is_derived_live_and_never_stored():
    """The same story, two runs, two answers — because the run changed, not a record."""
    green = Manifest(stories={"s": story(cite(result=PASSED))})
    red = Manifest(stories={"s": story(cite(result=FAILED))})
    assert derive_all(green)["s"].status == PROVEN
    assert derive_all(red)["s"].status == UNPROVEN, "a proof that fails un-proves its story"


@pytest.mark.proves("dev07-1-4", depth="component")
def test_no_entry_points_is_surfaced_with_its_code_never_silently_skipped():
    verdict = derive("s", story(cite(grounding=NOT_CHECKED)))
    assert verdict.status == PASSED_WIRING_NOT_VERIFIED
    assert NO_ENTRY_POINTS in verdict.conditions, "degrade and surface, never skip"


@pytest.mark.proves("dev07-1-4", depth="unit")
def test_a_grounded_story_surfaces_no_condition():
    assert derive("s", story(cite(grounding=GROUNDED))).conditions == ()


@pytest.mark.proves("dev07-5-1", depth="component")
def test_the_graph_runs_at_the_lowest_input_level_and_still_reports():
    """Markers alone, nothing declared: a real board, and not a failure."""
    manifest = Manifest(stories={
        "a": story(cite(grounding=NOT_CHECKED)),
        "b": story(cite(result=SKIPPED, grounding=NOT_CHECKED)),
    })
    verdicts = derive_all(manifest)
    assert verdicts["a"].status == PASSED_WIRING_NOT_VERIFIED
    assert verdicts["b"].status == UNPROVEN


@pytest.mark.proves("dev07-4-2", depth="component")
def test_the_structural_branch_handles_every_grounding_fact():
    """The bug this framework shipped once: a branch with no arm for one of the four facts.

    Note `not-checked` fails a structural story rather than partially passing it — it means
    production code *did* run, which is not what inspecting a shape looks like.
    """
    outcomes = {
        g: derive("s", story(cite(grounding=g), archetype=STRUCTURAL)).status
        for g in (GROUNDED, UNGROUNDED, INERT, NOT_CHECKED)
    }
    assert outcomes == {
        INERT: PROVEN,
        GROUNDED: UNPROVEN,
        UNGROUNDED: UNPROVEN,
        NOT_CHECKED: UNPROVEN,
    }


@pytest.mark.proves("dev07-4-3", depth="component")
def test_the_achieved_vector_reports_only_rungs_that_actually_passed():
    verdict = derive("s", story(
        cite(depth="unit", test="t::a"),
        cite(depth="wiring", test="t::b"),
        cite(depth="smoke", test="t::c", result=FAILED),
    ))
    assert verdict.achieved == ("unit", "wiring"), "a failing citation contributes no rung"


@pytest.mark.proves("dev07-3-1", depth="component")
def test_the_manifest_carries_no_verdict_for_the_gate_to_read():
    """Facts in, verdict out — an adapter cannot grant or revoke a status.

    The old form blacklisted three field names and passed when `done: bool = True` was added to
    Citation. This asserts the property instead: whatever an adapter writes, the verdict is a
    function of the gate's own rules, and no manifest field short-circuits them.
    """
    from plumb.core.gate import PROVEN as GATE_PROVEN

    # Every field an adapter can author, set to whatever it likes.
    authored = Citation(test="t::a", depth="wiring", result=SKIPPED, grounding=GROUNDED,
                        ref="LOOKS-DONE")
    assert derive("s", Story(citations=(authored,))).status == UNPROVEN, (
        "a skipped test cannot be talked into PROVEN by any other field an adapter controls"
    )
    # And the verdict vocabulary lives only in the gate: no manifest type can express one.
    for owner in (Citation, Story, Manifest):
        assert not {f.lower() for f in owner.__dataclass_fields__} & {
            "status", "proven", "verdict", "done", "complete"
        }, f"{owner.__name__} gained a field an adapter could stamp a verdict into"
