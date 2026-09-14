"""The per-test trace, proved against a real traced run (``dev07-1-3``).

Every test here drives the real tracer over the sample project — no fake trace, no
reimplemented call tree. The last two are the cases that reading the spec did not surface:
a test that touches nothing, and the same test giving different answers on run order.
"""

import ast
import inspect
from pathlib import Path

import pytest

from plumb.adapters.python.surface import ProductionSurface
from plumb.adapters.python.trace import trace_call, tracing

SAMPLE = Path(__file__).parent / "sample_project"


@pytest.fixture
def surface():
    return ProductionSurface.of(SAMPLE, entry_points=("sample_project:handle_request",))


@pytest.fixture
def blind_surface():
    """A project that declared no entry points — the `not-checked` condition (``dev07-1-4``)."""
    return ProductionSurface.of(SAMPLE)


@pytest.mark.proves("dev07-1-3", depth="component")
def test_trace_records_production_frames_in_call_order(surface):
    import sample_project

    trace = trace_call(surface, lambda: sample_project.handle_request(3))

    assert trace.executed == (
        "sample_project:handle_request",
        "sample_project:_double",
    )


@pytest.mark.proves("dev07-1-3", depth="component")
def test_trace_ignores_code_outside_the_production_surface(surface):
    def only_test_code():
        return sorted({"b": 2, "a": 1})

    trace = trace_call(surface, only_test_code)

    assert trace.executed == ()
    assert trace.touched_nothing


@pytest.mark.proves("dev07-1-4", depth="component")
def test_execution_under_a_declared_entry_point_is_distinguishable(surface):
    import sample_project

    grounded = trace_call(surface, lambda: sample_project.handle_request(3))
    orphaned = trace_call(surface, lambda: sample_project.orphan(3))

    assert grounded.ran_under_entry_point
    assert not orphaned.ran_under_entry_point
    assert orphaned.executed == ("sample_project:orphan",)


@pytest.mark.proves("dev07-1-4", depth="component")
def test_without_declared_entry_points_nothing_can_ground(blind_surface):
    import sample_project

    trace = trace_call(blind_surface, lambda: sample_project.handle_request(3))

    assert trace.executed  # production code certainly ran
    assert not trace.ran_under_entry_point
    assert not blind_surface.declares_entry_points  # ...but the question was unanswerable


@pytest.mark.proves("dev07-1-3", depth="component")
def test_reading_the_artifact_as_data_is_observed_without_executing_it(surface):
    def structural_rule():
        source = (SAMPLE / "__init__.py").read_text()
        names = [n.name for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef)]
        assert "handle_request" in names

    trace = trace_call(surface, structural_rule)

    assert trace.reads, "an inspecting rule must be visibly distinct from one that touched nothing"
    assert trace.executed == ()
    assert not trace.touched_nothing


@pytest.mark.proves("dev07-1-4", depth="component")
def test_a_test_that_touches_nothing_is_visible_as_such(surface):
    """The `assert True` fake. Today's spec calls this `inert` and lets it prove a
    structural story; the trace at least makes the emptiness observable."""
    trace = trace_call(surface, lambda: None)

    assert trace.touched_nothing
    assert trace.executed == ()
    assert trace.reads == ()


@pytest.mark.proves("dev07-1-3", depth="component")
def test_the_tracer_restores_whatever_tracing_was_already_in_place(surface):
    import sys

    def other_tracer(frame, event, arg):
        return other_tracer

    sys.settrace(other_tracer)
    try:
        with tracing(surface):
            pass
        assert sys.gettrace() is other_tracer
    finally:
        sys.settrace(None)


def test_inspecting_by_import_gives_a_different_answer_on_run_order(surface, tmp_path):
    """NOT a `proves` citation — this documents the defect filed in the friction log:
    the fact is order-dependent, so `dev07-1-4`'s "per-test fact" does not hold for a rule
    that inspects by importing. Kept as an executable record of why a structural rule
    must read the artifact rather than import it."""
    import subprocess
    import sys
    import textwrap

    script = textwrap.dedent(f"""
        import sys
        sys.path[:0] = [{str(Path(__file__).parent.parent / "src")!r}, {str(SAMPLE.parent)!r}]
        from plumb.adapters.python.surface import ProductionSurface
        from plumb.adapters.python.trace import trace_call

        surface = ProductionSurface.of({str(SAMPLE)!r})

        def inspect_by_import():
            import sample_project
            assert hasattr(sample_project, "handle_request")

        cold = trace_call(surface, inspect_by_import)
        warm = trace_call(surface, inspect_by_import)
        print(len(cold.executed), len(warm.executed))
    """)
    out = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    ).stdout.split()

    cold_frames, warm_frames = int(out[0]), int(out[1])
    assert cold_frames > 0, "the first import executes module-level production code"
    assert warm_frames == 0, "the second import is a sys.modules hit and touches nothing"


@pytest.mark.proves("dev07-1-4", depth="component")
@pytest.mark.proves("dev07-1-4", depth="component")
def test_a_per_thread_tracer_may_not_claim_inert_while_threads_are_unaccounted_for(surface):
    """The test that would have caught it, and did not exist.

    Every other case here hands `fact()` a `Trace` built by hand, so the tracer's own blind spot
    was invisible: the fixtures encoded the same assumption the code did. This one dispatches for
    real. Before `dev07-1-4` gained its precondition it reported `inert` — which is the *positive
    proof a structural story needs* — so a test that ran production code on a pool thread could
    prove a structural story. A false PROVEN, in the shipped adapter.
    """
    import sys
    from concurrent.futures import ThreadPoolExecutor

    sys.path.insert(0, str(SAMPLE.parent))
    import sample_project

    from plumb.adapters.python.grounding import fact
    from plumb.core.manifest import DISPATCHED, INERT

    pool = ThreadPoolExecutor(1)
    try:
        pool.submit(lambda: None).result()      # pre-existing, as every real pool is
        with tracing(surface) as recorder:
            pool.submit(sample_project.handle_request, 1).result()
        observed = fact(recorder.sealed(), surface)
    finally:
        pool.shutdown()

    assert observed != INERT, "the entry point ran; claiming nothing ran is the fake, inverted"
    assert observed == DISPATCHED, "say what happened: it left for a thread we could not follow"


@pytest.mark.proves("dev07-1-4", depth="component")
def test_inert_survives_when_there_is_nothing_to_account_for(surface):
    """The degrade must not swallow the honest case, or structural stories become unprovable."""
    from plumb.adapters.python.grounding import fact
    from plumb.core.manifest import INERT

    with tracing(surface) as recorder:
        (SAMPLE / "__init__.py").read_text()     # read the artifact, never run it
    assert fact(recorder.sealed(), surface) == INERT


@pytest.mark.proves("dev07-1-3", depth="component")
def test_a_production_root_may_be_a_single_file(tmp_path):
    """A project whose tests sit beside its code has to declare **files**, because declaring the
    directory puts the tests inside a production root — and then every test frame counts as
    production, so a structural story can never read `inert` and the archetype loses what it
    discriminates on. That is a legitimate declaration and the tracer used to die on it.

    The failure was not a crash anybody saw as a crash: a frame in the root itself made
    `relative_to` yield `.`, whose empty stem raises, so *every test touching that file failed*.
    On the board that reads as evidence which failed — a breach — rather than a tool that fell
    over. It was found dogfooding, and it had made an entire chore's stories unprovable.
    """
    module = tmp_path / "friction_api.py"
    module.write_text("def main():\n    return handled()\n\n\ndef handled():\n    return 'ok'\n")
    surface = ProductionSurface.of(module, entry_points=("friction_api:main",))

    import importlib.util
    spec = importlib.util.spec_from_file_location("friction_api", module)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)

    with tracing(surface) as recorder:
        loaded.main()
    seen = recorder.sealed()

    assert seen.executed == ("friction_api:main", "friction_api:handled"), \
        "a file-root qualifies by its stem — the form `entry_points` already uses"
    assert seen.ran_under_entry_point, "and the entry point in that file is recognised as one"
    assert surface.locate("friction_api:main") == module, "and qualify runs backwards"


@pytest.mark.proves("dev07-1-4", depth="component")
def test_the_trace_names_the_outermost_door_and_not_the_one_reached_on_the_way():
    """`dev07-1-4`: which door, where `dev07-1-4` carries only whether.

    `entry_points` is one flat project-wide set, so a door declared for one subject is open to
    every subject. The discriminating case is a project that declares an inner door for its own
    reasons: a test entering at the front must still read as having come in the front, or every
    new declaration silently rewrites the fact for tests that did not change.
    """
    import sample_project

    both = ProductionSurface.of(
        SAMPLE, entry_points=("sample_project:handle_request", "sample_project:_double"))

    front = trace_call(both, lambda: sample_project.handle_request(3))
    side = trace_call(both, lambda: sample_project._double(3))

    # It went through _double, which is itself a declared door — and still came in the front.
    assert front.entered_through == ("sample_project:handle_request",)
    assert "sample_project:_double" in front.executed_under_entry
    # Entered from outside every window, so the inner door is the arrival here.
    assert side.entered_through == ("sample_project:_double",)
    # Both ground. The bool cannot tell these apart, which is the whole reason for the field.
    assert front.ran_under_entry_point and side.ran_under_entry_point


@pytest.mark.proves("dev07-1-4", depth="component")
def test_a_test_driving_two_entrances_names_both_and_one_that_grounds_by_none_names_none(surface):
    """Ordinarily one door. A test that drives two says so rather than picking, and a test that
    reached none reports an empty set — which is *entered by none*, not *not reported*."""
    import sample_project

    two = ProductionSurface.of(
        SAMPLE, entry_points=("sample_project:handle_request", "sample_project:orphan"))

    def drive_both():
        sample_project.handle_request(3)
        sample_project.orphan(3)

    assert trace_call(two, drive_both).entered_through == (
        "sample_project:handle_request", "sample_project:orphan")
    assert trace_call(surface, lambda: sample_project.orphan(3)).entered_through == ()
