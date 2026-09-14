"""``dev07-6`` — the history a manifest deliberately is not."""

import json
from pathlib import Path

import pytest

from plumb.core.manifest import Citation, Manifest, Story
from plumb.core.series import Entry, Origin, Run, append, last_checked, read, state


def cited(test, when, result="passed"):
    return Citation(test=test, depth="unit", result=result, grounding="inert", when=when)


def run(*citations, observed=None):
    return Manifest(stories={"S-1": Story(citations=tuple(citations))},
                    observed_tests=observed)


@pytest.mark.proves("dev07-6-2", depth="component")
def test_a_series_records_what_changed_and_nothing_when_nothing_did(tmp_path):
    """**Transitions, not snapshots.** A fact that has not changed is not new information —
    measured at 0 of 55 facts differing between two runs of an unchanged tree — so a snapshot per
    run stores the same fact until somebody deletes it, and buries the one event anybody looks for
    under a hundred identical copies of everything that did not move.

    An unchanged run writes **no transition at all**, which is the ordinary case on a healthy
    project.
    """
    store = tmp_path / "series.jsonl"
    first = run(cited("t::a", "2026-08-01T09:00:00Z"), cited("t::b", "2026-08-01T09:00:00Z"))

    assert len(append(store, first)) == 2, "both facts are new"
    assert len(append(store, first)) == 0, "and nothing changed the second time"


@pytest.mark.proves("dev07-6-2", depth="component")
def test_a_measurement_time_is_not_part_of_what_a_fact_says(tmp_path):
    """*When we looked* is not *what we saw*, and folding one into the other makes every fact
    differ from itself on every run — a transition log that has forgotten it is one.

    The first working version did exactly that: a second identical run of this project wrote 317
    transitions where it should have written none. The bug is cheap to reintroduce and invisible
    once made, because the file still looks like a log.
    """
    store = tmp_path / "series.jsonl"
    append(store, run(cited("t::a", "2026-08-01T09:00:00Z")))

    later = append(store, run(cited("t::a", "2026-08-02T09:00:00Z")))

    assert later == [], "same fact, later clock — not a change"


@pytest.mark.proves("dev07-6-2", depth="component")
def test_a_fact_that_disappears_is_recorded_as_gone(tmp_path):
    """Absence has to be a transition rather than a silent stop, or a deleted test reads forever as
    whatever it last said — the store's own version of `dev07-3-3`."""
    store = tmp_path / "series.jsonl"
    append(store, run(cited("t::a", "2026-08-01T09:00:00Z"), cited("t::b", "2026-08-01T09:00:00Z")))

    gone = append(store, run(cited("t::a", "2026-08-02T09:00:00Z")))

    assert [e.test for e in gone] == ["t::b"] and gone[0].result is None
    assert sorted(k[1] for k in state(read(store))) == ["t::a"], "and it replays to what is true"


@pytest.mark.proves("dev07-6-2", depth="component")
def test_the_history_replays_exactly(tmp_path):
    """Transitions are not a lossy compression — base plus every change reconstructs the history
    exactly, which is the only reason this beats simply choosing a coarser grain."""
    store = tmp_path / "series.jsonl"
    append(store, run(cited("t::a", "2026-08-01T09:00:00Z")))
    append(store, run(cited("t::a", "2026-08-02T09:00:00Z", result="failed")))

    assert state(read(store)) == {("S-1", "t::a", None): ("failed", "inert")}


@pytest.mark.proves("dev07-6-3", depth="component")
def test_when_we_last_looked_is_derived_and_never_invented(tmp_path):
    """*Deriving looked rather than fine is the whole of the honesty here.*

    A log of changes cannot answer it alone: a fact that keeps holding never appears again, so
    silence means both *nothing moved* and *nobody looked*. One line per run fixes that, and it
    carries no list of what it covered — the covered set is the replayed state, because a subject
    enters it when its first fact appears and leaves when its last one goes, and both are already
    transitions.

    Never checked stays ``None``. It is not the same as checked long ago, and inventing a date for
    it is the fabrication `dev07-3-1` refuses.
    """
    store = tmp_path / "series.jsonl"
    for day in ("01", "02", "03"):
        append(store, run(cited("t::a", f"2026-08-{day}T09:00:00Z"), observed=1))
    history = read(store)

    assert last_checked(history, "S-1") == "2026-08-03T09:00:00Z", "looked at three times"
    assert last_checked(history, "S-9") is None, "and one nobody has ever looked at"
    assert sum(isinstance(r, Run) for r in history) == 3, "a marker per run, changed or not"
    assert sum(isinstance(r, Entry) for r in history) == 1, "and one transition across all three"


@pytest.mark.proves("dev07-6-2", depth="unit")
def test_every_record_carries_a_unique_monotonic_sequence(tmp_path):
    """So a reader can page, resume and de-duplicate, and so the **store** can move — file,
    appendable log, embedded database — without the **contract** moving. Added while the store held
    nothing, because retrofitting it after anything reads it costs a version of the contract and
    every consumer's upgrade."""
    store = tmp_path / "series.jsonl"
    append(store, run(cited("t::a", "2026-08-01T09:00:00Z")))
    append(store, run(cited("t::a", "2026-08-02T09:00:00Z", result="failed")))

    seqs = [r.seq for r in read(store)]

    assert seqs == sorted(seqs) and len(seqs) == len(set(seqs))
    assert seqs == list(range(1, len(seqs) + 1)), "dense, so a gap means a lost record"


def test_a_missing_store_is_an_empty_history_and_never_an_error(tmp_path):
    """A project that has never kept a series has no history, which is a different thing from a
    broken one and must not read as it (`dev07-5-1`)."""
    assert read(tmp_path / "never-written.jsonl") == []


@pytest.mark.proves("dev07-6-2", depth="component")
def test_compaction_says_what_it_dropped_and_still_replays(tmp_path):
    """**Not deletion.** A transition log is lossless only as base plus every change since, so
    dropping the oldest records removes the base and makes everything after it unreconstructable —
    it would not free space, it would destroy the remainder. That is why the bound was rewritten rather
    than amended: compaction reclaims **churn**, never the base.

    And the `Discarded` record is not bookkeeping. Without it the compacted span reads as a period
    in which nothing happened, so the store would be answering a question about the project with a
    fact about itself.
    """
    from plumb.core.series import Discarded, compact

    store = tmp_path / "series.jsonl"
    append(store, run(cited("t::a", "2026-08-01T09:00:00Z"),
                      cited("t::b", "2026-08-01T09:00:00Z")))
    append(store, run(cited("t::a", "2026-08-02T09:00:00Z"),
                      cited("t::b", "2026-08-02T09:00:00Z", result="failed")))
    before = state(read(store))

    note = compact(store, through=3, reason="compacted", when="2026-08-03T00:00:00Z")
    after = read(store)

    assert state(after) == before, "the history still replays to exactly what was true"
    # Found rather than indexed. The origin stamp is written ahead of it and survives compaction
    # (`dev07-6-1`), so position 0 was never the claim — what `dev07-6-2` requires is that the dropped
    # span is *recorded*, and that a reader meets it before any count (asserted where `show` runs).
    gone = [r for r in after if isinstance(r, Discarded)]
    assert len(gone) == 1 and gone[0].discarded_through == 3
    assert isinstance(after[0], Origin), "and the stamp still leads, so the copy can prove it began"
    assert note.reason == "compacted", "and says why in the store's own words, not a judgement"
    assert [r.seq for r in after] == list(range(1, len(after) + 1)), "dense after renumbering"


# ── reading it back (dev07-6-3) ──────────────────────────────────────────────────

def flapping(store, results, subject="FLAKY"):
    """A history over several runs: one subject steady, one flipping."""
    from plumb.core.manifest import Citation, Manifest, Story
    for n, result in enumerate(results, start=1):
        when = f"2026-08-0{n}T09:00:00Z"
        append(store, Manifest(stories={
            "STEADY": Story(citations=(cited("t::steady", when),)),
            subject: Story(citations=(cited("t::flaky", when, result=result),)),
        }))


@pytest.mark.proves("dev07-6-3", depth="component")
def test_unchanged_is_not_unexamined(tmp_path):
    """The difference the whole chapter turns on. A manifest cannot tell them apart at all — it is
    unlinked before every run — and `dev07-4-3-ur10` derives a watched decision's standing from *when we
    last looked* precisely because the answer itself lives somewhere we cannot compute.

    So a subject that has not moved since the first run must still report a recent look.
    """
    from plumb.core.series import overview, read

    store = tmp_path / "series.jsonl"
    flapping(store, ["passed", "failed", "passed"])

    steady = next(s for s in overview(read(store)) if s.subject == "STEADY")

    assert steady.changed == "2026-08-01T09:00:00Z", "it last moved on the first run"
    assert steady.checked == "2026-08-03T09:00:00Z", "and was looked at on the most recent one"
    assert steady.changed != steady.checked, "two questions, and a history that conflates them "\
                                             "reports a healthy project as an abandoned one"


@pytest.mark.proves("dev07-6-3", depth="component")
def test_what_keeps_changing_is_counted_in_runs_and_never_in_records(tmp_path):
    """*Which test is flaky* is a count, and the count has to be of **runs**.

    The first working version counted records. The first append writes one per citation, so a
    subject with sixteen citing tests came out as the most volatile thing in a project where
    nothing had ever changed — a number that is not merely useless but actively backwards, since
    the best-tested subject ranks worst.
    """
    from plumb.core.series import overview, read

    store = tmp_path / "series.jsonl"
    flapping(store, ["passed", "failed", "passed", "failed"])

    counted = {s.subject: s.changes for s in overview(read(store))}

    assert counted["FLAKY"] == 4, "it moved in every run"
    assert counted["STEADY"] == 1, "it moved once, on the run that first saw it"


@pytest.mark.proves("dev07-6-3", depth="component")
def test_one_subject_reads_back_as_when_it_broke(tmp_path):
    """The question a board cannot answer at all: not *is it failing* but *when did it start*."""
    from plumb.core.series import history, read

    store = tmp_path / "series.jsonl"
    flapping(store, ["passed", "passed", "failed"])

    went = [(e.when, e.result) for e in history(read(store), "FLAKY")]

    assert went == [("2026-08-01T09:00:00Z", "passed"), ("2026-08-03T09:00:00Z", "failed")], \
        "two transitions, not three runs — the middle run changed nothing and is not an event"


@pytest.mark.proves("dev07-6-3", depth="component")
def test_a_history_reports_and_never_grades(tmp_path):
    """A board derives status from a run (`dev07-4-3`). If a history graded anything it would be a
    second source of truth about the same subject, and the two would disagree the first time
    somebody opened an old file — so what comes back is facts and a replayed result, never a
    verdict, a label or a condition code."""
    from dataclasses import fields

    from plumb.core.series import Standing, overview, read

    store = tmp_path / "series.jsonl"
    flapping(store, ["passed", "failed"])

    named = {f.name for f in fields(Standing)}
    assert named == {"subject", "changed", "checked", "changes", "result"}
    assert not named & {"status", "label", "conditions", "proven", "achieved"}, \
        "a history that carried a status would be competing with the gate"

    flaky = next(s for s in overview(read(store)) if s.subject == "FLAKY")
    assert flaky.result == "failed", "where it stands is replayed from the record, not judged"


@pytest.mark.proves("dev07-6-2", depth="component")
def test_a_series_path_whose_directory_does_not_exist_yet_is_created(tmp_path):
    """`--series build/plumb/series.jsonl` on a runner made this minute.

    A build directory is exactly the kind that does not exist yet, and it is exactly where a series
    is most wanted (`dev07-6-3`). Before this the board finished a successful run and then died in a
    traceback about a file it had been asked to create — which reads as a fault in the project.
    """
    from plumb.core.series import append

    where = tmp_path / "build" / "plumb" / "series.jsonl"
    assert not where.parent.exists()
    append(where, Manifest(stories={}, observed_tests=0))
    assert where.is_file(), "the run's own record survives a directory nobody had made"




@pytest.mark.proves("dev07-6-2", depth="component")
def test_the_subject_comes_from_the_project_that_owns_the_series(tmp_path, monkeypatch):
    """Which series inside your store a signed request writes to is decided here, and the process's
    working directory used to be the last place it was read from.

    Measured: pushing a series out of a project declaring `acme-api`, while standing in a checkout
    declaring `plumb`, resolved `plumb` — and the pull that followed asked for `plumb` too. Both
    succeeded. Nothing about the credential prevents it: a store is keyed by whoever wrote to it, so
    the request authenticates correctly and lands in the writer's own store under the wrong name.
    """
    from plumb.transmit import _configured_subject

    owner = tmp_path / "acme"
    (owner / "build" / "plumb").mkdir(parents=True)
    (owner / "plumb.toml").write_text('adapter = "python"\nsubject = "acme-api"\n')
    series = owner / "build" / "plumb" / "series.jsonl"
    series.write_text("")

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "plumb.toml").write_text('adapter = "python"\nsubject = "somebody-else"\n')
    monkeypatch.chdir(elsewhere)

    assert _configured_subject(series) == "acme-api", (
        "the subject follows the series, not the shell — the series file is two directories below "
        "the plumb.toml that owns it, which is where a board writes one")


@pytest.mark.proves("dev07-6-2", depth="component")
def test_a_series_belonging_to_no_project_is_refused_rather_than_guessed(tmp_path, monkeypatch):
    """The push already declines to guess a subject when it has nothing to guess from, on the
    stated grounds that guessing would put somebody's history in a stranger's file. Reading the
    standing directory *was* that guess, made silently and reported as success."""
    from plumb.transmit import _configured_subject

    stray = tmp_path / "stray.jsonl"
    stray.write_text("")
    standing = tmp_path / "standing"
    standing.mkdir()
    (standing / "plumb.toml").write_text('adapter = "python"\nsubject = "somebody-else"\n')
    monkeypatch.chdir(standing)

    assert _configured_subject(stray) == "", "no owner is no subject, and the caller says so"


@pytest.mark.proves("dev07-6-2", depth="component")
def test_the_project_asked_for_outranks_the_one_that_owns_the_file(tmp_path):
    """`--project` says which project the command is *about*, and the two halves of one command
    must not disagree about that."""
    from plumb.transmit import _configured_subject

    owner = tmp_path / "acme"
    owner.mkdir()
    (owner / "plumb.toml").write_text('adapter = "python"\nsubject = "acme-api"\n')
    (owner / "series.jsonl").write_text("")
    named = tmp_path / "named"
    named.mkdir()
    (named / "plumb.toml").write_text('adapter = "python"\nsubject = "asked-for"\n')

    assert _configured_subject(owner / "series.jsonl", str(named)) == "asked-for"


@pytest.mark.proves("dev07-6-1", depth="component")
def test_a_line_a_reader_cannot_make_a_record_of_is_refused_by_name(tmp_path):
    """A series is an append-only log kept in the project's own tree, so it is exactly the file a
    hand-edit, a merge or another tool's writer reaches.

    It answered a bad line with `TypeError: Entry.__init__() got an unexpected keyword argument`,
    out of a dataclass constructor, at whatever command happened to be reading. Which line and
    which fields is what a reader can act on; the constructor's words are about a class they have
    never heard of.
    """
    from plumb.core.series import InvalidSeries, read

    log = tmp_path / "series.jsonl"
    log.write_text('{"seq": 1, "subject": "acme-api", "story": "A-1"}\n')

    with pytest.raises(InvalidSeries) as refused:
        read(log)

    said = str(refused.value)
    assert "series.jsonl:1" in said, "which line"
    assert "a transition" in said, "and in the reader's words, not the class's"
    assert "seq, subject, test, about, result, grounding, when" in said, "and what one carries"


@pytest.mark.proves("dev07-6-1", depth="component")
def test_a_line_that_is_not_json_says_so_at_its_own_line_number(tmp_path):
    from plumb.core.series import InvalidSeries, read

    log = tmp_path / "series.jsonl"
    log.write_text('{"seq": 1, "subject": "acme-api", "test": "t", "about": null, '
                   '"result": "passed", "grounding": "grounded", "when": null}\n{ not json\n')

    with pytest.raises(InvalidSeries) as refused:
        read(log)

    assert "series.jsonl:2 is not JSON" in str(refused.value)


@pytest.mark.proves("dev07-6-1", depth="component")
def test_an_unreadable_store_is_an_outcome_and_never_a_traceback(tmp_path, monkeypatch):
    """`transmit` never raises into a caller's workflow — a push is not allowed to take the run
    with it, whatever it finds.

    Enrolled deliberately, because enrolment is resolved *before* the store is read and an
    unenrolled push refuses for that reason instead. This test read the developer's own enrolment
    to get past that line until the suite stopped reaching outside the tmp dir at all, which is
    the version of passing where the assertion below never ran.
    """
    from plumb import transmit
    from plumb.transmit import push_series

    monkeypatch.setattr(transmit, "load", lambda *a, **k: transmit.Enrolment(
        "self", "tok", "https://example.invalid"))

    (tmp_path / "plumb.toml").write_text('adapter = "python"\nsubject = "acme-api"\n')
    log = tmp_path / "series.jsonl"
    log.write_text('{"seq": 1, "subject": "acme-api", "story": "A-1"}\n')

    outcome = push_series(log, project=str(tmp_path))

    assert not outcome.ok
    assert "does not read as a transition" in outcome.reason
    assert outcome.sent == () and outcome.queued == ()


@pytest.mark.proves("dev07-6-1", depth="wiring")
def test_reading_a_broken_store_through_the_command_says_which_line(tmp_path, capsys):
    """Driven through the command, because the claim is about what a person reading their own
    history is handed — and every path to that ran through a dataclass constructor."""
    from plumb import cli

    log = tmp_path / "series.jsonl"
    log.write_text('{"seq": 1, "subject": "acme-api", "story": "A-1"}\n')

    assert cli.main(["series", "show", str(log)]) == 1

    said = capsys.readouterr().err
    assert "series.jsonl:1" in said and "a transition" in said
    assert "Traceback" not in said


@pytest.mark.proves("dev07-6-2", depth="wiring")
def test_the_command_pushes_under_the_subject_of_the_project_it_was_given(tmp_path, monkeypatch,
                                                                          capsys):
    """The whole defect was that a correctly authenticated request landed under the wrong name, so
    the claim is about which subject the *command* resolves — not which one a helper returns."""
    from plumb import cli, transmit

    owner = tmp_path / "acme"
    (owner / "build" / "plumb").mkdir(parents=True)
    (owner / "plumb.toml").write_text(
        'adapter = "python"\nsubject = "acme-api"\nendpoint = "https://example.invalid"\n')
    log = owner / "build" / "plumb" / "series.jsonl"
    log.write_text(json.dumps({"seq": 1, "subject": "acme-api", "test": "t", "about": None,
                               "result": "passed", "grounding": "grounded", "when": None}) + "\n")

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "plumb.toml").write_text('adapter = "python"\nsubject = "somebody-else"\n')
    monkeypatch.chdir(elsewhere)

    asked = []
    monkeypatch.setattr(transmit, "_signing", lambda project=None: None)
    monkeypatch.setattr(transmit, "load", lambda *a, **k: transmit.Enrolment(
        "self", "tok", "https://example.invalid"))
    monkeypatch.setattr(transmit, "_deliver_batch",
                        lambda url, batch, enrolment: (asked.append(url), transmit.RETRY, "")[1:])

    cli.main(["series", "push", str(log)])

    assert asked and asked[0].endswith("/series/acme-api"), \
        f"pushed to {asked} — the subject followed the shell rather than the series"


@pytest.mark.proves("dev07-6-1", depth="component")
def test_a_series_is_stamped_once_when_it_is_created(tmp_path):
    """`dev07-6-2` makes a range *we discarded* legible and stops one step short — a history lost
    entirely leaves nothing behind to be legible about.

    Stamped at creation because that is the only moment at which *this file began* is a fact
    anybody holds. A stamp added later would be an assertion about a past the writer was not
    present for.
    """
    from plumb.core.series import Origin, append, began, read

    log = tmp_path / "series.jsonl"
    append(log, run(cited("t::a", "2026-08-26T09:00:00Z")))
    first = began(read(log))

    assert isinstance(first, Origin) and first.origin
    assert first.seq == 1, "before the facts it vouches for"
    assert first.started == "2026-08-26T09:00:00Z", \
        "taken from the run's own facts, never from our clock"

    append(log, run(cited("t::a", "2026-08-26T10:00:00Z", result="failed")))
    stamps = [r for r in read(log) if isinstance(r, Origin)]
    assert len(stamps) == 1, "stamped once; a series that re-stamps proves nothing about beginning"
    assert began(read(log)).origin == first.origin


@pytest.mark.proves("dev07-6-1", depth="component")
def test_two_series_are_stamped_differently(tmp_path):
    """The stamp answers *is this the same series*. Two files that cannot be told apart would make
    a lost history and a new one the same document, which is the whole defect."""
    from plumb.core.series import append, began, read

    one, two = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    append(one, run(cited("t::a", "2026-08-26T09:00:00Z")))
    append(two, run(cited("t::a", "2026-08-26T09:00:00Z")))

    assert began(read(one)).origin != began(read(two)).origin, (
        "identical runs, different series — the stamp is evidence of which file this is, not a "
        "summary of what it holds")


@pytest.mark.proves("dev07-6-1", depth="component")
def test_a_history_carrying_no_stamp_is_of_unknown_extent(tmp_path):
    """A counter cannot fix this: one restored from nothing reads exactly like one that has just
    started. What is missing is not a bigger number but proof of beginning, so its absence is the
    answer — a file written before stamping existed, or restored from a partial copy, is a history
    of unknown extent rather than a short one."""
    from plumb.core.series import began, read

    log = tmp_path / "series.jsonl"
    log.write_text(json.dumps({"seq": 1, "subject": "A-1", "test": "t", "about": None,
                               "result": "passed", "grounding": "grounded",
                               "when": "2026-08-26T09:00:00Z"}) + "\n")

    assert began(read(log)) is None


@pytest.mark.proves("dev07-6-1", depth="wiring")
def test_show_says_unknown_extent_rather_than_reporting_a_short_history(tmp_path, capsys):
    """The reader is the point. A confident `changes: 1` with nothing disagreeing is what makes an
    eviction silent, so the notice has to reach the person reading the count."""
    from plumb import cli
    from plumb.core.series import append

    unstamped = tmp_path / "old.jsonl"
    unstamped.write_text(json.dumps({"seq": 1, "subject": "A-1", "test": "t", "about": None,
                                     "result": "passed", "grounding": "grounded",
                                     "when": "2026-08-26T09:00:00Z"}) + "\n")

    assert cli.main(["series", "show", str(unstamped)]) == 0
    said = capsys.readouterr().out
    assert "UNKNOWN EXTENT" in said
    assert said.index("UNKNOWN EXTENT") < said.index("changes"), \
        "above the count it qualifies — a reader must not reach a number without passing it"
    assert "a floor, never a total" in said

    stamped = tmp_path / "new.jsonl"
    append(stamped, run(cited("t::a", "2026-08-26T09:00:00Z")))
    cli.main(["series", "show", str(stamped)])

    assert "UNKNOWN EXTENT" not in capsys.readouterr().out, \
        "and silent on a healthy history — a notice on every run is one nobody reads"


@pytest.mark.proves("dev07-6-3", depth="component")
def test_a_copy_a_holder_has_accepted_from_is_a_cache(tmp_path):
    """`dev07-6-2` moves the mark only on acceptance, so a mark that has moved *is* the evidence a
    holder exists — and once one does, the local file is derived rather than a second opinion.

    A history that may live in several places will live in several places. Several plausible
    sources cannot be read at all, where a single consistently-wrong one can be read around, so one
    of them has to say it is the copy.
    """
    from plumb.core.series import AUTHORITY, CACHE, append, extent, read, sent_mark

    log = tmp_path / "series.jsonl"
    append(log, run(cited("t::a", "2026-08-26T09:00:00Z")))

    assert extent(read(log), 0).role == AUTHORITY, "nothing else holds it, so it is the history"

    sent_mark(log).write_text("3")
    assert extent(read(log), 3).role == CACHE


@pytest.mark.proves("dev07-6-3", depth="component")
def test_a_pulled_copy_says_what_it_is_and_where_it_came_from(tmp_path):
    """The marker is in the file rather than worked out from configuration, because the question is
    about *this copy* and its answer has to survive being moved, mailed, or opened somewhere the
    project is not."""
    from plumb.core.series import CACHE, Retrieved, extent, read

    log = tmp_path / "pulled.jsonl"
    log.write_text(
        json.dumps({"seq": 1, "subject": "A-1", "test": "t", "about": None, "result": "passed",
                    "grounding": "grounded", "when": "2026-08-26T09:00:00Z"}) + "\n"
        + json.dumps({"seq": 2, "retrieved_from": "https://holder.invalid/series/acme",
                      "at": "2026-08-26T10:00:00Z"}) + "\n")

    entries = read(log)
    assert isinstance(entries[-1], Retrieved)
    holds = extent(entries, 0)

    assert holds.role == CACHE and holds.holder == "https://holder.invalid/series/acme"
    assert (holds.first, holds.last) == (1, 1), (
        "the marker is a fact about the file, not a record in the history — counting it would make "
        "a pulled copy claim one record more than the holder handed over")


@pytest.mark.proves("dev07-6-3", depth="component")
def test_a_cache_may_be_longer_than_the_authority(tmp_path):
    """**Cache does not mean shorter.** A holder keeping a history under a bound discards ranges it
    once held, so the local copy can be the longer of the two — which does not make it a second
    opinion, because the two never disagree about a range they both hold."""
    from plumb.core.series import CACHE, append, compact, extent, read, sent_mark

    local = tmp_path / "local.jsonl"
    append(local, run(cited("t::a", "2026-08-26T09:00:00Z")))
    append(local, run(cited("t::a", "2026-08-26T10:00:00Z", result="failed")))
    sent_mark(local).write_text("9")

    holder = tmp_path / "holder.jsonl"
    append(holder, run(cited("t::a", "2026-08-26T09:00:00Z")))
    append(holder, run(cited("t::a", "2026-08-26T10:00:00Z", result="failed")))
    compact(holder, through=3, reason="under a bound", when="2026-08-26T11:00:00Z")

    mine, theirs = extent(read(local), 9), extent(read(holder), 0)

    assert mine.role == CACHE and theirs.role == "authority"
    assert mine.last >= theirs.last - len(theirs.gaps), "the copy is not the shorter one by rule"
    assert theirs.gaps and not mine.gaps, "the authority is the one that let a range go"


@pytest.mark.proves("dev07-6-1", depth="component")
def test_the_origin_survives_compaction(tmp_path):
    """It is written first, so it is always inside the first span compacted — and rebuilding the log
    from replayed state kept only the entries and threw it away. A holder that had compacted once
    could no longer show where the history began, and every copy pulled from it read as one of
    unknown extent while the holder knew the answer perfectly well. Compaction reclaims churn;
    proof of beginning is not churn."""
    from plumb.core.series import append, began, compact, extent, read

    log = tmp_path / "series.jsonl"
    append(log, run(cited("t::a", "2026-08-26T09:00:00Z")))
    append(log, run(cited("t::a", "2026-08-26T10:00:00Z", result="failed")))
    stamped = began(read(log)).origin

    compact(log, through=3, reason="under a bound", when="2026-08-26T11:00:00Z")

    assert began(read(log)).origin == stamped, "the same series, still able to prove it"
    assert extent(read(log), 0).whole is True, "so a copy of it is not of unknown extent"


@pytest.mark.proves("dev07-6-3", depth="wiring")
def test_show_tells_the_reader_which_copy_they_are_holding(tmp_path, capsys):
    """The reader is the whole point. A role derived correctly and never printed leaves two files
    open on a desk with nothing to choose between them."""
    from plumb import cli
    from plumb.core.series import append, sent_mark

    log = tmp_path / "series.jsonl"
    append(log, run(cited("t::a", "2026-08-26T09:00:00Z")))

    assert cli.main(["series", "show", str(log)]) == 0
    assert "cache of" not in capsys.readouterr().out, "nothing else holds it, so it is the history"

    sent_mark(log).write_text("3")
    assert cli.main(["series", "show", str(log)]) == 0

    said = capsys.readouterr().out
    assert "cache of" in said and "not a second opinion" in said
    assert said.index("cache of") < said.index("subject"), \
        "before the table it qualifies, not after it"


@pytest.mark.proves("dev07-6-3", depth="wiring")
def test_a_pulled_copy_names_the_holder_it_came_from(tmp_path, capsys):
    from plumb import cli

    log = tmp_path / "pulled.jsonl"
    log.write_text(
        json.dumps({"seq": 1, "origin": "abc123", "started": "2026-08-26T09:00:00Z"}) + "\n"
        + json.dumps({"seq": 2, "subject": "A-1", "test": "t", "about": None, "result": "passed",
                      "grounding": "grounded", "when": "2026-08-26T09:00:00Z"}) + "\n"
        + json.dumps({"seq": 3, "retrieved_from": "https://holder.invalid/series/acme",
                      "at": "2026-08-26T10:00:00Z"}) + "\n")

    cli.main(["series", "show", str(log)])
    said = capsys.readouterr().out

    assert "cache of https://holder.invalid/series/acme" in said
    assert "UNKNOWN EXTENT" not in said, "it carries the holder's stamp, so its extent is known"
