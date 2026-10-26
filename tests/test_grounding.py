"""Grounding: did the citing test drive the real system? (chapter 3)"""

from pathlib import Path

import pytest

from plumb.core.gate import PROVEN, UNPROVEN, derive
from plumb.adapters.python.grounding import fact
from plumb.core.gate import contradicts_claimed_depth
from plumb.core.manifest import (
    GROUNDED,
    INERT,
    NOT_CHECKED,
    PASSED,
    STRUCTURAL,
    UNGROUNDED,
    UNTOUCHED,
    Citation,
    Story,
)
from plumb.adapters.python.surface import ProductionSurface
from plumb.config import Config
from plumb.adapters.python.trace import Trace, tracing


def traced(executed=(), reads=(), under_entry=False) -> Trace:
    return Trace(executed=tuple(executed), reads=tuple(reads), ran_under_entry_point=under_entry)


WIRED = ProductionSurface.of("src", entry_points=("plumb.cli:main",))
SAMPLE = Path(__file__).resolve().parent / "sample_project"
WIRED_SAMPLE = ProductionSurface.of(SAMPLE, entry_points=("sample_project:handle_request",))
BARE = ProductionSurface.of("src")


@pytest.mark.proves("dev07-1-4", depth="component")
def test_every_value_the_fact_can_take_is_derived_from_the_trace():
    assert fact(traced(["m:f"], under_entry=True), WIRED) == GROUNDED
    assert fact(traced(["m:f"]), WIRED) == UNGROUNDED
    assert fact(traced(reads=["mod.py"]), WIRED) == INERT
    assert fact(traced(["m:f"]), BARE) == NOT_CHECKED
    # The value that used to hide inside `inert`. Ran nothing **and** read nothing, which is what
    # `assert True` does — an absence `dev07-4-2` was accepting as proof of inspection.
    assert fact(traced(), WIRED) == UNTOUCHED


@pytest.mark.proves("dev07-1-4", depth="component")
def test_inertness_is_asked_first_because_it_needs_no_entry_points():
    """A project whose spec is entirely structural declares no surface and must still get a
    real fact rather than not-checked."""
    assert fact(traced(reads=["mod.py"]), BARE) == INERT, "no entry points, and still a real answer"
    assert fact(traced(reads=["mod.py"]), BARE) == INERT, "reading is not running"


@pytest.mark.proves("dev07-1-4", depth="unit")
def test_inert_needs_roots_not_merely_the_absence_of_entry_points():
    """With no production roots declared, no frame is ever recognised as ours, so an empty call
    tree means "nobody said what production code is" — not "the test ran none". Reporting inert
    here would hand every structural story a free pass on a project that declared nothing."""
    nothing = ProductionSurface.of()
    assert not nothing.declares_production_code
    assert fact(traced(reads=["mod.py"]), nothing) == NOT_CHECKED
    assert fact(traced(["m:f"]), nothing) == NOT_CHECKED
    # ...and with roots but no entry points, inert is a real answer again.
    assert fact(traced(reads=["mod.py"]), BARE) == INERT


@pytest.mark.proves("dev07-1-4", depth="component")
def test_orphaned_code_cannot_ground():
    """Code reachable from no entry point never runs under one, so a passing test over it
    never reads as done — the orphaned-'done' fake, caught by the mechanism."""
    orphan = traced(["plumb.dead:helper"], under_entry=False)
    assert fact(orphan, WIRED) == UNGROUNDED
    story = Story(citations=(Citation(test="t::a", depth="wiring", result=PASSED,
                                      grounding=fact(orphan, WIRED)),))
    assert derive("s", story).status == UNPROVEN


@pytest.mark.proves("dev07-4-2", depth="component")
def test_grounding_cross_checks_a_claimed_wired_rung():
    """A test claiming it reached the wired system, whose execution never grounded, is lying
    about its depth. A unit claim makes no such assertion and is never contradicted."""
    assert contradicts_claimed_depth("wiring", UNGROUNDED)
    assert contradicts_claimed_depth("standards-integration", INERT)
    assert not contradicts_claimed_depth("wiring", GROUNDED)
    assert not contradicts_claimed_depth("unit", UNGROUNDED), "isolation is the point of a unit"
    assert not contradicts_claimed_depth("component", UNGROUNDED)


@pytest.mark.proves("dev07-4-2", depth="component")
def test_the_depth_cross_check_actually_runs_in_the_gate():
    """The function was right for a day and called by nothing — it sat in the adapter, which the
    core may not import, so the only caller that could have used it was blocked by the seam.
    This asserts the pipeline, not the predicate."""
    from plumb.core.gate import DEPTH_UNSUPPORTED

    lying = Story(citations=(Citation(test="t::a", depth="wiring", result=PASSED,
                                      grounding=UNGROUNDED),))
    assert DEPTH_UNSUPPORTED in derive("s", lying).conditions, "the board must say it"

    honest = Story(citations=(Citation(test="t::b", depth="unit", result=PASSED,
                                       grounding=UNGROUNDED),))
    assert DEPTH_UNSUPPORTED not in derive("s", honest).conditions, "a unit claim reaches nothing by design"

    # And it survives the story being proven by some *other* citation.
    mixed = Story(citations=(
        Citation(test="t::c", depth="wiring", result=PASSED, grounding=GROUNDED),
        Citation(test="t::d", depth="smoke", result=PASSED, grounding=UNGROUNDED),
    ))
    verdict = derive("s", mixed)
    assert verdict.status == PROVEN and DEPTH_UNSUPPORTED in verdict.conditions


@pytest.mark.proves("dev07-4-2", depth="unit")
def test_a_not_checked_fact_contradicts_nothing():
    """With no entry points there is no evidence either way, so nothing is refuted."""
    assert not contradicts_claimed_depth("wiring", NOT_CHECKED)


@pytest.mark.proves("dev07-4-2", depth="component")
def test_a_behavioral_story_needs_a_citing_test_that_grounds():
    def cited(grounding):
        return Story(citations=(Citation(test="t::a", depth="wiring", result=PASSED,
                                         grounding=grounding),))

    assert derive("s", cited(GROUNDED)).status == PROVEN
    assert derive("s", cited(UNGROUNDED)).status == UNPROVEN
    assert derive("s", cited(INERT)).status == UNPROVEN, "running no production code proves no behaviour"


@pytest.mark.proves("dev07-4-2", depth="component")
def test_one_execution_yields_one_fact_so_no_test_serves_both_archetypes():
    """The split is enforced by the mechanism: a single execution cannot be both grounded and
    inert, so a test citing a behavioral and a structural story fails the side it did not serve.
    """
    citation = Citation(test="t::a", depth="wiring", result=PASSED, grounding=GROUNDED)
    behavioral = Story(citations=(citation,))
    structural = Story(archetype=STRUCTURAL, citations=(citation,))

    assert derive("b", behavioral).status == PROVEN
    assert derive("s", structural).status == UNPROVEN, "grounded is exactly what structural must not be"

    inert_citation = Citation(test="t::b", depth="unit", result=PASSED, grounding=INERT)
    assert derive("b", Story(citations=(inert_citation,))).status == UNPROVEN
    assert derive("s", Story(archetype=STRUCTURAL, citations=(inert_citation,))).status == PROVEN


@pytest.mark.proves("dev07-4-2", depth="component")
def test_the_gate_needs_grounding_and_never_mutation():
    """Grounding is on the critical path; mutation is beside it and never blocks (dev07-2-2)."""
    unfilled = Citation(test="t::a", depth="wiring", result=PASSED, grounding=GROUNDED)
    assert Story(citations=(unfilled,)).mutation is None
    assert derive("s", Story(citations=(unfilled,))).status == PROVEN, "a story proves with mutation off"

    survived = Citation(test="t::b", depth="wiring", result=PASSED,
                        grounding=GROUNDED)
    assert derive("s", Story(citations=(survived,))).status == PROVEN, "a survivor is advisory, never a gate"


@pytest.mark.proves("dev07-1-3", depth="component")
def test_a_project_declares_its_surface_in_config_not_in_its_source(tmp_path):
    """Config rather than a decorator: a decorator would make production code import the
    verifier, so the artifact would carry a dependency on the thing judging it."""
    (tmp_path / "plumb.toml").write_text(
        'production = ["src/app"]\nentry_points = ["app.cli:main", "app.api:handle"]\n'
    )
    surface = ProductionSurface.from_config(Config.find(tmp_path))
    assert surface.declares_entry_points
    assert surface.entry_points == frozenset({"app.cli:main", "app.api:handle"})
    assert surface.roots == (Path(tmp_path / "src/app").resolve(),)


@pytest.mark.proves("dev07-1-3", depth="unit")
@pytest.mark.proves("dev07-5-1", depth="unit")
def test_a_project_that_declares_nothing_degrades_rather_than_erroring(tmp_path):
    absent = ProductionSurface.from_config(Config.find(tmp_path))
    assert not absent.declares_entry_points
    (tmp_path / "plumb.toml").write_text("adapter = \"python\"\n")
    assert not ProductionSurface.from_config(Config.find(tmp_path)).declares_entry_points


@pytest.mark.proves("dev07-4-2", depth="component")
def test_the_archetype_is_per_subject_and_defaults_to_behavioral():
    """Declared in the project's config, never on the test — the thing being judged does not
    choose its own gate — and never inferred, which would make it guesswork."""
    from plumb.adapters.python import archetypes
    from plumb.core.manifest import BEHAVIORAL, InvalidManifest

    before = archetypes.declared()
    try:
        archetypes.reset()
        assert archetypes.archetype_of("never-mentioned") == BEHAVIORAL, "silence is a complete answer"

        archetypes.declare("s-1", STRUCTURAL)
        archetypes.declare("s-2")
        assert archetypes.archetype_of("s-1") == STRUCTURAL
        assert archetypes.archetype_of("s-2") == BEHAVIORAL

        with pytest.raises(InvalidManifest):
            archetypes.declare("s-3", "non-functional")
    finally:
        archetypes.reset()
        for sid, kind in before.items():
            archetypes.declare(sid, kind)


@pytest.mark.proves("dev07-4-2", depth="unit")
def test_an_archetype_selects_a_check_and_can_never_grant_a_pass():
    """A story declared structural cannot be proved by executing anything, so mis-declaring one
    costs its author the behavioral proof rather than buying a free pass (dev07-4-2)."""
    grounded = Citation(test="t::a", depth="wiring", result=PASSED, grounding=GROUNDED)
    assert derive("s", Story(archetype=STRUCTURAL, citations=(grounded,))).status == UNPROVEN


@pytest.mark.proves("dev07-1-4", depth="component")
def test_dispatched_is_not_a_weaker_not_checked():
    """One means the question could not be asked; the other that it was asked and the answer
    walked away. Same verdict, and the reader's next move is different."""
    from plumb.core.gate import NO_ENTRY_POINTS, WORK_DISPATCHED
    from plumb.core.manifest import DISPATCHED

    def cited(grounding):
        return Story(citations=(Citation(test="t::a", depth="wiring", result=PASSED,
                                         grounding=grounding),))

    lost = derive("s", cited(DISPATCHED))
    unasked = derive("s", cited(NOT_CHECKED))

    assert lost.status == unasked.status, "neither is a failure and neither is a pass"
    assert lost.conditions == (WORK_DISPATCHED,)
    assert unasked.conditions == (NO_ENTRY_POINTS,)
    assert lost.conditions != unasked.conditions, (
        "telling a project that already declared its entry points to declare them sends them "
        "looking in the wrong place"
    )


@pytest.mark.proves("dev07-1-4", depth="component")
def test_a_story_lost_two_different_ways_reports_both_reasons():
    from plumb.core.gate import NO_ENTRY_POINTS, WORK_DISPATCHED
    from plumb.core.manifest import DISPATCHED

    verdict = derive("s", Story(citations=(
        Citation(test="t::a", depth="wiring", result=PASSED, grounding=DISPATCHED),
        Citation(test="t::b", depth="unit", result=PASSED, grounding=NOT_CHECKED),
    )))
    assert set(verdict.conditions) == {WORK_DISPATCHED, NO_ENTRY_POINTS}


@pytest.mark.proves("dev07-4-2", depth="unit")
def test_dispatched_fails_a_structural_story_like_every_other_executing_fact():
    """Four of the five facts mean production code ran, so only `inert` proves a structural
    story — `dispatched` is production code that ran and then handed some work away."""
    from plumb.core.manifest import DISPATCHED

    citation = Citation(test="t::a", depth="unit", result=PASSED, grounding=DISPATCHED)
    assert derive("s", Story(archetype=STRUCTURAL, citations=(citation,))).status == UNPROVEN


@pytest.mark.proves("dev07-1-4", depth="component")
def test_a_coarse_dispatch_signal_never_weakens_the_orphan_check():
    """The asymmetry between the two branches is deliberate, and pinned so it stays deliberate.

    `inert` withholds when threads are unaccounted for, because it is a positive proof and a
    wrong one grants a pass. `ungrounded` does not, because this adapter's evidence is only
    "some other thread was alive" — applied there, any process with a background thread could
    never report `ungrounded`, and that is `dev07-1-4`, the orphan check the whole tool is for.
    """
    from plumb.core.manifest import UNGROUNDED as UG

    ran_but_not_under_entry = Trace(executed=("app:orphan",), reads=(),
                                    ran_under_entry_point=False,
                                    accounted_for_all_threads=False)
    assert fact(ran_but_not_under_entry, WIRED) == UG, (
        "withholding here would cost the orphaned-done check, which is the headline claim"
    )
    saw_nothing = Trace(executed=(), reads=(), ran_under_entry_point=False,
                        accounted_for_all_threads=False)
    assert fact(saw_nothing, WIRED) != INERT, "a positive proof must withhold on partial evidence"


@pytest.mark.proves("dev07-1-4", depth="component")
def test_a_test_that_grounds_and_also_reaches_orphaned_code_says_so():
    """`dev07-1-4`'s stated limit, made visible.

    Grounding is a property of the whole test (`dev07-1-4`), so a test that drives an entry point
    and then calls unreachable code still grounds — and closing that would need the story→code
    map `dev07-1-4` refuses to keep. What is available is the observation, and this is it.
    """
    from plumb.core.gate import REACHED_OUTSIDE

    mixed = Story(citations=(Citation(test="t::a", depth="wiring", result=PASSED,
                                      grounding=GROUNDED, reached_outside_entry=True),))
    verdict = derive("s", mixed)
    assert verdict.status == PROVEN, "it did ground; the status is not the thing in question"
    assert REACHED_OUTSIDE in verdict.conditions, "and the board must not let that pass silently"

    clean = Story(citations=(Citation(test="t::b", depth="wiring", result=PASSED,
                                      grounding=GROUNDED, reached_outside_entry=False),))
    assert REACHED_OUTSIDE not in derive("s", clean).conditions

    # Not reported is not the same as reported-false: an adapter that cannot see this says nothing.
    silent = Story(citations=(Citation(test="t::c", depth="wiring", result=PASSED,
                                       grounding=GROUNDED),))
    assert silent.citations[0].reached_outside_entry is None
    assert REACHED_OUTSIDE not in derive("s", silent).conditions


@pytest.mark.proves("dev07-1-4", depth="component")
def test_the_tracer_tells_a_mixed_test_from_a_clean_one():
    """End of the same claim, against the real tracer rather than a hand-built fact."""
    import sys
    sys.path.insert(0, str(SAMPLE.parent))
    import sample_project

    def traced_run(body):
        with tracing(WIRED_SAMPLE) as recorder:
            body()
        return recorder.sealed()

    assert not traced_run(lambda: sample_project.handle_request(1)).ran_outside_entry_point
    assert traced_run(lambda: sample_project.orphan(3)).ran_outside_entry_point
    mixed = traced_run(lambda: (sample_project.handle_request(1), sample_project.orphan(3)))
    assert mixed.ran_under_entry_point and mixed.ran_outside_entry_point, (
        "grounded on the first call, and outside on the second — the case dev07-1-4 concedes"
    )


@pytest.mark.proves("dev07-4-2", depth="component")
def test_the_cheapest_thing_that_passes_a_structural_claim_is_not_assert_true():
    """The fake the whole framework exists to catch, which the framework shipped.

    `dev07-4-2` asks for a test that *read the artifact rather than ran it* — a mirror of a presence,
    which has to be another presence. The check was only the second half: `inert` meant *no
    production frames*, and `assert True` produces none. Probed and confirmed on a fresh project —
    an empty test read as `inert` and proved a structural story.

    Written as *what is the cheapest thing that passes this?* rather than *does it catch the case I
    had in mind?*, because validating the check against the fake it was designed for and never
    against a test that does nothing is exactly how it survived.
    """
    from plumb.core.gate import CITATION_UNTOUCHED, PROVEN, UNPROVEN, derive

    def structural(grounding):
        return Story(archetype="structural",
                     citations=(Citation(test="t::a", depth="unit", result=PASSED,
                                         grounding=grounding),))

    empty = fact(traced(), WIRED)
    assert empty == UNTOUCHED, "ran nothing and read nothing"

    verdict = derive("S-1", structural(empty))
    assert verdict.status == UNPROVEN, "`assert True` proves no structural story"
    assert CITATION_UNTOUCHED in verdict.conditions, (
        "and is told it touched nothing — not that it executed production code, which is the "
        "opposite mistake and would send somebody to delete something that is not there")

    # The real one still proves: read the artifact, ran none of it.
    inspected = fact(traced(reads=["orders/__init__.py"]), WIRED)
    assert inspected == INERT
    assert derive("S-1", structural(inspected)).status == PROVEN


@pytest.mark.proves("dev07-4-2", depth="component")
def test_a_behavioural_story_gets_no_partial_credit_for_touching_nothing():
    """`not-checked` and `dispatched` are questions that could not be answered, and carry partial
    credit for that reason. This is an answer — the test did nothing to the artifact — and it is
    the weakest evidence there is."""
    from plumb.core.gate import PASSED_WIRING_NOT_VERIFIED, UNPROVEN, derive

    story = Story(citations=(Citation(test="t::a", depth="unit", result=PASSED,
                                      grounding=UNTOUCHED),))
    verdict = derive("S-1", story)

    assert verdict.status == UNPROVEN
    assert verdict.status != PASSED_WIRING_NOT_VERIFIED


@pytest.mark.proves("dev07-4-2", depth="component")
def test_an_inspect_by_import_structural_test_cannot_prove_in_either_order():
    """A fact that depends on execution order is not a fact (`dev07-1-4`).

    Probed and confirmed on a real project: the same inspect-by-import test reads `ungrounded` cold
    — the first import runs module-level code, so a production frame appears — and `untouched` warm,
    because the second import is a `sys.modules` hit that touches nothing observable. Same test,
    same assertions, and under a randomised or sharded run the story flipped between PROVEN and
    UNPROVEN with no change to the code.

    `dev07-4-2` closes it from the other end rather than with a cleverer tracer: `inert` is the
    positive claim, so an import-based structural test is unprovable in **either** order. The two
    runs still report different *facts*, which is honest — it is what each one saw — and the verdict
    no longer moves.
    """
    from plumb.core.gate import UNPROVEN, derive

    def structural(grounding):
        return Story(archetype="structural",
                     citations=(Citation(test="t::a", depth="unit", result=PASSED,
                                         grounding=grounding),))

    cold = fact(traced(["orders:<module>"]), WIRED)
    warm = fact(traced(), WIRED)

    assert cold != warm, "the facts differ, because what the two runs saw differs"
    assert derive("ORD-S", structural(cold)).status == UNPROVEN
    assert derive("ORD-S", structural(warm)).status == UNPROVEN, (
        "and the verdict does not, which is the whole of what determinism needed here")


@pytest.mark.proves("dev07-4-2", depth="component")
def test_a_structural_test_may_read_its_artifact_in_a_fixture(tmp_path):
    """A fixture is where a suite naturally puts the read — one file, shared by every test in the
    module — and the call-phase trace cannot see it by construction.

    Once `inert` became the positive claim *the artifact was read*, that made a whole shape of
    honest structural test unprovable. Measured on this project's sibling repository: seven
    structural stories went unproven with no change to their tests, and `scope="module"` made it
    worse — the file is opened once, so only whichever test ran first could ever prove.

    Run rather than reasoned about: this drives a real pytest session, because the thing under test
    is *which window the read lands in* and a test that recomputed the join would agree with itself.
    """
    from plumb.adapters.python.adapter import collect

    production = tmp_path / "app"
    production.mkdir()
    (production / "__init__.py").write_text("RULES = 'x'\n")
    suite = tmp_path / "tests"
    suite.mkdir()
    (suite / "test_shape.py").write_text(
        "import pathlib\n"
        "import pytest\n"
        f"SOURCE = pathlib.Path({str(production / '__init__.py')!r})\n"
        "@pytest.fixture(scope='module')\n"
        "def source():\n"
        "    return SOURCE.read_text()\n"
        "@pytest.mark.proves('S-1', depth='unit')\n"
        "def test_first(source):\n"
        "    assert 'RULES' in source\n"
        "@pytest.mark.proves('S-2', depth='unit')\n"
        "def test_second(source):\n"
        "    assert 'RULES' in source\n")

    manifest = collect([str(suite), "-p", "no:cacheprovider", "-q"],
                       surface=ProductionSurface.of(production))

    facts = {sid: [c.grounding for c in story.citations]
             for sid, story in manifest.stories.items()}
    assert facts == {"S-1": [INERT], "S-2": [INERT]}, (
        f"a module-scoped fixture opens the file once, so without attributing its read to whoever "
        f"asked for it only the first test can prove: {facts}")


@pytest.mark.proves("dev07-4-3", depth="unit")
def test_a_failed_citation_is_never_hidden_behind_another_reason():
    """`dev07-4-3-ur12` — a wired test failed and a unit test passed. The story is unproven for
    both reasons, and the board says both: told only that nothing reached the wired system, a
    reader goes looking for a missing entry point while a test is red."""
    from plumb.core.gate import EVIDENCE_FAILED, NOT_WIRED
    from plumb.core.manifest import FAILED

    story = Story(citations=(
        Citation(test="t::wired", depth="wiring", result=FAILED, grounding=GROUNDED),
        Citation(test="t::unit", depth="unit", result=PASSED, grounding=UNGROUNDED),
    ))
    verdict = derive("s", story)
    assert verdict.status == UNPROVEN
    assert EVIDENCE_FAILED in verdict.conditions and NOT_WIRED in verdict.conditions, \
        verdict.conditions


@pytest.mark.proves("dev07-4-3", depth="unit")
def test_a_refuted_rung_is_not_achieved():
    """`dev07-4-3-ur04` — `achieved` is the rungs actually reached. A wiring claim the run refuted
    is surfaced as `depth.unsupported` and is not reported as reached as well."""
    lying = Story(citations=(
        Citation(test="t::a", depth="wiring", result=PASSED, grounding=UNGROUNDED),
        Citation(test="t::b", depth="unit", result=PASSED, grounding=UNGROUNDED),
    ))
    assert derive("s", lying).achieved == ("unit",)
