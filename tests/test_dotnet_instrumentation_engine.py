"""A prototype that is a test (rule 4): plumb's .NET weave as an instrumentation method inside the
CLR Instrumentation Engine (`dev07-1-3-sr11`, `sr12`).

The runtime gives its code-rewriting hook to one profiler alone, and Microsoft's code coverage takes
it — measured: `--collect "Code Coverage"` sets the profiler to the Instrumentation Engine and loads
its own instrumenter into it, and a profiler of plumb's own would be silently replaced. The engine
exists to share that hook, and every VSTest project restores it, because `Microsoft.NET.Test.Sdk`
depends on `Microsoft.CodeCoverage`. So plumb joins it as one more instrumenter, beside coverage
rather than instead of it, and the build's output runs where the build wrote it.

What this prototype holds, in order:

1. the engine, found in the project's own restore, loads plumb's instrumenter into VSTest's testhost
   at the floor runtime;
2. with Microsoft's coverage collected as well, both still run;

3. the whole weave, carried out as the runtime compiles, gives every test of the reference suite the
   fact its shape produces — every shape of `grounded`, `ungrounded`, `untouched` and
   `dispatched` — on .NET 6 and .NET 10, under two versions of the engine, and still does with
   coverage instrumenting the same methods.

What to weave is a plan the adapter makes from the build's output (`PlumbSpec.Adapter plan`); the
instrumenter carries it out and decides nothing (`dev07-1-3-sr03`).
"""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
COLLECTOR = REPO / "adapters" / "dotnet" / "build" / "PlumbSpec.Adapter.dll"
INSTRUMENTER = REPO / "adapters" / "dotnet" / "instrumenter"
BUILT = REPO / "adapters" / "dotnet" / "build" / "instrumenter" / "linux-x64"
SAMPLE = REPO / "adapters" / "dotnet" / "sample" / "Tests"

#: The engine's own class id, as Microsoft's coverage names it in the profiler variables.
ENGINE_CLASS = "{324F817A-7420-4E6D-B3C1-143FBED6D855}"

needs_engine_platform = pytest.mark.skipif(
    shutil.which("dotnet") is None or platform.system() != "Linux" or platform.machine() != "x86_64",
    reason="the prototype is measured on Linux x64, the platform this machine has")


def _environment() -> dict:
    env = {**os.environ, "DOTNET_CLI_TELEMETRY_OPTOUT": "1", "DOTNET_NOLOGO": "1"}
    if not env.get("DOTNET_ROOT") and shutil.which("dotnet"):
        env["DOTNET_ROOT"] = str(Path(shutil.which("dotnet")).resolve().parent)
    return env


def _engine(project: Path) -> Path:
    """The engine the test project restored — never one plumb brings (`dev00-1-1-ur8`).

    Searched for rather than spelled: the package moved it between versions — measured, 17.8 keeps
    it under `InstrumentationEngine/ubuntu/x64`, 17.14.1 under `ubuntu/x64`.
    """
    assets = json.loads((project / "obj" / "project.assets.json").read_text())
    root = Path(assets["project"]["restore"]["packagesPath"])
    version = next(name.split("/")[1] for name in assets["libraries"]
                   if name.lower().startswith("microsoft.codecoverage/"))
    found = sorted((root / "microsoft.codecoverage" / version).rglob("ubuntu/x64/libInstrumentationEngine.so"))
    assert found, f"the project restored Microsoft.CodeCoverage {version} with no engine"
    return found[0]


@pytest.fixture(scope="module")
def instrumenter() -> Path:
    """The instrumenter, published native, with the config that names it beside it."""
    published = subprocess.run(
        ["dotnet", "publish", str(INSTRUMENTER), "-r", "linux-x64", "-c", "Release", "-o", str(BUILT)],
        capture_output=True, text=True, timeout=900, env=_environment())
    assert published.returncode == 0, published.stdout[-3000:]
    built = subprocess.run(["dotnet", "build", str(SAMPLE)], capture_output=True, text=True,
                           timeout=600, env=_environment())
    assert built.returncode == 0, built.stdout[-3000:]
    return BUILT / "PlumbInstrumenter.config"


#: The reference project's declaration, as the launcher resolves it into a run file.
ENTRY_POINTS = ("Sample.App.HandleRequest", "Sample.App.Shapes", "Sample.App.Echo",
                "Sample.App.Record", "Sample.App.FailingRequest", "Sample.App.HandleAsync")


def _expected() -> dict:
    """Every test's fact by its shape — one table, held by the board's own test, so this run is held
    to the same answers and never to a second copy of them."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from test_the_dotnet_adapter import EXPECTED
    return EXPECTED


def _run(config: Path, work: Path, *extra: str, project: Path = SAMPLE
         ) -> tuple[subprocess.CompletedProcess, list[str], dict[str, str]]:
    """A suite under the engine, with plumb's instrumenter configured into it and plumb's collector
    reading the run: what the suite said, what the instrumenter said, and each test's fact."""
    log = work / "plumb.log"
    settings = work / "engine.runsettings"
    run_file = work / "run.tsv"
    run_file.write_text("".join(f"entrypoint\t{e}\n" for e in ENTRY_POINTS)
                        + "production\tApp\nversion\tprototype\n")
    output = next((project / "bin" / "Debug").iterdir())
    planned = subprocess.run(["dotnet", str(COLLECTOR), "plan", str(output), "Tests.dll", str(run_file),
                              str(work / "plan.tsv")], capture_output=True, text=True, timeout=300,
                             env=_environment())
    assert planned.returncode == 0, planned.stderr
    variables = {
        "CORECLR_ENABLE_PROFILING": "1",
        "CORECLR_PROFILER": ENGINE_CLASS,
        "CORECLR_PROFILER_PATH_64": str(_engine(project)),
        "MicrosoftInstrumentationEngine_ConfigPath64_Plumb": str(config),
        # The engine checks an instrumenter's signature on Windows; Microsoft's coverage turns that
        # off for itself, and plumb's is unsigned (`dev07-1-3-sr12`).
        "MicrosoftInstrumentationEngine_DisableCodeSignatureValidation": "1",
        "PLUMB_INSTRUMENTER_LOG": str(log),
        "PLUMB_PLAN": str(work / "plan.tsv"),
    }
    settings.write_text(
        "<RunSettings><RunConfiguration><EnvironmentVariables>"
        + "".join(f"<{k}>{v}</{k}>" for k, v in variables.items())
        + "</EnvironmentVariables></RunConfiguration>"
        "<InProcDataCollectionRunSettings><InProcDataCollectors>"
        '<InProcDataCollector friendlyName="plumb" uri="InProcDataCollector://plumbspec/1" '
        'assemblyQualifiedName="PlumbSpec.Collector, PlumbSpec.Adapter, Version=1.0.0.0, '
        f'Culture=neutral, PublicKeyToken=null" enabled="True" codebase="{COLLECTOR}">'
        f"<Configuration><Manifest>{work / 'manifest.json'}</Manifest><RunFile>{run_file}</RunFile>"
        f"<InstrumenterLog>{log}</InstrumenterLog></Configuration></InProcDataCollector>"
        "</InProcDataCollectors></InProcDataCollectionRunSettings></RunSettings>")
    done = subprocess.run(
        ["dotnet", "test", "--no-build", "--settings", str(settings),
         "--results-directory", str(work / "results"), *extra],
        cwd=project, capture_output=True, text=True, timeout=600, env=_environment())
    report = work / "report.txt"
    facts = {}
    for line in (report.read_text().splitlines() if report.is_file() else []):
        if line.startswith("   "):
            fact, test = line.split(None, 1)
            facts[test.strip()] = fact
    return done, (log.read_text().splitlines() if log.is_file() else []), facts


@needs_engine_platform
def test_the_engine_loads_plumbs_instrumenter_into_the_testhost(instrumenter, tmp_path):
    """Point 1: loaded, initialised, and told of every module — inside the floor's testhost.

    The instrumenter's own runtime is NativeAOT's, inside a process running .NET 6; the suite's
    results must be the suite's, so the two runtimes sharing the process cost the tests nothing.
    """
    done, said, _ = _run(instrumenter, tmp_path)
    plain = subprocess.run(["dotnet", "test", "--no-build"], cwd=SAMPLE, capture_output=True,
                           text=True, timeout=600, env=_environment())
    def summary(out: str):
        counts = re.search(r"Failed:\s+\d+, Passed:\s+\d+, Skipped:\s+\d+, Total:\s+\d+", out)
        return counts.group(0) if counts else None
    assert summary(done.stdout) and summary(done.stdout) == summary(plain.stdout), (
        f"the suite under the engine must report what it reports without it: "
        f"{summary(done.stdout)!r} against {summary(plain.stdout)!r}")
    assert said[:2] == ["factory", "initialize"], f"the engine did not load and initialise it: {said}"
    shutdown = next((line for line in said if line.startswith("shutdown")), "")
    assert shutdown and int(shutdown.split("modules=")[1]) > 0, (
        f"it was never told of a module, so it could not instrument one: {said}")


@needs_engine_platform
def test_plumbs_instrumenter_and_microsofts_coverage_both_run(instrumenter, tmp_path):
    """Point 2, the one this route was chosen for: neither displaces the other (`sr12`).

    Coverage replaces the profiler variables with its own — the same engine — and loads its own
    instrumenter; plumb's is named by a variable of its own, which must survive that.
    """
    done, said, facts = _run(instrumenter, tmp_path, "--collect", "Code Coverage")
    assert "initialize" in said, (
        f"with coverage collected, plumb's instrumenter was not loaded: {said}")
    produced = list((tmp_path / "results").rglob("*.coverage"))
    assert produced and produced[0].stat().st_size > 0, (
        f"with plumb's instrumenter loaded, Microsoft's coverage produced nothing: {done.stdout[-2000:]}")
    # Both instrument the same methods; plumb's probes must still report through coverage's, and the
    # suite must still report what it reports unwoven. Measured: coverage rewrites the build's output
    # on disk for the length of its run, and a weave planned from the file before then pointed its
    # tokens at other members — eight tests failed that pass, and facts moved between tests.
    _assert_parity(facts, "with coverage")
    plain = subprocess.run(["dotnet", "test", "--no-build"], cwd=SAMPLE, capture_output=True,
                           text=True, timeout=600, env=_environment())
    counts = re.compile(r"Failed:\s+\d+, Passed:\s+\d+, Skipped:\s+\d+, Total:\s+\d+")
    assert counts.search(done.stdout).group(0) == counts.search(plain.stdout).group(0), (
        f"with coverage, the woven suite reports {counts.search(done.stdout).group(0)!r} where it "
        f"reports {counts.search(plain.stdout).group(0)!r} unwoven")


@pytest.fixture(scope="module")
def net10_sample(tmp_path_factory) -> Path:
    """The sample's suite at .NET 10 with a current test SDK — and so a newer engine — in a copy,
    because retargeting it in place would rewrite the floor sample's own restore."""
    root = tmp_path_factory.mktemp("net10")
    for part in ("sample/App", "sample/Tests", "annotations"):
        shutil.copytree(REPO / "adapters" / "dotnet" / part, root / part,
                        ignore=shutil.ignore_patterns("bin", "obj"))
    project = root / "sample" / "Tests" / "Tests.csproj"
    project.write_text(project.read_text().replace("net6.0", "net10.0")
                       .replace('"17.8.0"', '"17.14.1"').replace('"2.8.2"', '"3.1.4"'))
    built = subprocess.run(["dotnet", "build", str(project.parent)], capture_output=True, text=True,
                           timeout=600, env=_environment())
    assert built.returncode == 0, built.stdout[-3000:]
    return project.parent


def _assert_parity(facts: dict, where: str) -> None:
    expected = _expected()
    differ = {t: (expected.get(t), facts.get(t)) for t in set(expected) | set(facts)
              if expected.get(t) != facts.get(t)}
    assert not differ, f"{where}: facts differ from each test's shape:\n" + "\n".join(
        f"  {t}: expected {e!r}, said {g!r}" for t, (e, g) in sorted(differ.items()))


@needs_engine_platform
@pytest.mark.parametrize("runtime", ["net6.0", "net10.0"])
def test_the_whole_weave_as_the_runtime_compiles_gives_every_test_its_fact(
        instrumenter, net10_sample, tmp_path, runtime):
    """Point 3: every test of the reference suite reads the fact its shape produces, and the suite
    reports what it reports unwoven. Nothing is copied: what runs is what the build wrote."""
    project = SAMPLE if runtime == "net6.0" else net10_sample
    done, said, facts = _run(instrumenter, tmp_path, project=project)
    assert not [line for line in said if line.startswith(("left", "failed"))], said
    _assert_parity(facts, runtime)
    plain = subprocess.run(["dotnet", "test", "--no-build"], cwd=project, capture_output=True,
                           text=True, timeout=600, env=_environment())
    counts = re.compile(r"Failed:\s+\d+, Passed:\s+\d+, Skipped:\s+\d+, Total:\s+\d+")
    assert counts.search(done.stdout) and counts.search(done.stdout).group(0) == \
        counts.search(plain.stdout).group(0), "woven, the suite must report what it reports unwoven"
    runtimes = {c["observer"]["runtime"] for s in json.loads((tmp_path / "manifest.json").read_text())
                ["stories"].values() for c in s["citations"]}
    major = ".NET 6." if runtime == "net6.0" else ".NET 10."
    assert len(runtimes) == 1 and runtimes.pop().startswith(major), (
        f"{runtime}: the suite ran on another runtime than the one it targets")
