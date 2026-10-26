"""The shippable artifact, and running an adapter somewhere other than here (chapter 9).

`dev00-1-1` — obtainable without this repository — is deliberately **not** cited from here. Nothing in
this file downloads an artifact into an environment it did not build, which is the whole of what
that story claims; asserting the pieces and citing the whole is how a story comes to read PROVEN
on the strength of tests that never asked it.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from plumb import runfile
from plumb.config import Config
from plumb.launch import (_absolute, _bundled_jar, _interpreter, _own_path, _shadowing_root,
                          _subprocess_path)


@pytest.mark.proves("dev07-3-3", depth="component")
@pytest.mark.proves("dev00-1-2", depth="component")
def test_both_adapters_are_handed_the_same_resolved_facts(tmp_path):
    """The launcher's job is identical in both directions, which is what makes a third language a
    third reader of one file rather than a third shape of orchestration."""
    config = Config.parse(
        'entry_points = ["app.cli:main"]\nproduction = ["src/app"]\n'
        '[archetypes]\n"S-2" = "structural"\n', root=tmp_path)
    written = runfile.write(config, tmp_path / "run.tsv",
                            pytest_args=("tests/",), mutation=True)
    facts = runfile.read(written)

    assert runfile.values(facts, runfile.ENTRY_POINT) == ("app.cli:main",)
    assert runfile.values(facts, runfile.PRODUCTION) == ("src/app",)
    # Membership, not equality: the archetype registry is process-global by design, so a run
    # that executed a spec has more in it than this config named. The merge is the behaviour —
    # config supplies what an unexecuted spec cannot, and the spec declares over the top.
    assert ["S-2", "structural"] in facts[runfile.ARCHETYPE]
    assert runfile.values(facts, runfile.PYTEST_ARG) == ("tests/",)
    assert runfile.values(facts, runfile.MUTATION) == ("true",)


@pytest.mark.proves("dev07-5-1", depth="unit")
def test_an_absent_run_file_reads_as_nothing_declared(tmp_path):
    assert runfile.read(tmp_path / "absent.tsv") == {}


def test_a_venv_interpreter_is_never_resolved_through_its_symlink(tmp_path):
    """A venv's `bin/python` is a symlink to the base interpreter, and Python derives `sys.prefix`
    from the path it was *invoked* by — so following the link runs the base interpreter without
    the project's own packages, its test framework included.

    This shipped once and passed its first check anyway, because the machine also had pytest
    installed globally: the venv was destroyed and the run succeeded on the wrong interpreter.
    """
    venv = tmp_path / ".venv" / "bin"
    venv.mkdir(parents=True)
    link = venv / "python"
    link.symlink_to(sys.executable)

    chosen = _interpreter(Config(root=tmp_path))

    assert chosen == link, "the venv's own path, not what it points at"
    assert chosen != Path(os.path.realpath(sys.executable)) or Path(sys.executable) == link
    assert _absolute(link) == link


def test_a_declared_interpreter_beats_a_discovered_one(tmp_path):
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    (tmp_path / ".venv" / "bin" / "python").symlink_to(sys.executable)
    config = Config.parse(f'[python]\ninterpreter = "{sys.executable}"\n', root=tmp_path)

    assert _interpreter(config) == Path(sys.executable)


def test_with_no_project_interpreter_the_adapter_stays_in_this_process(tmp_path):
    """The fast path is not only speed — the tracer sees frames in the process it is installed
    in, so a caller driving the library directly keeps working exactly as before."""
    assert _interpreter(Config(root=tmp_path)) == Path(sys.executable)


def test_the_java_adapter_is_found_without_being_configured():
    """It ships inside the artifact, so where it lives is Plumb's business rather than a setting
    an adopter has to keep correct. From a checkout that is the compiled jar, if one is built."""
    found = _bundled_jar()
    assert found == "" or found.endswith("plumb-java.jar")


def _project_named_like_the_tool(tmp_path):
    """A project whose production package has the same name as the tool's own — which is Plumb
    tracing itself, and the only shape where the artifact can shadow the code under test."""
    ours = (tmp_path / "src" / "plumb")
    ours.mkdir(parents=True)
    (ours / "__init__.py").write_text("")
    return Config.parse(f'production = ["{ours}"]\n', root=tmp_path)


@pytest.mark.proves("dev07-1-1", depth="unit")
def test_a_project_shadowing_the_tool_leaves_this_process(tmp_path):
    """The fast path is safe only while the project has no package by our name. In-process,
    ``sys.modules`` already holds the tool's copy and no path setting can dislodge an import that
    has happened — so the suite exercises the *shipped* copy instead of the tree. Run from the
    artifact this reported 1 proven of 84 where source read 41, silently and in the flattering
    direction: a passing suite over the wrong code."""
    plain = Config.parse('production = ["src"]\n', root=tmp_path)
    (tmp_path / "src").mkdir()

    assert _shadowing_root(plain) is None
    assert _shadowing_root(_project_named_like_the_tool(tmp_path)) == str(tmp_path / "src")


@pytest.mark.proves("dev07-1-1", depth="unit")
def test_the_project_is_imported_before_the_artifact(tmp_path):
    """The artifact puts itself on the child's path so a foreign interpreter can import the
    adapter. Ahead of the project it shadowed the project's own package, so the suite exercised
    the shipped copy instead of the tree: every behavioural story read `inert`, and self-tracing
    reported 1 proven where the same commit run from source read 41."""
    config = _project_named_like_the_tool(tmp_path)

    parts = _subprocess_path(config, lambda line: None).split(os.pathsep)

    assert parts.index(str(tmp_path / "src")) < parts.index(_own_path())


@pytest.mark.proves("dev07-5-1", depth="unit")
def test_a_project_shadowing_the_tool_is_surfaced_not_silent(tmp_path):
    """Which copy of itself the tool just ran is the one thing a reader cannot recover from the
    board afterwards, so it is reported rather than inferred."""
    said = []

    _subprocess_path(_project_named_like_the_tool(tmp_path), said.append)

    assert any(str(tmp_path / "src") in line for line in said)


def test_an_inherited_pythonpath_survives(tmp_path, monkeypatch):
    """A project entitled to set PYTHONPATH is entitled to have it reach the adapter; the old
    line replaced the variable outright."""
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "vendor"))
    config = Config.parse('production = ["src"]\n', root=tmp_path)

    parts = _subprocess_path(config, lambda line: None).split(os.pathsep)

    assert str(tmp_path / "vendor") in parts
    assert parts.index(str(tmp_path / "vendor")) < parts.index(_own_path())


def test_the_python_adapter_runs_from_a_run_file_and_writes_a_manifest(tmp_path):
    """The out-of-process contract, exercised the way the launcher exercises it. Without this,
    the only thing proving the subprocess path is an installed artifact nobody has run yet."""
    (tmp_path / "src" / "app").mkdir(parents=True)
    (tmp_path / "src" / "app" / "__init__.py").write_text("")
    (tmp_path / "src" / "app" / "core.py").write_text("def entry(n):\n    return n * 2\n")
    (tmp_path / "test_gen.py").write_text(
        "import sys, pytest\n"
        f"sys.path.insert(0, {str(tmp_path / 'src')!r})\n"
        '@pytest.mark.proves("APP-1", depth="wiring")\n'
        "def test_it():\n"
        "    from app.core import entry\n"
        "    assert entry(2) == 4\n"
    )
    config = Config.parse(
        f'production = ["{tmp_path / "src" / "app"}"]\nentry_points = ["app.core:entry"]\n',
        root=tmp_path)
    run_file = runfile.write(config, tmp_path / "run.tsv")
    manifest = tmp_path / "manifest.json"

    completed = subprocess.run(
        [sys.executable, "-m", "plumb.adapters.python", str(run_file), str(manifest)],
        cwd=tmp_path, capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parent.parent / "src")})

    assert completed.returncode == 0, completed.stderr
    from plumb.core.manifest import Manifest

    read = Manifest.read(manifest)
    assert "APP-1" in read.stories, "a manifest produced by an adapter this process did not host"


@pytest.mark.proves("dev08", depth="component")
def test_a_project_declares_several_adapters_each_with_its_own_surface(tmp_path):
    """Production code and entry points are adapter-native (`dev07-1-3`) — a Java package and a
    Python module path are not the same kind of name — so they cannot be shared and each adapter
    gets its own block. One plumb.toml stays the single home; two files would be two sources of
    truth about one project."""
    config = Config.parse('''
specs = ["APP"]
[[adapters]]
adapter = "python"
production = ["src/app"]
entry_points = ["app.cli:main"]
[[adapters]]
adapter = "java"
production = ["com.example.app.*"]
sources = ["src/main/java"]
''', root=tmp_path)

    declared = config.adapters()

    assert [a.adapter for a in declared] == ["python", "java"]
    assert declared[0].entry_points == ("app.cli:main",)
    assert declared[1].production == ("com.example.app.*",)
    assert declared[1].sources == ("src/main/java",), "named apart where a language needs them apart"
    assert all(a.specs == ("APP",) for a in declared), "what the project declares about itself is shared"


@pytest.mark.proves("dev08", depth="unit")
def test_one_adapter_declared_the_ordinary_way_is_unchanged(tmp_path):
    """The single-language path must not pay for the multi-language one."""
    config = Config.parse('adapter = "python"\nproduction = ["src/app"]\n', root=tmp_path)

    assert config.adapters() == (config,)


@pytest.mark.proves("dev00-1-1", depth="component")
def test_the_bundled_vocabulary_is_the_one_published_to_maven_central():
    """Two jars carry the citation vocabulary — the one bundled in the artifact and the one on
    Maven Central — and nothing kept them equal.

    A build naming one source outright while the pom compiles the whole module ships two different
    vocabularies: an annotation exists for an adopter who took the coordinate and does not exist
    for one who took what we bundled. Same tool, same version, and the difference is invisible
    until a citation will not compile.

    Read from the sources the module owns rather than from a list here, because a list here is a
    third copy that goes stale the same way.
    """
    import zipfile

    module = Path(__file__).parent.parent / "adapters" / "java" / "annotations"
    bundled = Path(__file__).parent.parent / "adapters" / "java" / "build" / "plumb-annotations.jar"
    if not bundled.is_file():
        pytest.skip("no jar built in this checkout — "
                    "`mvn -f adapters/java/pom.xml package` makes one")

    declared = {source.stem for source in (module / "src/main/java/org/plumbspec").glob("*.java")}
    packaged = {name.split("/")[-1].removesuffix(".class").split("$")[0]
                for name in zipfile.ZipFile(bundled).namelist() if name.endswith(".class")}

    assert packaged == declared, (
        f"the bundled jar carries {sorted(packaged)} and the module declares {sorted(declared)} — "
        "an adopter taking the Maven coordinate would get a different vocabulary from one taking "
        "the artifact")
    # The adapter module compiles the vocabulary's whole source directory rather than a named
    # file, which is what keeps the two jars carrying the same set.
    adapter_pom = (module.parent / "adapter" / "pom.xml").read_text()
    assert "annotations/src/main/java" in adapter_pom, \
        "the adapter must add the vocabulary's source directory, not a named file, or these drift"
