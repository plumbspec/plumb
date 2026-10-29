"""The third runtime, exercised — .NET at its floor, through VSTest (`dev07-3-3`, `dev07-1-3`).

**A prototype that is a test**, and the first slice of it. What runs is the whole road an adopter
takes: their build has already happened, `plumb board` copies the test project's output out of their
tree, VSTest runs the copy with plumb's in-process collector loaded, and the collector writes the
manifest. One collector serves xUnit, NUnit and MSTest, because it hears each test start and end
from VSTest rather than from any one framework.

What this slice does **not** do yet is observe grounding: the weave (`dev07-1-3-sr11`, `sr12`) is the
next slice, and until it lands every citation reads `not-checked` and the run says it ran blind.
That is asserted below rather than left unsaid, so the day the weave arrives this file has to
change with it.

The sample targets `net6.0`, so its testhost runs on the floor runtime (`dev07-1-1-ur1`) whatever
SDK built it — the floor is held by running there, not by reading a version.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
DOTNET = REPO / "adapters" / "dotnet"
COLLECTOR = DOTNET / "build" / "PlumbSpec.Adapter.dll"
SAMPLE_OUTPUT = DOTNET / "sample" / "Tests" / "bin" / "Debug" / "net6.0"

needs_dotnet = pytest.mark.skipif(
    shutil.which("dotnet") is None or not COLLECTOR.is_file(),
    reason="no dotnet on PATH, or the .NET adapter is not built (`dotnet build adapters/dotnet`)")


def _environment() -> dict:
    """The run's environment, with the SDK's root named.

    An apphost — and VSTest's testhost is one — finds the runtime through `DOTNET_ROOT` when the SDK
    is not installed system-wide, and a shell that never sourced the workspace's profile has it
    unset. Derived from the `dotnet` on PATH rather than typed here.
    """
    env = {**os.environ, "PYTHONPATH": str(REPO / "src"),
           "DOTNET_CLI_TELEMETRY_OPTOUT": "1", "DOTNET_NOLOGO": "1"}
    if not env.get("DOTNET_ROOT") and shutil.which("dotnet"):
        env["DOTNET_ROOT"] = str(Path(shutil.which("dotnet")).resolve().parent)
    return env


def _tree_digest(root: Path) -> str:
    """Every file under `root`, by path, size and content — what "never written to" is held to."""
    digest = hashlib.blake2b(digest_size=16)
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _board(project: Path, build: Path) -> dict:
    """One board over a .NET project, after its own build.

    The project is built here because building is the adopter's step and never plumb's: the board
    reads what `dotnet build` left, as it would in their repository.
    """
    built = subprocess.run(["dotnet", "build", str(build)],
                           capture_output=True, text=True, timeout=600, env=_environment())
    assert built.returncode == 0, built.stdout[-3000:]

    sys.path.insert(0, str(REPO / "src"))
    from plumb.config import Config
    from plumb.launch import _scratch

    manifest = _scratch(Config.find(project)) / "manifest.json"
    manifest.unlink(missing_ok=True)
    # A subprocess with a timeout: a testhost that never exits is a hang, and a test calling the
    # launcher in-process would hang with it and report nothing.
    done = subprocess.run(
        [sys.executable, "-m", "plumb.cli", "board", "--json", "--tests", "--project", str(project)],
        capture_output=True, text=True, cwd=REPO, timeout=900, env=_environment())
    return {"done": done, "manifest": manifest}


@pytest.fixture(scope="module")
def board():
    """One board over the reference .NET project, shared by the tests below, with its build
    output's digest taken either side of it."""
    subprocess.run(["dotnet", "build", str(DOTNET / "sample" / "Tests")],
                   capture_output=True, timeout=600, env=_environment())
    before = _tree_digest(SAMPLE_OUTPUT)
    ran = _board(DOTNET, DOTNET / "sample" / "Tests")
    return {**ran, "before": before, "after": _tree_digest(SAMPLE_OUTPUT)}


def _written(board) -> dict:
    assert board["done"].returncode == 0, board["done"].stderr[-3000:]
    assert board["manifest"].is_file(), (
        f"the run wrote no manifest at all: {board['done'].stderr[-3000:]}")
    return json.loads(board["manifest"].read_text())


@needs_dotnet
@pytest.mark.proves("dev07-1-3", depth="smoke")
def test_the_dotnet_adapter_runs_a_suite_and_reports_what_the_runner_said(board):
    """The general corrective, as the JVM's: a test that fails when .NET is broken.

    Asserting a manifest exists is what a broken adapter can pass — the JVM one once wrote an empty
    one while hanging. What is asserted is what only a collector that heard every test can know.
    """
    written = _written(board)
    stories = written["stories"]
    results = {sid: [c["result"] for c in s["citations"]] for sid, s in stories.items()}

    assert results.get("CM-101") == ["passed"], results
    # `Skip` is xUnit's "specified, not built" — pytest's skip and JUnit's abort in another spelling.
    assert results.get("CM-104") == ["skipped"], results
    assert results.get("CM-105") == ["failed"], (
        f"a claimed-done story that broke must read as broken, not vanish: {results}")
    # One test citing two stories is two citations, each at its own depth.
    assert results.get("CM-102") == ["passed"] and results.get("CM-103") == ["passed"], results
    depths = {sid: s["citations"][0]["depth"] for sid, s in stories.items()}
    assert depths["CM-102"] == "unit" and depths["CM-103"] == "component", depths
    assert stories["CM-101"]["citations"][0]["ref"] == "JIRA-4412", (
        "the consumer's own key is carried through untouched (`dev07-3-1`)")

    # A citation on the class is a citation on every test in it, as `@Proves` on a type is.
    assert len(stories.get("CM-106", {}).get("citations", ())) == 2, stories.get("CM-106")


@needs_dotnet
@pytest.mark.proves("dev07-1-3", depth="unit")
def test_each_row_of_a_theory_is_its_own_citation(board):
    """A theory runs once per row, and VSTest names every row by the same method.

    Keyed by the method alone, two rows collapse into one test with whichever result arrived last —
    a failing row hidden behind a passing one is exactly the false PROVEN this tool exists to stop.
    Named apart, as pytest names a parametrized test's ids apart.
    """
    cited = _written(board)["stories"]["CM-107"]["citations"]
    names = [c["test"] for c in cited]
    assert len(names) == 2 and len(set(names)) == 2, (
        f"each row of the theory must be a citation of its own, named apart: {names}")
    assert sorted(c["result"] for c in cited) == ["failed", "passed"], (
        f"the row that failed must stay failed beside the row that passed: {cited}")


@needs_dotnet
@pytest.mark.proves("dev07-3-1", depth="unit")
def test_the_facts_name_the_runtime_and_the_instrument_that_made_them(board):
    """Provenance on every citation (`dev07-3-1`), and an honest one for this slice.

    The runtime is the floor's, because the sample targets `net6.0`. The mechanism says grounding
    was not observed, because nothing observes it yet, and the board says the run went blind
    rather than prompting the reader to declare entry points the project already declared.
    """
    written = _written(board)
    observers = {json.dumps(c["observer"], sort_keys=True)
                 for s in written["stories"].values() for c in s["citations"]}
    assert len(observers) == 1, f"one run, one instrument: {observers}"
    observer = json.loads(observers.pop())
    assert observer["adapter"] == "plumb-dotnet", observer
    assert observer["runtime"].startswith(".NET 6.0."), (
        f"the sample targets the floor, so its tests must have run on it: {observer}")
    assert observer["mechanism"].startswith("none"), observer

    groundings = {c["grounding"] for s in written["stories"].values() for c in s["citations"]}
    assert groundings == {"not-checked"}, (
        f"nothing observes grounding yet, so nothing may claim an answer to it: {groundings}")
    assert "observation.failed" in board["done"].stdout, (
        "entry points are declared and nothing watched them — the board must say the instrument "
        "did not run, not that the project declared nothing (`dev07-1-4-ur5`)")


@needs_dotnet
@pytest.mark.proves("dev07-3-2", depth="unit")
def test_every_test_the_run_saw_is_counted_cited_or_not(board):
    """`observed_tests` counts what ran, cited or not — the uncited test included (`dev07-3-2`).

    Counted per test case VSTest ran, so each row of a theory is one.
    """
    written = _written(board)
    assert written["observed_tests"] == 9, (
        f"the sample runs nine test cases and the run reported {written['observed_tests']}")


@needs_dotnet
@pytest.mark.proves("dev07-1-3", depth="unit")
def test_the_build_output_is_never_written_to(board):
    """`dev07-1-3-sr11`: the run happens in a copy outside the project's tree.

    Held now, before there is a weave to write anything, because the copy is the seam the weave
    will use — and a run that writes into somebody's `bin` once is a run that will one day leave a
    woven assembly there for their next `dotnet test`.
    """
    _written(board)
    assert board["before"] == board["after"], (
        "the board changed the build's own output — the run must happen in a copy of it")


@needs_dotnet
@pytest.mark.proves("dev07-1-3", depth="unit")
@pytest.mark.parametrize("framework", ["NUnitTests", "MSTestTests"])
def test_every_framework_vstest_runs_reads_the_same(framework):
    """One collector for every framework, so each framework's own spellings must land alike.

    Each sample cites one test per spelling. An ignore and an inconclusive are both "nothing
    observed either way" — measured: MSTest's inconclusive reaches VSTest as `Skipped` and NUnit's
    as `None`, and reading `None` as failed put a broken story on the board that no test had broken.
    NUnit names a row by its arguments and MSTest only displays them; both must stay apart.
    """
    project = DOTNET / "sample" / framework
    written = _written(_board(project, project))
    results = {sid: sorted(c["result"] for c in s["citations"])
               for sid, s in written["stories"].items()}
    assert results == {"FW-1": ["passed"], "FW-2": ["skipped"], "FW-3": ["skipped"],
                       "FW-4": ["failed", "passed"], "FW-5": ["failed"]}, results
    rows = [c["test"] for c in written["stories"]["FW-4"]["citations"]]
    assert len(set(rows)) == 2, f"{framework}: each row must be named apart: {rows}"
    assert written["observed_tests"] == 6, written["observed_tests"]


def test_the_citation_the_collector_reads_is_the_one_the_vocabulary_declares():
    """The collector reads a citation by its type's NAME, never by reference.

    It has to: the collector is loaded into somebody else's testhost beside whatever copy of the
    vocabulary their project compiled against, and a reference would bind it to one version. So the
    name is a string, a rename is invisible to the compiler on both sides, and the failure is
    silence — every test cites nothing. Read from the sources, which are where the name is a fact.
    """
    vocabulary = {
        f"{ns}.{name}"
        for path in (DOTNET / "annotations").glob("*.cs")
        for ns in re.findall(r"^namespace ([\w.]+)", path.read_text(), re.M)
        for name in re.findall(r"public sealed class (\w+Attribute)\b", path.read_text())}
    assert {"PlumbSpec.ProvesAttribute", "PlumbSpec.InformsAttribute"} <= vocabulary, vocabulary

    read = set(re.findall(r'"(PlumbSpec\.\w+Attribute)"',
                          "".join(p.read_text() for p in (DOTNET / "adapter").glob("*.cs"))))
    assert read, "the collector names no citation type, which cannot be true"
    assert read <= vocabulary, (
        f"the collector reads {sorted(read - vocabulary)}, which the vocabulary does not declare")
