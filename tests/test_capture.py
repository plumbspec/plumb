"""A series crossing the wire end to end — the push, the holder, and what it hands back.

The holder tests run a real HTTP server on a real socket. The claim is that a history crosses a
network boundary and comes back the same; a mocked transport would assert only that I wired my own
mock correctly.

**The support half of this file left with the capability** (`dev08-1-5`). Filing, the outbox and the
record schema were the core's, and are a module's now — what stayed is the transport underneath,
which both always shared.
"""

import io
import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from plumb import cli, transmit
from plumb.enrolment import Enrolment, NotEnrolled, load
from plumb.series_holder import build

RUB = "The gate accepted a test that touched nothing. Second time this week."
MEANS = "A check earns its place by what it rejects, not by what it was designed to catch."

@pytest.fixture
def server(tmp_path, request):
    """A real receiver on a real ephemeral port.

    Takes whatever `build` takes, through an indirect parametrisation, so a test that asserts what
    the holder contains can turn off the housekeeping it would otherwise be racing.
    """
    options = getattr(request, "param", {})
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"contributors": [
        {"credential": "tester-secret-token", "label": "a tester", "relationship": "trusted-tester"},
    ]}))
    received = tmp_path / "received"
    httpd = build(received, host="127.0.0.1", port=0, **options)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", received
    httpd.shutdown()


def enrolled(tmp_path, endpoint, credential="tester-secret-token") -> Path:
    path = tmp_path / "enrolment.json"
    path.write_text(Enrolment("trusted-tester", credential, endpoint).to_json())
    return path


# ── local by default (dev07-6-2-1-2) ──────────────────────────────────────────────────



def test_an_enrolment_without_a_credential_cannot_carry_consent():
    with pytest.raises(ValueError, match="credential"):
        Enrolment("trusted-tester", "  ", "https://example.invalid")
    with pytest.raises(ValueError, match="one of"):
        Enrolment("customer", "token", "https://example.invalid")


def test_a_missing_enrolment_is_the_ordinary_case_not_a_crash(tmp_path):
    with pytest.raises(NotEnrolled):
        load(tmp_path / "nothing.json")


AN_ENROLMENT = Enrolment("trusted-tester", "tok", "https://example.invalid")


class Refusal(urllib.error.HTTPError):
    def __init__(self, code, payload=b"{}"):
        super().__init__("http://x/support", code, "refused", {}, io.BytesIO(payload))









# ── the series, a second record type on the same receiver ─────────────────────

def _post_series(endpoint, subject, records, credential="tester-secret-token"):
    request = urllib.request.Request(
        f"{endpoint}/series/{subject}",
        data=json.dumps({"records": records}).encode(),
        headers={"Authorization": f"Bearer {credential}", "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as refused:
        return refused.code, json.loads(refused.read())


def _settles(condition, within=5.0) -> bool:
    """Wait for the receiver's housekeeping, which runs **after** the response is flushed so the
    adopter never waits for it. A test that reads the store the instant a POST returns is
    therefore racing the server by design — and did, for one run in eight."""
    deadline = time.monotonic() + within
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.02)
    return False


#: What the receiver answers a path it routes nowhere. Read from the service rather than restated,
#: because a second copy of its wording here would go quiet the day it was reworded.
UNROUTED = "no such endpoint"


def _reach(endpoint, method, path, credential="operator-secret-token"):
    """One request, the way a client makes it — over the socket, at the URL.

    The body is whatever the route will parse least happily, on purpose: this asks *did the request
    arrive and did something decide*, and a route that refuses the content has answered that. What
    it must never return is 404.
    """
    request = urllib.request.Request(
        f"{endpoint}{path}", method=method,
        data=b"{}" if method == "POST" else None,
        headers={"Authorization": f"Bearer {credential}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as refused:
        try:
            return refused.code, json.loads(refused.read() or b"{}")
        except ValueError:
            return refused.code, {}


def _get_series(endpoint, subject, credential="tester-secret-token"):
    request = urllib.request.Request(
        f"{endpoint}/series/{subject}",
        headers={"Authorization": f"Bearer {credential}"} if credential else {})
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as refused:
        return refused.code, json.loads(refused.read())


@pytest.mark.proves("dev07-6-2", depth="wiring")
def test_a_series_is_held_and_handed_back(server):
    """**Custodial, and demonstrated rather than asserted**. A store that cannot hand it
    back is holding nothing for anyone — so the returning half is what makes the word true, and it
    is also what *kept recent by use* measures, which makes retrieval a signal rather than
    a read-only convenience."""
    endpoint, _ = server

    status, held = _post_series(endpoint, "subject-one", [
        {"subject": "S-1", "test": "t::a", "about": None, "result": "passed",
         "grounding": "inert", "when": "2026-08-01T09:00:00Z"},
        {"run": "2026-08-01T09:00:00Z", "observed": 1},
    ])
    assert status == 201 and held["records"] == 2

    status, returned = _get_series(endpoint, "subject-one")

    assert status == 200
    assert [r["seq"] for r in returned["records"]] == [1, 2], "renumbered onto this store's own"
    assert returned["records"][0]["test"] == "t::a", "and held verbatim otherwise"


@pytest.mark.proves("dev07-6-2", depth="wiring")
def test_a_discarded_range_comes_back_as_discarded_and_never_as_a_gap(server):
    """`dev07-6-2`. A series is kept under a bound, so parts of it get dropped — and the two ways a
    reader finds nothing there are *nothing happened* and *we discarded it*. Opposite readings, and
    only one is about the project.

    Fourth arrival of the invariant `dev07-3-3`, `dev07-5-2` and `dev07-4-3-ur10` each reached, and the worst:
    every earlier one is somebody failing to look, and here the absence is one **we caused**.
    """
    endpoint, _ = server
    _post_series(endpoint, "subject-two", [
        {"discarded_from": 1, "discarded_through": 400, "when": "2026-08-02T00:00:00Z",
         "reason": "compacted"},
        {"subject": "S-1", "test": "t::a", "about": None, "result": "passed",
         "grounding": "inert", "when": "2026-08-02T09:00:00Z"},
    ])

    _, returned = _get_series(endpoint, "subject-two")

    assert returned["discarded"] == [{"discarded_from": 1, "discarded_through": 400,
                                      "when": "2026-08-02T00:00:00Z", "reason": "compacted",
                                      "seq": 1}]


@pytest.mark.proves("dev07-6-2", depth="wiring")
def test_never_held_and_emptied_are_different_answers(server):
    """A subject nobody has sent anything for is a 404 that says so. Returning an empty series
    would say *we hold nothing for you*, which is true of both and useful for neither."""
    endpoint, _ = server

    status, refused = _get_series(endpoint, "subject-nobody-sent")

    assert status == 404 and "nothing held" in refused["error"]


@pytest.mark.proves("dev07-6-2", depth="wiring")
def test_an_overgrown_series_is_compacted_and_still_replays(server):
    """Compaction is triggered **by a write** because this service has no scheduler, and adding one
    would be a second operational obligation — the cost we refused when we declined to self-host
    a tracker.

    It runs **after the response**. Measured at 2.7 seconds for a large project's log, so an
    adopter must not wait for our housekeeping; the reply is already flushed before this starts.

    And the compacted span comes back as `discarded` rather than as a gap, which is the whole of
    `dev07-6-2`: a store that returns what survived and calls it what it holds is not custodial.
    """
    endpoint, _ = server
    fact = {"subject": "S-1", "test": "t::a", "about": None, "grounding": "inert",
            "when": "2026-08-01T09:00:00Z"}

    for n in range(8):
        status, _ = _post_series(endpoint, "subject-busy", [
            {**fact, "result": "passed" if n % 2 else "failed"},
            {"run": f"2026-08-0{n + 1}T09:00:00Z", "observed": 1},
        ])
        assert status == 201

    for _ in range(40):                       # the reply is flushed before compaction begins
        _, returned = _get_series(endpoint, "subject-busy")
        if returned["discarded"]:
            break
        time.sleep(0.05)

    assert returned["discarded"], "an overgrown log is compacted"
    note = returned["discarded"][-1]
    assert note["reason"] == "compacted" and note["discarded_from"] == 1
    assert len(returned["records"]) < 16, "and is smaller than what it replaced"
    assert any(r.get("test") == "t::a" for r in returned["records"]), "while still saying what is true"


@pytest.mark.proves("dev07-6-2", depth="wiring")
def test_eviction_drops_the_least_recently_retrieved_and_leaves_a_tombstone(server, monkeypatch):
    """**Any write may evict any subject**, which is the hole this closes.

    Compaction is per-subject and a growing log belongs to somebody writing. Eviction is
    pool-level, and the subjects that should go are precisely the ones **nobody is writing to** —
    so a trigger that only looked at the subject being written would never reach them. A busy
    adopter's writes pay for evicting quiet ones, and nothing waits on a scheduler that does not
    exist. The pool only grows on a write, so a write is the only moment the bound can be crossed.

    And a dropped subject leaves a **tombstone**, not a hole. Deleting it outright would leave a
    reader meeting *never held* — the flattering answer and the wrong one, and the exact failure
    `dev07-6-2` exists to refuse.
    """
    from plumb import series_holder as receiver_module

    endpoint, root = server
    # Large enough to hold the busy subject and not both. A bound smaller than the surviving
    # subject makes "the one being used survived" unsayable — everything has to go, correctly, and
    # the test then fails on the product doing the only available thing.
    monkeypatch.setattr(receiver_module, "POOL_BYTES", 3000)
    fact = {"subject": "S-1", "test": "t::a", "about": None, "grounding": "inert",
            "when": "2026-08-01T09:00:00Z", "result": "passed"}

    # The quiet subject carries the bulk, which is what makes dropping it *reclaim* something.
    _post_series(endpoint, "quiet-one",
                 [{**fact, "test": f"t::quiet-{n}"} for n in range(20)]
                 + [{"run": "2026-08-01T09:00:00Z", "observed": 20}])
    _get_series(endpoint, "quiet-one")                       # retrieved, then left alone
    time.sleep(1.05)                                          # the marker has second resolution
    _post_series(endpoint, "busy-one", [fact, {"run": "2026-08-02T09:00:00Z", "observed": 1}])
    _get_series(endpoint, "busy-one")

    # Watched on disk, never by retrieving it. A GET *is* the signal eviction ranks on, so
    # probing the quiet subject makes it the most recently used one — after a single probe the
    # busy subject becomes the eviction candidate and the claim under test inverts. That is what
    # this loop did, and it passed only in the runs where the first write happened to cross the
    # bound before the first probe.
    # Located rather than assumed: a test that spells out the store's shape fails when the shape
    # is the thing being improved, and says nothing about the claim it was written for. It has
    # changed twice — once when stores were keyed by account, and once back when they stopped being.
    held = next((root / "series").glob("**/quiet-one.jsonl"))
    for _ in range(40):                                       # writes until the pool is crossed
        _post_series(endpoint, "busy-one", [
            {**fact, "test": f"t::{time.time_ns()}"},
            {"run": "2026-08-03T09:00:00Z", "observed": 1}])
        if "discarded_from" in held.read_text():
            break

    status, quiet = _get_series(endpoint, "quiet-one")
    assert status == 200, "evicted is not the same answer as never held"
    assert quiet["discarded"], "the quiet subject went first"
    assert "evicted" in quiet["discarded"][0]["reason"]
    assert _get_series(endpoint, "busy-one")[1]["records"], "and the one being used survived"


def _a_run(*tests, when="2026-08-01T09:00:00Z"):
    from plumb.core.manifest import Citation, Manifest, Story
    return Manifest(stories={"S-1": Story(citations=tuple(
        Citation(test=t, depth="unit", result="passed", grounding="inert", when=when)
        for t in tests))})


def _a_store_with(tmp_path, *runs) -> Path:
    from plumb.core.series import append
    store = tmp_path / "series.jsonl"
    for manifest in runs:
        append(store, manifest)
    return store


def _enrolled_for(tmp_path, endpoint, subject, name="enrolment.json",
                  credential="tester-secret-token") -> Path:
    path = tmp_path / name
    path.write_text(Enrolment("trusted-tester", credential, endpoint, subject).to_json())
    return path


@pytest.mark.proves("dev07-6-2", depth="component")
@pytest.mark.parametrize("server", [{"compact_above": 1 << 30}], indirect=True)
def test_a_push_hands_over_only_what_the_holder_has_not_been_given(tmp_path, server):
    """**The outbox is derived, not kept.** What is owed is the range past the mark, read off the
    log's own sequence (`dev07-4-3-ur06`), so nothing is owed twice and nothing needs a queue that is free
    to drift from the log it describes.

    A run that changed nothing still owes its marker — one line saying *we looked* — because that
    is the fact a log of changes cannot otherwise carry. What it never owes again is the history in
    front of it.
    """
    from plumb.core.series import append
    endpoint, _ = server
    store = _a_store_with(tmp_path, _a_run("t::a", "t::b"))
    enrolment = _enrolled_for(tmp_path, endpoint, "pushed-one")

    first = transmit.push_series(store, enrolment)
    assert first.ok and len(first.sent) == 4, (
        "the origin stamp, two facts, and the marker for the run that saw them — the stamp travels "
        "so the holder's copy can be told from a local one rather than averaged with it (`dev07-6-1`)")

    assert transmit.push_series(store, enrolment).sent == (), "nothing new, nothing owed"

    append(store, _a_run("t::a", "t::b"))
    assert len(transmit.push_series(store, enrolment).sent) == 1, "an unchanged run owes its marker"

    append(store, _a_run("t::a", "t::b", "t::c", when="2026-08-02T09:00:00Z"))
    assert len(transmit.push_series(store, enrolment).sent) == 2, "the new fact and its marker"

    held = _get_series(endpoint, "pushed-one")[1]["records"]
    # SEVEN, and the receiver is told not to compact while this is asked. The claim here is about
    # what the *client* sent — four, then nothing, then one, then two — so the holder's count is
    # only a proxy for it, and only while nothing else is changing that count. Compaction fires at
    # `records > 2 x facts`, which this sequence crosses on its second append, and it runs after the
    # reply is flushed — so the number asserted here was whatever housekeeping had reached
    # by the time the read arrived. It was `6`, which is one compaction in, and it failed in about
    # half of full-suite runs for no reason connected to what the test is about.
    assert len(held) == 7, "and the holder has each record exactly once, never the log resent"
    assert len({r["seq"] for r in held}) == len(held), "no sequence arrived twice"


@pytest.mark.proves("dev07-6-2", depth="wiring")
def test_the_operator_can_push_a_series_and_an_outage_is_not_a_failed_command(tmp_path, server, capsys):
    """Through the entry point, because that is the only place the claim is true of the *system*:
    a direct call proves the function and says nothing about whether anyone can reach it.

    The exit code answers *was the store readable*, never *was the network up* — a receiver outage
    that returned non-zero would fail the build of a project whose board is already complete."""
    endpoint, _ = server
    store = _a_store_with(tmp_path, _a_run("t::a"))
    reachable = _enrolled_for(tmp_path, endpoint, "pushed-by-hand")
    down = _enrolled_for(tmp_path, "http://127.0.0.1:1", "pushed-by-hand", name="down.json")

    assert cli.main(["series", "push", str(store), "--enrolment", str(down)]) == 0
    assert "not pushed" in capsys.readouterr().out, "an outage is reported, never raised"

    assert cli.main(["series", "push", str(store), "--enrolment", str(reachable)]) == 0
    assert "pushed 3 record(s)" in capsys.readouterr().out, "the origin stamp, a fact, a marker"

    assert cli.main(["series", "push", str(tmp_path / "absent.jsonl")]) == 1, \
        "an unreadable store is the one thing that is this command's fault"


@pytest.mark.proves("dev07-6-2", depth="component")
def test_an_unreachable_holder_leaves_the_backlog_and_never_fails_the_run(tmp_path, server):
    """A board is complete without the network, so an outage must defer rather than fail — and
    what it defers must still be there afterwards. The endpoint here is a real closed port: no
    mock can be wrong about what an unreachable host does."""
    endpoint, _ = server
    store = _a_store_with(tmp_path, _a_run("t::a"))

    down = transmit.push_series(
        store, _enrolled_for(tmp_path, "http://127.0.0.1:1", "pushed-two", name="down.json"))

    assert not down.ok and down.sent == (), "an outage is not a delivery"
    assert down.queued and "unreachable" in down.reason

    recovered = transmit.push_series(store, _enrolled_for(tmp_path, endpoint, "pushed-two"))
    assert len(recovered.sent) == 3, (
        "the backlog survived the outage and drained on the next attempt — the origin stamp is part "
        "of it, because a stamp that did not survive an outage would not be proof of anything")


@pytest.mark.proves("dev07-6-2", depth="component")
def test_a_refusal_leaves_the_mark_where_it_was(tmp_path, monkeypatch):
    """`dev07-6-2-ur3`: *stop trying* is not *arrived*. A refused
    batch is the one a human should look at, and a mark that moved past it has lost a range of
    somebody else's history silently — which is exactly the absence `dev07-6-2` exists to prevent."""
    from plumb.core.series import last_seq, sent_mark
    store = _a_store_with(tmp_path, _a_run("t::a"))
    enrolment = _enrolled_for(tmp_path, "https://example.invalid", "pushed-three")
    monkeypatch.setattr(transmit.urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(Refusal(422)))

    outcome = transmit.push_series(store, enrolment)

    assert outcome.sent == () and outcome.refused, "a refusal is not a send"
    assert not sent_mark(store).exists(), "and nothing was marked as handed over"
    assert last_seq(store) == 3, "the log itself is untouched — removal is never a side effect"


@pytest.mark.proves("dev07-6-2", depth="unit")
def test_an_enrolment_naming_no_store_is_answered_rather_than_guessed_at(tmp_path, monkeypatch):
    """An enrolment predating series support has no store to write to. Guessing one would
    put this project's history in a stranger's file, so it says so and sends nothing.

    Run somewhere with no config of its own, because a subject also comes from the `plumb.toml` of
    the project the command is run in — and this passed for years only because no project anywhere
    declared one. The day this repository configured its own series, the test started finding it and
    pushing to a real endpoint. A test that depends on ambient state is testing the ambience.
    """
    monkeypatch.chdir(tmp_path)
    store = _a_store_with(tmp_path, _a_run("t::a"))
    path = tmp_path / "old-enrolment.json"
    path.write_text(Enrolment("trusted-tester", "tok", "https://example.invalid").to_json())

    outcome = transmit.push_series(store, path)

    assert outcome.sent == () and "no subject" in outcome.reason


# ── a backlog too large for one request is split, never dropped (dev07-6-2) ──────

@pytest.mark.proves("dev07-6-2", depth="wiring")
def test_a_backlog_larger_than_one_request_still_arrives_whole(tmp_path, server, monkeypatch, capsys):
    """The case that shipped broken: over the receiver's limit, the whole hand-over came back
    413 — terminal by `dev07-6-2-ur3`, correctly — and the producer dropped the range for good. Green
    board, successful run, and a fortnight simply not there.

    The budget is squeezed rather than the data inflated, because what is under test is the
    splitting and not this machine's patience.
    """
    from plumb.core.series import append
    endpoint, _ = server
    monkeypatch.setattr(transmit, "CHUNK_BYTES", 600)  # a few records per request
    store = _a_store_with(tmp_path, _a_run(*[f"t::{n}" for n in range(40)]))
    enrolment = _enrolled_for(tmp_path, endpoint, "pushed-in-batches")
    pushed = ["series", "push", str(store), "--enrolment", str(enrolment)]

    real, requests = transmit._deliver_batch, []
    monkeypatch.setattr(transmit, "_deliver_batch",
                        lambda url, batch, enrol: (requests.append(len(batch)), real(url, batch, enrol))[1])
    assert cli.main(pushed) == 0

    assert len(requests) > 1, (
        "this passes without splitting anything unless the split is asserted — the budget was once "
        "bound as a default argument, so setting it did nothing and one request carried all 41")
    assert "pushed 42 record(s)" in capsys.readouterr().out, \
        "the origin stamp, 40 facts and the run marker, none lost"
    held = _get_series(endpoint, "pushed-in-batches")[1]["records"]
    assert [r["seq"] for r in held] == list(range(1, 43)), "in one unbroken order at the holder"

    cli.main(pushed)
    assert "nothing to push" in capsys.readouterr().out, "and nothing is owed twice"

    append(store, _a_run(*[f"t::{n}" for n in range(40)]))
    cli.main(pushed)
    assert "pushed 1 record(s)" in capsys.readouterr().out, "the next run owes its marker only"


@pytest.mark.proves("dev07-6-2", depth="component")
def test_an_outage_partway_through_keeps_the_batches_that_landed(tmp_path, server, monkeypatch):
    """A high-water sequence can already say *some of it arrived*, which is the whole reason
    batching costs no new concept — so a hand-over cut in half must leave the tail owed and not
    the whole run's history."""
    from plumb.core.series import sent_mark
    endpoint, _ = server
    monkeypatch.setattr(transmit, "CHUNK_BYTES", 600)
    store = _a_store_with(tmp_path, _a_run(*[f"t::{n}" for n in range(40)]))
    enrolment = _enrolled_for(tmp_path, endpoint, "cut-off-partway")

    real, attempts = transmit._deliver_batch, {"n": 0}

    def fails_after_two(url, batch, enrol):
        attempts["n"] += 1
        if attempts["n"] > 2:
            return transmit.RETRY, "receiver unreachable: pretend outage"
        return real(url, batch, enrol)

    monkeypatch.setattr(transmit, "_deliver_batch", fails_after_two)
    cut = transmit.push_series(store, enrolment)

    assert cut.sent and cut.queued, "part arrived and the rest is owed — both are true"
    landed = len(cut.sent)
    assert int(sent_mark(store).read_text()) == int(cut.sent[-1]), "the mark sits on what landed"

    monkeypatch.setattr(transmit, "_deliver_batch", real)
    resumed = transmit.push_series(store, enrolment)

    assert landed + len(resumed.sent) == 42, "the tail, and only the tail"
    assert [r["seq"] for r in _get_series(endpoint, "cut-off-partway")[1]["records"]] == list(range(1, 43))


@pytest.mark.proves("dev07-6-2", depth="unit")
def test_one_record_over_budget_is_handed_over_alone_rather_than_dropped(tmp_path):
    """Splitting cannot help a single record that is itself too big, so it is not silently joined
    to a batch and not refused here — it goes on its own and the receiver answers for it. A
    client-side refusal would be a guess about a limit this end does not own."""
    from plumb.core.series import read
    records = read(_a_store_with(tmp_path, _a_run("t::a", "t::" + "x" * 4000, "t::b")))
    oversized = max(records, key=lambda r: len(json.dumps(r.__dict__)))

    batches = transmit._batches(records, budget=500)

    assert all(batches), "never an empty request"
    assert [oversized] in batches, "the one that cannot be split travels alone"
    flattened = [entry for batch in batches for entry in batch]
    assert flattened == records, "and nothing is reordered, dropped or duplicated"


@pytest.mark.proves("dev07-6-2", depth="standards-integration")
def test_the_producer_batches_under_what_the_receiver_says_it_accepts(server):
    """The two ends are versioned separately and will drift (`dev07-3-2`), and this drift is expensive:
    over the cap, a batch is refused as terminal. So the receiver publishes its limit and this
    holds the one relation that matters — the producer's batch is *smaller*, never equal."""
    endpoint, _ = server
    published = json.loads(urllib.request.urlopen(f"{endpoint}/spec", timeout=5).read())

    cap = published["series"]["max_body_bytes"]
    assert transmit.CHUNK_BYTES < cap, (
        f"a producer batching {transmit.CHUNK_BYTES} B against a {cap} B cap has no headroom for "
        "the receiver ever tightening it")


@pytest.mark.proves("dev07-6-2", depth="wiring")
def test_a_tombstone_is_not_evicted_again_and_does_not_cost_a_live_subject(server, monkeypatch):
    """Evicting an already-tombstoned subject rewrites one short line with another and frees
    nothing — and because it frees nothing, the pass carried straight on into a subject that still
    held data. Observed: a live series dropped in the pass after a quiet one was already gone.

    The tombstone's own bytes stay counted, which is the honest reading: `dev07-6-2` requires the
    record be kept, so that is footprint we chose to carry, not space to pretend we can reclaim.

    Driven directly rather than by writing until a bound is crossed: what is under test is *which
    subject a pass picks*, and reaching that state through the front door made the assertion depend
    on margins between record sizes and the bound — a test that failed about one run in eight for
    reasons that had nothing to do with the claim.
    """
    from plumb import series_holder as receiver_module
    from plumb.core.series import Discarded

    endpoint, root = server
    series = root / "series"

    # Both retrieved, the tombstone longest ago — so it is exactly what an unguarded pass reaches
    # for first, and freeing nothing, walks on from.
    _post_series(endpoint, "spent", [{"run": "2026-08-01T09:00:00Z", "observed": 1}])
    _get_series(endpoint, "spent")
    time.sleep(1.05)
    _post_series(endpoint, "live", [
        {"subject": "S-1", "test": "t::a", "about": None, "grounding": "inert",
         "when": "2026-08-01T09:00:00Z", "result": "passed"},
        {"run": "2026-08-02T09:00:00Z", "observed": 1}])
    _get_series(endpoint, "live")

    # Located rather than spelled: the claim under test is which log a pass *picks*, and
    # hard-coding the layout makes it fail whenever the layout is what improved. It has now
    # changed twice.
    tombstone = next(series.glob("**/spent.jsonl"))
    living = next(series.glob("**/live.jsonl"))
    tombstone.write_text(json.dumps(Discarded(
        seq=1, discarded_from=1, discarded_through=99, when="2026-08-01T10:00:00Z",
        reason="evicted — the pool is at its bound").__dict__, separators=(",", ":")) + "\n")
    inscription = tombstone.read_text()

    # Asked of the holder rather than of the file, which is the same reason the two logs above are
    # located rather than spelled: *is this nothing but its own tombstone* is a question about a
    # history, and the receiver stopped answering it in `stat` when a second backend became
    # possible (`dev07-6-2`).
    from plumb.holder import FileHolder

    holder = FileHolder(series.parent)
    assert holder.is_tombstone(tombstone.stem), \
        "a log holding only its own tombstone"
    assert not holder.is_tombstone(living.stem), \
        "one still holding history"

    # Over the bound by any margin, so a pass must run and must choose.
    monkeypatch.setattr(receiver_module, "POOL_BYTES", 10)
    _post_series(endpoint, "live", [{"run": "2026-08-03T09:00:00Z", "observed": 1}])

    assert _settles(lambda: "discarded_from" in living.read_text()), (
        "the pass reached the subject that had bytes to reclaim, rather than spending itself "
        "rewriting one short line with another")
    assert tombstone.read_text() == inscription, "the tombstone still says what it said"


# ── reading a history back, locally and from its holder (dev07-6-3) ──────────────

@pytest.mark.proves("dev07-6-3", depth="wiring")
def test_the_operator_can_read_a_history_back(tmp_path, capsys):
    """Through the entry point, because the claim is that *somebody can ask* — a derivation nobody
    can reach answers nothing. For three stories this chapter accumulated a history, transmitted it
    and held it under a bound while offering no way to read a word of it."""
    from plumb.core.series import append
    store = _a_store_with(tmp_path, _a_run("t::a", "t::b"))
    append(store, _a_run("t::a", when="2026-08-02T09:00:00Z"))   # t::b disappears

    assert cli.main(["series", "show", str(store)]) == 0
    summary = capsys.readouterr().out
    assert "last changed" in summary and "last looked" in summary, \
        "the two questions a manifest cannot answer are the columns"
    assert "S-1" in summary

    assert cli.main(["series", "show", str(store), "--subject", "S-1"]) == 0
    transitions = capsys.readouterr().out.splitlines()
    assert [line.split()[0] for line in transitions][:2] == ["2026-08-01T09:00:00Z"] * 2, \
        "one subject reads back as its transitions, oldest first"
    assert transitions[-1].strip().endswith("t::b") and "gone" in transitions[-1], (
        "a fact that disappeared is a transition like any other — and carries no measurement "
        "time, because nothing measured it going away (`dev07-3-1`)")

    assert cli.main(["series", "show", str(tmp_path / "absent.jsonl")]) == 1, \
        "a store that is not there is this command's fault and says so"


@pytest.mark.proves("dev07-6-3", depth="wiring")
def test_a_discarded_range_is_the_first_thing_a_reader_is_told(tmp_path, capsys):
    """Not a footnote. A reader who scrolls past it reads the rest as the whole history, which is
    the one thing `dev07-6-2` exists to prevent — and here we are the ones who caused the absence."""
    from plumb.core.series import append, compact
    store = _a_store_with(tmp_path, _a_run("t::a"))
    append(store, _a_run("t::a", "t::b", when="2026-08-02T09:00:00Z"))
    compact(store, through=2, reason="compacted — bounded history")

    cli.main(["series", "show", str(store)])
    shown = capsys.readouterr().out

    assert shown.splitlines()[0].startswith("discarded "), "before anything it could be mistaken for"
    assert "bounded history" in shown, "and says why, because the reason is the reader's business"


@pytest.mark.proves("dev07-6-3", depth="wiring")
def test_a_history_can_be_fetched_from_the_holder_that_keeps_it(tmp_path, server, capsys):
    """**Custodial made real.** A store that cannot hand it back is holding nothing for anyone
   , and until this existed the only way to see it was a hand-written `curl` with a bearer
    token. Retrieval is also what eviction is ranked on, so reading your history is what keeps
    it — which makes this the command that gives *kept recent by use* something to measure."""
    endpoint, _ = server
    pushed = _a_store_with(tmp_path, _a_run("t::a", "t::b"))
    enrolment = _enrolled_for(tmp_path, endpoint, "held-for-me")
    transmit.push_series(pushed, enrolment)

    fetched = tmp_path / "pulled.jsonl"
    code = cli.main(["series", "pull", str(fetched), "--enrolment", str(enrolment)])

    assert code == 0, capsys.readouterr().err
    assert "pulled 4 record(s)" in capsys.readouterr().out, \
        "including the origin, so a pulled copy is not a history of unknown extent"
    assert fetched.read_text().splitlines(), "and it landed as a series, readable by `series show`"

    assert cli.main(["series", "show", str(fetched)]) == 0
    assert "S-1" in capsys.readouterr().out, "what came back replays like the history it is"


@pytest.mark.proves("dev07-6-3", depth="wiring")
def test_pulling_what_the_holder_does_not_have_says_so(tmp_path, server, capsys):
    """*Never held* and *we dropped it* are different answers and neither is a crash — the reader
    gets the holder's own word for it rather than an empty file that reads as silence."""
    endpoint, _ = server
    enrolment = _enrolled_for(tmp_path, endpoint, "nobody-sent-this")

    code = cli.main(["series", "pull", str(tmp_path / "out.jsonl"), "--enrolment", str(enrolment)])

    assert code == 1
    assert "nothing for nobody-sent-this" in capsys.readouterr().err
    assert not (tmp_path / "out.jsonl").exists(), "and no empty file is left behind to be believed"


@pytest.fixture
def operator_server(tmp_path):
    """A receiver holding a corpus, with both an operator's credential and a tester's.

    Two credentials rather than one, because the claim is about *which* may read the store back
    and a fixture with only the answer's own credential cannot fail.
    """
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"contributors": [
        {"credential": "operator-secret-token", "label": "the operator", "relationship": "self"},
        {"credential": "tester-secret-token", "label": "a tester", "relationship": "trusted-tester"},
    ]}))
    received = tmp_path / "received"
    received.mkdir()
    for n, project in ((1, "alpha"), (2, "beta")):
        (received / f"held-record-{n}.json").write_text(json.dumps({
            "id": f"held-record-{n}", "observed_at": "2026-08-03T00:00:00+00:00",
            "source": "trusted-tester", "observation": RUB, "implication": MEANS,
            "project": project, "version": 1}))
    (received / "torn-record.json").write_text("{not json")
    httpd = build(received, host="127.0.0.1", port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", received
    httpd.shutdown()


def test_every_endpoint_the_receiver_publishes_answers_at_its_url(operator_server):
    """Made mechanical: the receiver **publishes** what a client may reach, so every one
    of those routes is proven the way a client reaches it — over a socket, at the URL.

    A correct handler behind a route that does not reach it is *dark*, and invisible from either
    side: every unit test passes and the capability does not exist for anyone outside the host.
    That was measured — the handler implemented it, had been correct throughout, and
    the served route answered 404 without the request ever entering the process.

    Asserted against `/spec` rather than a list written here, because a list of routes beside the
    routes is the second home this project files most: it would agree on the day it was written and
    go quiet about the next endpoint added.
    """
    endpoint, _ = operator_server
    published = _reach(endpoint, "GET", "/spec")[1]["endpoints"]
    assert len(published) >= 4, "the document a client builds against is not nearly empty"

    dark = []
    for named in published:
        method, _, path = named.partition(" ")
        # A subject is the client's to choose (`dev07-6-2-ur7`), so the published form carries a
        # placeholder — reaching the route means substituting something, not sending a brace.
        reachable = path.replace("{subject}", "a-subject").replace("{id}", "some-id")
        status, said = _reach(endpoint, method, reachable)
        # **The receiver's own words for it, not a status code.** 404 is overloaded — it is also
        # how a route that works reports a resource that does not exist, and both `/support/{id}`
        # and `/series/{subject}` answer it on a fresh store. What only an unrouted path says is
        # *no such endpoint*, which is the receiver telling us the request arrived and matched
        # nothing. Every other answer proves routing: 401 is authentication working and 422 is
        # validation working, and re-asserting those is the other tests' job.
        if said.get("error") == UNROUTED:
            dark.append(f"{named} -> {method} {reachable} answered {status} {UNROUTED!r}")

    assert not dark, (
        "the receiver publishes these and nothing routes to them, so they are dark to every "
        "client that reads the document: " + "; ".join(dark))


def _get_json(url, credential):
    import urllib.request

    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {credential}"})
    with urllib.request.urlopen(request, timeout=5) as answered:
        return json.loads(answered.read())


def _file_one(endpoint, credential, record_id, project="gamma"):
    """File a record over the wire, so the receiver stamps whose it is.

    Written through the endpoint rather than into the store, because `filed_by` is the receiver's
    to fill and a fixture that wrote it directly would be asserting against its own guess.
    """
    import urllib.request

    body = json.dumps({
        # A valid `source` even though the receiver overwrites it: the record is validated before
        # it is stamped, so the enumeration still has to be satisfied by whoever sends one.
        "id": record_id, "observed_at": "2026-08-04T00:00:00+00:00", "source": "trusted-tester",
        "observation": RUB, "implication": MEANS, "project": project,
    }).encode()
    request = urllib.request.Request(
        f"{endpoint}/support", method="POST", data=body,
        headers={"Authorization": f"Bearer {credential}", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=5) as answered:
        return json.loads(answered.read())


def _delete(endpoint, record_id, credential):
    import urllib.error
    import urllib.request

    request = urllib.request.Request(
        f"{endpoint}/support/{record_id}", method="DELETE",
        headers={"Authorization": f"Bearer {credential}"})
    try:
        with urllib.request.urlopen(request, timeout=5) as answered:
            return answered.status, json.loads(answered.read())
    except urllib.error.HTTPError as refused:
        return refused.code, json.loads(refused.read() or b"{}")


