

# -- the ratified record contract, v4 (docs/record-contract.md) ---------------------------------

def test_the_wire_never_carries_a_marker_and_the_disk_always_does():
    """The round-trip case's correction, 2026-09-13: a marker word sent as text is stored as an
    answer the filer never gave. Absence on the wire is what produces the marker at the
    receiver; the disk keeps every field, markers and all, because the record outlives the
    wire."""
    import json
    from plumb.support import SupportRecord

    question = SupportRecord(id="q-1", observed_at="2026-09-13T00:00:00Z", source="self",
                             observation="asked", kind="question")
    wire = json.loads(question.to_wire())
    assert "implication" not in wire, "nothing to claim, so nothing to say"
    assert "excerpt" not in wire, "the marker word as text asserts a reply nobody gave"
    assert "attempting" not in wire and "instead" not in wire and "recurrence" not in wire, \
        "a question never asked is absent, and the receiver marks it uncaptured"
    disk = json.loads(question.to_json())
    assert disk["excerpt"] == "n/a", "the disk shape keeps its markers"

    # An implication is never required now that `friction` is retired, and a record that states
    # one anyway still carries it — the field outlived the kind that demanded it.
    stated = SupportRecord(id="f-1", observed_at="2026-09-13T00:00:00Z", source="self",
                           observation="rubbed", kind="report", implication="costs an hour",
                           recurrence="unknown")
    wire = json.loads(stated.to_wire())
    assert wire["implication"] == "costs an hour"
    assert wire["recurrence"] == "unknown", \
        "unknown answered deliberately is a value, and survives — the whole point of the None default"


def test_a_v3_record_climbs_to_v4_with_the_uncaptured_marker_never_a_value():
    """The intake fields applied to every v3 record and nothing wrote them down — which is the
    uncaptured marker's exact meaning, and not a value: `unknown` sent deliberately is a value,
    and the two stay different facts."""
    from plumb.support import SupportRecord, UNCAPTURED, SCHEMA_VERSION

    climbed = SupportRecord.from_json("""{
        "id": "old-1", "observed_at": "2026-09-10T00:00:00Z", "source": "self",
        "observation": "a v3 record", "kind": "report", "version": 3}""")
    assert SCHEMA_VERSION >= 4
    assert climbed.attempting == UNCAPTURED
    assert climbed.instead == UNCAPTURED
    assert climbed.recurrence == UNCAPTURED


def test_the_wire_carries_the_conversation_version_and_never_the_records():
    """Ratified: the record-version header is out of the contract until a change moves the
    record and not the wire. The record's version is stamped in the body, where a durable
    artifact's version belongs."""
    from plumb import transmit

    assert transmit.VERSION_HEADER == "Plumb-Support-Version"
    from plumb.support import SCHEMA_VERSION
    assert transmit.PROTOCOL_VERSION != SCHEMA_VERSION or transmit.PROTOCOL_VERSION == 2


def test_the_tool_version_is_the_artifacts_own_and_climbs_as_uncaptured():
    """Ratified 2026-09-13: read out of the artifact, never typed; a v4 record climbs with the
    uncaptured marker because something filed it and nothing wrote the version down."""
    from plumb.support import SupportRecord, UNCAPTURED, SCHEMA_VERSION

    assert SCHEMA_VERSION == 5
    climbed = SupportRecord.from_json("""{
        "id": "old-2", "observed_at": "2026-09-10T00:00:00Z", "source": "self",
        "observation": "a v4 record", "kind": "report", "version": 4}""")
    assert climbed.tool_version == UNCAPTURED

    import json
    fresh = SupportRecord(id="n-1", observed_at="2026-09-14T00:00:00Z", source="self",
                          observation="filed", kind="report", tool_version="0.6.0")
    assert json.loads(fresh.to_wire())["tool_version"] == "0.6.0"
    silent = SupportRecord(id="n-2", observed_at="2026-09-14T00:00:00Z", source="self",
                           observation="filed", kind="report")
    assert "tool_version" not in json.loads(silent.to_wire()), \
        "uncaptured is an absence on the wire, and the receiver assigns the marker"
