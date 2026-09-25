"""The session loop — opening from a cursor, closing on a measured delta (`ch13`).

The pure halves are exercised directly, because a cursor parser and a difference of two readings are
answerable without a run. The wiring gets one end-to-end pass over a **generated** project with a
real git tree, for the reason `test_end_to_end` gives: the runner is nested, so pointing an inner run
at this repository would recurse without bound.
"""

import json
import re
import subprocess
from pathlib import Path

import pytest

from plumb import session
from plumb.config import Config
from plumb.core.gate import PROVEN, UNPROVEN

from tests.test_end_to_end import project

#: Grounded on purpose. A delta is a change in what is **proven**, and a story that never reaches
#: PROVEN cannot move — so a fixture whose citation never runs under the declared entry point would
#: measure the loop against a story incapable of the transition being tested (`dev07-4-2`, `dev07-1-3`).
CITES_PASSING = '''
import pytest

@pytest.mark.proves("APP-1", depth="wiring")
def test_one():
    from {pkg}.core import entry
    assert entry(2) == 4
'''

#: The same citation, with its outcome read from the environment at call time. Editing the source
#: between two runs inside one process would not work: the inner runner imports the generated module
#: and Python caches it by name, so the second run re-executes the *first* run's code — the caching
#: `test_end_to_end` already warns about for packages, reaching the test module too.
TOGGLEABLE = '''
import os
import pytest

@pytest.mark.proves("APP-1", depth="wiring")
def test_one():
    from {pkg}.core import entry
    assert entry(2) == (5 if os.environ.get("PLUMB_BREAK_IT") else 4)
'''

SURFACE = 'production = ["src/{pkg}"]\nentry_points = ["{pkg}.core:entry"]\n'


def _ran(result):
    """One story, one citing test, one measured moment — the smallest thing a history records."""
    from plumb.core.manifest import Citation, Manifest, Story

    return Manifest(stories={"S-1": Story(citations=(
        Citation(test="t::a", depth="unit", result=result, grounding="inert",
                 when="2026-08-05T09:00:00Z"),))})


def _git(where, *args):
    subprocess.run(["git", "-C", str(where), *args], check=True, capture_output=True)


def _repo(root):
    """A generated project that is a real git repository with one commit behind it.

    It ignores its runner's droppings, the way a real project does. Not a convenience: the close
    runs the suite and *then* looks for uncommitted work, so a project that tracked `.pytest_cache`
    would fail the gate on a directory the gate's own run had just created.
    """
    (Path(root) / ".gitignore").write_text(".pytest_cache/\n__pycache__/\n")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "t")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "in")


# -- what the tool writes (`ado4`) -------------------------------------------------------------

@pytest.mark.proves("ado4", depth="component")
def test_every_place_the_tool_writes_is_in_the_documented_inventory(monkeypatch, tmp_path):
    """A hand-kept list of paths stays right until somebody adds a writer, and nothing goes red
    when they do. So the docs are a view of the code, and this is what holds them to it."""
    from plumb import footprint

    monkeypatch.delenv("PLUMB_ACCOUNT", raising=False)
    documented = (Path(__file__).resolve().parent.parent / "docs" / "command-line.md").read_text()

    for wrote in footprint.user_level():
        leaf = Path(wrote.where).name if Path(wrote.where).suffix else Path(wrote.where).parent.name
        assert leaf in documented, f"{wrote.where} is written and the reference never mentions it"


@pytest.mark.proves("ado4", depth="standards-integration")
def test_the_footprint_is_printed_with_the_paths_this_machine_actually_uses(monkeypatch, capsys,
                                                                            tmp_path):
    """The reference cannot show an adopter *their* paths — every location honours an `XDG_*`
    variable, so where the account sits is a property of the machine, not of the manual.

    It read `XDG_DATA_HOME`, which the core honoured only for the support store. That store left
    with the capability (`mod5`), so the variable proves nothing here now and the claim is made
    against one the core still reads.
    """
    from plumb import cli

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "elsewhere"))
    root = _wired(tmp_path, monkeypatch, extra='series = "history.jsonl"\n')

    assert cli.main(["footprint", "--project", str(root)]) == 0
    shown = capsys.readouterr().out
    assert str(tmp_path / "elsewhere") in shown, "the override, not the documented default"
    # `ado4-ur3` — the list marks what nothing else holds, so a person can point the backup they
    # already run at it. It used to say "Irreplaceable" inside the prose of one entry; it is a
    # marker on the entry now, and it reaches the series, which lives in the project and is
    # commonly git-ignored.
    assert "history.jsonl" in shown and "IRREPLACEABLE" in shown, "and what it would cost to lose"
    # `ado4-nfr3` — the marker names what the file IS. It said "never into an archive" and then
    # "never copy it anywhere", and both instructed a reader whose threat model, infrastructure and
    # obligations this tool cannot see. What follows from carrying a credential is theirs.
    marks = re.findall(r"\[([^\]]+)\]", shown)
    assert any("SECRET" in mark for mark in marks), "the one carrying a credential is named as such"
    assert all("\u2014" not in mark for mark in marks), (
        f"a marker names what a thing is and stops; these instruct: {marks}")


@pytest.mark.proves("ado4", depth="component")
def test_the_inventory_says_what_losing_each_place_would_cost(tmp_path):
    """A path on its own answers nothing: a cache and a session reading are both disposable and look
    nothing alike, and an account and an enrolment share a directory and could not differ more."""
    from plumb import footprint
    from plumb.config import Config

    everything = footprint.everything(Config(series="hist.jsonl", root=tmp_path), tmp_path)
    assert all(w.what.strip() for w in everything), "each says what it is"

    secret = [w for w in everything if w.secret]
    assert secret and all(w.keep for w in secret), "the credential is worth keeping and never copied"
    assert any(w.shared for w in everything), "and one identity serves several projects"
    assert any(not w.keep for w in everything), "while some of it is disposable by construction"


# -- the cursor (`dev03-1`, `dev03-1`) -------------------------------------------------------------

@pytest.mark.proves("dev03-1", depth="unit")
def test_a_cursor_holding_a_command_is_read_as_a_sentence_and_never_run(tmp_path):
    """The ergonomic way to read `key="value"` in a shell is to source it, and the context field is
    English prose carrying whatever punctuation somebody wrote in it."""
    evidence = tmp_path / "pwned"
    cursor = tmp_path / "next-session.txt"
    cursor.write_text(
        'NEXT_TASK="settle the thing"\n'
        'REF="dev03-1"\n'
        f'CONTEXT="do not $(touch {evidence}) and `touch {evidence}` — don\'t; see *.py"\n')

    read = session.read_cursor(cursor)

    assert not evidence.exists(), "reading a cursor never runs what it holds"
    assert "$(touch" in read.get("CONTEXT"), "the value survives verbatim"
    assert "don't" in read.get("CONTEXT"), "including the punctuation that made it worth writing"


@pytest.mark.proves("dev03-1", depth="unit")
def test_an_absent_cursor_is_an_answer_rather_than_a_guess(tmp_path):
    """A first session and a session that never wrapped leave identical evidence."""
    assert session.read_cursor(tmp_path / "nothing.txt") is None


@pytest.mark.proves("dev03", depth="unit")
def test_a_key_the_tool_does_not_know_rides_through_untouched(tmp_path):
    """One of the two field examples keeps a BRANCH there, and a tool that dropped what it did not
    recognise would silently eat somebody else's policy."""
    where = tmp_path / "cursor.txt"
    session.write_cursor(where, {"NEXT_TASK": "a", "REF": "dev03", "CONTEXT": "c",
                                 "BRANCH": "dissolve-core"})

    back = session.read_cursor(where)
    assert back.get("BRANCH") == "dissolve-core"
    assert not back.missing
    assert "written by plumb" in where.read_text(), "a file the tool owns says what wrote it"


# -- what is next ---------------------------------------------------------------------


@pytest.mark.proves("dev03-2", depth="component")
def test_the_ground_names_which_tree_is_dirty(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "a.txt").write_text("one")
    _repo(root)
    assert session.dirty(tmp_path, ["proj"]) == [], "a committed tree is clean"

    (root / "a.txt").write_text("two")
    assert session.dirty(tmp_path, ["proj"]) == ["proj"], "and an uncommitted one is named"


@pytest.mark.proves("dev10-2", depth="component")
def test_a_session_is_the_difference_between_two_readings():
    opened = session.Reading({"s-1": PROVEN, "s-2": UNPROVEN, "s-3": UNPROVEN})
    closed = session.Reading({"s-1": PROVEN, "s-2": PROVEN, "s-3": UNPROVEN})

    moved = session.difference(opened, closed)
    assert moved.became == ("s-2",)
    assert moved.lost == ()
    assert moved.moved == 1


@pytest.mark.proves("dev10-2", depth="component")
def test_a_negative_delta_is_a_result_and_not_a_fault():
    """A proof that later fails un-proves its story (`dev07-4-3`), and a loop that made the honest end
    of a hard day expensive is one people route around."""
    moved = session.difference(session.Reading({"s-1": PROVEN}), session.Reading({"s-1": UNPROVEN}))

    assert moved.lost == ("s-1",)
    assert moved.moved == -1, "reported, and nothing here refuses it"


@pytest.mark.proves("dev10-2", depth="component")
def test_a_story_that_was_deleted_is_not_reported_as_one_that_broke():
    """Deleting a story and breaking one are different events, and a session that tidied the spec
    should not read as having caused a regression."""
    moved = session.difference(session.Reading({"s-1": PROVEN, "s-2": PROVEN}),
                               session.Reading({"s-1": PROVEN}))

    assert moved.lost == (), "s-2 is gone, not broken"


@pytest.mark.proves("dev03-3", depth="unit")
def test_a_reading_records_what_a_run_found_and_never_a_verdict(tmp_path):
    reading = session.Reading({"s-1": PROVEN}, "2026-08-05T00:00:00+00:00", "0.5.0", 4)
    back = session.Reading.from_json(reading.to_json())

    assert back.statuses == {"s-1": PROVEN} and back.series_seq == 4
    assert "proven" not in json.loads(reading.to_json()), "no verdict of its own, only what it saw"


@pytest.mark.proves("dev03-3", depth="component")
def test_the_reading_is_kept_out_of_the_repository_it_measures(tmp_path, monkeypatch):
    """Written beside the cursor it would be uncommitted work at the moment the gate looks for
    uncommitted work — the tool's own scratch failing the tool's own gate."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    where = session.reading_path(tmp_path / "proj")

    assert (tmp_path / "proj") not in where.parents, "it does not live in the tree it measures"
    assert str(tmp_path / "state") in str(where)


# -- the history (`dev10-3`) ----------------------------------------------------------------------

@pytest.mark.proves("dev10-3", depth="component")
def test_a_session_brackets_the_history_the_project_already_keeps(tmp_path):
    """The delta says what today moved; the history says whether today was typical."""
    from plumb.core import series

    store = tmp_path / "series.jsonl"
    config = Config(series="series.jsonl", root=tmp_path)

    series.append(store, _ran("passed"))
    opened_at = series.last_seq(store)

    series.append(store, _ran("failed"))
    moved = session.since(config, tmp_path, opened_at)

    assert moved, "the transitions recorded since the open are exactly this session's"
    assert all(entry.seq > opened_at for entry in moved)
    assert session.since(config, tmp_path, series.last_seq(store)) == [], "and no more than those"


@pytest.mark.proves("dev10-3", depth="component")
def test_a_project_that_keeps_no_history_is_the_ordinary_case(tmp_path):
    """`dev07-6-1` refuses to grow a store as a side effect, and that refusal is inherited whole."""
    plain = Config(root=tmp_path)

    assert session.since(plain, tmp_path, 0) == []
    assert session.volatile(plain, tmp_path) == []
    assert not list(tmp_path.iterdir()), "and nothing was written to find that out"


# -- the whole loop, wired -----------------------------------------------------------------------
#
# A behavioral story is proven by running the wired system (`dev07-1-3`), so everything below drives
# `plumb.cli:main`. The component cases above answer the same questions faster and ground nothing,
# which is `dev07-4-2` working rather than a gap in them.

def _wired(tmp_path, monkeypatch, extra="", body=None):
    """A generated project that is a real repository, with the tool pointed at it."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    root = project(tmp_path, body or CITES_PASSING, config=SURFACE + extra)
    _repo(root)
    monkeypatch.syspath_prepend(root + "/src")
    monkeypatch.chdir(root)
    return Path(root)


def _cursor_at(root, where=".plumb/next-session.txt", **fields):
    session.write_cursor(root / where, {"NEXT_TASK": "the next thing", "REF": "APP-1",
                                        "CONTEXT": "why it is next", **fields})
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "cursor")


@pytest.mark.proves("dev03-1", depth="standards-integration")
def test_a_session_opens_from_the_cursor_the_last_one_left(monkeypatch, capsys, tmp_path):
    from plumb import cli

    root = _wired(tmp_path, monkeypatch)
    _cursor_at(root, NEXT_TASK="settle the derivation label", CONTEXT="a key in the field pins it")

    assert cli.main(["session", "--project", str(root), "start"]) == 0
    opened = capsys.readouterr().out
    assert "settle the derivation label" in opened, "what is next"
    assert "a key in the field pins it" in opened, "and the line that cannot be re-derived"


@pytest.mark.proves("dev03-1", depth="standards-integration")
def test_with_no_cursor_both_causes_are_named_and_neither_is_guessed(monkeypatch, capsys, tmp_path):
    from plumb import cli

    root = _wired(tmp_path, monkeypatch)

    assert cli.main(["session", "--project", str(root), "start"]) == 0
    opened = capsys.readouterr().out
    assert "first session" in opened and "did not wrap" in opened
    assert "reconstructed" in opened, "and the log is explicitly not consulted for it"


@pytest.mark.proves("dev03-1", depth="standards-integration")
def test_a_cursor_is_still_data_when_the_tool_reads_it_for_real(monkeypatch, capsys, tmp_path):
    from plumb import cli

    root = _wired(tmp_path, monkeypatch)
    evidence = tmp_path / "executed"
    _cursor_at(root, CONTEXT=f"careful: $(touch {evidence}) and `touch {evidence}`")

    assert cli.main(["session", "--project", str(root), "start"]) == 0
    assert not evidence.exists(), "nothing in the path interprets it"
    assert "$(touch" in capsys.readouterr().out, "and it is shown as written"


@pytest.mark.proves("dev10-2", depth="standards-integration")
def test_a_story_that_stopped_being_proven_is_reported_and_not_refused(monkeypatch, capsys,
                                                                      tmp_path):
    """The honest end of a hard day: the close says what was lost and still closes."""
    from plumb import cli

    root = _wired(tmp_path, monkeypatch, body=TOGGLEABLE)
    assert cli.main(["session", "--project", str(root), "start"]) == 0
    assert "0 unproven of 1" in capsys.readouterr().out, "it opened with the story proven"

    monkeypatch.setenv("PLUMB_BREAK_IT", "1")

    assert cli.main(["session", "--project", str(root), "wrap-up", "--next", "fix it",
                     "--ref", "APP-1", "--context", "it broke"]) == 0, "a loss is not a refusal"
    closed = capsys.readouterr().out
    assert "-1 proven" in closed and "APP-1 is no longer proven" in closed


@pytest.mark.proves("dev03", depth="standards-integration")
def test_where_the_cursor_lives_is_the_project_s_to_declare(monkeypatch, capsys, tmp_path):
    """One of the two field examples keeps it outside the repository entirely."""
    from plumb import cli

    root = _wired(tmp_path, monkeypatch, extra='cursor = "docs/handoff.txt"\n')
    _cursor_at(root, where="docs/handoff.txt", NEXT_TASK="declared elsewhere")

    assert cli.main(["session", "--project", str(root), "start"]) == 0
    assert "docs/handoff.txt" in capsys.readouterr().out
    assert not (root / ".plumb").exists(), "and the default was never used"


@pytest.mark.proves("dev10-3", depth="standards-integration")
def test_a_declared_history_is_where_the_session_is_recorded(monkeypatch, capsys, tmp_path):
    from plumb import cli

    root = _wired(tmp_path, monkeypatch, extra='series = "history.jsonl"\n')

    assert cli.main(["session", "--project", str(root), "start"]) == 0
    assert cli.main(["session", "--project", str(root), "wrap-up", "--next", "on",
                     "--ref", "APP-1", "--context", "why"]) == 0
    assert "transition(s) recorded this session" in capsys.readouterr().out
    assert (root / "history.jsonl").exists(), "in the store the project declared"


@pytest.mark.proves("dev10-3", depth="standards-integration")
def test_the_open_says_whether_today_s_move_would_be_the_first(monkeypatch, capsys, tmp_path):
    """The delta cannot tell a story that has flickered for a fortnight from one that moved for the
    first time — they are the same single transition to a session. Only the history can."""
    from plumb import cli

    root = _wired(tmp_path, monkeypatch, extra='series = "history.jsonl"\n', body=TOGGLEABLE)
    close = ["session", "--project", str(root), "wrap-up", "--next", "on", "--ref", "APP-1",
             "--context", "why"]

    assert cli.main(close) == 0, "one run recorded, with APP-1 passing"
    monkeypatch.setenv("PLUMB_BREAK_IT", "1")
    assert cli.main(close) == 0, "and a second that moved it"
    capsys.readouterr()

    assert cli.main(["session", "--project", str(root), "start"]) == 0
    opened = capsys.readouterr().out
    assert "history   history.jsonl" in opened, "where the history is, and how much of it there is"
    assert "has moved in 2 runs" in opened, "and that this subject is not moving for the first time"


@pytest.mark.proves("dev10-3", depth="standards-integration")
def test_a_project_declaring_no_history_grows_no_store(monkeypatch, capsys, tmp_path):
    """`dev07-6-1` refuses to grow a store as a side effect, and the loop inherits that whole."""
    from plumb import cli

    root = _wired(tmp_path, monkeypatch)

    assert cli.main(["session", "--project", str(root), "start"]) == 0
    assert cli.main(["session", "--project", str(root), "wrap-up", "--next", "on",
                     "--ref", "APP-1", "--context", "why"]) == 0
    assert not list(root.glob("*.jsonl")), "nothing was kept that nobody asked to keep"


# -- the whole loop, wired (`dev03`, `dev10-1`) --------------------------------------------------

@pytest.mark.proves("dev03", depth="standards-integration")
def test_a_project_that_never_opens_a_session_keeps_every_capability(monkeypatch, capsys, tmp_path):
    """The recommendation is argued, never enforced: nothing else in the tool reads any of this."""
    from plumb import cli

    root = project(tmp_path, CITES_PASSING)
    monkeypatch.syspath_prepend(root + "/src")
    monkeypatch.chdir(root)

    assert cli.main(["board", "--json", root]) == 0
    assert "APP-1" in json.loads(capsys.readouterr().out)["stories"]
    assert not (tmp_path / "proj" / ".plumb").exists(), "no cursor, and none needed"


@pytest.mark.proves("dev03-2", depth="standards-integration")
@pytest.mark.proves("dev10-1", depth="standards-integration")
def test_start_briefs_over_a_dirty_tree_and_wrap_up_refuses_it(monkeypatch, capsys, tmp_path):
    """The asymmetry: a wrong open costs the person who can see it, a wrong close costs a session
    that cannot."""
    from plumb import cli

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    root = project(tmp_path, CITES_PASSING, config=SURFACE)
    _repo(root)
    monkeypatch.syspath_prepend(root + "/src")
    monkeypatch.chdir(root)

    loose = Path(root) / "loose.txt"
    loose.write_text("mid-thought")

    assert cli.main(["session", "--project", root, "start"]) == 0, "start refuses nothing"
    opened = capsys.readouterr().out
    assert "UNCOMMITTED" in opened, "and reports what it found"
    assert "unproven of" in opened, "having taken a reading to measure against"

    assert cli.main(["session", "--project", root, "wrap-up", "--next", "x",
                     "--ref", "APP-1", "--context", "y"]) == 1, "the close is the gate"
    refused = capsys.readouterr().err
    assert "uncommitted" in refused

    # **A refused close writes nothing and reads nothing.** The gate is free and the reading is not,
    # so the free half is held first: a session caught here used to have had its cursor written and
    # a transition appended to its history before being told it had not wrapped, and satisfying the
    # gate then meant running the whole board a second time and appending a second time. Asserted on
    # the artifacts rather than on the message, because the message is what the old order also said.
    assert not (Path(root) / ".plumb" / "next-session.txt").exists(), (
        "the refused close left a cursor behind — the next session would open onto a handoff from "
        "a session that did not happen")
    assert "nothing was written" in refused, "and the refusal says so, since the old order did not"

    loose.unlink()
    assert cli.main(["session", "--project", root, "wrap-up", "--next", "next thing",
                     "--ref", "APP-1", "--context", "why it is next"]) == 0, (
        "the same command, run again once the ground was fixed — one pass, with nothing to undo")
    closed = capsys.readouterr().out
    assert "proven since" in closed, "the session is reported as a measured delta"
    assert session.read_cursor(Path(root) / ".plumb" / "next-session.txt").get("REF") == "APP-1"


@pytest.mark.proves("dev10-1", depth="standards-integration")
def test_a_refused_close_takes_no_reading_and_appends_no_history(monkeypatch, capsys, tmp_path):
    """The gate is free and the reading is not, so the free half is held first.

    This is the ordering, asserted on the expensive half rather than on the artifacts: a close that
    refuses must not have run the board, because the whole cost of the old order was paying for it
    twice — once on the run that was refused, and again on the run that satisfied the gate.

    The history is the sharper of the two. A cursor written by a refused close is wrong and
    recoverable; a transition appended by one is a session recorded in a history that never ended,
    and `dev10-3` reports the series as *whether this session is like the others*.
    """
    from plumb import cli, session

    root = _wired(tmp_path, monkeypatch, extra='series = "history.jsonl"\n')
    (root / "loose.txt").write_text("mid-thought")

    took = []
    real = session.take_reading
    monkeypatch.setattr(session, "take_reading",
                        lambda *a, **k: (took.append(1), real(*a, **k))[1])

    assert cli.main(["session", "--project", str(root), "wrap-up", "--next", "x",
                     "--ref", "APP-1", "--context", "y"]) == 1
    assert took == [], (
        "the board ran on a close the gate was always going to refuse — this is the round trip the "
        "ordering exists to remove, and it is the expensive half")
    assert not (root / "history.jsonl").exists(), (
        "a transition was recorded for a session that did not close")

    (root / "loose.txt").unlink()
    assert cli.main(["session", "--project", str(root), "wrap-up", "--next", "x",
                     "--ref", "APP-1", "--context", "y"]) == 0
    assert took == [1], "and the run that does close takes exactly one reading"
    assert (root / "history.jsonl").exists(), "which is the run the history records"
