"""The manifest — the contract between adapter and core (chapter 2)."""

import json
import re
from pathlib import Path

import pytest

from plumb.core.manifest import (
    PARSEABLE_VERSIONS,
    POLICY_WINDOW,
    SCHEMA_MAJOR,
    SCHEMA_VERSION,
    SUPPORTED_VERSIONS,
    BEHAVIORAL,
    FAILED,
    GROUNDED,
    NOT_CHECKED,
    PASSED,
    SKIPPED,
    STRUCTURAL,
    Citation,
    InvalidManifest,
    Manifest,
    Story,
)


def cite(**kw) -> Citation:
    return Citation(**{"test": "t::a", "depth": "unit", "result": PASSED, **kw})


@pytest.mark.proves("dev07-3-1", depth="unit")
def test_a_citation_is_test_depth_result_and_its_grounding_slot():
    c = cite(grounding=GROUNDED)
    assert (c.test, c.depth, c.result) == ("t::a", "unit", PASSED)
    assert c.grounding == GROUNDED


@pytest.mark.proves("dev07-3-1", depth="unit")
def test_grounding_and_mutation_are_slots_defaulting_to_unfilled():
    """Chapter 2 fixes where the facts sit, not how they are produced — and they sit at different
    levels: grounding is what one test did, while a mutant is run against every test citing the
    story, so its result is one fact about the story (`dev07-2-4`)."""
    assert cite().grounding == NOT_CHECKED, "an unfilled grounding slot is not-checked, not a guess"
    assert Story().mutation is None, "mutation is populated only when the opt-in is on (dev07-2-2)"


@pytest.mark.proves("dev07-3-1", depth="unit")
def test_the_result_vocabulary_is_the_runners_own_normalized():
    for result in (PASSED, SKIPPED, FAILED):
        assert cite(result=result).result == result
    with pytest.raises(InvalidManifest):
        cite(result="errored")


@pytest.mark.proves("dev07-3-2", depth="component")
def test_the_story_id_is_opaque_so_an_external_key_needs_no_catalog():
    """A spreadsheet row or a ticket number is as good a key as a chN-M."""
    m = Manifest(stories={"SHEET-42": Story(citations=(cite(),))})
    assert "SHEET-42" in m.stories
    assert Manifest.from_json(m.to_json()).stories["SHEET-42"].citations[0].test == "t::a"


@pytest.mark.proves("dev07-3-1", depth="component")
def test_a_citation_carries_the_consumers_key_and_plumb_owns_none_of_it():
    """Two stories cited by one test may carry two different refs — the join is per claim."""
    m = Manifest(stories={
        "dev05": Story(citations=(cite(ref="PROJ-7"),)),
        "dev07-4-2": Story(citations=(cite(ref="PROJ-9"),)),
    })
    assert m.stories["dev05"].citations[0].ref == "PROJ-7"
    assert m.stories["dev07-4-2"].citations[0].ref == "PROJ-9"
    # Absent is the ordinary case, and nothing invents one.
    assert cite().ref is None
    assert Manifest.from_json(m.to_json()).stories["dev05"].citations[0].ref == "PROJ-7"


@pytest.mark.proves("dev07-3-1", depth="unit")
def test_plumb_enforces_no_uniqueness_on_a_ref_it_does_not_own():
    """The foreign system owns that namespace and already has an identity rule."""
    m = Manifest(stories={"a": Story(citations=(cite(ref="SAME"), cite(test="t::b", ref="SAME")))})
    assert [c.ref for c in m.stories["a"].citations] == ["SAME", "SAME"]


@pytest.mark.proves("dev07-3-2", depth="unit")
def test_the_archetype_is_per_story_not_per_citation():
    """A citation is what a *test* claims; the archetype is the part a test may not claim."""
    assert Story().archetype == BEHAVIORAL, "silence means behavioral, so a spec is unchanged"
    assert Story(archetype=STRUCTURAL).archetype == STRUCTURAL
    assert not hasattr(cite(), "archetype")
    with pytest.raises(InvalidManifest):
        Story(archetype="non-functional")


@pytest.mark.proves("dev07-3-3", depth="component")
def test_the_manifest_round_trips_as_the_sole_interface():
    m = Manifest(stories={
        "dev05": Story(archetype=STRUCTURAL, citations=(cite(grounding=GROUNDED),)),
    })
    back = Manifest.from_json(m.to_json())
    assert back == m


@pytest.mark.proves("dev07-3-3", depth="unit")
def test_a_manifest_from_another_schema_version_is_refused_at_the_edge():
    with pytest.raises(InvalidManifest):
        Manifest.from_json('{"schema_version": 99, "stories": {}}')


# ---- the manifest as a contract somebody else writes against (dev07-3-2) -------------------


def doc(version=SCHEMA_VERSION, citation=None) -> str:
    cite = citation if citation is not None else {
        "test": "t::a", "depth": "unit", "result": "passed",
    }
    return json.dumps({"schema_version": version,
                       "stories": {"S-1": {"archetype": "behavioral", "citations": [cite]}}})


@pytest.mark.proves("dev07-3-2", depth="component")
def test_a_manifest_declares_the_shape_it_was_written_against():
    from plumb.core.manifest import SUPPORTED_VERSIONS

    assert SCHEMA_MAJOR in SUPPORTED_VERSIONS
    read = Manifest.from_json(doc())
    assert read.stories["S-1"].citations[0].test == "t::a"


@pytest.mark.proves("dev07-3-2", depth="unit")
def test_the_chain_reaches_one_major_deeper_than_the_window():
    """The version-window policy, revised. The published recommendation is *stay within one major of the latest*, and
    the rescue path is worth one major more than the advice — so nobody is stranded until they are
    three behind. Asserted rather than described, because the original form of this decision was a
    self-attestation in prose that nothing checked, and it turned out to be false."""
    from plumb.core.manifest import PARSEABLE_VERSIONS

    from plumb.core.manifest import _SHIPPED_ADAPTER_EMITS

    assert POLICY_WINDOW == {SCHEMA_MAJOR - 1, SCHEMA_MAJOR}, "what D34 says"
    assert SUPPORTED_VERSIONS == POLICY_WINDOW | _SHIPPED_ADAPTER_EMITS, (
        "and what holds: the policy, widened by whatever our own adapters still emit — the two "
        "are kept apart so the gap between them can be read rather than inferred")
    assert PARSEABLE_VERSIONS == {SCHEMA_MAJOR - 2, SCHEMA_MAJOR - 1, SCHEMA_MAJOR}, \
        "migration: two back"
    assert SUPPORTED_VERSIONS <= PARSEABLE_VERSIONS, "never wider than what can be parsed"


@pytest.mark.proves("dev07-3-2", depth="component")
def test_a_manifest_from_the_future_is_refused_and_told_what_is_supported():
    """Nothing can be inferred from a description that has not been written yet, so refusing is
    the honest answer — and the message is for an adapter author with no view of this source."""
    with pytest.raises(InvalidManifest) as refused:
        Manifest.from_json(doc(version=99))
    message = str(refused.value)
    assert "99" in message and "newer" in message
    assert f"{SCHEMA_MAJOR}.x" in message, "say what this Plumb does read"
    assert all(f"{v}.x" in message for v in SUPPORTED_VERSIONS), "every version a run accepts"
    assert not (PARSEABLE_VERSIONS - SUPPORTED_VERSIONS) & {
        int(part.split(".")[0]) for part in message.split() if part[:1].isdigit()}, (
        "and only those — naming a shape only `plumb manifest migrate` reads sends an adapter "
        "author to emit a document every run would then refuse")


@pytest.mark.proves("dev07-3-2", depth="unit")
def test_a_manifest_with_no_declared_version_is_refused():
    with pytest.raises(InvalidManifest, match="no schema_version"):
        Manifest.from_json('{"stories": {}}')


@pytest.mark.proves("dev07-3-2", depth="component")
def test_an_unknown_story_field_is_refused_rather_than_silently_dropped():
    """Stricter than it looks, and the asymmetry the other way would be dangerous: a typo like
    `archetypes` dropped in silence leaves the story quietly behavioral, and the archetype
    decides which check the gate applies — so a dropped key changes a status."""
    doc = json.dumps({"schema_version": "8.0", "stories": {
        "S-1": {"archetypes": "structural", "citations": []}}})
    with pytest.raises(InvalidManifest) as refused:
        Manifest.from_json(doc)
    assert "archetypes" in str(refused.value)


@pytest.mark.proves("dev07-3-2", depth="unit")
def test_the_version_table_and_the_code_cannot_drift_apart():
    """Each version's entry is the whole truth about that shape, so the newest entry must match
    what the dataclasses actually carry. If they diverge, every refusal message is wrong."""
    from plumb.core.manifest import CITATION_FIELDS, STORY_FIELDS

    assert CITATION_FIELDS[SCHEMA_MAJOR] == set(Citation.__dataclass_fields__)
    assert STORY_FIELDS[SCHEMA_MAJOR] == set(Story.__dataclass_fields__)
    assert set(STORY_FIELDS) == set(CITATION_FIELDS) == PARSEABLE_VERSIONS, \
        "a shape cannot be described and left unparseable, or parsed and left undescribed"
    assert POLICY_WINDOW < PARSEABLE_VERSIONS, (
        "the window policy allows is a strict subset of the chain migration can read — they "
        "stopped being one set the first time a version retired")


@pytest.mark.proves("dev07-3-2", depth="component")
def test_a_refusal_names_the_version_the_document_declared():
    """Not the core's current constant. Once two versions exist those differ, and telling an
    adapter author about a version they never claimed sends them looking in the wrong place."""
    doc = json.dumps({"schema_version": "8.0", "stories": {
        "S-1": {"citations": [{"test": "t", "depth": "unit", "result": "passed", "wat": 1}]}}})
    with pytest.raises(InvalidManifest) as refused:
        Manifest.from_json(doc)
    assert "schema_version 8" in str(refused.value)


@pytest.mark.proves("dev07-3-2", depth="component")
def test_a_field_the_declared_version_does_not_define_is_refused_by_name():
    """Within a version the field set is fixed, so an unrecognised key means the producer
    changed shape without changing the number it claims."""
    with pytest.raises(InvalidManifest) as refused:
        Manifest.from_json(doc(citation={
            "test": "t::a", "depth": "unit", "result": "passed", "confidence": 0.9,
        }))
    assert "confidence" in str(refused.value), "name the offending field, not just the failure"


@pytest.mark.proves("dev07-3-2", depth="component")
def test_a_citation_missing_a_required_field_is_refused_by_name():
    with pytest.raises(InvalidManifest) as refused:
        Manifest.from_json(doc(citation={"test": "t::a", "depth": "unit"}))
    assert "result" in str(refused.value)


@pytest.mark.proves("dev07-3-2", depth="component")
@pytest.mark.proves("dev07-5-1", depth="component")
def test_an_adapter_that_knows_nothing_of_grounding_still_emits_a_valid_document():
    """The optional fields carry defaults, so a first adapter can be small and still conform —
    it reports what it has and the board degrades honestly around the rest."""
    read = Manifest.from_json(doc())
    citation = read.stories["S-1"].citations[0]
    assert citation.grounding == NOT_CHECKED
    assert citation.ref is None
    assert read.stories["S-1"].mutation is None


@pytest.mark.proves("dev07-3-1", depth="component")
def test_the_manifest_names_the_instrument_that_measured_it():
    from plumb.core.manifest import Provenance

    instrument = Provenance(adapter="plumb-java", version="0.0.0", runtime="OpenJDK 25",
                            mechanism="JDWP breakpoints")
    m = Manifest(stories={"S-1": Story(citations=(
        Citation(test="t::a", depth="unit", result=PASSED, observer=instrument),))})

    back = Manifest.from_json(m.to_json())

    measured = back.stories["S-1"].citations[0].observer
    assert measured.mechanism == "JDWP breakpoints", "the mechanism is the load-bearing field"
    assert measured.adapter == "plumb-java"
    assert not hasattr(back, "observer"), \
        "the document names no instrument — a merged board carries several (`dev07-3-1`)"


@pytest.mark.proves("dev07-3-2", depth="component")
def test_a_retired_shape_is_refused_by_the_chain_and_not_merely_by_a_run():
    """`dev07-3-3-sr3`: a step retires when nothing stands on it, and retiring is *deleting its entry*.

    Major 5 named one instrument for a whole document and retired when major 8 moved the window
    past it. What replaces the climb it used to need is this: the chain is derived from the
    described shapes, so a retired one is unreachable by construction rather than by remembering to
    delete a branch — and the refusal still says what to do, because a derived document always has
    the answer of re-running the suite that made it.
    """
    retired = json.dumps({"schema_version": 5, "stories": {
        "S-1": {"citations": [{"test": "t::a", "depth": "unit", "result": "passed"}]}}})

    with pytest.raises(InvalidManifest) as refused:
        Manifest.migrate(retired)

    assert "re-run" in str(refused.value), "the answer that always works for a derived document"


@pytest.mark.proves("dev07-3-1", depth="unit")
def test_a_half_named_instrument_names_none():
    # On a citation, which is where major 6 moved the instrument to (`dev07-3-1`).
    with pytest.raises(InvalidManifest, match="observer is missing"):
        Manifest.from_json(json.dumps({
            "schema_version": "8.0", "stories": {"S-1": {"citations": [
                {"test": "t::a", "depth": "unit", "result": "passed",
                 "observer": {"adapter": "x", "version": "1"}}]}}, "observed_tests": 0}))


@pytest.mark.proves("dev07-3-2", depth="component")
def test_the_manifest_records_how_far_the_run_got_not_only_what_it_found():
    """The extent of the observation is a fact about the *run*, and it round-trips as one."""
    back = Manifest.from_json(Manifest(stories={}, observed_tests=38).to_json())
    assert back.observed_tests == 38


@pytest.mark.proves("dev07-3-2", depth="component")
def test_observing_no_tests_and_being_unable_to_count_are_different_answers():
    """The whole point of the field. Both produce a manifest with no stories, and only one of
    them is a broken run — so the two must not collapse into the same document."""
    looked = Manifest.from_json(Manifest(stories={}, observed_tests=0).to_json())
    could_not = Manifest.from_json(Manifest(stories={}).to_json())

    assert looked.observed_tests == 0, "it looked and there was nothing"
    assert could_not.observed_tests is None, "it could not tell, which is a weaker claim"
    assert looked.observed_tests != could_not.observed_tests


@pytest.mark.proves("dev07-3-2", depth="unit")
def test_a_count_nobody_measured_is_refused_rather_than_coerced():
    """`bool` is an `int` in Python, so `True` would otherwise be accepted and read as 1 — a
    number no adapter produced, which is exactly the invention dev07-3-1 forbids."""
    for bad in (True, -1, "38", 1.5):
        with pytest.raises(InvalidManifest):
            Manifest(stories={}, observed_tests=bad)


@pytest.mark.proves("dev07-3-2", depth="component")
@pytest.mark.proves("dev07-3-3", depth="component")
def test_a_version_4_manifest_carries_forward_with_the_extent_absent_not_zero():
    """The migration that matters most here, because getting it wrong is not a missing fact but a
    false alarm: filling a pre-v5 manifest with 0 would make every older document claim its run
    observed nothing, and the board would report a broken run for every one of them.

    The document is at the chain's floor rather than at a fixed number — 6 retired when major 9
    landed, and a test pinned to a retired version stops exercising the migration and starts
    asserting that a retirement happened."""
    older = json.dumps({"schema_version": 7, "stories": {
        "S-1": {"citations": [{"test": "t::a", "depth": "unit", "result": "passed"}]}}})
    read = Manifest.migrate(older)
    assert read.observed_tests is None, "absent, never a zero it would then be alarmed by"
    assert read.stories["S-1"].citations[0].test == "t::a", "and the rest still reads"


@pytest.mark.proves("dev07-3-2", depth="unit")
@pytest.mark.proves("dev07-3-2", depth="unit")
def test_a_retired_field_is_not_one_a_newer_version_may_carry():
    """`dev07-3-2`: within a declared version the field set is fixed, in both directions. Major 6
    moved the instrument onto the fact (`dev07-3-1`), so a document claiming 6.0 while still naming
    a document-level observer changed shape without changing the number it claims."""
    with pytest.raises(InvalidManifest, match="observer"):
        Manifest.from_json(json.dumps({
            "schema_version": "8.0", "stories": {}, "observed_tests": 0,
            "observer": {"adapter": "x", "version": "1", "runtime": "y", "mechanism": "z"}}))


@pytest.mark.proves("dev07-3-1", depth="component")
def test_the_instrument_is_a_property_of_the_fact_not_of_the_document():
    """`dev07-3-1` says two facts are comparable only when the same kind of observer produced them.
    One observer per document was true while one run meant one adapter; the moment a board carries
    a JVM observer's fact beside a CPython tracer's, a single document-level instrument asserts a
    comparability it cannot support — the same word meaning different evidence."""
    from plumb.core.board import Board
    from plumb.core.manifest import Provenance

    jvm = Provenance(adapter="plumb-java", version="0.1", runtime="OpenJDK 25", mechanism="JDWP")
    cpy = Provenance(adapter="plumb-python", version="0.1", runtime="CPython 3.13",
                     mechanism="sys.settrace")
    mixed = Manifest(stories={
        "S-1": Story(citations=(Citation(test="a", depth="unit", result=PASSED, observer=jvm),)),
        "S-2": Story(citations=(Citation(test="b", depth="unit", result=PASSED, observer=cpy),)),
    }, observed_tests=2)

    observers = Board.render(mixed).as_dict()["observers"]

    assert [o["adapter"] for o in observers] == ["plumb-java", "plumb-python"], \
        "both instruments are named, so a mixed board can be read at all"
    assert mixed.stories["S-1"].citations[0].observer.mechanism == "JDWP", \
        "and each fact still says which one made it"


def test_no_bundled_adapter_emits_a_version_the_core_refuses():
    """Plumb ships every adapter (`dev00-1-1`), so an adapter Plumb ships is Plumb's to keep readable.

    Retiring a schema version its **own** adapter still emits does not inconvenience an adopter —
    it breaks every project in that language, and the refusal it prints is a loop: *re-run your
    suite* produces the same refused document again, and *bring the file forward* migrates a file
    that is regenerated on the next run.

    Found by pointing the tool at a real Java project and watching it refuse: the Java adapter
    hardcodes 5, the window had moved to 6 and 7, and **284 green tests did not notice**. They
    could not — the Python adapter emits the current version, and the Java path skips without a
    JVM, so this repository passes whichever way that constant reads. The check runs where the
    machinery is *assembled* rather than where it is used, which is the same reason `dev00-1-1` lives
    where it does.

    A pure source scan of a constant, needing no JVM and no build, so it costs nothing and
    therefore always runs.
    """
    java = Path(__file__).resolve().parents[1] / (
        "adapters/java/adapter/src/main/java/org/plumbspec/Manifest.java")
    declared = re.search(r"SCHEMA_MAJOR\s*=\s*(\d+)", java.read_text())

    assert declared, f"no SCHEMA_MAJOR in {java.name} — it moved, and this check would now " \
                     "pass by having nothing to look at"
    assert int(declared.group(1)) in SUPPORTED_VERSIONS, (
        f"the Java adapter emits schema {declared.group(1)} and this core reads "
        f"{sorted(SUPPORTED_VERSIONS)} — every Java project would be refused, and re-running "
        "their suite would produce the same refused document")


def test_the_adapter_never_calls_a_citation_annotation_member_directly():
    """`plumb-annotations` is the **consumer's** artifact (`dev00-1-1`), so the `Proves` the Java
    adapter binds to at runtime is whichever version *their* build resolved — which may predate
    any member added since. A direct call compiles cleanly here and throws `NoSuchMethodError`
    there.

    And that failure is invisible. It is raised inside a JUnit listener callback, the platform
    swallows it to keep the run alive, and the manifest comes out with every test observed and
    **no citations at all** — a board reading *you have not cited anything yet* for a project whose
    suite is covered in citations. Found exactly that way, against a real project carrying
    `plumb-annotations-0.1.0`: 38 tests observed, 0 stories, empty board, no error.

    So members added after publication are read by name with absent as the ordinary answer. This
    scan is what keeps that true for the next one: `value`, `depth` and `ref` shipped in 0.1.0 and
    are safe to call, and anything else is not. A pure source scan, no JVM and no build.
    """
    listener = Path(__file__).resolve().parents[1] / (
        "adapters/java/adapter/src/main/java/org/plumbspec/PlumbListener.java")
    source = listener.read_text()
    #: Shipped in `plumb-annotations-0.1.0`, so calling these can never bind to a version that
    #: lacks them. Anything added later is not on this list, which is the point of the list.
    published = {"value", "depth", "ref"}
    #: Declared by `java.lang.annotation.Annotation` itself, which every annotation implements —
    #: part of the JDK's contract rather than the consumer's vocabulary, so never absent.
    inherited = {"annotationType", "equals", "hashCode", "toString"}

    called = set(re.findall(r"cited\.(\w+)\(\)", source))

    assert called <= published | inherited, (
        f"the adapter calls {sorted(called - published - inherited)} directly on a consumer's "
        "annotation — "
        "read it by name instead, or a project on an older plumb-annotations silently reports no "
        "citations at all")


@pytest.mark.proves("dev07-3-1", depth="component")
def test_a_measurement_time_rides_the_fact_and_absent_is_never_now():
    """`dev07-3-1`'s argument, one field over. That story moved the instrument onto the citation
    because a merged board carries several adapters, and two facts are comparable only when the
    same kind of observer produced them. A merged board carries several **runs** for exactly the
    same reason, so one document-level time would be the same false claim.

    Absent means *not reported* and is never read as *now* (`dev07-3-3`). An adapter that cannot say
    when it measured says nothing, which is strictly weaker than a time it invented — and every
    document written before this field carries none, which is the honest reading of them rather
    than a gap to fill in.
    """
    stamped = json.dumps({"schema_version": "9.0", "stories": {"S": {"citations": [
        {"test": "t::a", "depth": "unit", "result": "passed", "when": "2026-08-02T15:04:05Z"}]}}})
    silent = json.dumps({"schema_version": "9.0", "stories": {"S": {"citations": [
        {"test": "t::a", "depth": "unit", "result": "passed"}]}}})

    assert Manifest.from_json(stamped).stories["S"].citations[0].when == "2026-08-02T15:04:05Z"
    assert Manifest.from_json(silent).stories["S"].citations[0].when is None, "never invented"


@pytest.mark.proves("dev07-3-2", depth="component")
def test_a_measurement_time_in_the_wrong_shape_is_refused_rather_than_coerced():
    """A time is the axis a series is ordered on, so one that parses differently in two languages
    orders differently in two languages — and a board would disagree with itself about what
    happened first. RFC 3339 in UTC is the one spelling every language reads without an argument
    about format."""
    doc = json.dumps({"schema_version": "9.0", "stories": {"S": {"citations": [
        {"test": "t::a", "depth": "unit", "result": "passed", "when": "2 Aug 2026"}]}}})

    with pytest.raises(InvalidManifest, match="RFC 3339"):
        Manifest.from_json(doc)


def test_both_shipped_adapters_stamp_a_measurement_time():
    """A field nothing fills is worse than no field: it reads as *not reported* everywhere and
    nobody can tell that from an adapter that simply never learned to. Checked at the source of
    both, because the Java one is not exercised by this suite without a JVM — the blindness
    `dev00-1-1` records, and the one that let it sit two majors behind."""
    root = Path(__file__).resolve().parents[1]
    java = (root / "adapters/java/adapter/src/main/java/org/plumbspec/PlumbListener.java").read_text()
    python = (root / "src/plumb/adapters/python/adapter.py").read_text()

    assert "measuredAt" in java and "Instant.now()" in java, "the Java adapter stamps a time"
    assert "measured_at" in python and "datetime.now" in python, "and so does the Python one"
