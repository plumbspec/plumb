"""End to end, through the declared entry point.

Every other test in this suite calls the library directly, so its execution never runs under a
declared production entry point and the citations it carries read UNGROUNDED. That is `dev07-4-2`
working, and it means the core cannot be proven by unit tests however green they are.

These drive ``plumb.cli:main`` — the real entry point, in-process. In-process is the whole point:
a subprocess would be correct end-to-end coverage and would still ground nothing, because the
tracer lives in this process and would never see the frames.

The runner is nested, which is why every case here points at a **tiny generated project** under
``tmp_path`` rather than at this repository. Pointing the inner run at our own tests would
recurse without bound.
"""

import json
from pathlib import Path

import pytest

from plumb.core.board import BOARD_VERSION

from plumb import cli
from plumb.core.gate import PASSED_WIRING_NOT_VERIFIED, PROVEN, UNPROVEN
from plumb.core.manifest import Manifest


def project(tmp_path, body: str, config: str = "") -> str:
    """A minimal consumer project: one package, one test file, optionally a declared surface.

    The **package name is unique per project**, not just the test module's. Python caches an
    imported module by name, so a second generated project reusing ``app`` would silently get
    the first one's module object — whose file lives under a previous ``tmp_path`` and therefore
    outside this project's declared roots. The trace would then see no production frames and the
    board would read UNPROVEN for a reason that has nothing to do with the code under test.
    """
    uniq = "".join(c if c.isalnum() else "_" for c in tmp_path.name)[:40]
    pkg = f"app_{uniq}"
    root = tmp_path / "proj"
    (root / "src" / pkg).mkdir(parents=True)
    (root / "src" / pkg / "__init__.py").write_text("")
    (root / "src" / pkg / "core.py").write_text(
        "def entry(n):\n"
        "    return double(n)\n"
        "\n"
        "def double(n):\n"
        "    return n * 2\n"
        "\n"
        "def orphan(n):\n"
        "    return n + 1\n"
    )
    # An absolute sys.path entry: the inner runner sets its own rootdir, so a relative "src"
    # resolves against a directory the generated test cannot predict.
    (root / f"test_gen_{uniq}.py").write_text(
        f"import sys\nsys.path.insert(0, {str(root / 'src')!r})\n" + body.format(pkg=pkg)
    )
    if config:
        (root / "plumb.toml").write_text(config.format(pkg=pkg))
    return str(root)


def board_from(monkeypatch, capsys, root: str, *args) -> dict:
    """Run ``plumb board --json`` over a generated project and read what came out."""
    monkeypatch.syspath_prepend(root + "/src")
    monkeypatch.chdir(root)
    rc = cli.main(["board", "--json", *args, root])
    assert rc == 0
    return json.loads(capsys.readouterr().out)


CITES_PASSING = '''
import pytest

@pytest.mark.proves("APP-1", depth="unit")
def test_one():
    from {pkg}.core import double
    assert double(2) == 4
'''


@pytest.mark.proves("dev07-5-1", depth="smoke")
@pytest.mark.proves("dev07-5-3", depth="smoke")
@pytest.mark.proves("dev07-5-3", depth="smoke")
@pytest.mark.proves("dev07-4-3", depth="smoke")
@pytest.mark.proves("dev07-3-2", depth="smoke")
def test_the_board_comes_out_of_the_command_line(monkeypatch, capsys, tmp_path):
    """The whole graph, driven the way a user drives it: spec + run in, board out."""
    payload = board_from(monkeypatch, capsys, project(tmp_path, CITES_PASSING))
    assert payload["board_version"] == BOARD_VERSION
    # "APP-1" is a foreign key with no Plumb-side catalog behind it — exactly dev07-3-2.
    assert "APP-1" in payload["stories"]
    assert payload["stories"]["APP-1"]["achieved"] == ["unit"]


@pytest.mark.proves("dev07-5-1", depth="smoke")
@pytest.mark.proves("dev07-1-4", depth="smoke")
@pytest.mark.proves("dev07-5-2", depth="smoke")
def test_with_no_entry_points_declared_the_board_says_so(monkeypatch, capsys, tmp_path):
    """The lowest input level still produces a real board, and names what it could not do."""
    payload = board_from(monkeypatch, capsys, project(tmp_path, CITES_PASSING))
    story = payload["stories"]["APP-1"]
    assert story["status"] == PASSED_WIRING_NOT_VERIFIED
    assert [c["code"] for c in story["conditions"]] == ["grounding.not-checked"]
    assert story["conditions"][0]["example"], "the hint must show where the value goes"


@pytest.mark.proves("dev07-4-3", depth="smoke")
@pytest.mark.proves("dev07-3-1", depth="smoke")
def test_a_failing_citation_un_proves_its_story(monkeypatch, capsys, tmp_path):
    """Status is derived live from the run — nothing stored, so nothing stale."""
    failing = CITES_PASSING.replace("assert double(2) == 4", "assert double(2) == 5")
    payload = board_from(monkeypatch, capsys, project(tmp_path, failing))
    assert payload["stories"]["APP-1"]["status"] == UNPROVEN


@pytest.mark.proves("dev07-4-2", depth="smoke")
@pytest.mark.proves("dev07-3-1", depth="smoke")
def test_a_skipped_citation_is_a_claim_not_a_proof(monkeypatch, capsys, tmp_path):
    skipped = CITES_PASSING.replace("def test_one():", "@pytest.mark.skip\ndef test_one():")
    payload = board_from(monkeypatch, capsys, project(tmp_path, skipped))
    assert payload["stories"]["APP-1"]["status"] == UNPROVEN


DECLARES_SURFACE = """production = ["src/{pkg}"]
entry_points = ["{pkg}.core:entry"]
"""

GROUNDS = '''
import pytest

@pytest.mark.proves("APP-1", depth="wiring")
def test_through_the_entry_point():
    from {pkg}.core import entry
    assert entry(2) == 4

@pytest.mark.proves("APP-2", depth="unit")
def test_around_it():
    from {pkg}.core import orphan
    assert orphan(2) == 3
'''


@pytest.mark.proves("dev07-4-2", depth="smoke")
@pytest.mark.proves("dev07-1-4", depth="smoke")
def test_declaring_entry_points_separates_wired_proof_from_isolated_proof(
    monkeypatch, capsys, tmp_path
):
    """The product's whole claim, end to end: one story reached the real system and one did
    not, and only the first reads PROVEN however green both tests are."""
    payload = board_from(
        monkeypatch, capsys, project(tmp_path, GROUNDS, config=DECLARES_SURFACE)
    )
    assert payload["stories"]["APP-1"]["status"] == PROVEN, "ran under the declared entry point"
    assert payload["stories"]["APP-2"]["status"] == UNPROVEN, "passed, but reached nothing wired"


@pytest.mark.proves("dev07-1-4", depth="smoke")
def test_orphaned_code_cannot_ground_however_green_its_test_is(
    monkeypatch, capsys, tmp_path
):
    """`orphan` is reachable from no entry point, so a passing test over it never reads done."""
    payload = board_from(
        monkeypatch, capsys, project(tmp_path, GROUNDS, config=DECLARES_SURFACE)
    )
    assert payload["stories"]["APP-2"]["achieved"] == ["unit"], "the rung it did reach is shown"
    assert payload["stories"]["APP-2"]["status"] == UNPROVEN


@pytest.mark.proves("dev07-5-3", depth="smoke")
def test_plumb_runs_the_whole_graph_on_a_project_it_has_never_seen(
    monkeypatch, capsys, tmp_path
):
    """The same orchestration produces a board for any project, with no core change."""
    payload = board_from(
        monkeypatch, capsys, project(tmp_path, GROUNDS, config=DECLARES_SURFACE)
    )
    assert set(payload["stories"]) == {"APP-1", "APP-2"}
    assert payload["board_version"] == BOARD_VERSION


@pytest.mark.proves("dev07-5-1", depth="smoke")
@pytest.mark.proves("dev07-5-2", depth="smoke")
@pytest.mark.proves("dev07-5-2", depth="smoke")
def test_the_emitted_board_carries_evidence_and_its_own_next_step(
    monkeypatch, capsys, tmp_path
):
    """What crosses the boundary must let a reviewer act: the citation and how it was judged,
    plus what this run has earned the right to suggest, every part keyed by a stable code."""
    from plumb.core.gate import ALL_CODES

    payload = board_from(
        monkeypatch, capsys, project(tmp_path, GROUNDS, config=DECLARES_SURFACE)
    )

    evidence = payload["stories"]["APP-1"]["evidence"]
    assert [e["grounding"] for e in evidence] == ["grounded"], "how it was judged, not just the verdict"
    assert evidence[0]["depth"] == "wiring"

    unlocks = payload["unlocks"]
    assert unlocks, "a run with something to improve says so"
    for signal in unlocks:
        assert signal["code"] in ALL_CODES, "what the board can say is a list, not open-ended"
        assert signal["next_step"], "a code without an instruction helps nobody"


OPTS_INTO_MUTATION = """production = ["src/{pkg}"]
entry_points = ["{pkg}.core:entry"]
mutation = true
"""

ONE_CHECKS_AND_ONE_DOES_NOT = '''
import pytest

@pytest.mark.proves("APP-1", depth="wiring")
def test_checks_what_it_ran():
    from {pkg}.core import entry
    assert entry(2) == 4

@pytest.mark.proves("APP-2", depth="wiring")
def test_runs_it_without_checking():
    from {pkg}.core import entry
    entry(2)
'''


@pytest.mark.proves("dev07-2-3", depth="smoke")
@pytest.mark.proves("dev07-2-2", depth="smoke")
@pytest.mark.proves("dev07-2-1", depth="smoke")
@pytest.mark.proves("dev07-2-4", depth="smoke")
@pytest.mark.proves("dev07-2-4", depth="smoke")
def test_mutation_separates_a_test_that_checks_from_one_that_merely_runs(
    monkeypatch, capsys, tmp_path
):
    """What grounding cannot see, driven the way a user turns it on.

    Both stories ground through the same entry point and both read PROVEN — that is `dev07-2-4`, and
    it is the point rather than an omission: mutation is beside the gate, never in it. The
    difference between the two shows up only in the manifest slot (`dev07-2-4`), which is where a
    human triages it.

    APP-1 scoring full marks is also what checks `dev07-2-1` here: `orphan` sits in the same file and
    no entry point reaches it, so a pass scoped to the *file* rather than to the wired code would
    leave survivors and this assertion would fail.
    """
    root = project(tmp_path, ONE_CHECKS_AND_ONE_DOES_NOT, config=OPTS_INTO_MUTATION)
    payload = board_from(monkeypatch, capsys, root, "--mutation")

    assert payload["stories"]["APP-1"]["status"] == PROVEN
    assert payload["stories"]["APP-2"]["status"] == PROVEN, "survivors never un-prove (dev07-2-4)"

    checked, blind = (payload["stories"][s]["mutation"] for s in ("APP-1", "APP-2"))
    assert checked["killed"] == checked["total"] > 0, "its test checks what it drove"
    assert blind["killed"] == 0 and blind["total"] == checked["total"], \
        "same code, same mutants — the difference is entirely in what the test asserts"


@pytest.mark.proves("dev07-2-4", depth="smoke")
def test_every_python_survivor_is_named(monkeypatch, capsys, tmp_path):
    """`dev07-2-4-ur3` — each survivor is named, because the reader's next move differs per
    survivor. A score with an empty list is a count with nothing to act on."""
    root = project(tmp_path, ONE_CHECKS_AND_ONE_DOES_NOT, config=OPTS_INTO_MUTATION)
    payload = board_from(monkeypatch, capsys, root, "--mutation")

    checked, blind = (payload["stories"][s]["mutation"] for s in ("APP-1", "APP-2"))
    assert checked["survivors"] == [], "nothing survived a test that checks"
    assert len(blind["survivors"]) == blind["survived"] > 0, blind
    for one in blind["survivors"]:
        assert one["operator"] and one["where"] and one["file"].endswith("core.py") and one["line"] > 0


@pytest.mark.proves("dev07-2-3", depth="smoke")
def test_a_run_killed_mid_mutant_is_put_back_by_the_next_one(monkeypatch, capsys, tmp_path):
    """The recovery has to happen *before* anything reads a source file, so driving it through the
    command line is the only way to check it is wired there rather than merely written.

    Set up exactly what a killed process leaves: a mutant on disk and the original parked beside
    it. If nothing put it back, the mutated `entry` would return None, both stories would fail
    their tests, and the board would read UNPROVEN — a silent wrong answer, not a crash.
    """
    from pathlib import Path

    from plumb.adapters.python.mutation import RESCUE

    root = project(tmp_path, ONE_CHECKS_AND_ONE_DOES_NOT, config=OPTS_INTO_MUTATION)
    core = next(Path(root).glob("src/*/core.py"))
    original = core.read_bytes()
    Path(root, RESCUE).write_bytes(str(core).encode() + b"\n" + original)
    core.write_text("def entry(n):\n    return None\n")

    monkeypatch.syspath_prepend(root + "/src")
    monkeypatch.chdir(root)
    assert cli.main(["board", "--json", "--mutation", root]) == 0
    captured = capsys.readouterr()

    assert core.read_bytes() == original, "the tree is put back before anything reads it"
    assert not Path(root, RESCUE).exists(), "and the parked copy is cleared once it has been used"
    assert "put back" in captured.err, "silently repairing it would hide that a run died"
    assert json.loads(captured.out)["stories"]["APP-1"]["status"] == PROVEN


# ---- the manifest as a boundary, not an in-memory object ------------------------------

#: Deliberately shaped like something Python did not produce: JUnit method handles, a foreign
#: work-item key, a structural story. Nothing here can be created by our own adapter.
#: Major 7 on purpose. A foreign adapter that watches execution and cannot see reads is exactly
#: the case major 8 splits — `inert` at 7 means *ran none of it* and claims nothing about reading,
#: so `CM-102` is proven by a document that never overstates what its instrument saw. Plumb's own
#: Java adapter is in the same position.
FOREIGN_MANIFEST = """{
  "schema_version": "9.0",
  "stories": {
    "CM-101": {"archetype": "behavioral", "citations": [
      {"test": "acme.layerspec.Layer03OverlaySpec#routes", "depth": "wiring",
       "result": "passed", "grounding": "grounded", "ref": "JIRA-4412"}]},
    "CM-102": {"archetype": "structural", "citations": [
      {"test": "acme.layerspec.LayerDecompositionSpec#noUpEdges", "depth": "unit",
       "result": "passed", "grounding": "inert", "ref": null}]},
    "CM-103": {"archetype": "behavioral", "citations": [
      {"test": "acme.delivery.AckRouterTest#retries", "depth": "wiring",
       "result": "passed", "grounding": "ungrounded", "ref": null}]}
  }
}"""


@pytest.mark.proves("dev07-3-3", depth="smoke")
@pytest.mark.proves("dev07-3-3", depth="smoke")
def test_a_manifest_this_process_did_not_produce_renders_a_board(capsys, tmp_path):
    """`dev07-3-3`'s founding claim, demonstrated rather than asserted: the core reads only the
    manifest, so a language it has never met needs no core change at all.

    With one adapter, "the core is language-blind" and "the core happens to work" are the same
    observation. This is the first thing that tells them apart.
    """
    path = tmp_path / "junit.json"
    path.write_text(FOREIGN_MANIFEST)

    assert cli.main(["board", "--json", "--manifest", str(path)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["stories"]["CM-101"]["status"] == PROVEN, "behavioral + grounded"
    assert payload["stories"]["CM-102"]["status"] == PROVEN, "structural + inert — the mirror check"
    assert payload["stories"]["CM-103"]["status"] == UNPROVEN, "the orphaned-done fake, in Java"
    assert payload["stories"]["CM-101"]["evidence"][0]["ref"] == "JIRA-4412", "their key, carried"


@pytest.mark.proves("dev07-3-3", depth="smoke")
def test_a_manifest_survives_the_round_trip_out_and_back(monkeypatch, capsys, tmp_path):
    """Emit what the runner produced, feed it back, and get the same board. If these differ the
    manifest is not a contract, it is an implementation detail that happens to serialize."""
    root = project(tmp_path, GROUNDS, config=DECLARES_SURFACE)
    out = tmp_path / "m.json"

    monkeypatch.syspath_prepend(root + "/src")
    monkeypatch.chdir(root)
    assert cli.main(["board", "--json", "--emit-manifest", str(out), root]) == 0
    direct = json.loads(capsys.readouterr().out)

    assert cli.main(["board", "--json", "--manifest", str(out)]) == 0
    replayed = json.loads(capsys.readouterr().out)

    # `rendered_at` is when a board was *rendered*, not what it says — so two derivations a second
    # apart differ in it and in nothing else. Second time this has bitten: `_without_when` above
    # exists for the same reason on the scoping test, and both failures read as the claim under
    # test being false rather than as a clock ticking between two calls.
    assert {k: v for k, v in replayed.items() if k != "rendered_at"} == \
           {k: v for k, v in direct.items() if k != "rendered_at"}, \
        "a board derived from the emitted manifest must be the same board"


@pytest.mark.proves("dev07-3-3", depth="smoke")
@pytest.mark.proves("dev07-3-2", depth="smoke")
def test_a_malformed_manifest_is_refused_at_the_edge(capsys, tmp_path):
    """The manifest is the sole interface, so a bad one is caught where it enters rather than
    misread downstream by a core that cannot see where it came from.

    Driven through the command line on purpose: the refusal is part of the contract (`dev07-3-2`),
    and what an adapter author actually meets is the exit code and the message on stderr, not
    the exception type."""
    bad = tmp_path / "bad.json"
    bad.write_text('{"schema_version": 99, "stories": {}}')
    assert cli.main(["board", "--manifest", str(bad)]) == 2
    refusal = capsys.readouterr().err
    assert "schema_version" in refusal
    from plumb.core.manifest import SUPPORTED_VERSIONS

    assert all(f"{v}.x" in refusal for v in SUPPORTED_VERSIONS), (
        "a refusal that does not say what is supported is a dead end, and it names what a *run* "
        "accepts rather than a literal set that would go stale the next time one is retired")

    assert cli.main(["board", "--manifest", str(tmp_path / "absent.json")]) == 2


NO_TESTS_AT_ALL = ""

UNCITED_ONLY = '''
def test_something_uncited():
    assert True
'''


def _exit_code(monkeypatch, root: str, *args) -> int:
    monkeypatch.syspath_prepend(root + "/src")
    monkeypatch.chdir(root)
    return cli.main(["board", "--json", *args, root])


@pytest.mark.proves("dev07-5-3", depth="smoke")
@pytest.mark.proves("dev07-5-2", depth="smoke")
def test_a_run_that_observed_nothing_fails_the_step(monkeypatch, capsys, tmp_path):
    """The whole point, driven the way CI drives it. Before this the step could not fail, so a
    board wired into a job was green whether or not the runner had found anything to look at."""
    from plumb.cli import EXIT_NOTHING_OBSERVED
    from plumb.core.gate import NOTHING_OBSERVED

    code = _exit_code(monkeypatch, project(tmp_path, NO_TESTS_AT_ALL))
    assert code == EXIT_NOTHING_OBSERVED, "a board derived from nothing must not report success"

    payload = json.loads(capsys.readouterr().out)
    assert payload["observed_tests"] == 0
    assert [c["code"] for c in payload["conditions"]] == [NOTHING_OBSERVED]


@pytest.mark.proves("dev07-5-3", depth="smoke")
@pytest.mark.proves("dev07-4-3", depth="smoke")
def test_unproven_stories_are_not_a_failure(monkeypatch, capsys, tmp_path):
    """The other half of the contract, and the half that is easy to lose. Proof happens at the
    desk, so a fresh spec is all-unproven and green — a tool that exited non-zero here would be
    the CI gate this one declines to be."""
    failing = CITES_PASSING.replace("assert double(2) == 4", "assert double(2) == 5")
    assert _exit_code(monkeypatch, project(tmp_path, failing)) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["stories"]["APP-1"]["status"] == UNPROVEN, "unproven, and still exit 0"
    assert payload["observed_tests"] == 1, "because a test WAS observed — that is the whole test"


@pytest.mark.proves("dev07-5-3", depth="smoke")
@pytest.mark.proves("dev07-5-2", depth="smoke")
@pytest.mark.proves("dev07-5-2", depth="smoke")
@pytest.mark.proves("dev07-3-2", depth="smoke")
def test_a_suite_that_cites_nothing_yet_is_a_correct_first_run(monkeypatch, capsys, tmp_path):
    """The case that must stay **green**, and the reason the discriminator is *tests observed*
    rather than *stories cited*: every adopter's first run looks like this, and failing it would
    make the tool unusable on the day it is installed.

    Green, and not silent (`dev07-5-2`). This asserted no condition at all until a consumer lost hours
    to the other thing that looks exactly like this — a name-identical annotation compiled into
    their project, which made thirty-eight real citations invisible and printed the words a first
    run gets. Not failing it is the claim; saying nothing was the accident.
    """
    assert _exit_code(monkeypatch, project(tmp_path, UNCITED_ONLY)) == 0, "green, and stays green"

    payload = json.loads(capsys.readouterr().out)
    assert payload["stories"] == {}, "no stories — the same empty board as a broken run"
    assert payload["observed_tests"] == 1, "and this is the one field that tells them apart"
    assert [c["code"] for c in payload["conditions"]] == ["observation.uncited"]
    said = payload["conditions"][0]["what"]
    assert "nothing is claimed here yet" in said and "could not be read" in said, (
        "and it names both possibilities rather than picking one — the manifest cannot tell, and a "
        "condition that guessed would send a project doing the tutorial in order hunting for a bug")


@pytest.mark.proves("dev07-4-2", depth="smoke")
def test_config_can_declare_an_archetype_the_run_never_learned(monkeypatch, capsys, tmp_path):
    """An archetype is a fact no run can observe, so a project states it where the tool reads one.

    This is the only channel, in every language. A spec authored as Python modules could be
    collected by the run, and one once handed this over; no other language has such a moment, so
    that made one fact reachable in one language and left this a second home. It is a **property table**
    rather than a list (`dev07-3-2`): keyed by id, consulted when that id turns up in a run, and
    silent about every id it does not mention — so it says how to judge a subject without ever
    claiming to know which subjects exist.
    """
    cites_inertly = '''
import pytest
from pathlib import Path

@pytest.mark.proves("APP-1", depth="unit")
def test_reads_the_source_and_never_runs_it():
    core = Path(__file__).parent / "src" / "{pkg}" / "core.py"
    assert "def double" in core.read_text()
'''
    root = project(tmp_path, cites_inertly,
                   config='production = ["src/{pkg}"]\n\n[archetypes]\nAPP-1 = "structural"\n')

    payload = board_from(monkeypatch, capsys, root)

    assert payload["stories"]["APP-1"]["status"] == PROVEN, (
        "an inert test proves a structural story — and plumb.toml is where this project said it "
        "was structural, because nothing in the run could have")


@pytest.mark.proves("dev07-3-2", depth="smoke")
def test_a_manifest_outside_the_window_is_migrated_and_then_read(
        monkeypatch, capsys, tmp_path):
    """The version-window policy's outcome, asserted — and it was **false** until `plumb manifest migrate` existed.

    **No longer narrowed by hand.** This used to monkeypatch the window, because every version in
    the chain was also one a run accepted — our own Java adapter emitted the oldest, so the window
    was held open to cover it and the migrate path had no naturally out-of-range case. Major 8
    gave it one: the chain parses three majors and a run accepts two, so a major-6 document is
    genuinely readable and genuinely refused, and this exercises the real constants.
    """
    old = tmp_path / "archived.json"
    old.write_text(json.dumps({
        "schema_version": "7.0", "observed_tests": 1,
        "stories": {"APP-1": {"citations": [
            {"test": "t::a", "depth": "unit", "result": "passed"}]}}}))

    assert cli.main(["board", "--manifest", str(old)]) == 2, "out of the window a run accepts"
    assert "manifest migrate" in capsys.readouterr().err, "and told the way forward"

    assert cli.main(["manifest", "migrate", str(old)]) == 0
    capsys.readouterr()

    assert cli.main(["board", "--json", "--manifest", str(old)]) == 0, "and now it reads"
    payload = json.loads(capsys.readouterr().out)
    assert "APP-1" in payload["stories"], "the citation survived the climb"


@pytest.mark.proves("dev07-3-2", depth="smoke")
def test_migrating_a_current_manifest_rewrites_nothing(capsys, tmp_path):
    """Idempotent and silent about it. A migration that always writes would touch every file it
    was pointed at, so `mtime` would stop meaning *this was brought forward*."""
    current = tmp_path / "now.json"
    current.write_text(Manifest(stories={}, observed_tests=0).to_json())
    before = current.read_text()

    assert cli.main(["manifest", "migrate", str(current)]) == 0
    assert "already at schema" in capsys.readouterr().out
    assert current.read_text() == before, "not one byte"


@pytest.mark.proves("dev07-3-2", depth="smoke")
def test_a_shape_below_the_chain_is_refused_without_naming_a_command_that_cannot_help(
        capsys, tmp_path):
    """A circular instruction is worse than none, because it reads like a remedy. Telling somebody
    to run `plumb manifest migrate` when they *are* running it sends them round the loop; the
    honest answer is that the chain does not reach that far and nothing can infer the shape."""
    ancient = tmp_path / "ancient.json"
    ancient.write_text('{"schema_version": 3, "stories": {}}')

    assert cli.main(["manifest", "migrate", str(ancient)]) == 1
    refusal = capsys.readouterr().err
    assert "no migration path" in refusal
    assert "manifest migrate" not in refusal, "never point at the command being run"


@pytest.mark.proves("dev07-5-3", depth="smoke")
def test_every_shape_the_rendered_board_prints_is_exercised(monkeypatch, capsys, tmp_path):
    """`dev07-5-3`. Every other check here reads the emitted **format**; nothing reads the **page**.

    So a row shape can vanish from the rendering entirely while the JSON is byte-identical and the
    suite stays green — which is what happened: a per-claim group stopped printing when an
    identifier was renamed in a loop header and not its body, and it was found by a human looking
    at output.

    Shapes, not wording. Asserting exact text would be a golden file that fails on every reword
    and gets deleted, which is the cries-wolf failure already filed once here.
    """
    cites_three = '''
import pytest

@pytest.mark.proves("APP-1", depth="unit")
def test_one():
    from {pkg}.core import double
    assert double(2) == 4

@pytest.mark.proves("APP-2", depth="unit")
def test_two():
    assert True

@pytest.mark.proves("DEC-1", depth="unit", about="levers")
def test_levers():
    from {pkg}.core import double
    assert double(1) == 2
'''
    # The subjects are the ones the run cited; the aspects and the reduction are the facts no run
    # can observe, so they come from the project's declaration (`dev07-3-2`).
    root = project(tmp_path, cites_three, config=(
        '[aspects]\nDEC-1 = ["levers", "outcome", "falsifier"]\n\n'
        '[reduce]\nDEC-1 = "worst"\n'))

    monkeypatch.syspath_prepend(root + "/src")
    monkeypatch.chdir(root)
    assert cli.main(["board", root]) == 0
    page = capsys.readouterr().out

    assert "══════ BOARD ══════" in page, "the board is framed, so it can be found in a log"
    assert "APP-1" in page and "PROVEN" in page, "a plain verdict"
    assert "APP-2" in page and "UNPROVEN" in page, "one that is given and not cited"
    # The shape that silently disappeared: a subject with aspects prints a bare subject line and
    # one indented row per aspect, and never a status of its own (`dev07-4-3-ur05`).
    subject = next(l for l in page.splitlines() if l.strip() == "DEC-1")
    assert subject.strip() == "DEC-1", "the subject line carries no status"
    for aspect in ("levers", "outcome", "falsifier"):
        assert any(f"· {aspect}" in l for l in page.splitlines()), f"a row for {aspect}"


@pytest.mark.proves("dev07-6-2", depth="smoke")
def test_a_series_accumulates_across_runs_and_is_never_written_unasked(
        monkeypatch, capsys, tmp_path):
    """`dev07-6`, through the entry point an adopter actually uses.

    The component tests exercise the store directly and read **ungrounded** for it — they run
    production code without entering through a declared surface, which is `dev07-4-2` catching the
    orphaned-*done* shape and is why this exists rather than being redundant with them.

    **Opt-in, and the assertion that matters is the negative one.** A board run without `--series`
    writes nothing at all: a store that appeared because somebody asked for JSON would be a
    mutating read, and a series nobody chose to keep is one nobody knows the shape of.
    """
    root = project(tmp_path, CITES_PASSING)
    store = Path(root) / "series.jsonl"

    monkeypatch.syspath_prepend(root + "/src")
    monkeypatch.chdir(root)

    assert cli.main(["board", root]) == 0
    assert not store.exists(), "no series unless one was asked for"

    assert cli.main(["board", "--series", str(store), root]) == 0
    first = len(store.read_text().splitlines())
    assert cli.main(["board", "--series", str(store), root]) == 0
    second = len(store.read_text().splitlines())

    assert first > 1, "the first run records its facts and that it happened"
    assert second == first + 1, "and an unchanged second run records only that it happened"


@pytest.mark.proves("dev07-5-1", depth="smoke")
def _without_when(story: dict) -> dict:
    """A story minus the instant each run observed it.

    Two boards are two runs, and `when` is a property of the run rather than of the story — so a
    second boundary crossed between them made this comparison fail about once in eight, and the
    failure said *scoping changed the story* about a clock. What the claim is actually about is
    everything else.
    """
    return {**story, "evidence": [{k: v for k, v in cited.items() if k != "when"}
                                  for cited in story["evidence"]]}


def test_scoping_the_board_is_a_view_and_never_a_gate(monkeypatch, capsys, tmp_path):
    """A repository can carry more than one spec. Scoping shows one of them, and every story
    reads exactly what it reads unscoped — narrowing to the spec that happens to look good must
    buy nothing."""
    cites_two_namespaces = '''
import pytest

@pytest.mark.proves("APP-1", depth="unit")
def test_app():
    from {pkg}.core import double
    assert double(2) == 4

@pytest.mark.proves("OPS-1", depth="unit")
def test_ops():
    from {pkg}.core import double
    assert double(3) == 6
'''
    root = project(tmp_path, cites_two_namespaces)

    everything = board_from(monkeypatch, capsys, root)
    scoped = board_from(monkeypatch, capsys, root, "--scope", "OPS")

    assert sorted(everything["stories"]) == ["APP-1", "OPS-1"]
    assert sorted(scoped["stories"]) == ["OPS-1"], "the view narrows"
    assert _without_when(scoped["stories"]["OPS-1"]) == _without_when(everything["stories"]["OPS-1"]), \
        "and a story reads the same in every scope that contains it"


CITES_A_DECISION = '''
import pytest

@pytest.mark.informs("D-1", about="falsifier")
def test_the_condition_has_not_fired():
    from {pkg}.core import double
    assert double(2) == 4

@pytest.mark.informs("D-1", about="outcome")
def test_what_it_was_meant_to_achieve_happened():
    from {pkg}.core import entry
    assert entry(3) == 6

@pytest.mark.proves("APP-1", depth="wiring")
def test_an_ordinary_story_alongside_it():
    from {pkg}.core import entry
    assert entry(1) == 2
'''

DECLARES_A_DECISION = '''
adapter = "python"
production = ["src/{pkg}"]
entry_points = ["{pkg}.core:entry"]

# The facts no run can observe, as property tables keyed by id (`dev07-3-2`). Nothing here says
# which subjects exist — only how to judge one, if the run turns it up.
[lexicon]
D-1 = "decision"

[aspects]
D-1 = ["levers", "outcome", "falsifier"]

[reduce]
D-1 = "worst"
'''


@pytest.mark.proves("dev07-3-1", depth="smoke")
def test_a_decision_is_cited_per_aspect_and_reads_in_its_own_words(monkeypatch, capsys, tmp_path):
    """**The first time `informs` has run at all.** It was implemented, registered against
    `--strict-markers`, documented — and exercised only through hand-built fake marks inside this
    project's own suite, which is the favourable case by construction: a fake mark cannot tell you
    pytest accepts the real one, that the aspect survives into the manifest, or that the board says
    a decision's word rather than a story's.

    A subject with several aspects has **no aggregate status**: they close at different times and
    for different reasons, so one word for all three loses the finding rather than simplifying it.
    """
    root = project(tmp_path, CITES_A_DECISION, DECLARES_A_DECISION)

    payload = board_from(monkeypatch, capsys, root)
    decision, story = payload["stories"]["D-1"], payload["stories"]["APP-1"]

    assert [c["code"] for c in decision["conditions"]] == ["aspects.per-aspect"], \
        "a subject with aspects has no single status, and says so rather than inventing one"
    assert story["label"] == "proven", "and a story beside it is unaffected by any of this"

    assert decision["aspects"] is not None, (
        "`aspects.per-aspect` tells a consumer to read the aspects, so the machine-readable board "
        "has to carry them — it did not, and `--json` was a dead end at the word 'unproven'")
    assert decision["aspects"]["levers"]["label"] == "silent", \
        "nothing cites the levers, and for a decision that is *silent*, never *unproven*"
    assert decision["aspects"]["outcome"]["label"] == "holding", \
        "the outcome ran under the entry point and passed — a decision *holds*"
    assert story["aspects"] is None, "one aspect is no aspects to report"

    assert {c["about"] for c in decision["evidence"]} == {"falsifier", "outcome"}, \
        "each citation says which aspect it is about, so a per-aspect verdict is auditable"
    assert all(c.get("depth") in (None, "") for c in decision["evidence"]), \
        "`informs` claims no rung, and none may be invented for it"


@pytest.mark.proves("dev07-5-1", depth="smoke")
def test_the_one_field_read_alone_is_never_greener_than_what_earned_it(
    monkeypatch, capsys, tmp_path
):
    """`dev07-5-1` where it is actually consumed. Per-aspect verdicts only protect a reader who looks
    at them, and the commonest reader does not: a CI step, a badge, a dashboard column each take
    `status` alone. So the aggregate above the aspects has to refuse to summarise, and refusing is
    the whole behaviour — there is nothing to render.

    `D-1` has one aspect holding and one nobody has looked at. Averaging them, taking the best, or
    falling back to the story reduction would each turn that into a green, and each would read as
    presentation rather than as a claim, which is exactly why the rule is a story rather than a
    convention someone remembers.

    Driven through `plumb board` rather than `derive`, because the failure this forbids is a
    property of what *crosses the boundary*: the same verdict object is already correct in-process
    and would still be, with the emitted field wrong.
    """
    root = project(tmp_path, CITES_A_DECISION, DECLARES_A_DECISION)
    decision = board_from(monkeypatch, capsys, root)["stories"]["D-1"]

    assert decision["aspects"]["outcome"]["label"] == "holding", "one aspect did earn a green"
    assert decision["aspects"]["levers"]["label"] == "silent", "and one was never looked at"

    assert decision["status"] == "unproven", (
        "the field a consumer reads on its own carried a green no aspect earned")
    assert decision["label"] not in ("proven", "holding"), (
        "and the word must not hand back what the status withheld — a lexicon is a projection of "
        "a derived status, never a second place to author standing. Asserted as *not green* "
        "rather than as one exact word, because which word an aggregate carries is a rendering "
        "decision and this story is only about the direction it may not move in")


CITES_TWO_NAMESPACES = '''
import pytest

@pytest.mark.proves("APP-1", depth="unit")
def test_one():
    from {pkg}.core import double
    assert double(2) == 4

@pytest.mark.proves("OPS-1", depth="unit")
def test_two():
    from {pkg}.core import double
    assert double(3) == 6
'''


@pytest.mark.proves("dev07-3-2", depth="smoke")
def test_a_board_covers_what_was_cited_and_offers_no_denominator(monkeypatch, capsys, tmp_path):
    """The subjects on a board are the ones something cited, and the board says as much.

    Written because the alternative shipped and had to be taken back out. A `stories` key once
    named a file of subjects for the board to answer against, so an uncited subject read UNPROVEN
    instead of being absent — a list handed over is a copy of a list the project owns, and it goes
    stale the moment theirs moves with nothing here able to detect it. Nothing tested that it was
    gone, which is how it would come back.

    Two halves, and the second is the one a reader is hurt by. The board must carry only cited
    subjects, *and* it must say so: counts with no denominator stated read as a denominator, and
    "78 proven, 54 unproven" is taken for the whole of a project by whoever is looking now.
    """
    root = project(tmp_path, CITES_PASSING)
    # A key naming a set of subjects is not part of the config and cannot be reintroduced by
    # writing one: whatever is here, the board answers for citations.
    (Path(root) / "stories.csv").write_text("id\nAPP-1\nAPP-99\nAPP-100\n")

    payload = board_from(monkeypatch, capsys, root)

    assert set(payload["stories"]) == {"APP-1"}, (
        "the board answered for a subject nothing cited — the only source of subjects is a "
        f"citation, and a file sitting beside the project is not one: {sorted(payload['stories'])}")

    monkeypatch.chdir(root)
    assert cli.main(["board", root]) == 0
    text = capsys.readouterr().out
    assert "answering for the 1 subject(s) this run's tests cited" in text, (
        "the text board printed its counts without saying what they are counts *of*, so a reader "
        f"has nothing telling them this is their citations rather than their project:\n{text}")


@pytest.mark.proves("dev07-3-2", depth="smoke")
def test_a_namespace_is_declared_and_is_never_a_directory(monkeypatch, capsys, tmp_path):
    """Two namespaces coexist on one board, and what places a subject in one is its **id**.

    Nothing is read from a path: the two subjects below live in one file, in one directory, and
    are told apart only by what they are called. That is what makes a namespace stable where a
    directory is not — a directory belongs to whichever runner collected the files, so it differs
    per language and stops existing the moment two languages share a repository.
    """
    root = project(tmp_path, CITES_TWO_NAMESPACES,
                   config='adapter = "python"\nspecs = ["APP", "OPS"]\n'
                          'production = ["src/{pkg}"]\n')

    payload = board_from(monkeypatch, capsys, root)

    assert set(payload["stories"]) == {"APP-1", "OPS-1"}, \
        "two declared namespaces share one board, and neither excludes the other"

    scoped = board_from(monkeypatch, capsys, root, "--scope", "OPS")
    assert set(scoped["stories"]) == {"OPS-1"}, \
        "scoping selects by id prefix, with no directory anywhere in the question"
    assert scoped["stories"]["OPS-1"]["label"] == payload["stories"]["OPS-1"]["label"], \
        "and a subject reads the same in every scope containing it (`dev07-5-1`)"


@pytest.mark.proves("dev00-1-2", depth="smoke")
def test_adoption_is_one_command_one_file_and_then_a_board(monkeypatch, capsys, tmp_path):
    """The whole distance from a project with no Plumb in it to a board, measured.

    `dev00-1-2` and `dev00-1-3` already hold what `init` writes and what it says afterwards. What neither
    reaches is the claim's own measure: adoption is the distance to **a board**, so a test that
    stops at the config stops one step before the thing being claimed.

    The two halves are asserted in the order a project meets them. **One file**, because
    everything past `plumb.toml` is the project's own business and a tool that writes it is
    choosing somebody's workflow — this once emitted six Python modules into whatever repository
    ran it. **Then a board**, from a citation and nothing else: no spec, no catalog, no list of
    subjects, which is what makes the id opaque (`dev07-3-2`) rather than something we hold.
    """
    from plumb.scaffold import init

    root = project(tmp_path, CITES_PASSING)          # no plumb.toml — the pre-adoption state
    before = {p.name for p in Path(root).iterdir()}
    assert "plumb.toml" not in before, "the fixture has to start with no declaration to measure one"

    init(root)

    landed = {p.name for p in Path(root).iterdir()} - before
    assert landed == {"plumb.toml"}, (
        f"adoption wrote more than the declaration: {sorted(landed)} — everything past plumb.toml "
        f"is the project's own business, and in another language it is a toolchain they may not have")

    payload = board_from(monkeypatch, capsys, root)
    assert set(payload["stories"]) == {"APP-1"}, (
        "one command and one file did not reach a board — the honest measure of adoption is the "
        f"distance to a board, and this is where it is read: {sorted(payload['stories'])}")


@pytest.mark.proves("dev07-1-1", depth="wiring")
def test_a_board_refuses_rather_than_observing_a_run_the_build_does_not_perform(tmp_path, capsys):
    """Driven through the command, because the claim is that the *board* stops — not that a helper
    raises. A check that refuses and a launcher that goes ahead anyway are the same defect the
    check exists to prevent, one layer up.
    """
    from plumb import cli

    (tmp_path / "pom.xml").write_text(
        '<project xmlns="http://maven.apache.org/POM/4.0.0"><artifactId>app</artifactId>'
        "<modules><module>core</module></modules></project>")
    core = tmp_path / "core" / "target" / "classes"
    core.mkdir(parents=True)
    (core / "Thing.class").write_bytes(b"\xca\xfe\xba\xbe")
    (tmp_path / "core" / "pom.xml").write_text(
        '<project xmlns="http://maven.apache.org/POM/4.0.0"><artifactId>core</artifactId></project>')
    (tmp_path / "plumb.toml").write_text(
        'adapter = "java"\nproduction = ["com.acme.*"]\n\n[java]\n'
        'tests = "core/target/classes"\nclasspath = "core/target/classes"\n')
    # The one the build compiles into and the classpath does not carry. `classes` is present so the
    # refusal is about `test-classes` alone, which is what makes it a divergence rather than an
    # empty project.
    (tmp_path / "core" / "target" / "test-classes").mkdir()
    (tmp_path / "core" / "target" / "test-classes" / "ThingTest.class").write_bytes(b"\xca\xfe\xba\xbe")

    assert cli.main(["board", "--project", str(tmp_path)]) == 2, \
        "a board it cannot honestly derive is not one"

    said = capsys.readouterr()
    assert "core/target/test-classes" in said.err
    assert "not the one your build runs on" in said.err


@pytest.mark.proves("dev07-1-3", depth="wiring")
def test_a_blind_run_still_boards_and_the_board_says_the_instrument_failed(
        tmp_path, monkeypatch, capsys):
    """The fact crosses four seams between the launcher that learns it and the board that prints
    it, and each of them was a place it could be dropped silently.

    Driven through the command for that reason: a launcher that knows the observer died and a board
    that does not say so is the same outage as not knowing, and every layer in between reports
    success either way.
    """
    from plumb import cli, launch
    from plumb.core.gate import OBSERVATION_FAILED
    from plumb.core.manifest import Citation, Manifest, Story

    (tmp_path / "plumb.toml").write_text('adapter = "java"\n\n[java]\nclasspath = "x"\n')
    ran = Manifest(
        stories={"APP-1": Story(citations=(Citation(test="t", depth="unit", result="passed",
                                                    grounding="not-checked"),))},
        observed_tests=1)
    monkeypatch.setattr(launch, "_run_adapter", lambda *a, **k: (ran, True))

    assert cli.main(["board", "--json", "--project", str(tmp_path)]) == 0

    board = json.loads(capsys.readouterr().out)
    codes = [c["code"] for c in board["conditions"]]

    assert OBSERVATION_FAILED in codes, "the board reports a run it was told was blind"
    assert board["stories"]["APP-1"]["status"] == "passed-wiring-not-verified", \
        "and the story degrades rather than failing — the tests still answered"


@pytest.mark.proves("dev07-6-1", depth="smoke")
def test_a_board_read_from_a_manifest_appends_to_the_series(capsys, tmp_path):
    """`--manifest` and `--series` together: the run's mark lands in the history and the board
    renders — not a crash after the append."""
    path = tmp_path / "junit.json"
    path.write_text(FOREIGN_MANIFEST)
    store = tmp_path / "series.jsonl"

    assert cli.main(["board", "--manifest", str(path), "--series", str(store)]) == 0
    assert "series:" in capsys.readouterr().err
    assert store.read_text().strip(), "the run left its mark"


@pytest.mark.proves("dev07-3-2", depth="smoke")
def test_a_python_run_names_every_citing_test_when_asked(monkeypatch, capsys, tmp_path):
    """`--tests` lists each citing test and what it grounded, for Python as for Java — the per-test
    fact a reader needs when a board is not what they expected."""
    root = project(tmp_path, CITES_PASSING)
    monkeypatch.syspath_prepend(root + "/src")
    monkeypatch.chdir(root)
    assert cli.main(["board", "--tests", root]) == 0
    said = capsys.readouterr().err
    assert "python: not-checked" in said and "::test_one" in said, said


@pytest.mark.proves("dev07-4-1", depth="smoke")
@pytest.mark.proves("dev07-5-2", depth="smoke")
def test_a_condition_names_what_it_is_about(monkeypatch, capsys, tmp_path):
    """`dev07-4-1-ur4`, `dev07-5-2-ur12` — an id outside the declared namespaces is named on its own
    subject, the text board names the stories each condition is about, and each piece of evidence
    says whether its test reached outside the entry point."""
    body = (CITES_PASSING.replace('"APP-1"', '"APX-9"')
            + '\n\n@pytest.mark.proves("APP-1", depth="unit")\n'
              'def test_two():\n    from {pkg}.core import double\n    assert double(2) == 4\n')
    root = project(tmp_path, body, config='specs = ["APP"]\n')
    payload = board_from(monkeypatch, capsys, root)
    codes = {sid: [c["code"] for c in s["conditions"]] for sid, s in payload["stories"].items()}
    assert "spec.orphan" in codes["APX-9"] and "spec.orphan" not in codes["APP-1"], codes
    evidence = payload["stories"]["APP-1"]["evidence"][0]
    assert "reached_outside_entry" in evidence, evidence

    assert cli.main(["board", root]) == 0
    text = capsys.readouterr().out
    assert any("[spec.orphan]" in line and "APX-9" in line for line in text.splitlines()), text


@pytest.mark.proves("dev07-4-1", depth="smoke")
def test_an_id_the_project_declared_in_its_own_tables_is_not_an_orphan(monkeypatch, capsys,
                                                                       tmp_path):
    """`dev07-4-1-ur5` — a decision or parameter the project names in `[aspects]`, `[lexicon]` or
    `[reduce]` is already declared, so it is no typo; an id named nowhere still is one."""
    body = (CITES_PASSING
            + '\n\n@pytest.mark.informs("D27", about="falsifier")\n'
              'def test_decision():\n    assert True\n'
            + '\n\n@pytest.mark.informs("RETRIES", about="value")\n'
              'def test_parameter():\n    assert True\n'
            + '\n\n@pytest.mark.informs("D99")\n'
              'def test_typo():\n    assert True\n')
    config = ('specs = ["APP"]\n\n[lexicon]\nD27 = "decision"\nRETRIES = "parameter"\n\n'
              '[reduce]\nD27 = "worst"\n\n[aspects]\nD27 = ["falsifier"]\n')
    root = project(tmp_path, body, config=config)
    payload = board_from(monkeypatch, capsys, root)
    codes = {sid: [c["code"] for c in s["conditions"]] for sid, s in payload["stories"].items()}
    assert "spec.orphan" not in codes["D27"], codes
    assert "spec.orphan" not in codes["RETRIES"], codes
    assert "spec.orphan" in codes["D99"], "an id declared nowhere is still named"
    assert "spec.orphan" in [c["code"] for c in payload["conditions"]], "D99 is outside, so the run says so"

    only_declared = body.split("\n\n@pytest.mark.informs(\"D99\")")[0]
    root = project(tmp_path / "again", only_declared, config=config)
    payload = board_from(monkeypatch, capsys, root)
    assert "spec.orphan" not in [c["code"] for c in payload["conditions"]], \
        "and with every outside id declared, the run has nothing to say about namespaces"
    assert cli.main(["board", root]) == 0
    assert "spec.orphan" not in capsys.readouterr().out, "and the text board agrees with the JSON"


#: Two stories the same test drives unchecked, one that checks, and one that never reaches an entry
#: point — so it is cited, unproven, and never mutated.
SURVIVORS_SHARED = ONE_CHECKS_AND_ONE_DOES_NOT + '''
@pytest.mark.proves("APP-2", depth="wiring")
@pytest.mark.proves("APP-3", depth="wiring")
def test_also_runs():
    from {pkg}.core import entry
    entry(3)

@pytest.mark.proves("APP-4", depth="unit")
def test_not_wired():
    assert True
'''


def _mutated(monkeypatch, capsys, tmp_path, *flags):
    root = project(tmp_path, SURVIVORS_SHARED, config=OPTS_INTO_MUTATION)
    monkeypatch.syspath_prepend(root + "/src")
    monkeypatch.chdir(root)
    assert cli.main(["board", "--mutation", *flags, root]) == 0
    return capsys.readouterr()


@pytest.mark.proves("dev07-2-2", depth="smoke")
def test_mutation_progress_counts_what_it_mutates_and_starts_on_its_own_line(
        monkeypatch, capsys, tmp_path):
    """A counter that stopped at [3/4] read as a run that died; APP-4 is never mutated, so it is
    not one of the things being counted. And the cost line was glued to the runner's `[100%]`."""
    said = _mutated(monkeypatch, capsys, tmp_path).err
    progress = [line.strip() for line in said.splitlines() if line.strip().startswith("[")]
    assert [line.split("]")[0] + "]" for line in progress] == ["[1/3]", "[2/3]", "[3/3]"], said
    assert not any("APP-4" in line for line in progress), said
    assert any(line.startswith("mutation: ") for line in said.splitlines()), (
        f"the cost is said on a line of its own: {said}")


@pytest.mark.proves("dev07-2-4", depth="smoke")
def test_each_survivor_names_the_stories_it_sits_in(monkeypatch, capsys, tmp_path):
    """`dev07-2-4-ur3` — `(2 stories)` left the reader to work out which two."""
    said = _mutated(monkeypatch, capsys, tmp_path, "--survivors").out
    sites = [line for line in said.splitlines() if "swap-return" in line]
    assert sites, said
    for line in sites:
        assert "APP-2" in line and "APP-3" in line and "stories)" not in line, line


@pytest.mark.proves("dev07-2-4", depth="smoke")
def test_a_reach_nobody_measured_is_not_reported_rather_than_zero(monkeypatch, capsys, tmp_path):
    """`dev07-2-4-ur7` — the Python pass does not observe reach, so `unreached: 0` claimed every
    survivor was reached."""
    root = project(tmp_path, SURVIVORS_SHARED, config=OPTS_INTO_MUTATION)
    payload = board_from(monkeypatch, capsys, root, "--mutation")
    blind = payload["stories"]["APP-2"]["mutation"]
    assert blind["survivors"] and all(s["reached"] is None for s in blind["survivors"]), blind
    assert blind["unreached"] is None, blind
    assert payload["stories"]["APP-1"]["mutation"]["unreached"] == 0, \
        "with no survivors there is nothing unmeasured, and none went unreached"

    assert cli.main(["board", "--mutation", root]) == 0
    board = capsys.readouterr().out
    line = next(l for l in board.splitlines() if "APP-2" in l)
    assert "not reported" in line, line


@pytest.mark.proves("dev07-3-3", depth="smoke")
def test_a_board_from_a_saved_manifest_asks_the_namespace_question_of_the_project_named(
        monkeypatch, capsys, tmp_path):
    """`dev07-3-3-ur7` — the CI recipe renders its log board from the run's saved manifest, and
    that board never carried `spec.orphan`, so the log and the run's own JSON disagreed. Told the
    project, it reads that project's `specs`; not told, it reads nobody's — least of all whatever
    plumb.toml sits where the command was typed."""
    body = (CITES_PASSING.replace('"APP-1"', '"APX-9"')
            + '\n\n@pytest.mark.proves("APP-1", depth="unit")\n'
              'def test_two():\n    from {pkg}.core import double\n    assert double(2) == 4\n'
            + '\n\n@pytest.mark.informs("D27")\ndef test_d():\n    assert True\n')
    root = project(tmp_path, body, config='specs = ["APP"]\n\n[lexicon]\nD27 = "decision"\n')
    saved = tmp_path / "artifacts" / "manifest.json"
    saved.parent.mkdir()

    monkeypatch.syspath_prepend(root + "/src")
    monkeypatch.chdir(root)
    assert cli.main(["board", "--json", "--emit-manifest", str(saved), root]) == 0
    direct = json.loads(capsys.readouterr().out)

    elsewhere = tmp_path / "someone-else"
    elsewhere.mkdir()
    (elsewhere / "plumb.toml").write_text('specs = ["ZZZ"]\n')
    monkeypatch.chdir(elsewhere)

    assert cli.main(["board", "--json", "--manifest", str(saved)]) == 0
    untold = json.loads(capsys.readouterr().out)
    assert "spec.orphan" not in json.dumps(untold), "the plumb.toml it stood beside is not read"

    assert cli.main(["board", "--json", "--manifest", str(saved), "--project", root]) == 0
    told = json.loads(capsys.readouterr().out)
    codes = {sid: [c["code"] for c in s["conditions"]] for sid, s in told["stories"].items()}
    assert "spec.orphan" in codes["APX-9"] and "spec.orphan" not in codes["APP-1"], codes
    assert "spec.orphan" not in codes["D27"], "and what the project declared is still declared"
    assert {k: v for k, v in told.items() if k != "rendered_at"} == \
           {k: v for k, v in direct.items() if k != "rendered_at"}, \
        "told the project, the saved manifest renders the board the run rendered"

    assert cli.main(["board", "--manifest", str(saved), "--project", root]) == 0
    assert "[spec.orphan]" in capsys.readouterr().out, "the text board too"


@pytest.mark.proves("dev07-3-3", depth="smoke")
def test_a_run_that_cannot_board_leaves_no_manifest_from_an_earlier_one(monkeypatch, capsys,
                                                                       tmp_path):
    """A reused CI workspace published last run's manifest as this run's, because a run that could
    not board left the file at `--emit-manifest` untouched."""
    broken = CITES_PASSING + "\ndef this is not python\n"
    root = project(tmp_path, broken)
    saved = tmp_path / "manifest.json"
    saved.write_text('{"schema_version": 9, "stories": {}}')

    monkeypatch.syspath_prepend(root + "/src")
    monkeypatch.chdir(root)
    assert cli.main(["board", "--json", "--emit-manifest", str(saved), root]) == 2
    capsys.readouterr()
    assert not saved.exists(), "the earlier run's manifest is gone, not passed off as this one's"


@pytest.mark.proves("dev07-5-2", depth="smoke")
def test_the_text_board_says_an_adapter_ran_blind_as_the_json_does(monkeypatch, capsys, tmp_path):
    """The text board and the JSON say the same run-level things: an adapter that ran blind is
    `observation.failed` on both, never on one alone."""
    import plumb.launch
    from plumb.core.manifest import Manifest

    monkeypatch.setattr(plumb.launch, "produce",
                        lambda config, **kw: (Manifest(stories={}, observed_tests=3), (), ("java",)))
    root = project(tmp_path, CITES_PASSING)
    monkeypatch.chdir(root)
    cli.main(["board", "--json", root])
    in_json = [c["code"] for c in json.loads(capsys.readouterr().out)["conditions"]]
    assert "observation.failed" in in_json, in_json
    cli.main(["board", root])
    assert "observation.failed" in capsys.readouterr().out
