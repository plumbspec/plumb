"""The board — what crosses the boundary (chapter 5), and the adapter that feeds it."""

import json

import pytest

from plumb.adapters.python.adapter import PlumbAdapter
from plumb.core.board import BOARD_VERSION, Board
from plumb.core.gate import (
    NO_ENTRY_POINTS,
    NOT_CITED,
    PASSED_WIRING_NOT_VERIFIED,
    PROVEN,
    UNPROVEN,
    derive,
    label,
)
from plumb.core.manifest import (
    FAILED,
    GROUNDED,
    INERT,
    Mutation,
    NOT_CHECKED,
    PASSED,
    SKIPPED,
    Survivor,
    BEST,
    WORST,
    STRUCTURAL,
    Citation,
    Manifest,
    Story,
)


def manifest(**grounding_by_story) -> Manifest:
    return Manifest(stories={
        sid: Story(citations=(Citation(test=f"t::{sid}", depth="wiring", result=PASSED, grounding=g),))
        for sid, g in grounding_by_story.items()
    })


@pytest.mark.proves("dev07-5-1", depth="component")
def test_the_board_reports_status_and_achieved_depth_per_story():
    board = Board.render(manifest(a=GROUNDED, b=NOT_CHECKED))
    rendered = board.as_dict()["stories"]
    assert rendered["a"]["status"] == PROVEN
    assert rendered["a"]["achieved"] == ["wiring"]
    assert rendered["b"]["status"] == PASSED_WIRING_NOT_VERIFIED


@pytest.mark.proves("dev07-5-3", depth="component")
def test_the_board_emits_a_neutral_json_any_tool_can_read():
    payload = json.loads(Board.render(manifest(a=GROUNDED)).to_json())
    assert payload["stories"]["a"]["status"] == PROVEN
    assert isinstance(payload["stories"]["a"]["achieved"], list)


@pytest.mark.proves("dev07-5-3", depth="unit")
def test_the_emitted_format_carries_its_version():
    """External tools depend on the shape, so a breaking change is a new version."""
    assert json.loads(Board.render(Manifest()).to_json())["board_version"] == BOARD_VERSION


@pytest.mark.proves("dev07-5-3", depth="unit")
def test_the_boards_version_is_its_own_not_the_manifests():
    """The manifest is internal and the board is the public contract; tying the two would make
    an internal refactor look like a breaking change to every consumer."""
    from plumb.core import manifest as manifest_module

    board_fields = set(json.loads(Board.render(Manifest()).to_json()))
    assert "schema_version" not in board_fields, "the board must not leak the internal version"
    # The discriminating assertion: the two move independently. Tying them — BOARD_VERSION =
    # SCHEMA_VERSION — is the exact thing this story forbids, and the old test passed with it.
    assert BOARD_VERSION != manifest_module.SCHEMA_VERSION, (
        "they are at different numbers today precisely because they version for different "
        "reasons; if they ever coincide, assert independence some other way"
    )


@pytest.mark.proves("dev07-1-4", depth="component")
@pytest.mark.proves("dev07-5-2", depth="component")
def test_the_board_says_what_it_could_not_check_and_names_the_code():
    stories = Board.render(manifest(a=NOT_CHECKED)).as_dict()["stories"]
    condition = stories["a"]["conditions"][0]
    assert condition["code"] == NO_ENTRY_POINTS
    # The diagnosis, the instruction and the syntax are separately addressable: a reader wants
    # a different one of the three depending on why they are looking.
    assert condition["what"], "a code without a diagnosis helps nobody"
    assert condition["next_step"], "saying what is wrong without what to do is half an answer"
    assert "entry_points" in condition["example"], "an example must show where the value goes"


@pytest.mark.proves("dev07-5-2", depth="unit")
def test_an_unknown_code_still_emits_rather_than_vanishing():
    """A consumer keys off the code, so prose it has never seen must not break it."""
    from plumb.core.board import _signal

    assert _signal("some.future.code") == {
        "code": "some.future.code", "what": "", "next_step": "", "example": "",
    }


@pytest.mark.proves("dev07-5-2", depth="unit")
def test_what_the_board_can_say_is_a_list_not_an_open_question():
    """The set of codes is finite and knowable, so a consumer can enumerate what it must handle.

    Run-level conditions are in it for the same reason the others are: a consumer branching on a
    code has to be able to enumerate every code it might meet, and one that attaches to the run
    rather than to a story is not a different kind of promise.
    """
    from plumb.core.gate import ALL_CODES, CONDITIONS, RUN_CONDITIONS, UNLOCKS

    assert ALL_CODES == set(CONDITIONS) | set(UNLOCKS) | set(RUN_CONDITIONS)
    assert ALL_CODES, "a board that can say nothing surfaces nothing"
    # Every code carries its own name, so a consumer that has the code has the key it was found
    # under — the one place a typo would make a code unfindable by the id it advertises.
    for code, condition in (CONDITIONS | UNLOCKS | RUN_CONDITIONS).items():
        assert condition.code == code


@pytest.mark.proves("dev07-5-1", depth="component")
def test_the_board_carries_the_evidence_not_just_the_verdict():
    """A reviewer must be able to act on it — which citation, at what depth, grounded or not —
    rather than take the verdict on trust."""
    board = Board.render(manifest(a=GROUNDED))
    evidence = board.as_dict()["stories"]["a"]["evidence"]
    assert [e["grounding"] for e in evidence] == [GROUNDED]
    assert evidence[0]["depth"] == "wiring"
    assert evidence[0]["result"] == PASSED
    assert "test" in evidence[0], "the citation itself, so it can be opened"


@pytest.mark.proves("dev07-5-2", depth="component")
def test_the_board_surfaces_what_the_next_step_would_unlock():
    """The board markets its own next step from its own output, so nobody is sold anything."""
    from plumb.core.gate import UNLOCK_GROUNDING, UNLOCK_MUTATION

    partial = Board.render(manifest(a=NOT_CHECKED)).as_dict()["unlocks"]
    codes = [u["code"] for u in partial]
    assert UNLOCK_GROUNDING in codes
    assert "1" in [u for u in partial if u["code"] == UNLOCK_GROUNDING][0]["what"], \
        "the count comes from this run, not from something written down elsewhere"

    proven = Board.render(manifest(a=GROUNDED)).as_dict()["unlocks"]
    assert UNLOCK_MUTATION in [u["code"] for u in proven]


@pytest.mark.proves("dev07-5-2", depth="component")
@pytest.mark.proves("dev07-5-1", depth="component")
def test_a_step_already_taken_is_no_longer_offered():
    """"Turn on mutation" said to a project that just did is the board asserting a gap its own
    source does not show (`dev07-5-1`) — the same defect as telling someone to declare entry points
    when they already have."""
    from plumb.core.gate import UNLOCK_MUTATION

    checked = Manifest(stories={"a": Story(
        citations=(Citation(test="t::a", depth="wiring", result=PASSED, grounding=GROUNDED),),
        mutation=Mutation(total=8, killed=3),
    )})

    assert UNLOCK_MUTATION in [u["code"] for u in Board.render(manifest(a=GROUNDED)).as_dict()["unlocks"]]
    assert UNLOCK_MUTATION not in [u["code"] for u in Board.render(checked).as_dict()["unlocks"]]


@pytest.mark.proves("dev07-5-1", depth="component")
def test_the_board_carries_the_mutation_score_as_a_proportion_not_a_word():
    """A capability whose result the board never shows is one a reader has to go and find in the
    manifest — and `null` is *not asked* rather than a pass (`dev07-2-4`, `dev07-3-3`). It is a score
    because "survived" reads as a failing grade, and 39-of-40 has not failed anything."""
    assert Board.render(manifest(a=GROUNDED)).as_dict()["stories"]["a"]["mutation"] is None

    checked = Manifest(stories={"a": Story(
        citations=(Citation(test="t::a", depth="wiring", result=PASSED, grounding=GROUNDED),),
        mutation=Mutation(total=40, killed=39),
    )})
    # `survived` is the shortfall and `survivors` names it. Both: a consumer wanting the number
    # should not have to length-check a list, and an adapter that reports the shortfall without
    # naming it leaves the names empty while the count still answers (`dev07-5-1`).
    assert Board.render(checked).as_dict()["stories"]["a"]["mutation"] == {
        "total": 40, "killed": 39, "survived": 1, "unreached": 0, "survivors": []}

    named = Manifest(stories={"a": Story(
        citations=(Citation(test="t::a", depth="wiring", result=PASSED, grounding=GROUNDED),),
        mutation=Mutation(total=40, killed=39, survivors=(
            Survivor(operator="swap-return", where="Repo#find", file="src/Repo.java", line=12),)),
    )})
    assert Board.render(named).as_dict()["stories"]["a"]["mutation"]["survivors"] == [
        {"operator": "swap-return", "where": "Repo#find", "file": "src/Repo.java", "line": 12,
         "reached": None}], (
        "a surviving mutant is the most actionable thing mutation produces, and the reader's next "
        "move needs to know which one and where — a count leaves it to be re-derived by hand")

    # And a survivor no test reached is not a weak test: `unreached` counts only those an adapter
    # said `false` for, so an adapter that cannot observe reach reports none rather than all.
    unreachable = Manifest(stories={"a": Story(
        citations=(Citation(test="t::a", depth="wiring", result=PASSED, grounding=GROUNDED),),
        mutation=Mutation(total=40, killed=37, survivors=(
            Survivor(operator="swap-return", where="Repo#find", file="src/Repo.java",
                     line=12, reached=False),
            Survivor(operator="negate-branch", where="Repo#find", file="src/Repo.java",
                     line=13, reached=True),
            Survivor(operator="flip-comparison", where="Repo#find", file="src/Repo.java",
                     line=14),
        )),
    )})
    assert Board.render(unreachable).as_dict()["stories"]["a"]["mutation"]["unreached"] == 1, (
        "only the survivor observed NOT to have been reached counts — one nobody could observe is "
        "not reported, and reading it as unreachable would excuse a mutant on no evidence")


@pytest.mark.proves("dev07-5-2", depth="unit")
def test_an_empty_run_advertises_nothing():
    """An unlock is earned by the run. With nothing to improve, the board stays quiet."""
    assert Board.render(Manifest()).as_dict()["unlocks"] == []


def test_ids_order_numerically_and_still_handle_a_foreign_key():
    """Presentation, not a story claim — but a regression here reads as a bug in the board."""
    from plumb.core.board import natural_key

    ids = ["flow-10", "flow-2", "dev07-4", "dev07-4-2", "SHEET-42", "PROJ-7"]
    assert sorted(ids, key=natural_key) == [
        "PROJ-7", "SHEET-42", "dev07-4", "dev07-4-2", "flow-2", "flow-10",
    ]


def test_the_emitted_json_keeps_that_order_rather_than_re_sorting_lexically():
    board = Board.render(manifest(**{"flow-10": GROUNDED, "flow-2": GROUNDED}))
    assert list(json.loads(board.to_json())["stories"]) == ["flow-2", "flow-10"]


@pytest.mark.proves("dev07-3-3", depth="component")
def test_the_manifest_is_the_only_input_the_board_needs():
    """Every chapter meets at the manifest — render takes it and nothing else, and what comes
    out is derived from what went in. The old assertion was empty-in-empty-out, which passed
    with the entire gate replaced by `return {}`."""
    from plumb.core.gate import derive_all

    manifest = Manifest(stories={
        "a": Story(citations=(Citation(test="t::a", depth="unit", result=PASSED, grounding=GROUNDED),)),
        "b": Story(citations=(Citation(test="t::b", depth="unit", result=FAILED, grounding=GROUNDED),)),
    })
    board = Board.render(manifest)
    assert set(board.verdicts) == {"a", "b"}, "every story in, every story out"
    assert board.verdicts == derive_all(manifest), "the board renders what the gate derived"
    assert board.verdicts["a"].status != board.verdicts["b"].status, (
        "and the verdicts follow the manifest's contents, so deleting the gate cannot pass"
    )
    assert Board.render(Manifest()).verdicts == {}


@pytest.mark.proves("dev07-4-3", depth="component")
def test_authored_in_derived_out():
    """The citation is authored; the status is not. Change only the run, and the status moves."""
    passing = Manifest(stories={"a": Story(citations=(
        Citation(test="t::a", depth="unit", result=PASSED, grounding=GROUNDED),))})
    failing = Manifest(stories={"a": Story(citations=(
        Citation(test="t::a", depth="unit", result=FAILED, grounding=GROUNDED),))})
    assert Board.render(passing).verdicts["a"].status == PROVEN
    assert Board.render(failing).verdicts["a"].status == UNPROVEN


# ---- the adapter: pytest in, neutral facts out -----------------------------------------


def _cite(result=PASSED):
    """A real citation, inert so a structural subject can derive at all."""
    return Citation(test="t::a", depth="", result=result, grounding=INERT)


class FakeMark:
    """A pytest ``Mark``: a name, positional args and kwargs. `name` is part of that shape, and a
    double omitting it hides the code that tells one convention from another."""

    def __init__(self, *stories, depth="", ref=None, about=None, name="proves"):
        self.name = name
        self.args, self.kwargs = tuple(stories), {"depth": depth}
        if ref:
            self.kwargs["ref"] = ref
        if about:
            self.kwargs["about"] = about


class FakeItem:
    """Stands in for a pytest ``Item``, and carries `own_markers` because the real one does.

    A double that is missing part of the shape it imitates hides exactly the code that reads that
    part — the adapter looks at every marker on a test, not only its own, so that an empty board
    can say which convention it *did* find.
    """

    def __init__(self, nodeid, marks, own=None):
        self.nodeid, self._marks = nodeid, marks
        self.own_markers = own if own is not None else list(marks)

    def iter_markers(self, name):
        # **Filtered by name**, because the real one is. Returning every mark regardless made the
        # double blind to the code that tells one convention from another — and it stayed blind
        # until a second marker existed, at which point every citation was collected twice. A
        # double that ignores an argument does not simplify the shape, it deletes a behaviour.
        return iter([m for m in self._marks if m.name == name])


class FakeReport:
    def __init__(self, nodeid, outcome, when="call"):
        self.nodeid, self.outcome, self.when = nodeid, outcome, when


def run(items, reports) -> Manifest:
    adapter = PlumbAdapter()
    adapter.pytest_collection_modifyitems(items)
    for r in reports:
        adapter.pytest_runtest_logreport(r)
    return adapter.manifest()


@pytest.mark.proves("dev07-3-3", depth="component")
def test_the_adapter_turns_a_runners_own_signal_into_neutral_facts():
    m = run([FakeItem("t::a", [FakeMark("dev05", depth="wiring")])],
            [FakeReport("t::a", "passed")])
    citation = m.stories["dev05"].citations[0]
    assert (citation.result, citation.depth) == (PASSED, "wiring")


@pytest.mark.proves("dev05", depth="component")
def test_the_only_authored_link_is_the_marker_on_the_test():
    """Story -> test is derived from the citation and nothing else. There is no spec-side test
    list to drift against, so an uncited test is simply invisible rather than an inconsistency
    somebody has to reconcile."""
    m = run(
        [FakeItem("t::cited", [FakeMark("dev05", depth="component")]), FakeItem("t::silent", [])],
        [FakeReport("t::cited", "passed"), FakeReport("t::silent", "passed")],
    )
    assert [c.test for c in m.stories["dev05"].citations] == ["t::cited"]
    assert list(m.stories) == ["dev05"], "an uncited test contributes nothing to reconcile"
    assert "tests" not in Story.__dataclass_fields__, "no reverse citation from the spec side"


@pytest.mark.proves("dev07-5-1", depth="component")
@pytest.mark.proves("dev07-5-2", depth="component")
@pytest.mark.proves("dev07-5-1", depth="component")
@pytest.mark.parametrize("citations, reduce, story_word, decision_word", [
    ((), "best", "unproven", "silent"),
    ((_cite(),), "best", "proven", "holding"),
    ((_cite(result=FAILED),), "worst", "unproven", "breached"),
])
def test_a_subject_says_its_status_in_its_own_vocabulary(citations, reduce, story_word,
                                                         decision_word):
    """The words are a projection, never a second status.

    `proven` is the wrong word for a claim about the future — a decision can only be un-falsified
    *so far*, so `holding` is the strongest thing it may say. And the two readings of unproven,
    which for code are one situation, are opposites for it: **silent** is nobody watching
    (`dev07-4-3-ur10`, where the silence is the finding) and **breached** is the condition having fired
    (`dev07-4-3-nfr4`, which informs rather than fails). Splitting `evidence.none` from `evidence.failed`
    is what made either sayable.

    Every label below is derived from a status the gate already computed plus a condition it
    already carried, so nothing here can say what the derivation did not — `dev07-5-1` applied to the
    vocabulary rather than to a view, which is what stops a lexicon becoming a place where
    standing is quietly authored.
    """
    story = Story(archetype=STRUCTURAL, reduce=reduce, citations=citations)
    verdict = derive("s", story)

    assert label(verdict, "story") == story_word
    assert label(verdict, "decision") == decision_word
    assert verdict.status == story_word, "the stable code never moves — only the word does"


@pytest.mark.proves("dev07-3-1", depth="unit")
@pytest.mark.parametrize("outcome, wasxfail, expected", [
    ("skipped", False, SKIPPED),
    ("skipped", True, FAILED),
])
def test_an_xfail_is_not_a_skip(outcome, wasxfail, expected):
    """pytest spells both `skipped` and hands over `wasxfail` to tell them apart.

    An xfailed test **ran and failed**; a skipped one never ran. Collapsing them is the translation
    loss `dev07-3-1` refuses, and it hid the one case that matters: a decision whose falsifier has
    fired, recorded as a strict xfail so the suite stays green, was indistinguishable from a check
    nobody ran. It only became visible when `evidence.failed` split from `evidence.not-observed` —
    before that both landed on the same word and the loss cost nothing, which is why it survived.
    """
    from plumb.adapters.python.adapter import _normalize

    report = FakeReport("t::a", outcome)
    if wasxfail:
        report.wasxfail = "known"

    assert _normalize(report) == expected


@pytest.mark.proves("dev07-5-1", depth="component")
def test_a_parameter_reads_as_a_parameter_and_its_folds_reduce_all_of():
    """The third subject kind, and it costs a row in a table rather than a branch anywhere.

    A parameter derives exactly as a decision does — `dev07-4-3-ur09` says it **is** a decision with a
    model and a measurement — and reads differently, because neither *holding* nor *breached*
    fits. A value is not held; a hypothesis that loses to its own placebo has not been breached, it
    has been **refuted**. `unvalidated` is the ordinary case for a real corpus: priors with a
    stated way to test each and no observation against any.

    The reduction is the part that matters. A tuning plan requires a mechanism to show up *in
    every out-of-sample fold, not on average* — so four folds holding and one not is a **refuted**
    hypothesis, and `best` would call it supported. That is overfitting reported as success, in
    the flattering direction, which is what `worst` exists to refuse.
    """
    folds = tuple(Citation(test=f"t::fold{n}", depth="", result=PASSED, grounding=INERT,
                           about="out-of-sample") for n in range(4))
    dissenting = folds + (Citation(test="t::fold4", depth="", result=FAILED, grounding=INERT,
                                   about="out-of-sample"),)

    def read(citations, reduce):
        story = Story(archetype=STRUCTURAL, aspects=("out-of-sample",), reduce=reduce,
                      lexicon="parameter", citations=citations)
        return label(derive("P", story).aspects["out-of-sample"], "parameter")

    assert read((), WORST) == "unvalidated", "a prior nobody has measured"
    assert read(folds, WORST) == "supported", "held in every fold"
    assert read(dissenting, WORST) == "refuted", "four of five is not every fold"
    assert read(dissenting, BEST) == "supported", (
        "and best-of would have called it supported — the overfitting `worst` refuses")


@pytest.mark.proves("dev07-5-2", depth="unit")
def test_a_lexicon_with_no_word_for_a_state_says_the_state_rather_than_inventing_one():
    """An unlabelled status is a gap in the vocabulary, and a made-up word would hide it. Saying
    the code is the honest fallback and the one that gets the gap noticed."""
    verdict = derive("s", Story(archetype=STRUCTURAL, citations=(_cite(),)))

    assert label(verdict, "no-such-lexicon") == verdict.status


@pytest.mark.proves("dev07-3-1", depth="component")
def test_informs_cites_without_a_depth_and_never_invents_one():
    """A second marker, for a subject that is never *done*.

    A decision is a claim about the future and a parameter is a decision with a model, so neither
    can be **proven** — only informed, repeatedly, by evidence that keeps arriving. Reusing
    `proves` would import the doneness reading into the one place it must not be.

    It carries **no depth**, and that is a claim rather than an omission. Depth is a rung the run
    refutes (`dev07-4-2` checks a claimed one against grounding); the analogue for a decision would be
    authored and uncheckable, which is `dev07-4-3-nfr3`'s prohibition wearing a new name. So an `informs`
    citation reports no rung, and a `depth` written on one is ignored rather than carried — the
    marker cannot be talked into making a claim it has no way to lose.
    """
    m = run(
        [FakeItem("t::falsifier", [FakeMark("D27", about="falsifier", name="informs")]),
         FakeItem("t::story", [FakeMark("APP-1", depth="unit")])],
        [FakeReport("t::falsifier", "passed"), FakeReport("t::story", "passed")],
    )

    informed = m.stories["D27"].citations[0]
    assert informed.about == "falsifier", "which aspect it bears on"
    assert informed.depth == "", "no rung claimed, so none to refute"
    assert m.stories["APP-1"].citations[0].depth == "unit", "and `proves` is untouched"


@pytest.mark.proves("dev07-3-1", depth="component")
def test_a_depth_written_on_informs_is_not_carried():
    """The refusal that makes the previous test a claim rather than a coincidence. Somebody will
    write one out of habit, and carrying it would put a rung on the board that nothing can check —
    which is worse than dropping it, because it reads as evidence."""
    m = run([FakeItem("t::a", [FakeMark("D27", depth="wiring", name="informs")])],
            [FakeReport("t::a", "passed")])

    assert m.stories["D27"].citations[0].depth == ""


@pytest.mark.proves("dev07-3-1", depth="component")
@pytest.mark.parametrize("outcome,expected", [("passed", PASSED), ("skipped", SKIPPED), ("failed", FAILED)])
def test_every_runner_outcome_maps_without_translation_loss(outcome, expected):
    m = run([FakeItem("t::a", [FakeMark("s", depth="unit")])], [FakeReport("t::a", outcome)])
    assert m.stories["s"].citations[0].result == expected


@pytest.mark.proves("dev07-3-1", depth="component")
def test_a_green_setup_is_not_a_pass_and_a_teardown_error_is_not_either():
    setup_only = run([FakeItem("t::a", [FakeMark("s", depth="unit")])],
                     [FakeReport("t::a", "passed", when="setup")])
    assert setup_only.stories["s"].citations[0].result == SKIPPED, "a body that never ran proves nothing"

    broke_late = run([FakeItem("t::b", [FakeMark("s", depth="unit")])],
                     [FakeReport("t::b", "passed"), FakeReport("t::b", "failed", when="teardown")])
    assert broke_late.stories["s"].citations[0].result == FAILED


@pytest.mark.proves("dev07-3-1", depth="component")
def test_one_test_citing_two_stories_yields_two_citations_with_their_own_refs():
    m = run([FakeItem("t::a", [FakeMark("dev05", depth="wiring", ref="PROJ-7"),
                               FakeMark("dev07-3-3", depth="unit", ref="PROJ-9")])],
            [FakeReport("t::a", "passed")])
    assert m.stories["dev05"].citations[0].ref == "PROJ-7"
    assert m.stories["dev07-3-3"].citations[0].depth == "unit"


@pytest.mark.proves("dev07-3-1", depth="component")
def test_the_adapter_leaves_grounding_unfilled_rather_than_guessing_it():
    """Nothing declares a production surface yet, so inventing a fact would be the adapter
    stamping a verdict — the one thing dev07-3-1 forbids."""
    m = run([FakeItem("t::a", [FakeMark("s", depth="unit")])], [FakeReport("t::a", "passed")])
    assert m.stories["s"].citations[0].grounding == NOT_CHECKED


@pytest.mark.proves("dev07-5-2", depth="component")
def test_a_session_that_never_finished_is_not_a_run_that_observed_nothing(tmp_path, monkeypatch):
    """`dev07-5-2`'s condition has two doors and only one was watched. A collection error observes
    zero tests just as an empty suite does, but the adapter reported the *partial* count it had
    reached and the gate only fires at zero — so the board read `unproven` and exited 0, which
    for a live spec is the ordinary green state. A broken suite was indistinguishable from
    routine incompleteness and passed CI."""
    from plumb.adapters.python.adapter import ABORTED, SuiteAborted, collect

    monkeypatch.setattr("pytest.main", lambda *a, **k: pytest.ExitCode.INTERRUPTED)

    with pytest.raises(SuiteAborted):
        collect([])

    assert pytest.ExitCode.TESTS_FAILED not in ABORTED, \
        "a suite that ran and failed is a complete observation — dev07-4-3 forbids making CI the gate"
    assert pytest.ExitCode.NO_TESTS_COLLECTED not in ABORTED, \
        "that session finished and honestly saw nothing — already observation.none, already exit 3"


@pytest.mark.proves("dev07-5-3", depth="component")
def test_an_aborted_session_cannot_board_rather_than_observing_nothing():
    """Two different outcomes and two different codes: the run that finished and saw nothing
    exits 3, the run that never finished exits 2. Collapsing them would say the tool looked."""
    from plumb.cli import EXIT_CANNOT_BOARD, EXIT_NOTHING_OBSERVED
    from plumb.launch import LaunchFailed

    assert EXIT_CANNOT_BOARD != EXIT_NOTHING_OBSERVED
    assert issubclass(LaunchFailed, RuntimeError), "the tool being unable to ask, not an answer"


@pytest.mark.proves("dev07-5-2", depth="component")
def test_a_run_that_observed_nothing_is_not_a_board_with_no_stories():
    """The two empty boards, side by side. Before this they were the same bytes, which is how a
    broken classpath passed for a project that had not cited anything yet."""
    from plumb.core.gate import NOTHING_CITED, NOTHING_OBSERVED

    saw_nothing = Board.render(Manifest(stories={}, observed_tests=0)).as_dict()
    cited_nothing = Board.render(Manifest(stories={}, observed_tests=38)).as_dict()

    assert saw_nothing["stories"] == cited_nothing["stories"] == {}, "both are empty of stories"
    assert [c["code"] for c in saw_nothing["conditions"]] == [NOTHING_OBSERVED]
    # **Each empty board says which one it is** (`dev07-5-2`). This used to assert the second carried
    # nothing at all, on the reasoning that 38 tests citing nothing is a correct first run — which
    # it is, and it is also what a shadowing annotation looks like when it makes every citation
    # invisible. A condition is not an alarm: it fails nothing, and the alternative is the disguise
    # `dev07-5-2` exists to remove, one step along.
    assert [c["code"] for c in cited_nothing["conditions"]] == [NOTHING_CITED]
    assert saw_nothing != cited_nothing, "the one thing that must never be true again"


@pytest.mark.proves("dev07-5-2", depth="component")
@pytest.mark.proves("dev07-5-2", depth="component")
def test_the_run_level_condition_carries_a_code_and_all_three_parts():
    """It is a condition like any other — a consumer reads it with the machinery it already has."""
    from plumb.core.gate import NOTHING_OBSERVED

    condition = Board.render(Manifest(stories={}, observed_tests=0)).as_dict()["conditions"][0]
    assert condition["code"] == NOTHING_OBSERVED
    assert condition["what"], "a code without a diagnosis helps nobody"
    assert condition["next_step"], "saying what is wrong without what to do is half an answer"
    assert condition["example"], "the example is the load-bearing part"


@pytest.mark.proves("dev07-5-2", depth="component")
@pytest.mark.proves("dev07-3-3", depth="component")
def test_an_adapter_that_could_not_count_raises_no_alarm():
    """dev07-3-2's cost, made visible: silence from the adapter is not evidence of an empty run, so
    the board declines to claim one. Reading `None` as zero would fire this on every manifest
    written before the field existed."""
    board = Board.render(Manifest(stories={})).as_dict()
    assert board["observed_tests"] is None
    assert board["conditions"] == [], "not reported is not a claim that there was nothing"


@pytest.mark.proves("dev07-5-1", depth="component")
@pytest.mark.proves("dev07-5-2", depth="component")
def test_the_board_carries_the_extent_it_drew_the_condition_from():
    """Evidence, not opinion: the count is on the board beside the conclusion, so a consumer can
    see what the condition was derived from rather than take it on trust."""
    assert Board.render(Manifest(stories={}, observed_tests=0)).as_dict()["observed_tests"] == 0
    assert Board.render(Manifest(stories={}, observed_tests=7)).as_dict()["observed_tests"] == 7


@pytest.mark.proves("dev07-5-1", depth="component")
def test_scoping_removes_rows_from_the_view_and_never_moves_a_status():
    """Scope is a question a reader asks, not a partition of the store. Filtering the manifest is
    what makes that true by construction: a story derives from its own citations, so removing
    others cannot move the one you are looking at — and narrowing to the spec that happens to look
    good buys nothing."""
    from dataclasses import replace

    full = Manifest(stories={
        "APP-1": Story(citations=(Citation(test="t::a", depth="unit", result=PASSED),)),
        "OPS-1": Story(citations=()),
    }, observed_tests=2)
    scoped = replace(full, stories={k: v for k, v in full.stories.items() if k.startswith("OPS")})

    assert list(Board.render(scoped).as_dict()["stories"]) == ["OPS-1"]
    assert Board.render(scoped).as_dict()["stories"]["OPS-1"] == \
        Board.render(full).as_dict()["stories"]["OPS-1"], "a story reads the same in every scope"


@pytest.mark.proves("dev07-3-3", depth="component")
def test_several_manifests_become_one_board_and_a_disagreement_refuses():
    """`dev07-3-3` makes the manifest the hub and `dev07-3-3` makes the core language-blind, so a second
    language is a second manifest and nothing else. Where two carry the same story and test with
    different facts, that is a defect in the run — silently preferring one would make the board
    depend on which adapter finished first."""
    from plumb.core.manifest import InvalidManifest, merge

    java = Manifest(stories={"A": Story(citations=(
        Citation(test="Spec#routes", depth="wiring", result=PASSED, grounding=GROUNDED),))},
        observed_tests=3)
    python = Manifest(stories={"B": Story(citations=(
        Citation(test="t::b", depth="unit", result=PASSED),))}, observed_tests=4)

    merged = merge(java, python)

    assert sorted(merged.stories) == ["A", "B"], "a second language is a second manifest"
    assert merged.observed_tests == 7, "the extent is the whole run, across adapters"

    disagrees = Manifest(stories={"A": Story(citations=(
        Citation(test="Spec#routes", depth="wiring", result=FAILED),))}, observed_tests=1)
    with pytest.raises(InvalidManifest, match="cannot choose"):
        merge(java, disagrees)


@pytest.mark.proves("dev07-3-3", depth="unit")
def test_an_extent_nobody_can_complete_is_not_a_total():
    """One adapter that cannot count makes the sum unknowable, and absent is *not reported*
    rather than an undercount (`dev07-3-3`, `dev07-3-2`) — a smaller number would read as a fact."""
    from plumb.core.manifest import merge

    assert merge(Manifest(observed_tests=4), Manifest(observed_tests=None)).observed_tests is None


@pytest.mark.proves("dev07-4-1", depth="component")
def test_a_story_belonging_to_no_declared_spec_is_named():
    """An id outside every declared namespace is not a story in a spec nobody named, it is a typo
    — and it lands on the board looking exactly as authoritative as a real one."""
    from plumb.core.gate import ORPHAN_STORY

    m = Manifest(stories={"APP-1": Story(citations=()), "WAT-9": Story(citations=())},
                 observed_tests=1)

    codes = [c["code"] for c in Board.render(m, namespaces=("APP",)).as_dict()["conditions"]]
    quiet = [c["code"] for c in Board.render(m).as_dict()["conditions"]]

    assert ORPHAN_STORY in codes
    assert ORPHAN_STORY not in quiet, \
        "a project that declared no namespaces is not asked a question it never posed"


@pytest.mark.proves("dev07-3-3", depth="component")
def test_a_board_missing_a_language_says_so():
    """With several adapters, one failing while the others succeed produces a board that looks
    complete and is missing a language. `dev07-5-2` already says absence of observation is its own
    outcome; this is that claim once there is more than one observer to be absent."""
    from plumb.core.gate import ADAPTER_ABSENT

    m = Manifest(stories={"A": Story(citations=())}, observed_tests=2)

    codes = [c["code"] for c in Board.render(m, absent_adapters=("java",)).as_dict()["conditions"]]

    assert ADAPTER_ABSENT in codes, "a board about a different project must not read as the answer"
    assert ADAPTER_ABSENT not in [c["code"] for c in Board.render(m).as_dict()["conditions"]]


@pytest.mark.proves("dev07-1-3", depth="component")
def test_a_board_whose_observer_died_says_that_and_not_declare_entry_points():
    """`not-checked` has two causes and one word, and the reader's next move differs.

    From `dev07-1-4` it means nobody said where the wired system begins, and declaring entry points is
    the fix. From here it means the instrument died, and a project that already declared them would
    be sent looking in exactly the wrong place — `dev07-1-4`'s objection about `dispatched`, one level
    up. So the reason is a fact about the run, said once, rather than the same sentence copied onto
    every citation.
    """
    from plumb.core.gate import ADAPTER_ABSENT, OBSERVATION_FAILED

    m = Manifest(stories={"A": Story(citations=())}, observed_tests=2)

    emitted = Board.render(m, blind_adapters=("java",)).as_dict()["conditions"]
    codes = [c["code"] for c in emitted]

    assert OBSERVATION_FAILED in codes
    assert ADAPTER_ABSENT not in codes, "it ran and reported — it did not fail to run"
    assert OBSERVATION_FAILED not in [c["code"] for c in Board.render(m).as_dict()["conditions"]]

    said = next(c for c in emitted if c["code"] == OBSERVATION_FAILED)
    assert "not your project" in said["what"]
    assert "declared no entry points" in said["example"], \
        "the board says which of the two silences this is, or the code buys nothing"


@pytest.mark.proves("dev07-5-2", depth="component")
def test_every_condition_a_subject_can_carry_resolves_to_its_prose():
    """The registry a code is *defined* in was deciding whether a reader was told anything.

    `evidence.none`, `evidence.failed` and `aspects.per-aspect` are the three commonest conditions
    a subject can carry and are authored beside the run-level ones, so a lookup that knew only
    about `CONDITIONS` emitted them with the field for the remedy present and empty. The board is
    read most often where there is no network, so prose that does not resolve locally is prose the
    reader does not get.
    """
    from plumb.core.gate import ALL_CODES, prose

    unresolved = sorted(code for code in ALL_CODES if prose(code) is None)
    assert not unresolved, f"the board can emit these and cannot say what they mean: {unresolved}"

    uncited = Board.render(Manifest(stories={"A": Story(citations=())},
                                    observed_tests=1)).as_dict()
    condition = uncited["stories"]["A"]["conditions"][0]
    assert condition["code"] == NOT_CITED
    assert condition["what"], "a code with an empty diagnosis is what shipped"
    assert condition["next_step"], "the field for the remedy was present and empty"


@pytest.mark.proves("dev07-5-2", depth="component")
def test_a_cited_story_that_passed_and_is_still_unproven_says_which_reason():
    """The third shape of unproven, which had no code at all.

    Cited by nothing is `evidence.none` and cited-and-failed is `evidence.failed`; this is the one
    where the test exists, runs and passes, and what it executed does not support the claim. It
    presented as an empty condition list, so the author who had done the most work was told the
    least. One code per arm of the second check, because the next move differs.
    """
    from plumb.core.gate import CITATION_INERT, NOT_WIRED, STRUCTURAL_EXECUTED, UNGROUNDED

    def one(archetype, grounding):
        story = Story(archetype=archetype,
                      citations=(Citation("t", "unit", PASSED, grounding),))
        return derive("s", story)

    from plumb.core.manifest import BEHAVIORAL

    reached_nothing_wired = one(BEHAVIORAL, UNGROUNDED)
    executed_nothing = one(BEHAVIORAL, INERT)
    structural_that_ran = one(STRUCTURAL, UNGROUNDED)

    assert reached_nothing_wired.status == UNPROVEN
    assert reached_nothing_wired.conditions == (NOT_WIRED,)
    assert executed_nothing.conditions == (CITATION_INERT,), \
        "a test that touched nothing arriving as a verdict, not as a suspicion"
    assert structural_that_ran.conditions == (STRUCTURAL_EXECUTED,)

    for verdict in (reached_nothing_wired, executed_nothing, structural_that_ran):
        assert verdict.conditions, "an unproven verdict with no reason is what a reader cannot act on"


@pytest.mark.proves("dev07-5-2", depth="component")
def test_the_advice_says_which_branch_advances_the_story_and_which_only_ends_the_complaint():
    """`dev07-5-2` promises what you would *get* by fixing it, and `depth.unsupported` offered two
    repairs as equals when they do different things.

    Measured on the getting-started tutorial: a story claiming `wiring` while calling the function
    directly was told to *lower the claimed depth to what the test actually reaches*. Following
    that exactly, the message disappeared and the story stayed UNPROVEN — which reads as the advice
    not having worked. Only one of the two branches can move a verdict, and the text led with the
    other one.
    """
    from plumb.core.gate import DEPTH_UNSUPPORTED, prose

    said = prose(DEPTH_UNSUPPORTED)

    entry = said.next_step.index("entry point")
    lower = said.next_step.index("lower the claimed depth")
    assert entry < lower, (
        "the branch that can reach proven comes first — a board that says what would make a check "
        "possible must not open with the option that stands still")
    assert "moves the verdict no further" in said.next_step, \
        "and lowering the depth says outright that it does not advance the story"
    assert "the board says why separately" in said.example, \
        "and points at the condition that explains the verdict it leaves behind"


@pytest.mark.proves("dev07-5-2", depth="component")
def test_lowering_a_depth_ends_the_complaint_and_leaves_the_reason_standing(tmp_path):
    """The state the advice lands you in is explained rather than silent — which is the half
    `dev07-5-2` already fixed, and the half that makes the reworded advice true.

    Both halves are asserted together on purpose: the wording promises the board will say why
    separately, and a test for the wording alone would keep passing if that stopped being so.
    """
    from plumb.core.gate import DEPTH_UNSUPPORTED, NOT_WIRED, UNPROVEN, derive
    from plumb.core.manifest import Citation, Story

    claiming = Story(citations=(Citation(test="t::a", depth="wiring", result="passed",
                                         grounding="ungrounded"),))
    lowered = Story(citations=(Citation(test="t::a", depth="unit", result="passed",
                                        grounding="ungrounded"),))

    before, after = derive("ORD-2", claiming), derive("ORD-2", lowered)

    assert DEPTH_UNSUPPORTED in before.conditions
    assert DEPTH_UNSUPPORTED not in after.conditions, "the complaint ends, as the advice says"
    assert after.status == UNPROVEN, "and the verdict does not move, as the advice now also says"
    assert NOT_WIRED in after.conditions, (
        "and the reader is not left with an unexplained UNPROVEN — the silent dead end this "
        "condition used to route them into")


@pytest.mark.proves("dev07-5-1", depth="component")
@pytest.mark.proves("dev07-5-2", depth="component")
def test_a_scope_narrows_the_verdicts_and_never_the_run_level_facts():
    """The run observed what it observed whatever you asked to see.

    Scope used to be applied by filtering the *document* before rendering it, which made every
    run-level fact a fact about the view. That was true by accident while the only such fact read
    `observed_tests`, which no filter touches — `dev07-5-2`'s is the first to read the story set, and
    it turned any scope matching nothing into *tests ran and none of them cited a subject* on a
    project with a hundred citations.
    """
    from plumb.core.gate import NOTHING_CITED

    m = Manifest(stories={"dev07-6-2": Story(citations=(
        Citation(test="t::a", depth="unit", result="passed", grounding="grounded"),))},
        observed_tests=38)

    empty_view = Board.render(m, scope="ch99").as_dict()

    assert empty_view["stories"] == {}, "the view is narrowed, which is what was asked for"
    assert [c["code"] for c in empty_view["conditions"]] == [], (
        "and the run is not reported as having cited nothing — it cited something you did not ask "
        "to see")
    assert empty_view["observed_tests"] == 38, "the extent is the run's, not the view's"

    # And the condition still fires on a genuinely uncited run, scoped or not.
    uncited = Manifest(stories={}, observed_tests=38)
    assert [c["code"] for c in Board.render(uncited, scope="ch99").as_dict()["conditions"]] \
        == [NOTHING_CITED]


@pytest.mark.proves("dev07-5-3", depth="component")
def test_the_board_says_what_rendered_it_and_when_and_keeps_measurement_on_the_fact():
    """Two different times, and only one of them is a measurement.

    A board is rendered once by one tool however many runs' facts it carries, so *what wrote this*
    and *when* are true of the document. When each fact was measured is not — that stays on the
    citation for `dev07-3-1`'s reason, and was being recorded by the adapter and dropped here.
    """
    measured = "2026-08-30T09:00:00Z"
    doc = Manifest(stories={"a": Story(citations=(
        Citation(test="t::a", depth="wiring", result=PASSED, grounding=GROUNDED, when=measured),))})

    payload = json.loads(Board.render(
        doc, rendered_by="9.9.9", rendered_at="2026-08-30T17:00:00Z").to_json())

    assert payload["rendered_by"] == "9.9.9"
    assert payload["rendered_at"] == "2026-08-30T17:00:00Z"
    # The discriminating assertion: the fact's own time survives to the consumer and is NOT
    # overwritten by the document's. A render stamp that also answered "when was this measured"
    # would be the false claim `dev07-3-1` refuses, one field over.
    assert payload["stories"]["a"]["evidence"][0]["when"] == measured
    assert payload["rendered_at"] != payload["stories"]["a"]["evidence"][0]["when"]


@pytest.mark.proves("dev07-5-3", depth="unit")
def test_the_core_is_told_what_rendered_the_board_rather_than_reading_it():
    """A core that reaches for a version of its own stops being language-blind (`dev07-3-3`)."""
    assert json.loads(Board.render(Manifest()).to_json())["rendered_by"] is None
