"""Two adapters, one system, one graph (``dev07-1-3-sr08``).

An edge is a fact about how a system is put together rather than about the language it is written
in, so the same program written twice has to draw the same picture. It did not: the JVM probe
compared the two *classes*, so a surface of one class drew no graph at all, while the Python
recorder refused only a member calling itself. Nothing held them to the same grain, and nothing
would have noticed — the Java sample's edge file was empty and read as *nothing to draw*.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from plumb.adapters.python.surface import ProductionSurface
from plumb.adapters.python.trace import trace_call

REPO = Path(__file__).resolve().parent.parent
JAVA = REPO / "adapters" / "java"
PARITY = Path(__file__).parent / "sample_parity"

#: The one thing the two fixtures are allowed to differ in: each language's own spelling of a
#: name. Written out rather than derived, because a rule that transforms one into the other would
#: be a rule that could make a difference disappear.
SPELLING = {"handle_request": "handleRequest", "work": "work",
            "dense": "dense", "sparse": "sparse"}


def _members(edges, separator):
    """An edge set with each language's own naming taken off, leaving the shape."""
    return {(a.split(separator)[-1], b.split(separator)[-1]) for a, b in edges}


def _java_work() -> Path:
    from plumb.config import Config
    from plumb.launch import _scratch

    return _scratch(Config.find(JAVA))


def adapter_is_built() -> bool:
    return (JAVA / "adapter" / "target" / "classes" / "org" / "plumbspec" / "PlumbRunner.class").is_file()


needs_jvm = pytest.mark.skipif(
    not adapter_is_built(),
    reason="needs `mvn -f adapters/java/pom.xml package` to have run")


@pytest.mark.proves("dev07-1-3", depth="component")
def test_the_python_recorder_draws_members_of_one_module():
    """A module's own members join. Only a member calling itself does not."""
    sys.path.insert(0, str(PARITY.parent))
    import sample_parity

    surface = ProductionSurface.of(PARITY, entry_points=("sample_parity:handle_request",))
    drawn = _members(trace_call(surface, lambda: sample_parity.handle_request(2)).edges, ":")

    assert drawn == {("handle_request", "work"), ("work", "dense"), ("work", "sparse")}


@needs_jvm
@pytest.mark.proves("dev07-1-3", depth="wiring")
def test_both_adapters_draw_the_same_graph_over_the_same_program():
    """The Java sample and its Python twin, each observed by its own adapter."""
    sys.path.insert(0, str(PARITY.parent))
    import sample_parity

    surface = ProductionSurface.of(PARITY, entry_points=("sample_parity:handle_request",))
    in_python = _members(trace_call(surface, lambda: sample_parity.handle_request(2)).edges, ":")
    spelled = {(SPELLING[a], SPELLING[b]) for a, b in in_python}

    done = subprocess.run(
        [sys.executable, "-m", "plumb.cli", "board", "--json", "--project", str(JAVA)],
        capture_output=True, text=True, cwd=REPO, timeout=900,
        env={**os.environ, "PYTHONPATH": str(REPO / "src")})
    assert done.returncode == 0, done.stderr[-3000:]

    written = (_java_work() / "edges.tsv").read_text().splitlines()
    in_java = _members((line.split("\t") for line in written if line), "#")

    assert in_java, "the JVM adapter drew no edges at all, which is how this went unnoticed before"
    assert spelled == in_java
