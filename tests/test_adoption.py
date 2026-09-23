"""Getting a project from nothing to a board, and admitting a contributor (chapter 9)."""

import os
import sys
from functools import lru_cache
from pathlib import Path

import pytest

from plumb.config import Config, JAVA, PYTHON
from plumb.scaffold import detect, init, next_steps, render


def maven(tmp_path: Path, package: str = "com/acme/orders") -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "pom.xml").touch()
    (tmp_path / "src" / "main" / "java" / package).mkdir(parents=True)
    return tmp_path


@pytest.mark.proves("ado2", depth="component")
def test_adoption_writes_what_is_missing_and_keeps_what_is_there(tmp_path):
    """Finishing a partial adoption is the common path, not the exceptional one — and a tool that
    destroys work when run twice is a tool nobody dares run once."""
    first = init(maven(tmp_path))
    # Two things for Java: the config, and the annotation jar — without which a citation cannot
    # be compiled at all, so `@Proves` would be shown in the next steps and be unreachable.
    assert "plumb.toml" in first.written and first.kept == ()

    (tmp_path / "plumb.toml").write_text('adapter = "java"\n# hand-edited\n')
    second = init(tmp_path)

    assert second.written == () and "plumb.toml" in second.kept
    assert "hand-edited" in (tmp_path / "plumb.toml").read_text(), "left exactly as it is"


@pytest.mark.proves("ado2", depth="component")
def test_what_it_writes_is_a_config_the_tool_can_actually_read(tmp_path):
    """A scaffold that emits something the tool then refuses is worse than emitting nothing: the
    adopter cannot tell their project apart from a broken tool."""
    init(maven(tmp_path))
    config = Config.find(tmp_path)

    assert config.adapter == JAVA
    assert config.production == ("com.acme.orders.*",)
    assert config.options["tests"] == "target/test-classes"


def test_the_detected_package_is_the_deepest_one_that_still_covers_everything(tmp_path):
    """Not a story claim — a real defect. Stopping at the first directory emits `com.*`, and the
    observer filters production classes by that pattern, so an over-broad one turns a deliberately
    narrow probe into a whole-program trace."""
    assert detect(maven(tmp_path)).production == ("com.acme.orders.*",)

    two = maven(tmp_path / "two", package="com/acme/orders")
    (two / "src" / "main" / "java" / "com" / "acme" / "billing").mkdir(parents=True)
    assert detect(two).production == ("com.acme.*",), "stops where the tree forks"


@pytest.mark.proves("ado1", depth="component")
@pytest.mark.proves("ado1", depth="component")
def test_a_java_project_is_told_exactly_what_to_paste(tmp_path):
    """The blocker a second adoption hits. `@Proves` is a Java annotation, so it must be on the
    COMPILE classpath or the adopter's test does not compile — and it otherwise appeared only as a
    side effect of a successful run, which cannot happen until something is cited.

    Python needs nothing here; a pytest marker is a string. Plumb does not close that gap by
    editing their build file: an aggregator pom accepts an inert dependency and reports success,
    so the automated version can leave an adopter worse off than the manual one. What it owes them
    instead is the exact text, with no assembly required.
    """
    steps = next_steps(detect(maven(tmp_path)))

    assert "org.plumbspec" in steps and "plumb-annotations" in steps
    assert "<dependency>" in steps and "<scope>test</scope>" in steps, "complete, not a fragment"
    assert "testImplementation" in steps, "and the Gradle line, since detection accepts Gradle too"
    assert "install:install-file" not in steps, "the pre-Central workaround is gone"


@pytest.mark.proves("dev07-1-1", depth="unit")
def test_each_build_tool_is_told_how_to_produce_its_own_classpath(tmp_path):
    """`plumb init` has accepted Gradle since detection did, and told every Java project to run a
    Maven command — which is not a smaller answer for a Gradle project, it is no answer.

    The two instructions are not variants of each other. Maven cannot hand over its own test
    runtime, so the classpath is reconstructed and every reconstruction can be short of it. Gradle
    can, so the honest instruction there is to stop reconstructing (`dev07-1-1`).
    """
    from plumb.scaffold import detect, next_steps

    with_maven = next_steps(detect(maven(tmp_path / "m")))
    assert "dependency:build-classpath" in with_maven
    assert "sourceSets" not in with_maven

    (tmp_path / "g" / "src" / "main" / "java").mkdir(parents=True)
    (tmp_path / "g" / "build.gradle").write_text("plugins { id 'java' }\n")
    with_gradle = next_steps(detect(tmp_path / "g"))

    assert "sourceSets.test.runtimeClasspath" in with_gradle, "Gradle's own test runtime, borrowed"
    assert "dependency:build-classpath" not in with_gradle, "and not a Maven command"
    assert "build/resources/test" in with_gradle, \
        "and why it matters — Gradle keeps resources out of the class directories"


@pytest.mark.proves("ado1", depth="unit")
def test_nothing_is_written_into_a_java_project_beyond_its_config(tmp_path):
    """`plumb init` earns the right to be run on somebody's repository by touching almost nothing.

    One config file it owns, and no jar, no `.plumb/`, no edit to their build, and **no source file
    in a language they do not use**. That last one was the expensive part: this project once wrote
    six Python modules into a Java repository, carrying gates that could not run and a spec the
    board could not read.
    """
    root = maven(tmp_path)
    (root / "pom.xml").write_text("<project><dependencies></dependencies></project>\n")
    before = (root / "pom.xml").read_text()

    outcome = init(root)

    assert outcome.written == ("plumb.toml",), \
        f"wrote more than its own config: {outcome.written}"
    assert not list(root.rglob("*.py")), "and nothing in a language this project does not use"
    assert (root / "pom.xml").read_text() == before, "their build file is untouched"
    assert not (root / ".plumb").exists(), "no jar planted in their tree"


@pytest.mark.proves("ado3", depth="component")
def test_adoption_ends_by_saying_what_to_do_next_in_commands(tmp_path):
    """A capability nobody is told to reach for is a capability nobody uses. The difference
    between handing someone a directory and handing them a method they can continue."""
    steps = next_steps(detect(maven(tmp_path)))

    assert "plumb board" in steps
    assert "@Proves" in steps, "in the language they are actually writing"
    assert "entry_points" in steps
    assert "dependency:build-classpath" in steps, "the step Java cannot start without"


@pytest.mark.proves("ado3", depth="unit")
def test_a_python_project_is_told_python_things(tmp_path):
    (tmp_path / "src" / "myapp").mkdir(parents=True)
    (tmp_path / "src" / "myapp" / "__init__.py").touch()
    found = detect(tmp_path)

    assert found.adapter == PYTHON and found.production == ("src/myapp",)
    assert "pytest.mark.proves" in next_steps(found)


@pytest.mark.proves("ado3", depth="unit")
def test_what_it_could_not_work_out_is_said_rather_than_guessed(tmp_path):
    """A config that looks complete and is wrong costs more than one visibly unfinished."""
    notes = " ".join(detect(maven(tmp_path)).notes)
    assert "entry_points is empty" in notes
    assert "classpath_file must exist" in notes


# ---- the install answers for itself ---------------------------------------------------------

@pytest.mark.proves("ado1", depth="component")
def test_the_installed_artifact_says_which_version_it_is(capsys):
    """Asked, the tool names itself. Until this existed the answer was an argument-parsing error —
    the first thing Plumb ever said to a first-time user was that it did not understand the
    question. It is also the only route to the version on a machine that installed from a rolling
    `latest` URL, which is every machine: a friction record or a defect report against an
    unidentifiable build lands the ambiguity on the maintainer rather than the filer."""
    from plumb import __version__
    from plumb.cli import build_parser

    with pytest.raises(SystemExit) as exited:
        build_parser().parse_args(["--version"])

    assert exited.value.code == 0, "asking what it is, is not an error"
    assert __version__ in capsys.readouterr().out


@pytest.mark.proves("dev07-1-4", depth="component")
def test_a_failed_helper_reports_why_and_not_only_that_it_failed(monkeypatch):
    """`dev07-1-4` is degrade-and-surface, and half of it was missing. A consumer's first cold CI run
    reported `observer failed (1)` and nothing else. The JVM had already written its exception to
    stderr — this captured it and never read it — so the one artifact naming the cause was
    produced and thrown away, on a runner whose workspace leaves with it. Diagnosing it meant
    reconstructing the run by hand, off the machine that had been told the answer."""
    import subprocess

    from plumb import launch

    trace = ('Exception in thread "main" java.io.IOException: could not attach to the observed '
             'JVM at 127.0.0.1:58657\n\tat org.plumbspec.Observer.attach(Observer.java:309)')
    monkeypatch.setattr(launch.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a[0], 1, "", trace))
    said = []

    launch._run("java", [], cwd=Path("."), say=said.append, what="observer")

    assert any("observer failed (1)" in line for line in said), "the failure must not be silent"
    assert any("could not attach" in line for line in said), "the reason was captured and dropped"
    assert any("Observer.java:309" in line for line in said), "the trace is the diagnosis"


@pytest.mark.proves("ado1", depth="component")
def test_a_missing_adapter_names_plumbs_install_and_not_the_project(tmp_path, monkeypatch):
    """`_bundled` returned "" for an install layout that does not carry the jar, the entry was
    dropped from the classpath, and a JVM launched without its main class exited 1 in 0.127s —
    reported as `observer failed (1)` against a project that was entirely correct."""
    from plumb import launch

    monkeypatch.setattr(launch, "_bundled_jar", lambda: "")
    (tmp_path / "classes").mkdir()
    config = Config(root=tmp_path, adapter=JAVA,
                    options={"classpath": "classes", "tests": "classes"})

    with pytest.raises(launch.LaunchFailed) as refused:
        launch._classpath(config)

    message = str(refused.value)
    assert "Plumb's installation, not your project" in message, "the adopter must not debug theirs"
    assert "install.sh" in message or "PLUMB_JAVA_CLASSPATH" in message, "name the repair"


@pytest.mark.proves("ado1", depth="component")
def test_a_project_supplying_the_adapter_itself_is_not_refused(tmp_path, monkeypatch):
    """Relative entries resolve against the project root, because that is the JVM's working
    directory. Checking them against Plumb's own would refuse a working project — a worse
    failure than the one this prevents, and the reference project is entirely relative."""
    from plumb import launch

    monkeypatch.setattr(launch, "_bundled_jar", lambda: "")
    supplied = tmp_path / "adapter" / "org" / "plumbspec"
    supplied.mkdir(parents=True)
    (supplied / "PlumbRunner.class").touch()
    config = Config(root=tmp_path, adapter=JAVA,
                    options={"classpath": "adapter", "tests": "adapter"})

    assert "adapter" in launch._classpath(config)


@lru_cache(maxsize=1)
def _the_built_artifact() -> Path:
    """The artifact these tests exercise, **rebuilt before it is read**.

    They are the only tests that reach the packaged form, so what they read has to be this tree.
    Reading whatever pyz happened to be on disk made them vouch for code nobody was running:
    measured, `dist/plumb.pyz` was four sessions old, missing three modules entirely, and both
    tests passed against it. Green, and proving nothing.

    Comparing and failing was the first fix and it was worse in practice — editing anything under
    `src/plumb/` left two standing failures for the rest of the session, and a check that is red
    all afternoon is one people learn to scroll past. Rebuilding removes the question instead of
    reporting it, which is what `release.py`'s `check_docs` already does for the identical problem:
    it once scraped the artifact as found, so every flag added since the last build read as
    nonexistent — a verdict that depended on what was on disk rather than on the tree.

    Built once per session, and the checksums with it, so nothing here leaves `dist/` holding a
    `SHA256SUMS` that describes a different artifact.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
    from build_artifact import build, checksums

    try:
        artifact = build()
    except SystemExit as why:
        # The Java jars are built by `mvn -f adapters/java/pom.xml package` and are not in a fresh checkout.
        # Skipped rather than failed: nothing about the tree is wrong, the toolchain is absent.
        pytest.skip(f"cannot build the artifact — {why}")
    checksums(artifact)
    return artifact




@pytest.mark.proves("dev07-1-3", depth="component")
def test_an_instrument_that_reached_nothing_says_so_rather_than_reporting_a_clean_run():
    """`dev07-1-3`'s requirement outlived its cause.

    It was written about an observer dying: a second process on a socket, and `not-checked` meaning
    *the instrument failed* rather than *nobody declared anything*. There is no observer now
    (`dev07-1-3`) and nothing to die — but the instrument can still fail to reach a project, by
    matching no class or by having its classes excluded with the test root, and that produces the
    same word from the same absence. One word, two causes, and the reader's next move differs: from
    `dev07-1-4` declare entry points, from here look at where your production classes live.

    The failure mode this refuses is the flattering one. With nothing instrumented every fact is
    read from an absence, so a board would report `inert` everywhere and prove every structural
    story on the strength of nobody looking.
    """
    from plumb import launch

    assert launch.NOTHING_INSTRUMENTED, "the launcher has to have a prefix to match on"
    runner = (Path(__file__).resolve().parent.parent / "adapters" / "java" / "adapter" / "src"
              / "main" / "java" / "org" / "plumbspec" / "PlumbRunner.java").read_text()
    assert launch.NOTHING_INSTRUMENTED.removeprefix("plumb: ") in runner, (
        "the prefix lives in two files — the runner that prints it and the launcher that reads it — "
        "and nothing but this holds them together")
    assert "not-checked" in (Path(__file__).resolve().parent.parent / "adapters" / "java" / "adapter"
                             / "src" / "main" / "java" / "org" / "plumbspec"
                             / "PlumbListener.java").read_text(), (
        "and the fact it produces has to be the honest one: a question nobody could answer, not a "
        "claim about the project")



def reactor(root: Path, *modules: str) -> Path:
    """A Maven reactor: an aggregator pom naming modules, each with compiled output."""
    root.mkdir(parents=True, exist_ok=True)
    named = "".join(f"<module>{m}</module>" for m in modules)
    (root / "pom.xml").write_text(
        '<project xmlns="http://maven.apache.org/POM/4.0.0">'
        f"<artifactId>app-parent</artifactId><modules>{named}</modules></project>")
    for module in modules:
        here = root / module
        (here / "target" / "classes").mkdir(parents=True)
        (here / "target" / "classes" / "Thing.class").write_bytes(b"\xca\xfe\xba\xbe")
        (here / "pom.xml").write_text(
            '<project xmlns="http://maven.apache.org/POM/4.0.0">'
            f"<artifactId>{module}</artifactId></project>")
    return root


@pytest.mark.proves("dev07-1-1", depth="component")
def test_a_reactor_module_missing_from_the_classpath_refuses_the_run(tmp_path):
    """`dependency:build-classpath` resolves DEPENDENCIES, so a module of the adopter's own comes
    back as whatever is installed in `~/.m2` — or as nothing — while Surefire uses the classes it
    has just compiled.

    Measured: a secondary tier of Flyway migrations existed for the build tool's run and not for the
    observed one, failing a Spring context that boots green. Every such divergence arrives as a test
    that fails under Plumb and passes under the build, which reads as the project's defect and is
    the observation's.
    """
    from plumb.config import Config
    from plumb.launch import LaunchFailed, _classpath_parity

    root = reactor(tmp_path, "core", "web")
    config = Config.parse('adapter = "java"\n', root=root)
    only_one = f"{root / 'core' / 'target' / 'classes'}:/somewhere/junit.jar"

    with pytest.raises(LaunchFailed) as refused:
        _classpath_parity(config, only_one, lambda line: None)

    said = str(refused.value)
    # The DIAGNOSIS only. The remedy below it names every output directory in the order the build
    # runs them, because a classpath is a whole thing and half of one cannot be pasted — but what
    # this run is *missing* has to be the missing one alone, or the reader is sent to a directory
    # that was never the problem.
    diagnosis = said.split("mvn -q")[0]
    assert "web/target/classes" in diagnosis, "it names the module that would not have been observed"
    assert "core/target/classes" not in diagnosis, "and not the one that is already there"
    assert "check_classpath = false" in said, "and how to proceed anyway, knowing what it costs"


@pytest.mark.proves("dev07-1-1", depth="component")
def test_a_classpath_with_the_build_outputs_out_of_order_is_refused(tmp_path):
    """Two classpaths with equal members are not the same classpath.

    Maven copies `src/main/resources` into `target/classes` and `src/test/resources` into
    `target/test-classes`, so a project can hold `application.properties` in both — and the
    classpath decides which the suite loads. Surefire puts test outputs first. A guard comparing
    membership passes a classpath that silently runs the production configuration.

    Measured, and this tool caused it: the remedy this guard printed said to APPEND the
    output directories, yielding `deps:classes:test-classes`. The main properties shadowed the test
    ones, a Flyway location vanished, the shared Spring context died, and every `@SpringBootTest`
    citation sharing it read *did not pass* for tests that are green under Surefire. A gate whose
    own instruction manufactures the divergence it exists to prevent is worse than no gate: it is
    the failure, delivered with a reassurance.
    """
    from plumb.config import Config
    from plumb.launch import LaunchFailed, _classpath_parity

    root = reactor(tmp_path, "web")
    (root / "web" / "target" / "test-classes").mkdir(parents=True)
    (root / "web" / "target" / "test-classes" / "ThingTest.class").write_bytes(b"\xca\xfe\xba\xbe")
    config = Config.parse('adapter = "java"\n', root=root)

    main = str((root / "web" / "target" / "classes").resolve())
    test = str((root / "web" / "target" / "test-classes").resolve())

    # Both present, test first: Surefire's own order.
    _classpath_parity(config, f"{test}:{main}", lambda line: None)

    # Both present, main first — every member the set-comparison wanted, and the wrong run.
    with pytest.raises(LaunchFailed) as refused:
        _classpath_parity(config, f"{main}:{test}", lambda line: None)
    said = str(refused.value)
    assert "wrong order" in said, "it says the members are right and the order is not"
    assert "test outputs must come first" in said, "and which way round they go"
    assert "check_classpath = false" in said, "and how to proceed anyway"


@pytest.mark.proves("dev07-1-1", depth="unit")
def test_the_remedy_prepends_in_the_order_the_build_runs():
    """The hint is generated from the directories the project actually builds, in runtime order.

    It used to say *append each directory above*, which leaves the reader to choose an order — and
    is how the wrong one gets chosen. A remedy that can be pasted has to be the whole classpath,
    already ordered, because that ordering is the thing being corrected.
    """
    from plumb.launch import _maven_fix

    remedy = _maven_fix([(Path("web/target/test-classes"), "web"),
                         (Path("web/target/classes"), "web")])
    assert ">>" not in remedy, (
        "the remedy still appends — appending puts the dependencies first and the build's own "
        "outputs last, which is the order that shadows the test resources")
    assert remedy.index("test-classes") < remedy.index("web/target/classes"), \
        "test outputs before main outputs, which is the order Surefire runs"
    assert "plumb-deps.txt" in remedy and "> target/plumb-classpath.txt" in remedy, \
        "and it writes a whole classpath rather than editing one in place"


@pytest.mark.proves("dev07-1-1", depth="component")
def test_a_module_answered_by_an_installed_jar_says_so(tmp_path):
    """"Add this directory" and "your classpath is serving you a stale jar of your own module" send
    a reader to two different places, and only one of them is where the problem is."""
    from plumb.config import Config
    from plumb.launch import LaunchFailed, _classpath_parity

    root = reactor(tmp_path, "core")
    config = Config.parse('adapter = "java"\n', root=root)

    with pytest.raises(LaunchFailed) as refused:
        _classpath_parity(config, "/home/me/.m2/repository/com/acme/core/1.2.0/core-1.2.0.jar",
                          lambda line: None)

    assert "answered instead by" in str(refused.value)
    assert "core-1.2.0.jar" in str(refused.value)


@pytest.mark.proves("dev07-1-1", depth="component")
def test_a_run_wider_than_the_build_is_not_refused(tmp_path):
    """A run narrower than the build's manufactures failures the build does not have. A wider one
    cannot, so it is left alone — `dev07-5-1`, applied to the thing doing the checking."""
    from plumb.config import Config
    from plumb.launch import _classpath_parity

    root = reactor(tmp_path, "core")
    config = Config.parse('adapter = "java"\n', root=root)
    said = []

    _classpath_parity(config, f"{root / 'core' / 'target' / 'classes'}:/extra/thing.jar",
                      said.append)

    assert any("parity ok" in line for line in said)


@pytest.mark.proves("dev07-1-1", depth="component")
def test_a_project_with_no_build_tool_is_asked_nothing(tmp_path):
    """The check holds the run against what a build tool declares. Where nothing declares one there
    is no second answer to hold it against, and inventing one would be this check asserting a
    convention rather than reading a fact.

    Narrower than it reads: *not Maven* is not the same as *no build tool*, and writing this test
    as the former is what left Gradle silently unchecked while `plumb init` was accepting it.
    """
    from plumb.config import Config
    from plumb.launch import _classpath_parity

    (tmp_path / "build").mkdir()
    config = Config.parse('adapter = "java"\n', root=tmp_path)
    said = []

    _classpath_parity(config, "build/classes", said.append)

    assert said == [], "nothing to say about a question that does not arise"


@pytest.mark.proves("dev07-1-1", depth="component")
def test_the_check_can_be_turned_off_and_says_that_it_was(tmp_path):
    """Refusing is right and it is not infallible. What is not offered is turning it off quietly:
    a board whose run is not the build's must read as one."""
    from plumb.config import Config
    from plumb.launch import _classpath_parity

    root = reactor(tmp_path, "core")
    config = Config.parse('adapter = "java"\n\n[java]\ncheck_classpath = false\n', root=root)
    said = []

    _classpath_parity(config, "/somewhere/junit.jar", said.append)

    assert any("not checked" in line for line in said)


def gradle(root: Path, *projects: str, kotlin_dsl: bool = False) -> Path:
    """A Gradle build with compiled classes and test resources, in Gradle's own layout."""
    root.mkdir(parents=True, exist_ok=True)
    suffix = ".kts" if kotlin_dsl else ""
    listed = "".join(f'include("{p}")\n' if kotlin_dsl else f"include ':{p}'\n" for p in projects)
    (root / f"settings.gradle{suffix}").write_text(
        ('rootProject.name = "app"\n' if kotlin_dsl else "rootProject.name = 'app'\n") + listed)
    (root / f"build.gradle{suffix}").write_text("plugins { id 'java' }\n")
    for project in projects:
        here = root / project
        for phase in ("main", "test"):
            classes = here / "build" / "classes" / "java" / phase
            classes.mkdir(parents=True)
            (classes / "Thing.class").write_bytes(b"\xca\xfe\xba\xbe")
        migrations = here / "build" / "resources" / "test" / "db" / "migration"
        migrations.mkdir(parents=True)
        (migrations / "V2__extra.sql").write_text("create table x();")
    return root


def gradle_classes(root: Path, *projects: str) -> str:
    """Only the compiled classes — the classpath a reconstruction actually produces."""
    return ":".join(str(root / p / "build" / "classes" / "java" / phase)
                    for p in projects for phase in ("main", "test"))


@pytest.mark.proves("dev07-1-1", depth="component")
def test_gradle_resources_left_off_the_classpath_refuse_the_run(tmp_path):
    """**Gradle keeps resources apart from classes**, and that is why this matters more here than
    under Maven, which copies them in beside the code.

    `build/resources/test` is its own classpath entry, so a classpath assembled out of the compiled
    class directories alone loses every migration, fixture and property file the suite loads — by
    default, on a conventional project, rather than as an edge case. That is the measured failure
    (a secondary Flyway migration tier) arriving as the ordinary outcome.
    """
    from plumb.config import Config
    from plumb.launch import LaunchFailed, _classpath_parity

    root = gradle(tmp_path, "core")
    config = Config.parse('adapter = "java"\n', root=root)

    with pytest.raises(LaunchFailed) as refused:
        _classpath_parity(config, gradle_classes(root, "core"), lambda line: None)

    said = str(refused.value)
    assert "core/build/resources/test" in said, "the resources the suite loads and this run cannot"
    assert "core/build/classes/java/test" not in said, "and not what is already there"
    assert "sourceSets.test.runtimeClasspath" in said, \
        "and Gradle is told to hand over its own runtime rather than to patch a reconstruction"


@pytest.mark.proves("dev07-1-1", depth="component")
def test_a_gradle_subproject_missing_entirely_is_named(tmp_path):
    """`include` is how Gradle says a project exists. A classpath carrying one of two subprojects
    is answering for a subset of the build while presenting itself as answering for all of it."""
    from plumb.config import Config
    from plumb.launch import LaunchFailed, _classpath_parity

    root = gradle(tmp_path, "core", "web")
    config = Config.parse('adapter = "java"\n', root=root)
    everything_of_one = ":".join([gradle_classes(root, "core"),
                                  str(root / "core" / "build" / "resources" / "test")])

    with pytest.raises(LaunchFailed) as refused:
        _classpath_parity(config, everything_of_one, lambda line: None)

    said = str(refused.value)
    assert "web/build/classes/java/main" in said
    assert "core/" not in said, "the project that is fully present is not part of the complaint"


@pytest.mark.proves("dev07-1-1", depth="component")
def test_the_kotlin_dsl_declares_projects_the_same_way(tmp_path):
    """`settings.gradle.kts` is not a dialect this can afford to be blind to: reading only the
    Groovy form would report a multi-project Kotlin build as a single project, which is the exact
    shape of silence this check exists to end."""
    from plumb.config import Config
    from plumb.launch import LaunchFailed, _classpath_parity

    root = gradle(tmp_path, "core", kotlin_dsl=True)
    config = Config.parse('adapter = "java"\n', root=root)

    with pytest.raises(LaunchFailed) as refused:
        _classpath_parity(config, gradle_classes(root, "core"), lambda line: None)

    assert "core/build/resources/test" in str(refused.value)


@pytest.mark.proves("dev07-1-1", depth="component")
def test_a_gradle_build_with_everything_on_the_classpath_passes(tmp_path):
    """It has to be quiet on a healthy build, or it is a standing refusal people turn off."""
    from plumb.config import Config
    from plumb.launch import _classpath_parity

    root = gradle(tmp_path, "core")
    config = Config.parse('adapter = "java"\n', root=root)
    whole = ":".join([gradle_classes(root, "core"),
                      str(root / "core" / "build" / "resources" / "test")])
    said = []

    _classpath_parity(config, whole, said.append)

    assert any("parity ok" in line for line in said)


@pytest.mark.proves("dev07-1-1", depth="component")
def test_an_output_directory_the_build_never_wrote_is_not_demanded(tmp_path):
    """Gradle's layout is a convention, not a promise that every phase exists. A project with no
    test resources has no `build/resources/test`, and demanding one would refuse a healthy build
    for the shape of somebody else's."""
    from plumb.config import Config
    from plumb.launch import _classpath_parity

    root = gradle(tmp_path, "core")
    import shutil
    shutil.rmtree(root / "core" / "build" / "resources")
    config = Config.parse('adapter = "java"\n', root=root)
    said = []

    _classpath_parity(config, gradle_classes(root, "core"), said.append)

    assert any("parity ok" in line for line in said)


@pytest.mark.proves("dev08", depth="unit")
def test_the_plugin_stays_hashable_so_a_runner_may_hold_it_in_a_set():
    """A plain `@dataclass` generates `__eq__`, which sets `__hash__ = None`.

    A pytest that keeps its plugins in a set then dies with `TypeError: unhashable type:
    PlumbAdapter` — twenty frames down, under a headline telling the reader to fix their own suite.
    Measured on a system pytest 8.3.5, where the first minutes went on `pytest.ini`.

    Identity equality is what a plugin wants anyway: the session holds one, and nothing here has
    ever compared two.
    """
    from plumb.adapters.python.adapter import PlumbAdapter

    assert hash(PlumbAdapter()) is not None
    assert PlumbAdapter() != PlumbAdapter(), "two plugins are two plugins, not one value"
    assert len({PlumbAdapter(), PlumbAdapter()}) == 2, "a set of them is a set, not a collision"


@pytest.mark.proves("dev07-5-1", depth="component")
def test_an_internal_runner_error_is_not_reported_as_the_project_s_fault():
    """`pytest exit 3` is **pytest crashing**, and never a test failing.

    Every aborted status got one sentence — *fix the run first; the runner's own output above says
    why* — which sends somebody to read their own conftest for a fault in the pair of programs
    above it. The runner's version is named because it is half of that pair and the half nobody
    thinks to check: Plumb runs under the interpreter the project declares, which is routinely not
    the one Plumb was installed into.
    """
    import pytest as runner

    from plumb.adapters.python.adapter import _whose_fault

    crashed = _whose_fault(runner.ExitCode.INTERNAL_ERROR)
    assert "not your suite" in crashed
    assert runner.__version__ in crashed, "the runner's version, which is half the pair"
    assert "[python] interpreter" in crashed, "and where that runner came from"

    misused = _whose_fault(runner.ExitCode.USAGE_ERROR)
    assert "refused its own arguments" in misused
    assert "not your suite" not in misused, "a usage error is ours or theirs, and it says which"

    stopped = _whose_fault(runner.ExitCode.INTERRUPTED)
    assert "Fix the run first" in stopped, "a killed or uncollectable run is still the run's"


@pytest.mark.proves("ado2", depth="unit")
def test_the_written_config_carries_no_note_that_acting_on_it_makes_false(tmp_path):
    """`plumb init`'s notes describe the moment it looked, and the config is what then changes.

    A `plumb.toml` said *entry_points is empty* above two named entry points and *add
    junit-platform-launcher* above a pom that declared it: every instruction had been followed and
    the file still said it had not. The notes are printed instead, where being about a moment is
    what they are for.
    """
    found = detect(maven(tmp_path))
    assert found.notes, "this Java project should detect something still to do, or it checks nothing"

    written = render(found)
    for note in found.notes:
        assert note not in written, (
            f"`plumb init` wrote a note into the config it is describing: {note!r} — acting on it "
            "is what makes it false, and the file is where the adopter looks to learn otherwise")
    assert "Still to do" not in written


def test_init_reports_against_the_file_it_kept_and_not_against_a_fresh_project(tmp_path):
    """`plumb init` is a command an adopter runs again, so it has to read what they did.

    `detect` reads the filesystem and never the config, because its job is to propose one — so
    every note it carries describes a project that has declared nothing. Observed: `still to do:
    entry_points is empty` printed directly above a file naming two, on the same run that said
    `kept plumb.toml (left exactly as it is)`. The one command an adopter runs to find out whether
    they are set up told them they were not, about the file it had just read and declined to change.
    """
    from plumb.scaffold import init

    (tmp_path / "src" / "app").mkdir(parents=True)
    (tmp_path / "src" / "app" / "__init__.py").write_text("")

    fresh = init(tmp_path)
    assert any("entry_points is empty" in note for note in fresh.detected.notes), (
        "a project that has declared nothing should be told so — this is the note's real job")

    (tmp_path / "plumb.toml").write_text(
        'production   = ["src/app"]\nentry_points = ["app.main:run"]\n')

    again = init(tmp_path)
    assert "plumb.toml" in again.kept, "the existing declaration must be left exactly as it is"
    assert again.detected.entry_points == ("app.main:run",), (
        "init did not read the entry points the project declares, so everything it says about "
        "them is about a project that is not this one")
    assert not any("entry_points is empty" in note for note in again.detected.notes), (
        f"init still reports an empty entry_points over a file naming one: {again.detected.notes}")

    from plumb.scaffold import next_steps
    assert "Name where your wired system begins" not in next_steps(again.detected), (
        "the numbered steps still open with a step this project has taken")
