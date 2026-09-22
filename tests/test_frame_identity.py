"""A name a trace records is a path of source definitions (``dev07-1-3``).

The names must not depend on which runtime observed them, because a series compares runs made
over months and a runtime upgrade happens inside that. Testing *two runtimes agree* needs two
runtimes; testing the property that makes them agree needs one. That property is this: **no
observed name carries a segment a runtime invented.** A comprehension, a lambda and a generator
expression are expressions inside a definition — a runtime may give them a frame or not, and
CPython has done both — so a name that mentions one is a name that moves when the runtime does.

``<locals>`` is not invented: it is how a qualified name spells a definition nested in another,
and the definition either side of it is declared in the source.
"""

import pytest

from plumb.adapters.python.surface import ProductionSurface
from plumb.adapters.python.trace import trace_call

SHAPES = __import__("pathlib").Path(__file__).parent / "sample_shapes"

#: Segments a runtime makes up. A name holding one of these is a name another runtime may spell
#: differently, or not produce at all.
INVENTED = ("<lambda>", "<listcomp>", "<setcomp>", "<dictcomp>", "<genexpr>")

#: What `sample_shapes.handle` declares and runs, and the whole of what a trace of it should name.
DECLARED = {
    "sample_shapes:handle",
    "sample_shapes:Work.__init__",
    "sample_shapes:Work.run",
    "sample_shapes:Work.run.<locals>.helper",
}


@pytest.fixture
def shapes():
    return ProductionSurface.of(SHAPES, entry_points=("sample_shapes:handle",))


def _observed(surface):
    import sample_shapes

    return trace_call(surface, lambda: sample_shapes.handle(3))


@pytest.mark.proves("dev07-1-3", depth="component")
def test_no_observed_name_carries_a_segment_the_runtime_invented(shapes):
    """The steadiness property itself, checkable on one runtime."""
    trace = _observed(shapes)

    offending = [name for name in trace.executed
                 if any(segment in name for segment in INVENTED)]

    assert not offending, (
        "these names move with the runtime that observed them: "
        f"{offending} — a frame is named for the definition containing it (dev07-1-3-ur09)")


@pytest.mark.proves("dev07-1-3", depth="component")
def test_the_names_observed_are_exactly_the_definitions_declared(shapes):
    """The other half: folding must not lose a definition that really ran."""
    trace = _observed(shapes)

    assert set(trace.executed) == DECLARED


@pytest.mark.proves("dev07-1-3", depth="component")
def test_the_edges_are_named_by_the_same_rule(shapes):
    """One rule for the whole adapter (``dev07-1-3-sr08``) — edges included."""
    trace = _observed(shapes)

    named = {end for edge in trace.edges for end in edge}

    assert named <= DECLARED, f"edges name something no definition declares: {named - DECLARED}"


# ---- the reconstruction, against the runtime that can still name a frame ---------------------

SRC = __import__("pathlib").Path(__file__).resolve().parent.parent / "src" / "plumb"

#: `co_qualname` arrived in 3.11. Where it is present it is the truth the reconstruction is held
#: against; where it is absent there is nothing to hold it against and this cannot run.
names_frames = pytest.mark.skipif(
    not hasattr((lambda: 0).__code__, "co_qualname"),
    reason="this runtime does not report co_qualname, so it cannot be the oracle")


def _code_objects(compiled):
    yield compiled
    for const in compiled.co_consts:
        if hasattr(const, "co_consts"):
            yield from _code_objects(const)


@names_frames
@pytest.mark.proves("dev07-1-3", depth="unit")
def test_the_reconstruction_agrees_with_a_runtime_that_reports_the_name():
    """Every code object plumb ships, named both ways, compared.

    Below 3.11 the name is read out of the source because the runtime carries none. That path
    cannot be checked where it is needed, so it is checked where it is not: here, against the
    runtime's own answer, over the whole of what this project ships.
    """
    from plumb.adapters.python.surface import _from_source, definition

    disagreed = []
    for path in sorted(SRC.rglob("*.py")):
        compiled = compile(path.read_text(encoding="utf-8"), str(path), "exec")
        for code in _code_objects(compiled):
            reconstructed = _from_source(code)
            reported = definition(code.co_qualname)
            if reconstructed != reported:
                disagreed.append(
                    f"{path.name}:{code.co_firstlineno} {code.co_name} — "
                    f"source said {reconstructed!r}, runtime said {reported!r}")
    assert not disagreed, disagreed[:10]
