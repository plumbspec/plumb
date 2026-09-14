"""Mutation: do a story's tests actually *check* its code? (chapter 4)

The cases that run a mutant build a **tiny project under ``tmp_path``** and point the check at
that, never at this repository. Mutation writes to the file it mutates, so aiming it at Plumb's
own source from inside Plumb's own test run would have the suite editing itself while it ran.
"""

from pathlib import Path

import pytest

from plumb.adapters.python.mutants import (
    FLIP_COMPARISON,
    NEGATE_BRANCH,
    OPERATORS,
    SWAP_RETURN,
    mutants,
    site_count,
)
from plumb.adapters.python.mutation import OptIn, fill, plan, run, scope
from plumb.adapters.python.surface import ProductionSurface
from plumb.core.gate import PROVEN, derive
from plumb.core.manifest import (
    GROUNDED,
    InvalidManifest,
    PASSED,
    Citation,
    Manifest,
    Mutation,
    Story,
)

#: Every mutable site in ``entry`` and ``double`` is on the path ``entry(2)`` takes, so a survivor
#: there can only mean the tests did not *check* the result — never that they did not reach it.
#: ``orphan`` is reachable from no entry point and exists to prove it is never mutated.
SOURCE = '''
def entry(n):
    total = 0
    if n > 0:
        total = double(n)
    return total


def double(n):
    return n * 2


def orphan(n):
    return n + 1
'''


def sample(tmp_path: Path, body: str) -> tuple[Path, ProductionSurface, str]:
    """A one-package project with one production module and one test file.

    The package name is unique per project for the reason ``test_end_to_end`` documents: an
    already-imported module of the same name would shadow this one, and the subprocess would
    quietly test a file from a previous case.
    """
    uniq = "".join(c if c.isalnum() else "_" for c in tmp_path.name)[:40]
    pkg = f"mut_{uniq}"
    root = tmp_path / "proj"
    (root / "src" / pkg).mkdir(parents=True)
    (root / "src" / pkg / "__init__.py").write_text("")
    (root / "src" / pkg / "core.py").write_text(SOURCE)
    (root / "test_mut.py").write_text(
        f"import sys\nsys.path.insert(0, {str(root / 'src')!r})\n"
        f"from {pkg}.core import entry, orphan\n" + body
    )
    return root, ProductionSurface.of(root / "src" / pkg,
                                      entry_points=(f"{pkg}.core:entry",)), pkg


def wired(pkg: str) -> tuple[str, ...]:
    """What the trace reports for a test that drove the entry point: the wired frames only."""
    return (f"{pkg}.core:entry", f"{pkg}.core:double")


CHECKS = '''
def test_it():
    assert entry(2) == 4
'''

RUNS_WITHOUT_CHECKING = '''
def test_it():
    entry(2)
'''

#: Two tests citing one story, and only the second would notice `double` breaking.
TWO_CITING_TESTS = '''
def test_reaches_it():
    entry(2)

def test_checks_it():
    assert entry(3) == 6
'''


# ---- the check itself ------------------------------------------------------------------

@pytest.mark.proves("dev07-2-3", depth="component")
@pytest.mark.proves("dev07-2-4", depth="component")
def test_the_score_separates_a_test_that_checks_from_one_that_merely_runs(tmp_path):
    """The whole of chapter 4 in one comparison. Both tests pass, both drive the same wired code,
    and only one of them would notice that code being broken — which is exactly what grounding
    cannot see and what a green suite therefore hides.

    A *score* rather than a word: a story's tests routinely run more than they check, so "did any
    mutant survive" is yes almost everywhere and tells a reader nothing about which story to open.
    """
    root, surface, pkg = sample(tmp_path, RUNS_WITHOUT_CHECKING)
    blind = run(plan("APP-1", ("test_mut.py::test_it",), {"test_mut.py::test_it": wired(pkg)},
                     surface), root)

    assert blind.killed == 0, "a test that asserts nothing notices nothing"
    assert blind.total > 1 and blind.survived == blind.total

    (root / "test_mut.py").write_text(
        (root / "test_mut.py").read_text().replace("    entry(2)", "    assert entry(2) == 4")
    )
    checking = run(plan("APP-1", ("test_mut.py::test_it",),
                        {"test_mut.py::test_it": wired(pkg)}, surface), root)

    assert checking.killed == checking.total, "every mutant on the checked path is caught"


@pytest.mark.proves("dev07-2-3", depth="component")
def test_every_test_citing_the_story_gets_a_chance_to_notice(tmp_path):
    """A mutant is run against *all* of the story's citing tests, so a survivor means "no test of
    this story noticed" rather than "the one I happened to pick did not" — which is what a reader
    assumes the word means anyway. Here the first test only reaches the code and the second
    checks it, and the score is the same as if the second had been alone."""
    root, surface, pkg = sample(tmp_path, TWO_CITING_TESTS)
    tests = ("test_mut.py::test_reaches_it", "test_mut.py::test_checks_it")
    both = run(plan("APP-1", tests, {t: wired(pkg) for t in tests}, surface), root)

    assert both.killed == both.total, "the checking citation catches what the blind one misses"


@pytest.mark.proves("dev07-2-4", depth="unit")
def test_a_question_never_asked_is_reported_as_nothing_not_as_a_score(tmp_path):
    """`None` is the unfilled slot (`dev07-3-3`). A story whose tests drove nothing wired has not
    been asked, and `0/0` would read like an answer."""
    _, surface, _ = sample(tmp_path, CHECKS)

    assert run(plan("APP-1", ("test_mut.py::test_it",), {}, surface)) is None
    assert run(plan("APP-1", (), {}, surface)) is None
    with pytest.raises(InvalidManifest, match="never a score out of zero"):
        Mutation(total=0, killed=0)


# ---- what gets mutated -----------------------------------------------------------------

@pytest.mark.proves("dev07-2-1", depth="component")
def test_only_code_that_ran_under_an_entry_point_is_mutated(tmp_path):
    """Scoping to the whole call tree instead was measurably wrong: it pulls in every helper a
    test brushed past, so nearly every story reported a survivor and the fact stopped
    distinguishing anything. `orphan` is in the same file and reachable from no entry point."""
    _, surface, pkg = sample(tmp_path, CHECKS)
    one = plan("APP-1", ("t",), {"t": wired(pkg)}, surface)

    assert one.targets and one.mutants
    assert one.targets[0].qualnames == ("double", "entry"), "orphan is not among them"

    nothing_wired = plan("APP-1", ("t",), {"t": ()}, surface)
    assert nothing_wired.mutants == 0, "a project with no wired code is asked nothing"


@pytest.mark.proves("dev07-2-1", depth="unit")
def test_the_scope_is_the_union_over_every_citing_test_grouped_by_file(tmp_path):
    root, surface, pkg = sample(tmp_path, CHECKS)
    targets = scope((f"{pkg}.core:entry", f"{pkg}.core:double", "outside.mod:fn"), surface)

    assert len(targets) == 1, "one file, whatever the trace called the frames in it"
    assert targets[0].path == root / "src" / pkg / "core.py"
    assert targets[0].qualnames == ("double", "entry")


@pytest.mark.proves("dev07-2-1", depth="unit")
def test_only_the_named_functions_are_mutated():
    """`dev07-2-1`'s cost argument and its honesty argument are the same argument: mutation is scoped
    to what the trace saw, so it adds no second map of story to code — the artifact `dev07-1-4`
    refuses to keep. What "only what changed" would add on top is still open (`dev07-2-1`)."""
    produced = list(mutants(SOURCE, module="app.core", scope=("entry",)))

    assert produced, "the wired function has mutable sites"
    assert {m.where for m in produced} == {"app.core:entry"}
    assert all("n + 1" in m.source for m in produced), "the unwired function is left alone"


@pytest.mark.proves("dev07-2-3", depth="unit")
def test_the_operator_set_is_three_source_mutations_applied_to_pythons_own_tree():
    """No PIT, no mutmut — the adapter owns a small AST transform, the same principle as the
    grounding tracer. A mutation engine answers a hundred questions and Plumb needs one; the
    other ninety-nine arrive as a dependency it has to carry."""
    produced = list(mutants(SOURCE, module="app.core", scope=("entry",)))

    assert set(OPERATORS) == {FLIP_COMPARISON, NEGATE_BRANCH, SWAP_RETURN}
    assert {m.operator for m in produced} == set(OPERATORS)
    assert all(m.line for m in produced), "a mutant names where it was made"


@pytest.mark.proves("dev07-2-3", depth="unit")
def test_a_comparison_is_flipped_to_its_negation_not_to_a_neighbour():
    """`>` becomes `<=`. Swapping it for `<` would leave the boundary case behaving identically,
    which is an equivalent mutant on the very input a test is most likely to use (`dev07-2-4`)."""
    flipped = [m for m in mutants(SOURCE, module="app.core", scope=("entry",))
               if m.operator == FLIP_COMPARISON]

    assert len(flipped) == 1
    assert "if n <= 0:" in flipped[0].source


@pytest.mark.proves("dev07-2-3", depth="unit")
def test_a_returned_value_is_swapped_for_a_different_one_never_the_same_one():
    """`return None` becoming `return None` is a test run spent to learn nothing (`dev07-2-4`)."""
    swaps = [m for m in mutants("def f(x):\n    if x:\n        return None\n    return\n",
                                module="app.core", scope=("f",))
             if m.operator == SWAP_RETURN]

    assert len(swaps) == 2
    assert all(m.source.count("return True") == 1 for m in swaps)


# ---- knowing the cost before paying it -------------------------------------------------

@pytest.mark.proves("dev07-2-2", depth="component")
def test_the_cost_can_be_read_off_before_any_of_it_is_spent(tmp_path):
    """Mutation is opt-in because it is slow, not because it is optional — it finds defects a
    green suite does not. So the decision is *when*, and a caller who cannot ask "how much"
    without starting the run can only find out by starting it."""
    _, surface, pkg = sample(tmp_path, CHECKS)
    one = plan("APP-1", ("test_mut.py::test_it",), {"test_mut.py::test_it": wired(pkg)}, surface)

    assert one.runnable and one.mutants > 0
    assert one.mutants == sum(site_count(t.path.read_text(), module=t.module, scope=t.qualnames)
                              for t in one.targets), "the estimate counts what the run will run"


@pytest.mark.proves("dev07-2-2", depth="unit")
def test_mutation_is_off_unless_the_project_asks_for_it(tmp_path):
    """Default-off is the story, so the default is what is checked — not merely that the switch
    works when thrown."""
    from plumb.config import Config

    assert OptIn().enabled is False
    assert OptIn.from_config(Config.find(tmp_path)).enabled is False, "nothing declared is off"

    (tmp_path / "plumb.toml").write_text('production = ["src"]\n')
    assert OptIn.from_config(Config.find(tmp_path)).enabled is False, \
        "declaring a surface is not opting in"

    (tmp_path / "plumb.toml").write_text("mutation = true\n")
    assert OptIn.from_config(Config.find(tmp_path)).enabled is True


@pytest.mark.proves("dev07-2-2", depth="component")
def test_with_the_opt_in_off_the_slot_is_left_unfilled_and_nothing_runs(tmp_path):
    """Not "runs and reports nothing" — does not run. A pass costs one test run per mutant, and a
    default that spends minutes is a default nobody leaves on."""
    _, surface, pkg = sample(tmp_path, CHECKS)
    manifest = Manifest(stories={"APP-1": Story(citations=(
        Citation(test="test_mut.py::test_it", depth="wiring", result=PASSED, grounding=GROUNDED),
    ))})

    # A root that does not exist: anything that tried to run a mutant here would fail loudly.
    filled = fill(manifest, {"test_mut.py::test_it": wired(pkg)},
                  surface, OptIn(), root=tmp_path / "nowhere")

    assert filled == manifest
    assert filled.stories["APP-1"].mutation is None


@pytest.mark.proves("dev07-2-3", depth="component")
def test_an_interrupted_run_leaves_the_tree_recoverable_and_says_so(tmp_path):
    """A pass runs for minutes to hours, so being killed is an ordinary way for one to end — and a
    leftover mutant is silent: the source still imports, still passes most tests, and answers
    slightly wrong. An interrupted run on a working copy already produced a measurement wrong by
    an order of magnitude with nothing about it looking wrong.
    """
    from plumb.adapters.python.mutation import RESCUE, restore

    root, _, pkg = sample(tmp_path, CHECKS)
    source = root / "src" / pkg / "core.py"
    original = source.read_bytes()

    # Exactly what a killed process leaves: the mutant on disk and the original parked beside it.
    (root / RESCUE).write_bytes(str(source).encode() + b"\n" + original)
    source.write_text("def entry(n):\n    return None\n")

    assert restore(root) == source
    assert source.read_bytes() == original
    assert not (root / RESCUE).exists()
    assert restore(root) is None, "a clean tree needs no rescue and reports none"


# ---- what the score may never do -------------------------------------------------------

@pytest.mark.proves("dev07-2-4", depth="unit")
def test_survivors_are_advisory_and_cannot_un_prove_a_story():
    """The gate is grounding, and mutation sits beside it. A survivor may be a weak test or an
    equivalent mutant and nothing can tell them apart (`dev07-2-4`), so blocking on one would be
    this framework shipping the heuristic-dressed-as-proof it warns about (`ch7-10`)."""
    citations = (Citation(test="t", depth="wiring", result=PASSED, grounding=GROUNDED),)
    none_killed = Story(citations=citations, mutation=Mutation(total=40, killed=0))
    all_killed = Story(citations=citations, mutation=Mutation(total=40, killed=40))

    assert derive("s", none_killed).status == PROVEN
    assert derive("s", none_killed) == derive("s", all_killed), \
        "the gate derives the same status either way"


@pytest.mark.proves("dev07-2-4", depth="unit")
def test_a_score_must_be_a_proportion_that_holds_together():
    """A vocabulary the core reasons over, checked at the manifest's edge like grounding's. More
    killed than were run is not a stricter result, it is a corrupt one."""
    assert Mutation(total=40, killed=39).survived == 1
    for bad in ((40, 41), (40, -1)):
        with pytest.raises(InvalidManifest, match="not within"):
            Mutation(total=bad[0], killed=bad[1])
