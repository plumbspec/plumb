"""The other runtime, exercised — the language boundary (`dev07-3-3`).

**Two hundred green tests once said nothing about whether Java worked.** Renaming the Java package
from `plumb` to `org.plumbspec` passed every one of them while the adapter was completely broken:
four class names live in string literals rather than imports, so `javac` could not see them and the
Python side is text. The symptom was a **hang** — the observer died and the suite sat suspended at
`-agentlib:jdwp=…suspend=y` waiting for a debugger that never attached — and a manifest was still
written, with zero citations.

A cross-language rename is not type-checked at the seam, because the seam is a string. So this file
holds the two correctives the record names: the **narrow** one, that every identifier crossing the
launcher-to-adapter boundary resolves to something real, and the **general** one, that the count
that matters is how many tests exercise the *other* runtime — which was zero.
"""

import inspect
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
JAVA = REPO / "adapters" / "java"
SOURCES = JAVA / "adapter" / "src" / "main" / "java" / "org" / "plumbspec"

def declared_package() -> str:
    """The package the Java sources actually declare — the one place this is a fact.

    Read rather than written down here, because a constant naming the package would be a third
    spelling of the thing whose second spelling is the defect.
    """
    found = re.search(r"^package ([\w.]+);", (SOURCES / "PlumbRunner.java").read_text(), re.M)
    assert found, "the observer declares no package; this scan has nothing to hold anything to"
    return found.group(1)


def qualified_uses(paths, classes: set[str]) -> dict[str, set[str]]:
    """Every ``<package>.<Class>`` or ``<package>/<Class>`` spelled in these files, by package.

    Matched on the **class** and not on the package, which is the whole point: a rename moves the
    package, so a scan anchored to the package stops seeing the thing that broke.
    """
    # `/` belongs in the package group as well as in the separator: the launcher spells one of
    # these as a path inside a jar — `org/plumbspec/PlumbRunner.class` — and a package group that
    # matched only dots read that as the package `plumbspec`.
    pattern = re.compile(r"([\w./]+)[./](" + "|".join(sorted(classes)) + r")\b")
    found: dict[str, set[str]] = {}
    for path in paths:
        for package, name in pattern.findall(path.read_text()):
            found.setdefault(package.replace("/", "."), set()).add(f"{name} in {path.name}")
    return found


def test_every_java_class_named_across_the_seam_carries_the_package_java_declares():
    """The narrow corrective: one place says what the package is, and both sides are held to it.

    Anchored to the **class names**, not to the package — a first version scanned for
    `org.plumbspec.X` and would have missed the defect it was written for, because renaming the
    package means the pattern stops matching rather than starts failing. Reproduced: pointing the
    launcher at `plumb.PlumbRunner` left this scan finding nothing to complain about.
    """
    package = declared_package()
    classes = {p.stem for p in SOURCES.glob("*.java")} | \
              {p.stem for p in (JAVA / "annotations").rglob("*.java")}
    assert len(classes) > 5, "the adapter has sources; finding almost none means this scan broke"

    seen = qualified_uses(sorted((REPO / "src" / "plumb").rglob("*.py")) +
                          sorted(SOURCES.glob("*.java")), classes)
    assert seen, "nothing names a Java class across the seam, which cannot be true"

    wrong = {where: named for where, named in seen.items() if where != package}
    assert not wrong, (
        f"the Java sources declare `package {package};` and these name the same classes under a "
        f"different one — the compiler cannot see either side of that, so the break arrives as a "
        f"hang rather than as a failure: {wrong}")


@pytest.mark.proves("dev07-1-3", depth="unit")
def test_every_probe_the_advice_calls_is_one_the_flag_declares():
    """The agent writes references to `PlumbFlag` into somebody else's bytecode; the listener reads
    what they set. Neither side imports the other — an advice spells the owner as an internal name
    in a string it puts into a constant pool — so if the two drift, the probe writes to a field
    nobody reads or calls a method that is not there. The first is silent: every test grounds as
    though it ran nothing, and the suite passes and the manifest writes exactly as they would have
    anyway. The second is a `NoSuchMethodError` inside instrumented production code.

    Checked over *every* member the pointcut asks for rather than the two this test was first
    written against. `dev07-1-3` made adding an advice cheap, which makes adding a member to this seam
    cheap, and a seam check that has to be extended by hand each time is one that will be right
    until the first time it matters.
    """
    advice = (SOURCES / "Advice.java").read_text()
    assert '"org/plumbspec/PlumbFlag"' in advice, (
        "the owner is spelled as an internal name in full, or the reference resolves to nothing")

    flag = (SOURCES / "PlumbFlag.java").read_text()
    pointcut = (SOURCES / "Pointcut.java").read_text()

    # What the pointcut names, by the advice kind that carries it — the argument of each
    # `Advice.flag(...)` / `signal(...)` / `report(...)` it hands the weaver.
    fields = set(re.findall(r"Advice\.flag\(\"(\w+)\"", pointcut))
    calls = set(re.findall(r"Advice\.signal\(\"(\w+)\"", pointcut))
    reports = set(re.findall(r"Advice\.report\(\"(\w+)\"", pointcut))
    assert fields and calls and reports, (
        "no advice was found in the pointcut at all — this check reads it by shape, and the shape "
        "has changed"
    )

    for field in fields:
        assert f"public static volatile boolean {field};" in flag, (
            f"the pointcut stores into `PlumbFlag.{field}` and the probe does not declare it — a "
            f"store nothing reads is how every test grounds as though it ran nothing")
    for method in calls:
        assert f"public static void {method}()" in flag, (
            f"the pointcut calls `PlumbFlag.{method}()` and the probe does not declare it")
    for method in reports:
        assert f"public static void {method}(String " in flag, (
            f"the pointcut calls `PlumbFlag.{method}(String)` and the probe does not declare it")

    # The two advices that carry a reference across the seam, and the only ones whose SIGNATURE is
    # part of it: one takes the receiver, one takes an argument and hands back what replaces it.
    # A mismatch here is a `NoSuchMethodError` inside an instrumented JDK class — every
    # `Thread.start` in the VM, or every task any pool is given.
    for method, kind in re.findall(r"Advice\.passReceiver\(\"(\w+)\", \"([\w/]+)\"", pointcut):
        assert f"public static void {method}({kind.rsplit('/', 1)[-1]} " in flag, (
            f"the pointcut hands the receiver to `PlumbFlag.{method}({kind})` and the probe does "
            "not declare it with that parameter")
    for _, method, kind in re.findall(
            r"Advice\.replaceArgument\((\d+), \"(\w+)\", \"([\w/]+)\"", pointcut):
        short = kind.rsplit("/", 1)[-1]
        assert f"public static {short} {method}({short} " in flag, (
            f"`PlumbFlag.{method}` must take AND return {short}: the advice stores the result back "
            "into the argument slot, so a different type would leave every stack-map frame that "
            "mentions that local disagreeing with what is in it")

    # The exit join point is woven by generating a method, not by an advice, so it is named here.
    assert "public static void left()" in flag, (
        "`dev07-1-3`'s wrapper closes the window with `left()`, and a window that opens and never "
        "closes scopes every later test's mutation to whatever the first one drove")

    listener = (SOURCES / "PlumbListener.java").read_text()
    assert "PlumbFlag.ran" in listener and "PlumbFlag.enteredOn" in listener, (
        "the listener has to read what the agent writes, or grounding is decided by a field that "
        "nothing sets")
    assert "PlumbFlag.wiredHere()" in listener, (
        "and the mutation scope has to be read out of the window before it closes, or chapter 4 "
        "mutates nothing and reports the project clean")


def _work() -> Path:
    """Where a board over the reference project puts its run file and manifest.

    **Asked of the tool rather than assumed.** These were spelled `build/plumb` here, which was true
    only while the Java adapter wrote inside the adopter's tree — the thing `dev00-1-2` refuses, and the
    disagreement with the Python adapter that nothing caught until the two were asked the same
    question. A test that spells the answer out is a test that has to be edited when the answer
    moves, which is how it comes to be the last thing still asserting the old one.
    """
    sys.path.insert(0, str(REPO / "src"))
    from plumb.config import Config
    from plumb.launch import _scratch

    return _scratch(Config.find(JAVA))


def adapter_is_built() -> bool:
    return (JAVA / "adapter" / "target" / "classes" / "org" / "plumbspec" / "PlumbRunner.class").is_file()


needs_jvm = pytest.mark.skipif(
    shutil.which("java") is None or not adapter_is_built(),
    reason="needs a JDK and `mvn -f adapters/java/pom.xml package` to have run")


@needs_jvm
@pytest.mark.proves("dev07-1-3", depth="unit")
def test_the_bootstrap_probe_compiles_to_one_class_and_no_other():
    """`PlumbFlag` ships as its own jar on the bootstrap class path, and must be self-contained.

    An instrumented JDK class resolves the probe through the bootstrap loader or not at all, so a
    loader that finds `PlumbFlag` and not something it references fails during the agent's premain
    — which is a FATAL VM error before a line of the suite runs, not a missing fact. An anonymous
    `ThreadLocal` subclass produced `PlumbFlag$1` and did exactly that; a lambda produces a hidden
    class the bootstrap loader has to define at agent startup.

    The file has carried *no inner classes, no lambdas* as a comment since the first of those was
    fixed, and the rule was broken again within the hour by an `updateAndGet(n -> …)` that reads
    like ordinary Java. A rule with no gate behind it is a rule that will be broken by whoever did
    not write it — including whoever did.

    Checked on the COMPILED OUTPUT rather than the source, because that is where the rule actually
    binds: what matters is how many class files javac emitted, whatever the source looked like.
    """
    compiled = sorted((JAVA / "adapter" / "target" / "classes" / "org" / "plumbspec").glob("PlumbFlag*.class"))
    assert compiled, "the adapter must be built before this can say anything"
    assert [c.name for c in compiled] == ["PlumbFlag.class"], (
        "PlumbFlag compiled to more than one class file, so something in it is an inner class or "
        f"a lambda: {[c.name for c in compiled]}. The bootstrap loader gets the jar this test "
        "guards, and a reference it cannot resolve kills the VM during premain")

    boot = JAVA / "build" / "plumb-boot.jar"
    if boot.is_file():
        import zipfile
        held = sorted(n for n in zipfile.ZipFile(boot).namelist() if n.endswith(".class"))
        assert held == ["org/plumbspec/PlumbCarrier.class", "org/plumbspec/PlumbFlag.class"], (
            f"the boot jar carries {held} — it ships the probe and the task wrapper and nothing "
            "else, because a bootstrap loader that can see the whole adapter defines the runner "
            "there too, where the test framework is not visible. Both are needed: `PlumbCarrier` "
            "is referenced by `PlumbFlag.carry`, and a reference the bootstrap loader cannot "
            "satisfy is a fatal VM error during premain")


@needs_jvm
@pytest.mark.proves("dev07-1-3", depth="smoke")
def test_the_jvm_adapter_runs_a_suite_and_reports_what_it_watched(tmp_path):
    """The general corrective: a test that fails when Java is broken.

    Driven through the command an adopter runs, against the reference Java project, because the
    failure this replaces produced a *manifest* — an empty one — while hanging. Asserting the
    document exists is what the old code could already pass; asserting the facts only a live JDWP
    observer can produce is what it could not.
    """
    manifest = _work() / "manifest.json"
    manifest.unlink(missing_ok=True)

    # A subprocess, and a **timeout**, because the failure this replaces was a hang: the suite sat
    # suspended waiting for a debugger that never attached, so a test that called the launcher
    # in-process would have hung with it and reported nothing.
    done = subprocess.run(
        [sys.executable, "-m", "plumb.cli", "board", "--json", "--project", str(JAVA)],
        capture_output=True, text=True, cwd=REPO, timeout=900,
        env={**os.environ, "PYTHONPATH": str(REPO / "src")})

    assert done.returncode == 0, done.stderr[-3000:]
    assert manifest.is_file(), "the run wrote no manifest at all"
    written = json.loads(manifest.read_text())

    assert written["stories"], (
        "a manifest with no citations is exactly what the broken adapter produced while the suite "
        "hung — the document is not the evidence, what is in it is")
    facts = {c["grounding"] for s in written["stories"].values() for c in s["citations"]}
    assert "grounded" in facts, (
        "no citation grounded, so either the observer never attached or the probe it watches for "
        "is not the one the runner calls")
    assert "dispatched" in facts, (
        "nothing read `dispatched`, so the hand-off breakpoints are not firing — the one fact this "
        "adapter exists to observe from outside the process (`dev07-1-4`)")

    mechanisms = {(c.get("observer") or {}).get("mechanism")
                  for s in written["stories"].values() for c in s["citations"]}
    assert any("probes" in (m or "") for m in mechanisms), \
        "the facts do not name the instrument that made them (`dev07-3-1`)"
    assert not any("none" in (m or "") for m in mechanisms), (
        "the provenance says grounding was not observed on a run that observed it — it is recorded "
        "after the run for exactly this reason, because nothing is instrumented until classes load")


#: What the observer said about each test, off the launcher's own report. Parsed rather than
#: recomputed: the point of both invariants below is what a *reader* is told, and the manifest
#: holds only the cited half of that.
SAID = re.compile(r"^java:\s+(grounded|ungrounded|inert|untouched|dispatched)\s+(\S+)$", re.M)


@pytest.fixture(scope="module")
def mutated_board():
    """One board over the reference Java project, shared by the tests below."""
    # `--tests` because this reads the PER-TEST grounding, which the board now counts rather than
    # recites: on a mature suite the citing tests are a small minority and the recital buries the
    # verdict. The fact is not gone, it is asked for.
    done = subprocess.run(
        [sys.executable, "-m", "plumb.cli", "board", "--json", "--tests", "--project", str(JAVA)],
        capture_output=True, text=True, cwd=REPO, timeout=900,
        env={**os.environ, "PYTHONPATH": str(REPO / "src")})
    assert done.returncode == 0, done.stderr[-3000:]
    return dict((test, fact) for fact, test in SAID.findall(done.stderr))


@needs_jvm
@pytest.mark.proves("dev07-1-4", depth="unit")
def test_a_test_that_touches_no_production_code_reads_untouched(mutated_board):
    """The surface is watched for every test now, so `inert` is answerable for every test.

    It used to be watched only for cited tests, because watching it through the debugger cost so
    much that paying for a verdict nobody would read was the difference between a board and no
    board. `dev07-1-3` removed the cost rather than the coverage, and with it the gate — and gating
    was never free: the first cut of it armed on citation and left `verdictFor` alone, so every
    unwatched test read `inert`, the strongest claim available, asserted exactly where nothing had
    looked.
    """
    said = mutated_board
    uncited = [t for t in said if "UncitedTest" in t]
    assert uncited, "the sample's uncited test is missing, and this checks nothing without it"
    assert all(said[t] == "untouched" for t in uncited), (
        "a test that cites nothing and runs nothing is answered rather than withheld — the agent "
        "watched it like any other. `untouched` and not `inert`: `inert` is the POSITIVE claim "
        "that the artifact was read and none of it run, and this test read nothing either "
        f"(`dev07-4-2`): {[(t, said[t]) for t in uncited]}")
    # **And the mirror**, which is the whole reason `untouched` exists. `inert` is the positive
    # proof a structural story rests on, so something has to still earn it — the structural test
    # reads the class file as bytes and runs none of it, and that is what `inert` means.
    structural = [t for t in said if "StructuralTest" in t]
    assert structural and all(said[t] == "inert" for t in structural), (
        "a test that READS the artifact and runs none of it is `inert`, and if this reads "
        f"`untouched` the read is not being observed at all: {[(t, said[t]) for t in structural]}")
    assert "grounded" in said.values(), "and a test that drives the entry point still grounds"

    # The other half, and the one that fails silently: a test that DID run production code must not
    # read `inert`. The sample compiles production to `target/classes` and tests to `target/test-classes`,
    # so the agent's exclusion is asked a question a bare string prefix gets wrong — `sample-app`
    # starts with `sample` and is not inside it. Getting it wrong excludes production as though it
    # were a test, nothing sets the flag, and every test reads `inert`: the strongest claim, from an
    # instrument that was not running.
    ran_production = [t for t in said if "exercisesCodeNoEntryPointReaches" in t]
    assert ran_production, "the sample's run-production-but-reach-no-entry-point test is missing"
    assert all(said[t] == "ungrounded" for t in ran_production), (
        "a test that called production code read `inert`, so nothing was watching the surface — "
        f"the usual cause is the production classes being excluded with the test root: "
        f"{[(t, said[t]) for t in ran_production]}")


@pytest.mark.proves("dev07-1-4", depth="unit")
def test_a_surface_nobody_watches_is_not_named_to_the_adapter(tmp_path):
    """`inert` is read from the ABSENCE of a production hit, so an unwatched surface is the
    dangerous case, not the harmless one.

    The adapter asserts `inert` where a surface was declared and nothing reported running under it
    (`dev07-1-4`). Nothing reports anything when the agent that instruments the surface is not running —
    so naming the surface anyway turns an installation fault into a board on which every test claims
    to have executed no production code. The declaration and the instrument are two facts and the
    run file carries only the one it can stand behind.
    """
    from plumb import runfile

    class Config:
        archetypes: dict = {}
        entry_points = ("com.acme.Api#handle",)
        production = ("com.acme.*",)
        marker = "proves"

    watched = runfile.read(runfile.write(Config(), tmp_path / "watched.tsv", surface=True))
    assert watched.get("production") == [["com.acme.*"]], "a watched surface is named"
    assert watched.get("entrypoint"), "and the entry points are unaffected either way"

    unwatched = runfile.read(runfile.write(Config(), tmp_path / "unwatched.tsv", surface=False))
    assert "production" not in unwatched, (
        "a surface nobody is watching must not be named — the adapter reads `inert` from the "
        "absence of a hit, and absence is exactly what an unwatched surface produces")
    assert unwatched.get("entrypoint"), "grounding does not depend on the agent and must survive it"


@pytest.fixture(scope="module")
def mutated():
    """ONE mutation board over the reference project, and everything read out of it.

    The tests below were each running their own and then reading `build/plumb/wired.txt` — a file
    every board rewrites, and which a *plain* board correctly leaves empty because nothing was
    scoping. So they passed alone and failed together, in an order nothing declared, on the state
    the previous test happened to leave. Shared mutable state between tests is a defect in the
    tests whatever it is testing, and it costs five thirty-second boards to keep.
    """
    done = subprocess.run(
        [sys.executable, "-m", "plumb.cli", "board", "--json", "--project", str(JAVA), "--mutation"],
        capture_output=True, text=True, cwd=REPO, timeout=900,
        env={**os.environ, "PYTHONPATH": str(REPO / "src")})
    assert done.returncode == 0, (done.stdout + done.stderr)[-3000:]
    return {
        "out": done.stdout + done.stderr,
        "scope": (_work() / "wired.txt").read_text(),
        "stories": json.loads(done.stdout)["stories"],
    }


@needs_jvm
def test_the_reference_project_boards_the_way_it_is_built_to(mutated):
    """The sample's board is a fixture, and nothing was checking it.

    Every JVM test here runs a board over this project and asserts something narrow — a grounding
    word, a scope entry, a returncode — so the sample could be *wrong* and the suite stay green.
    It was: a `--mutation` run leaves the working tree mutated while it runs, a `git add -A` landed
    during one, and three mutants were committed into `App.java`. One line had been mutated four
    times over, each run parking an already-mutated file as its original. `work(2)` returned 9
    instead of 4 for two days and 538 tests had nothing to say about it.

    So this pins what the sample is FOR. Each verdict is a case the project was built to
    demonstrate, and a sample that stops demonstrating them is a broken fixture rather than a
    finding about Plumb.
    """
    said = {sid: story["status"] for sid, story in mutated["stories"].items()}
    assert said == {
        "APP-1": "proven",                        # drives the entry point and checks the answer
        "APP-2": "passed-wiring-not-verified",    # reaches it on a pool thread — dispatched
        "APP-3": "unproven",                      # drives production reaching no entry point
        "APP-4": "proven",                        # structural: inspects, runs nothing
        "APP-5": "proven",                        # drives the entry point without checking it
        "CM-101": "unproven",
        # Declared structural, and its test asserts `"plumb".length() == 5` — it reads the
        # artifact no more than it runs it. It was PROVEN here until the JVM adapter learned to
        # see a read: `inert` was granted from the absence of execution alone, which is the
        # orphaned-`done` fake wearing the one costume the gate was built to trust. The sample now
        # demonstrates that being refused, which is a better case than the one it used to make.
        "CM-102": "unproven", "CM-103": "unproven",
        "CM-104": "unproven", "CM-105": "unproven",
    }, "the reference project no longer boards the way it is built to"

    # And the one mutation asks that grounding cannot: APP-5 grounds exactly as APP-1 does and
    # would not notice the answer changing, which is the whole reason chapter 4 exists.
    scores = {sid: story["mutation"] for sid, story in mutated["stories"].items()
              if story.get("mutation")}
    assert scores["APP-5"]["killed"] == 0, (
        "APP-5's test runs the entry point and asserts nothing, so every mutant must survive it — "
        "a kill here means the sample stopped demonstrating the case mutation is for")
    assert scores["APP-1"]["killed"] > 0, (
        "APP-1's test checks the answer, so it must notice something — otherwise the sample cannot "
        "tell a checking test from a passing one")
    assert scores["APP-1"]["total"] == scores["APP-5"]["total"], (
        "both cite tests that drive the same code through the same entry point, so they face the "
        "same mutants and differ only in what their tests notice")


@needs_jvm
@pytest.mark.proves("dev07-2-1", depth="component")
def test_mutation_scopes_to_what_ran_under_an_entry_point_and_no_wider(mutated):
    """Chapter 4 mutates the code a test drove **under** a declared entry point and no wider.

    The sample is built to separate the two. `App#work` is reached through the declared entry
    point; `App#orphan` is production code that a test drives *directly*, reaching no entry point
    at all — the `ungrounded` case. Both run in the same suite, in the same class, on the same
    surface, so nothing but the entry-point window tells them apart.

    Mutating everything a test touched is the failure this pins against, and it is not a small one:
    it pulls in every helper a test brushed past, so a story's kill ratio stops being about that
    story and the number stops distinguishing anything. The narrow scope is what makes an unnoticed
    mutant mean *this story's tests do not check this*.

    Scope is collected by the agent — the site name is woven into the production method, and the
    window is opened and closed by wrapping the entry point (`dev07-1-3`), not watched from outside.
    """
    scoped = mutated["scope"]
    assert "App#work" in scoped, (
        "the method the entry point reaches is what chapter 4 mutates, and it is missing — so "
        "either the window never opened or the production advice never named its site")
    assert "App#orphan" not in scoped, (
        "`orphan` is driven by a test and reaches no entry point. Mutating it would be mutating "
        "the whole call tree, which is exactly the scope `dev07-2-1` refuses")

    board = json.loads(subprocess.run(
        [sys.executable, "-m", "plumb.cli", "board", "--json", "--project", str(JAVA)],
        capture_output=True, text=True, cwd=REPO, timeout=900,
        env={**os.environ, "PYTHONPATH": str(REPO / "src")}).stdout)
    assert board["stories"]["APP-3"]["status"] == "unproven", (
        "the story whose test drives production directly must not have been proven by a mutation "
        "run — a scope that leaked would be observable here first")


@needs_jvm
@pytest.mark.proves("dev07-1-3", depth="component")
def test_the_window_closes_when_the_entry_point_throws(mutated):
    """The exit join point has to run on *every* path out, and the exception path is the one a
    prologue cannot reach.

    A window that opens and never closes does not fail — it over-reports. Every production method
    called afterwards on that thread is recorded as having run under an entry point, so chapter 4
    mutates code no test reached through the front door and reports kills and survivals about it.
    Nothing about that is visible in a board: the numbers are all present and all wrong.

    So the exit probe is not a store before each `return`. The method is renamed and a wrapper is
    generated around it whose body is `entered(); try { return orig(args); } finally { left(); }`,
    and the `finally` is what makes the throwing path the same path (`dev07-1-3`).

    The sample drives an entry point that throws, catches it, then — same test, same thread —
    drives production code no entry point reaches. Whether the window closed is exactly whether
    that second call is in scope.
    """
    scoped = {
        line.split("\t")[0]: line.split("\t")[1].split(",")
        for line in mutated["scope"].splitlines() if "\t" in line
    }
    throwing = next((sites for test, sites in scoped.items()
                     if "closesTheWindowWhenTheEntryPointThrows" in test), None)
    assert throwing is not None, (
        "the test that drives a throwing entry point recorded no scope at all — it should have "
        "recorded the entry point itself, so either the wrapper did not run or the sample changed")
    assert "App#failingRequest" in throwing, "the throwing entry point ran and is production code"
    assert "App#orphan" not in throwing, (
        "code called AFTER the entry point threw was recorded as having run under it — the "
        "`finally` did not run, and from here every call on this thread joins the same open window")


@needs_jvm
@pytest.mark.proves("dev07-1-3", depth="component")
def test_a_method_containing_a_switch_survives_the_weave(mutated):
    """`tableswitch` and `lookupswitch` are the only variable-length instructions in the set.

    Each is padded with up to three bytes so its jump table starts on a four-byte boundary measured
    from the start of the method. Shift one by a number of bytes that is not a multiple of four and
    the padding it needs changes — the padding already written is now the wrong length, the table is
    read from the wrong place, and the method is garbage from that instruction on.

    This hides better than any other defect in the weaver. The `flag` advice is four bytes and
    preserves alignment *by luck*, so an instrument built on it weaves switches correctly forever
    and the first advice of another width breaks them everywhere. It was found the expensive way:
    six-byte scope advice over a real project, `VerifyError: Bad instruction` at a `lookupswitch`,
    38 tests, in classes the four-byte prologue had been weaving correctly for weeks.

    So the sample carries both switch forms, under the entry point, where the widest advice reaches
    them. `Advice` pads every advice to the boundary and no advice can opt out — this is the check
    that the sample still contains the shape that would catch it if one could.
    """
    source = (JAVA / "sample" / "App.java").read_text()
    assert "case 500:" in source and "case 100000:" in source, (
        "the sample lost its sparse switch, so nothing here emits a `lookupswitch` and this test "
        "passes without checking anything")

    assert "VerifyError" not in mutated["out"], (
        "the JVM rejected a woven class — an advice is not aligned to the switch boundary")

    scoped = mutated["scope"]
    assert "App#dense" in scoped and "App#sparse" in scoped, (
        "the switch-bearing methods ran under the entry point and are missing from the scope, so "
        "either they were not instrumented or the class did not load")


@needs_jvm
@pytest.mark.proves("dev07-1-3", depth="unit")
def test_an_entry_point_inside_the_surface_is_mutated_like_any_other_production_code(mutated):
    """A method can deserve more than one advice, and the front door is the case that proves it.

    An entry point inside the declared production surface is both things at once: it opens the
    window, and it is production code that ran inside it. The instrument gave it only the first, so
    `App#handleRequest` — the method every wired story in the sample goes through — was the one
    method chapter 4 never mutated. Silent, because mutation still reported a score, over a scope
    with the front door quietly missing from it.

    `dev07-1-3` is what made this a two-line fix rather than a new branch in the weaver: advice
    composes, so "both" is `and`, and the weaver never learns that entry points exist.
    """
    scoped = mutated["scope"]
    assert "App#handleRequest" in scoped, (
        "the declared entry point is inside the declared production surface and is missing from "
        "the mutation scope — the surface advice lost to the entry-point advice instead of "
        "composing with it")
    assert "App#work" in scoped, "and what it calls, which was never the half at risk"


@needs_jvm
@pytest.mark.proves("dev07-3-2", depth="component")
def test_the_board_counts_the_tests_it_observed_rather_than_reciting_them():
    """The board's output should scale with the spec, not with the suite.

    Measured on a first successful board: the one-line PROVEN verdict arrived beneath
    several hundred individually-listed tests. On a mature suite the citing tests are always a
    small minority, so the uncited majority is the least interesting output printed at the greatest
    length — and every run buries the verdict the team adopted the tool to see.

    The per-test fact is not dropped, which would trade one wrong default for another: it is what a
    reader needs when a board is not what they expected (`dev07-3-2`), and `--tests` asks for it.
    """
    def board(*extra: str) -> str:
        done = subprocess.run(
            [sys.executable, "-m", "plumb.cli", "board", "--json", "--project", str(JAVA), *extra],
            capture_output=True, text=True, cwd=REPO, timeout=900,
            env={**os.environ, "PYTHONPATH": str(REPO / "src")})
        assert done.returncode == 0, done.stderr[-2000:]
        return done.stderr

    counted = board()
    recited = board("--tests")

    # The grounding word FOLLOWED BY A TEST ID. `java: grounded 11 test(s) -> …` is the summary
    # header and stays in both modes; matching it would make this pass on the wrong evidence.
    per_test = re.compile(
        r"^java:\s+(?:grounded|inert|ungrounded|dispatched|not-checked)\s+\[", re.M)
    assert not per_test.search(counted), (
        "the default board recites the per-test grounding — on 1,941 tests that is 1,941 lines "
        "above a one-line verdict")
    assert per_test.search(recited), "`--tests` has to bring it back, or the fact is simply gone"
    assert re.search(r"^java: .*\d+ inert", counted, re.M), (
        "and the count has to be there instead — dropping the recital without replacing it loses "
        "the shape of the run, which is the reason those lines existed")
    assert "--tests" in counted, "the summary says how to get the detail"
    assert len(recited.splitlines()) > len(counted.splitlines()), "which is the whole point"


@needs_jvm
@pytest.mark.proves("dev07-1-3", depth="component")
def test_a_long_run_says_where_it_has_got_to():
    """A heartbeat that only repeats itself explains why a run is slow and never where it is.

    Measured: 9h46m in which the only signal was one sentence every 20 seconds, position
    obtainable only by grepping the raw output, and remaining time unestimable at every point — so
    the run was killed at a scheduling cap, possibly minutes from the evidence it was about to
    produce. An operator who cannot estimate completion will kill correct runs, and the method
    loses its answer at the moment it had one.

    The contract is *done / discovered*. Written to a file rather than to stdout, which the
    project's own logging owns — thousands of lines of it on a real suite — and which a watcher
    would have to have been reading from the start to make sense of.
    """
    progress = _work() / "progress.txt"
    progress.unlink(missing_ok=True)
    done = subprocess.run(
        [sys.executable, "-m", "plumb.cli", "board", "--json", "--project", str(JAVA)],
        capture_output=True, text=True, cwd=REPO, timeout=900,
        env={**os.environ, "PYTHONPATH": str(REPO / "src")})
    assert done.returncode == 0, done.stderr[-2000:]

    assert progress.is_file(), "the run reported no position at all"
    finished, discovered, when = progress.read_text().split()
    assert int(discovered) > 0, "the denominator is what makes a count an estimate"
    assert int(finished) == int(discovered), (
        f"the suite ended at {finished} of {discovered} — a position that stops short of the total "
        "reads as a stalled run to the operator deciding whether to keep waiting")
    assert int(when) > 0, "and when it was last true, so a stalled file is visible as stalled"


@pytest.mark.proves("dev07-1-3", depth="unit")
def test_the_heartbeat_estimates_from_the_position_it_was_given():
    """`~2h left` is what a decision to wait or not is made on.

    Deliberately arithmetic and unqualified: tests are not uniform and it will be wrong. A wrong
    estimate that moves is decidable and no estimate is not — which is the state that got a correct
    9h46m run killed.
    """
    from plumb.launch import _duration

    assert _duration(45) == "45s"
    assert _duration(600) == "10m"
    assert _duration(7200) == "2h00m"
    assert _duration(9000) == "2h30m", "coarse on purpose — precision this estimate does not have"


@pytest.mark.proves("dev07-1-3", depth="unit")
def test_the_position_names_the_unit_the_phase_actually_counts(tmp_path):
    """A progress line whose noun is wrong is one the reader has to decode.

    Two phases report through one contract and count different things. The mutation phase said
    `2/252 tests` while running no tests of its own — it compiles and runs mutants — and reported
    `0.1 mutants/s`, which is a rounding of a number nobody wanted. `~4.3s each` is the same fact
    in the form a decision to wait is made on.
    """
    import re
    from plumb.launch import _position

    progress = tmp_path / "progress.txt"
    progress.write_text("9 252 1787961001203")
    slow = _position(progress, elapsed=40.0, unit="mutants")
    assert "9/252 mutants (3%)" in slow, f"the phase counts mutants and must say so: {slow}"
    assert "tests" not in slow, f"and must not claim tests it never ran: {slow}"
    assert re.search(r"~4\.4s each", slow), (
        f"at well under one a second a rate rounds to nothing, and a pace reads: {slow}")

    progress.write_text("800 1937 1787961001203")
    fast = _position(progress, elapsed=20.0, unit="tests")
    assert "800/1937 tests (41%)" in fast and "40.0 tests/s" in fast, (
        f"and where the rate is the natural form, it stays the rate: {fast}")

    progress.write_text("0 500 1787961001203")
    assert "left" not in _position(progress, elapsed=30.0, unit="mutants"), (
        "nothing has finished, so there is no pace to divide by and no estimate to give")
    assert _position(None, elapsed=30.0, unit="tests") == "", (
        "a phase that reports no position gets no fraction invented for it")


@needs_jvm
@pytest.mark.proves("dev07-2-4", depth="component")
def test_mutation_names_what_survived_and_not_only_how_many(mutated):
    """A surviving mutant is the most actionable thing mutation produces.

    The reader's next move — strengthen the test that missed it — needs to know *which* mutant and
    *where*. Measured: one story at 23/50 left twenty-seven work items with no file, no
    line and no operator recorded anywhere, to be re-derived by hand against a tool that had known
    all three at the moment it generated them and dropped them one line later.

    Same reasoning as a condition code (`dev07-4-3`): the reader's next move differs per survivor, so a
    number that cannot distinguish them is not the fact they need.
    """
    stories = mutated["stories"]

    short = {sid: s["mutation"] for sid, s in stories.items()
             if s.get("mutation") and s["mutation"]["survived"] > 0}
    assert short, "the sample must leave a survivor or this checks nothing"

    for sid, fact in short.items():
        named = fact["survivors"]
        assert len(named) == fact["survived"], (
            f"{sid} reports {fact['survived']} survivor(s) and names {len(named)} — a shortfall "
            "the reader cannot locate is the count again, spelled longer")
        for one in named:
            assert one["operator"] in ("flip-comparison", "negate-branch", "swap-return")
            assert "#" in one["where"], "Class#method, as the scope spells it"
            assert one["file"].endswith(".java") and one["line"] >= 1, (
                "file and line, or the reader cannot go and look at it")
            assert (JAVA / one["file"]).is_file(), (
                f"{one['file']} is named as a survivor's source and is not there — a path "
                "relative to the wrong directory sends the reader nowhere")

    # ONCE EACH ON THE BOARD, and only when asked. A survivor sits in the scope of every story that
    # reached its method, so printing them under each story repeats one work item many times: on a
    # measured: 205 distinct sites printed 2,378 times, in a board of 2,449 lines, with the
    # verdicts buried underneath. The manifest keeps them per story, because a consumer wants them
    # keyed that way; a person wants the list of things to go and fix.
    def board(*extra: str) -> str:
        done = subprocess.run(
            [sys.executable, "-m", "plumb.cli", "board", "--project", str(JAVA), "--mutation",
             *extra],
            capture_output=True, text=True, cwd=REPO, timeout=900,
            env={**os.environ, "PYTHONPATH": str(REPO / "src")})
        assert done.returncode == 0, done.stdout + done.stderr
        return done.stdout

    quiet, asked = board(), board("--survivors")
    # ONE ROW PER SITE, whatever its reach. A site one story reached and another did not was
    # printing twice — the same line, once excused and once not — because reach was keyed into the
    # identity rather than read across the stories that scoped it.
    rows = [line for line in asked.splitlines() if ".java:" in line and "·" in line]
    where = [line.split()[0] for line in rows]
    assert len(where) == len(set(where)), f"a site is listed more than once: {where}"
    assert "surviving mutant" not in quiet, (
        "the default board lists survivors — on a real project that is thousands of lines of "
        "repetition above the verdict")
    assert "surviving mutant" in asked, "`--survivors` has to bring them back"
    assert any("never reached" in line for line in rows), (
        "no site reads as unreachable, so the reader cannot tell a missing assertion from a line "
        "their tests never run")


@needs_jvm
@pytest.mark.proves("dev07-2-4", depth="component")
def test_a_survivor_no_test_reached_is_said_apart_from_one_no_test_noticed(mutated):
    """A survivor nobody reached is not a weak test, and the reader's next move differs entirely.

    Scope is per method and a method is scoped whole, so a story whose test drives one path gets
    mutants on every other path through the same method — lines it never enters, and mutants it
    could not kill however good its assertions were. Reported beside real gaps, they send a reader
    to strengthen a test against code it was never going to run. Measured: 205 surviving
    sites, an unknown share of them unreachable by the tests being blamed for them.

    Unlike equivalence — undecidable, and open as `dev07-2-4` — this is observed. The mutated
    expression is wrapped in a probe that returns its argument, so the run reports whether the line
    evaluated, one call per mutant and no coverage tool (`dev07-1-3`).

    The sample is built to separate them. `App#dense` is a `switch` and every test drives `n=2`, so
    `case 1`, `case 3` and `default` are never entered — while `case 2` is entered by all of them
    and still survives APP-5, whose test asserts nothing.
    """
    survivors = {}
    for sid, story in mutated["stories"].items():
        for one in (story.get("mutation") or {}).get("survivors", []):
            survivors.setdefault((one["line"], one["where"]), set()).add(one["reached"])

    dense = {line: got for (line, where), got in survivors.items() if where == "App#dense"}
    assert dense, "the sample lost its switch, so nothing here is unreachable and this checks nothing"
    unreached = sorted(line for line, got in dense.items() if got == {False})
    reached = sorted(line for line, got in dense.items() if True in got)

    assert len(unreached) >= 3, (
        f"only {unreached} of App#dense reads as unreached — every test drives n=2, so the other "
        "switch arms cannot be evaluated and must not be counted against the tests")
    assert reached, (
        "no arm of App#dense reads as reached, so the probe is not firing at all and every mutant "
        "would be excused rather than the unreachable ones")
    assert set(unreached).isdisjoint(reached), "a line cannot be both"

    # And the count travels, so a reader does not have to total the list themselves.
    for sid in ("APP-1", "APP-5"):
        fact = mutated["stories"][sid]["mutation"]
        assert fact["unreached"] == sum(
            1 for one in fact["survivors"] if one["reached"] is False)


@needs_jvm
@pytest.mark.proves("dev07-2-3", depth="component")
def test_a_mutation_that_changes_nothing_is_never_generated():
    """An identity mutant is worse than a missing one.

    `swap-return` on `return null;` replaces `null` with `null`: the mutated source is
    byte-identical, it compiles, it runs, and no test can possibly notice it. So it is counted as a
    survivor forever, capping the story's ratio below 100% however strong the tests get, and sending
    the reader to hunt for an assertion that cannot exist. An adopter found it by chasing survivors
    by name with a `diff`.

    Checked as *output equals input* rather than by special-casing `return null`, because that is
    the property that makes a mutant unkillable and any operator can have it.
    """
    harness = JAVA / "build" / "identity"
    harness.mkdir(parents=True, exist_ok=True)
    (harness / "Nullable.java").write_text(
        "class Nullable {\n"
        "    String absent() { return null; }\n"          # swap-return -> null: identity
        "    String present() { return \"x\"; }\n"      # swap-return -> null: a real mutant
        "}\n")
    (harness / "Count.java").write_text(
        # `Paths.get` and `Arrays.asList`, not `Path.of` and `List.of`: this release declares a
        # Java 8 floor and those two arrived at 11 and 9. The harness compiled anyway because the
        # suite runs on whatever JDK is default — 25 here — so a fixture the floor cannot build
        # passed every run. What a floor claims and what the tests are built against are two facts,
        # and only one of them was being checked.
        "import java.nio.file.*;\nimport java.util.*;\n"
        "public class Count {\n"
        "  public static void main(String[] a) throws Exception {\n"
        "    for (String m : new String[]{\"Nullable#absent\", \"Nullable#present\"})\n"
        "      System.out.println(m + \" \" + org.plumbspec.Mutants.count(\n"
        "          Paths.get(a[0]), new HashSet<>(Arrays.asList(m))));\n"
        "  }\n}\n")
    adapter = JAVA / "adapter" / "target" / "classes"
    # The compiler tree API this reads is an exported package from Java 9 and sits in `tools.jar`
    # below it, on nobody's classpath. `launch._compiling_classpath` arranges that for the product
    # — `dev07-3-1-sr3` says holding at the floor is ours to arrange — and a harness that skips it
    # tests the adapter on a classpath the tool never gives it.
    from plumb.launch import _compiling_classpath

    cp = _compiling_classpath(shutil.which("java"), f"{adapter}{os.pathsep}{harness}")
    assert subprocess.run(["javac", "-cp", cp, "-d", str(harness),
                           str(harness / "Count.java")], capture_output=True).returncode == 0
    done = subprocess.run(["java", "-cp", cp, "Count",
                           str(harness / "Nullable.java")], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    got = dict((w.split()[0], int(w.split()[1]))
               for w in done.stdout.strip().splitlines())
    assert got["Nullable#present"] >= 1, (
        "`return \"x\"` has a real swap-return mutant, so the collector is working at all")
    assert got["Nullable#absent"] == 0, (
        "`return null` swapped to `null` is byte-identical — an unkillable mutant that reads as a "
        "permanent test gap and caps the ratio forever")


@needs_jvm
@pytest.mark.proves("dev07-1-4", depth="component")
def test_inert_is_withheld_when_nothing_instrumented_the_surface(tmp_path):
    """`inert` needs something to have been watching, not merely nothing to have been seen.

    An unset flag means *no production method ran* or *nothing was instrumented*, and those are the
    same observation. Reading the second as the first hands every structural story a proof on the
    strength of nobody looking — and it is silent, because a board full of `inert` looks exactly
    like a project whose tests inspect rather than execute.

    Three defects reached it by three different routes: a test root matched on a bare string prefix
    so production was excluded with the tests; production and tests compiled to one directory so the
    question could not be answered at all; and javac implicitly compiling a production class into
    the test output as well, which came and went with file timestamps. Each was fixed where it
    happened. This is the check that makes the next route — a symlink, a shaded jar, a layout nobody
    here has imagined — loud instead of flattering, and it is written against the *end state* those
    three share rather than against any one of their causes.
    """
    production = JAVA / "sample" / "target" / "classes" / "App.class"
    intruder = JAVA / "sample" / "target" / "test-classes" / "App.class"
    assert production.is_file(), "the sample must be built before this can say anything"

    def board() -> str:
        # `--tests`: this asserts on one test's grounding word, which the default output counts.
        done = subprocess.run(
            [sys.executable, "-m", "plumb.cli", "board", "--json", "--tests",
             "--project", str(JAVA)],
            capture_output=True, text=True, cwd=REPO, timeout=900,
            env={**os.environ, "PYTHONPATH": str(REPO / "src")})
        assert done.returncode == 0, done.stderr[-2000:]
        return done.stderr

    healthy = board()
    assert re.search(r"^java:\s+inert", healthy, re.M), (
        "the sample proves structural stories through `inert`; without one this checks nothing")

    # The end state all three defects share: the production class also sits under the test root, so
    # the agent excludes it and rewrites nothing.
    intruder.write_bytes(production.read_bytes())
    try:
        blinded = board()
    finally:
        intruder.unlink(missing_ok=True)

    assert not re.search(r"^java:\s+inert", blinded, re.M), (
        "the surface was not instrumented and `inert` was asserted anyway — which is the strongest "
        "claim the gate can make, from an instrument that was not running")
    assert "nothing was instrumented" in blinded, (
        "and the run has to say so. `not-checked` is the honest answer for a question nobody asked, "
        "but a reader cannot act on it without being told the instrument never reached their code")
    assert re.search(r"^java:\s+not-checked", blinded, re.M), (
        "every fact read from an absence has to fall back, not just the `inert` ones — an absent "
        "entry-point hit means as little as an absent production hit when nothing was watching")


@needs_jvm
@pytest.mark.proves("dev07-2-3", depth="standards-integration")
def test_an_ordinary_board_puts_back_what_an_interrupted_mutation_left():
    """A mutant outlives the run that wrote it, and the next thing an adopter runs is a board.

    The recovery lived inside the mutation entry point, so a mutation killed part-way left the
    source rewritten until somebody ran mutation *again* — and every board in between measured the
    mutant and reported it as the project. Silent, because the mutant compiles and the suite runs.

    Observed here: a leftover mutant in the sample made the mutation scores of the *next* run
    disagree with themselves, and only `git status` said why. The Python adapter has always
    recovered on every run; this is the same rule on the other side.
    """
    # **The scratch is shared, and this test is the only one that writes to it.** `mutated_board` is
    # module-scoped: one mutation board runs, and every mutation test below reads its manifest,
    # `wired.txt` and `scores.tsv` back out of the work directory. A second board over the same
    # project overwrites all three, so this test — which must run a real board to prove the
    # recovery — puts the fixture's artefacts back when it is done. Without that it silently broke
    # two mutation tests, and only in a full run, which reads exactly like a flake.
    work = _work()
    kept = {f: f.read_bytes() for f in work.glob("*") if f.is_file()} if work.is_dir() else {}

    app = JAVA / "sample" / "App.java"
    original = app.read_text()
    # Read out of the adapter rather than retyped. A constant spelled in two places is one that
    # drifts, and a test asserting recovery against the wrong filename would assert nothing while
    # passing — which is the shape of every drift found in this file today.
    declared = re.search(r'PARKED\s*=\s*"([^"]+)"',
                         (JAVA / "adapter/src/main/java/org/plumbspec/Rescue.java").read_text())
    assert declared, "Rescue no longer declares PARKED, and this test is guessing"
    rescue = _work() / declared.group(1)
    _work().mkdir(parents=True, exist_ok=True)
    try:
        rescue.write_text(f"{app.resolve()}\n{original}")
        app.write_text(original.replace(
            "return work(n); }", "return org.plumbspec.PlumbFlag.hit((int)((work(n)) + 1)); }"))
        assert app.read_text() != original, "the sample no longer has the line this mutates"

        done = subprocess.run(
            [sys.executable, "-m", "plumb.cli", "board", "--project", str(JAVA)],
            capture_output=True, text=True, cwd=REPO, timeout=900,
            env={**os.environ, "PYTHONPATH": str(REPO / "src")})

        assert app.read_text() == original, (
            "an ordinary board left the mutant in the adopter's source, so every fact it just "
            f"reported was measured against code the project never wrote: {done.stderr[-1500:]}")
        assert not rescue.is_file(), "the parked copy is consumed once it has been put back"
    finally:
        app.write_text(original)
        rescue.unlink(missing_ok=True)
        for f, was in kept.items():
            f.write_bytes(was)


@pytest.mark.proves("dev07-1-3", depth="unit")
def test_a_member_the_toolchain_made_is_not_an_end_of_an_edge():
    """Read as source, because what is being checked is which fact the rule is keyed on.

    A private member read from a nested class needed an `access$N` bridge until nest-based access
    arrived in Java 11, so the same source compiled either side of that line has a different member
    in it and calls it from a real `invokestatic`. The graph may not move when the compiler does
    (`dev07-1-3-ur11`), so such a member is refused — off the **flag** the class file carries, never
    off what the compiler chose to call it, which is the guessing `dev07-1-3-sr10` rules out.
    """
    sites = (JAVA / "adapter" / "src" / "main" / "java" / "org" / "plumbspec" / "Sites.java").read_text()
    probe = (JAVA / "adapter" / "src" / "main" / "java" / "org" / "plumbspec" / "Probe.java").read_text()

    assert "undeclared.contains(from)" in sites and "undeclared.contains(to)" in sites, (
        "Sites.taken hands back every edge it recorded, so a member that exists only on some "
        "toolchains is still an end of one")
    assert "Wrapper.ACC_SYNTHETIC" in probe and "Sites.toolchainMade" in probe, (
        "nothing tells Sites which members the toolchain made, so the filter above holds nothing")
    assert "Sites.writtenInside" in probe and "settled(callers[i])" in sites, (
        "a lambda body is compiler-made too, and refusing it would drop every call made from "
        "inside one — it is reported against the method it was written inside instead")
    assert '"EnclosingMethod".equals(utf8[nameIndex])' in probe and "declaredInside" in probe, (
        "a class declared inside a method still reports under its own number, and a compiler "
        "numbers those in declaration order — add one above and every one below is renamed")
    assert "nameAndType <= 0" in probe, (
        "a class declared in an initializer names no enclosing method, and reading index zero as "
        "one is how a fold reports against whatever happens to sit at that constant")
    assert '"<init>".equals(name)' in probe, (
        "without holding the constructor out, an accessor carrying the class's own line reports "
        "a field read as a call to the constructor — a false edge for an unsteady one")
    assert "access$" not in probe and "lambda$" not in probe, (
        "the weaver is matching what a compiler-made member is called, which is what reading the "
        "flag replaced")
