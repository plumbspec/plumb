"""The friction record, proved against the real validator (``ch6-2``…`ch6-4`, `ch6-11`)."""

import json

import pytest

from plumb.support import INAPPLICABLE, SCHEMA_VERSION, SupportRecord, InvalidRecord, excerpt, load_all

WELL_FORMED = dict(
    id="2026-07-26-per-test-fact-is-not-per-test",
    observed_at="2026-07-26T00:00:00+00:00",
    source="self",
    observation="the fact changed between runs",
    implication="a fact that depends on execution order is not a fact",
)


def test_a_record_carries_its_observation_and_its_anchors():
    record = SupportRecord(**WELL_FORMED, story="dev07-1-4", location="spec/chapter_03.py:12")

    assert record.observation == "the fact changed between runs"
    assert record.anchors == {"story": "dev07-1-4", "location": "spec/chapter_03.py:12"}


def test_a_writer_that_cannot_state_the_implication_cannot_file():
    with pytest.raises(InvalidRecord, match="implication is required"):
        SupportRecord(**{**WELL_FORMED, "implication": "   "})


def test_rejection_names_everything_missing_at_once():
    with pytest.raises(InvalidRecord) as rejected:
        SupportRecord(**{**WELL_FORMED, "observation": " ", "implication": " ", "source": "customer"})

    message = str(rejected.value)
    assert "observation is required" in message
    assert "implication is required" in message
    assert "source must be one of" in message


def test_an_inapplicable_anchor_is_distinct_from_a_blank_one():
    record = SupportRecord(**WELL_FORMED)
    assert record.commit == INAPPLICABLE
    assert "commit" not in record.anchors

    with pytest.raises(InvalidRecord, match="blank is not a value"):
        SupportRecord(**WELL_FORMED, commit="")


def test_time_must_be_utc_not_whatever_the_desk_clock_said():
    with pytest.raises(InvalidRecord, match="UTC"):
        SupportRecord(**{**WELL_FORMED, "observed_at": "2026-07-26T00:00:00+02:00"})

    with pytest.raises(InvalidRecord, match="UTC"):
        SupportRecord(**{**WELL_FORMED, "observed_at": "yesterday"})


def test_a_record_round_trips_under_its_own_id(tmp_path):
    record = SupportRecord(**WELL_FORMED, story="dev07-1-4")

    path = record.write_to(tmp_path)

    assert path.name == f"{record.id}.json"
    assert SupportRecord.from_json(path.read_text()) == record
    assert load_all(tmp_path) == ([record], [])


def test_removal_is_an_operation_not_an_excavation(tmp_path):
    kept = SupportRecord(**WELL_FORMED)
    withdrawn = SupportRecord(**{**WELL_FORMED, "id": "2026-07-26-withdrawn"})
    kept.write_to(tmp_path)
    path = withdrawn.write_to(tmp_path)

    path.unlink()

    assert [r.id for r in load_all(tmp_path)[0]] == [kept.id]


def test_an_unknown_field_is_rejected_rather_than_silently_kept():
    with pytest.raises(InvalidRecord, match="unknown field"):
        SupportRecord.from_json('{"id": "x", "severity": "high"}')


def test_the_record_carries_the_code_rather_than_a_reference_to_it(tmp_path):
    source = tmp_path / "rubbed.py"
    source.write_text("import a\nimport b\n\ndef the_line_that_rubbed():\n    return 1\n")

    location, body = excerpt(source, 4, 5, root=tmp_path)

    assert location == "rubbed.py:4-5"
    assert body == "4  def the_line_that_rubbed():\n5      return 1"
    record = SupportRecord(**WELL_FORMED, location=location, excerpt=body)
    assert "the_line_that_rubbed" in record.anchors["excerpt"]


def test_an_excerpt_survives_the_file_it_came_from(tmp_path):
    """Why the code is carried, not referenced: the record still reads after the source is gone."""
    source = tmp_path / "rubbed.py"
    source.write_text("x = 1\n")
    _, body = excerpt(source, 1, 1)
    record = SupportRecord(**WELL_FORMED, excerpt=body)

    source.unlink()

    assert SupportRecord.from_json(record.to_json()).excerpt == body


def test_an_excerpt_that_needs_the_whole_file_is_not_pointing_at_the_rub(tmp_path):
    source = tmp_path / "big.py"
    source.write_text("\n".join(f"line {n}" for n in range(200)))

    with pytest.raises(ValueError, match="not pointing at the rub"):
        excerpt(source, 1, 120)


def test_an_excerpt_range_that_does_not_exist_is_refused_not_padded(tmp_path):
    source = tmp_path / "short.py"
    source.write_text("only = 1\n")

    with pytest.raises(ValueError, match="does not exist"):
        excerpt(source, 1, 9)
    with pytest.raises(ValueError, match="not a line range"):
        excerpt(source, 5, 2)


def test_capturing_an_excerpt_writes_nothing(tmp_path):
    source = tmp_path / "rubbed.py"
    source.write_text("x = 1\n")
    before = {p: p.stat().st_mtime_ns for p in tmp_path.rglob("*")}

    excerpt(source, 1, 1)

    assert {p: p.stat().st_mtime_ns for p in tmp_path.rglob("*")} == before


def test_a_record_records_the_schema_that_wrote_it(tmp_path):
    """A reader years later should not have to infer the schema from which fields happen to be
    present — that inference is the thing a version exists to remove."""
    record = SupportRecord(**WELL_FORMED)

    on_disk = json.loads(record.write_to(tmp_path).read_text())

    assert on_disk["version"] == SCHEMA_VERSION
    assert SupportRecord.from_json(json.dumps(on_disk)).version == SCHEMA_VERSION


def test_a_record_written_before_versioning_still_reads(tmp_path):
    """Every record already on a contributor's disk predates the stamp. Requiring it would have
    retired the entire existing knowledge base to add a field about not losing it."""
    pre_stamp = {k: v for k, v in {**WELL_FORMED, "id": "2026-07-20-pre-stamp"}.items()}
    assert "version" not in pre_stamp

    loaded = SupportRecord.from_json(json.dumps(pre_stamp))

    assert loaded.version == SCHEMA_VERSION, "read as the shape it structurally is"


def test_a_record_written_by_an_older_schema_still_reads(tmp_path):
    """The producer renamed `layer` to `depth` and left seven records on a contributor's machine
    unreadable — every one still perfectly good knowledge, none of it any longer listable."""
    v0 = {k: v for k, v in WELL_FORMED.items()}
    v0["layer"] = "n/a"
    path = tmp_path / f"{v0['id']}.json"
    path.write_text(json.dumps(v0))

    loaded = SupportRecord.from_json(path.read_text())

    assert loaded.id == WELL_FORMED["id"], "the knowledge survives the rename"
    assert loaded.depth == "n/a", "the retired field's value lands in the field that replaced it"
    assert loaded.version == SCHEMA_VERSION


def test_an_old_record_climbs_to_the_current_schema_and_is_written_back(tmp_path):
    """Read-time compatibility alone is unbounded — the reader would have to understand every
    shape that ever existed. Migrating forward is what lets a step be retired."""
    from plumb.store import SupportStore

    v0 = {**WELL_FORMED, "layer": "n/a"}
    (tmp_path / f"{v0['id']}.json").write_text(json.dumps(v0))
    store = SupportStore(tmp_path)

    upgraded, failed = store.migrate()

    assert upgraded == [WELL_FORMED["id"]] and failed == []
    on_disk = json.loads((tmp_path / f"{v0['id']}.json").read_text())
    assert on_disk["version"] == SCHEMA_VERSION, "the climb is persisted, not repeated per load"
    assert "layer" not in on_disk and on_disk["depth"] == "n/a"
    assert store.migrate() == ([], []), "idempotent: nothing already current is rewritten"


def test_migration_never_destroys_what_it_cannot_read(tmp_path):
    """A record it cannot climb is named and left exactly where it is."""
    from plumb.store import SupportStore

    (tmp_path / "2026-07-29-truncated.json").write_text('{"id": "trunc')

    upgraded, failed = SupportStore(tmp_path).migrate()

    assert upgraded == []
    assert [bad.id for bad in failed] == ["2026-07-29-truncated"]
    assert (tmp_path / "2026-07-29-truncated.json").read_text() == '{"id": "trunc'


# ── what the tool knows about itself (ch6-32) ─────────────────────────────────────────────

def _project(tmp_path, adapter="python"):
    (tmp_path / "plumb.toml").write_text(f'adapter = "{adapter}"\n')
    from plumb.config import Config

    return Config.find(tmp_path)


def test_the_observer_is_read_from_the_manifest_rather_than_restated(tmp_path):
    """Chapter 2 owns which adapter watched with what; this borrows it (`dev07-3-1`).

    Restating those fields here would be a second home for them, and the two spellings would
    disagree the first time either moved — which is the fault this repository found four times in
    one session and is the reason the element table says *borrowed*.
    """
    from plumb.core.manifest import Citation, Manifest, Provenance, Story
    from plumb.provenance import observed

    scratch = tmp_path / "scratch"
    scratch.mkdir()
    watched = Provenance(adapter="plumb-python", version="0.6.0", runtime="CPython 3.13",
                         mechanism="sys.settrace")
    Manifest(stories={"S-1": Story(citations=(
        Citation(test="t::a", depth="unit", result="passed", grounding="grounded",
                 when="2026-09-01T00:00:00Z", observer=watched),))}).write(scratch / "manifest.json")

    facts = observed(_project(tmp_path), scratch=scratch)
    assert facts["observer"] == "plumb-python 0.6.0 on CPython 3.13"


def test_nothing_having_run_is_told_apart_from_a_run_nobody_recorded(tmp_path):
    """`n/a` and `unknown` are different facts and the whole schema turns on it (`ch6-4`).

    A record filed at a desk with nothing running has no observer — the field did not apply. A run
    that happened and was not recorded is a lost value. Collapsing them would leave an operator
    unable to tell *there was no run* from *we failed to look*, and only one of those is a defect.
    """
    from plumb.provenance import observed
    from plumb.support import INAPPLICABLE, UNCAPTURED

    facts = observed(_project(tmp_path), scratch=tmp_path / "never-ran")
    assert facts["observer"] == INAPPLICABLE, "no run applied, so it is not a lost value"
    assert facts["invocation"] == UNCAPTURED, "a filing is itself a run nobody recorded the shape of"


def test_the_recorded_invocation_keeps_the_options_and_never_the_values(tmp_path):
    """This field travels by default, so what it carries is a privacy claim (`ch6-29`, `ch6-32`).

    *That mutation was on* answers most of what an operator asks the option list for. *Which
    directory, which story, which host* answers nothing they need and is the adopter's. An untested
    claim about what leaves a machine is the one kind that must not be taken on trust.
    """
    from plumb.launch import _scratch
    from plumb.provenance import RAN, record_run

    config = _project(tmp_path)
    record_run(config, ["board", "--mutation", "--project", "/home/someone/secret-client",
                        "--tests", "--story", "ACME-4412"], "exit 1")

    kept = (_scratch(config) / RAN).read_text()
    assert "--mutation" in kept and "--tests" in kept, "the shape of the run is the point"
    assert "secret-client" not in kept, "a path is the adopter's and this field travels"
    assert "ACME-4412" not in kept, "so is a story id"
    assert "exit 1" in kept, "and how it ended is what tells a refusal from a crash"
