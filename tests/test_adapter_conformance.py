"""One set of questions, asked of every adapter (``dev07-3-3``, ``dev07-1-3``).

Chapter 3 is language-agnostic: it names the observations an adapter makes and the fact derived
from them, and says nothing about how any language makes them. Nothing enforced that. Each adapter
had its own suite, each suite asked that adapter what it does, and both passed while disagreeing —
`trace.reads` is a mandatory element of chapter 3 and the Java adapter has never emitted it, so
`inert` there is read from *ran nothing* alone. That is the absence `dev07-4-2` refuses: the positive
proof a structural story needs, handed to a test whose body is `assert 2 + 2 == 4`.

So the scenarios live here, once, and every adapter answers the same ones. A language that cannot
answer is behind rather than exempt — an element the table marks mandatory is not optional because
one implementation has not caught up.
"""

# `X | None` in a signature is evaluated at import on 3.9, so without this the module does not
# collect at the floor this project declares.
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
JAVA = REPO / "adapters" / "java"
DOTNET = REPO / "adapters" / "dotnet"

#: What every adapter must answer, whatever it observes. The key is the shape of the test; the
#: value is the fact chapter 3 says that shape produces.
CONFORMANCE = {
    "drives a declared entry point": "grounded",
    "runs production under no entry point": "ungrounded",
    "reads the artifact and runs none of it": "inert",
    "neither runs nor reads the artifact": "untouched",
}


def _groundings(project: Path, extra_env: dict | None = None) -> dict:
    """Per-citation grounding, read from the manifest rather than from a printed line.

    The manifest is the one place both adapters write the same shape, which is the only reason this
    can ask them the same question.
    """
    done = subprocess.run(
        [sys.executable, "-m", "plumb.cli", "board", "--json", "--project", str(project)],
        capture_output=True, text=True, cwd=REPO, timeout=900,
        env={**os.environ, "PYTHONPATH": str(REPO / "src"), **(extra_env or {})})
    manifest = _manifest_of(project)
    assert manifest and manifest.is_file(), (
        f"no manifest from {project}: {done.stderr[-2000:]}")
    written = json.loads(manifest.read_text())
    return {story: c["grounding"]
            for story, s in written["stories"].items() for c in s["citations"]}


def _manifest_of(project: Path):
    """Where this project's manifest landed — one place, for every adapter.

    This looked in two places while the adapters disagreed: the Python one wrote to the scratch
    `dev00-1-2` keeps outside an adopter's tree and the Java one wrote `build/plumb/` inside it. The
    fallback is gone with the disagreement, deliberately — a lookup that tries both is a lookup that
    would go on passing if either adapter started writing into somebody's repository again, and this
    suite exists to notice exactly that.
    """
    sys.path.insert(0, str(REPO / "src"))
    from plumb.config import Config
    from plumb.launch import _scratch

    return _scratch(Config.find(project)) / "manifest.json"


def _python_project(root: Path) -> Path:
    """A project with one test of each shape, in the language this tool is written in."""
    (root / "app").mkdir(parents=True)
    (root / "app" / "__init__.py").write_text("")
    (root / "app" / "core.py").write_text(
        "def handle(n):\n    return helper(n) * 2\n\n\ndef helper(n):\n    return n + 1\n")
    (root / "plumb.toml").write_text(
        'adapter = "python"\nproduction = ["app"]\nentry_points = ["app.core:handle"]\n')
    (root / "test_shapes.py").write_text(
        "import pytest\nfrom pathlib import Path\n\n\n"
        "@pytest.mark.proves('S-GROUNDED', depth='wiring')\n"
        "def test_drives_the_entry_point():\n"
        "    from app.core import handle\n    assert handle(1) == 4\n\n\n"
        "@pytest.mark.proves('S-UNGROUNDED', depth='unit')\n"
        "def test_runs_production_under_no_entry_point():\n"
        "    from app.core import helper\n    assert helper(1) == 2\n\n\n"
        "@pytest.mark.proves('S-INERT', depth='unit')\n"
        "def test_reads_the_artifact_as_data():\n"
        "    text = Path('app/core.py').read_text()\n    assert 'def handle' in text\n\n\n"
        "@pytest.mark.proves('S-UNTOUCHED', depth='unit')\n"
        "def test_neither_runs_nor_reads():\n    assert 2 + 2 == 4\n")
    return root


#: Which citation in each adapter's sample stands for each shape above.
PYTHON_CITES = {
    "drives a declared entry point": "S-GROUNDED",
    "runs production under no entry point": "S-UNGROUNDED",
    "reads the artifact and runs none of it": "S-INERT",
    "neither runs nor reads the artifact": "S-UNTOUCHED",
}
JAVA_CITES = {
    "drives a declared entry point": "APP-1",
    "runs production under no entry point": "APP-3",
    "reads the artifact and runs none of it": "APP-4",
    "neither runs nor reads the artifact": "CM-101",
}


@pytest.mark.proves("dev07-1-4", depth="standards-integration")
@pytest.mark.parametrize("shape", list(CONFORMANCE))
def test_the_python_adapter_answers_the_shared_scenario(tmp_path, shape):
    facts = _groundings(_python_project(tmp_path / "project"))
    story = PYTHON_CITES[shape]
    assert facts.get(story) == CONFORMANCE[shape], (
        f"python: a test that {shape} must ground as {CONFORMANCE[shape]!r}, "
        f"and this run said {facts.get(story)!r}")


needs_jvm = pytest.mark.skipif(
    not (JAVA / "build" / "plumb-java.jar").is_file(),
    reason="the Java adapter is not built on this machine")


@needs_jvm
@pytest.mark.proves("dev07-1-4", depth="standards-integration")
@pytest.mark.parametrize("shape", list(CONFORMANCE))
def test_the_java_adapter_answers_the_shared_scenario(shape):
    facts = _groundings(JAVA)
    story = JAVA_CITES[shape]
    assert facts.get(story) == CONFORMANCE[shape], (
        f"java: a test that {shape} must ground as {CONFORMANCE[shape]!r}, "
        f"and this run said {facts.get(story)!r}")


DOTNET_CITES = {
    "drives a declared entry point": "APP-1",
    "runs production under no entry point": "APP-3",
    "reads the artifact and runs none of it": "APP-4",
    "neither runs nor reads the artifact": "CM-102",
}

needs_dotnet = pytest.mark.skipif(
    shutil.which("dotnet") is None or not (DOTNET / "build" / "PlumbSpec.Adapter.dll").is_file(),
    reason="no dotnet on PATH, or the .NET adapter is not built on this machine")


def _dotnet_groundings() -> dict:
    """The sample after its own build, which is the adopter's step and never plumb's."""
    env = {**os.environ, "DOTNET_CLI_TELEMETRY_OPTOUT": "1", "DOTNET_NOLOGO": "1"}
    if not env.get("DOTNET_ROOT"):
        env["DOTNET_ROOT"] = str(Path(shutil.which("dotnet")).resolve().parent)
    built = subprocess.run(["dotnet", "build", str(DOTNET / "sample" / "Tests")],
                           capture_output=True, text=True, timeout=600, env=env)
    assert built.returncode == 0, built.stdout[-3000:]
    return _groundings(DOTNET, env)


@needs_dotnet
@pytest.mark.proves("dev07-1-4", depth="standards-integration")
@pytest.mark.parametrize("shape", [
    pytest.param(shape, marks=pytest.mark.xfail(
        strict=True, reason="a .NET read of the artifact is not observed yet (dev07-1-3-u7)"))
    if shape == "reads the artifact and runs none of it" else shape
    for shape in CONFORMANCE])
def test_the_dotnet_adapter_answers_the_shared_scenario(shape):
    facts = _dotnet_groundings()
    story = DOTNET_CITES[shape]
    assert facts.get(story) == CONFORMANCE[shape], (
        f"dotnet: a test that {shape} must ground as {CONFORMANCE[shape]!r}, "
        f"and this run said {facts.get(story)!r}")


@pytest.mark.proves("dev07-1-4", depth="unit")
def test_the_core_reads_back_every_fact_an_adapter_may_report():
    """The readers must know the whole vocabulary, not the part somebody typed out.

    An adapter emitting a fact the core cannot parse is the same drift as an adapter not emitting
    it, arriving from the other end and quieter: the fact reaches the manifest and the board never
    counts or recites it. Measured — `untouched` was added to the manifest's vocabulary and both of
    `launch.py`'s regexes were written by hand without it, so a per-test line carrying the new
    answer matched nothing and was dropped in the core rather than in either adapter.

    This is the adapter conformance above pointed the other way. That asks whether each adapter
    says what the chapter says; this asks whether the reader can hear it.
    """
    sys.path.insert(0, str(REPO / "src"))
    from plumb.core.manifest import GROUNDING
    from plumb.launch import GROUNDING_LINE, PER_TEST

    for fact in GROUNDING:
        line = f"   {fact} SomeTest#someCase"
        assert PER_TEST.match(line), (
            f"the board cannot count a test reported as {fact!r}, so an adapter that answers it "
            "correctly has the answer dropped between the run and the board")
        assert GROUNDING_LINE.match(line), (
            f"the board will not recite a test reported as {fact!r} under --tests")
