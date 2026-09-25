"""Where one capability's output goes (`snd`).

**Asserted as a difference.** Each test configures a destination and then changes exactly one
thing, because a resolver that answers the same whatever it is given passes a suite as readily as
one that reads its inputs.

The case the whole chapter exists for is `test_two_capabilities_reach_two_different_hosts`: one
credential and one base URL for everything made self-hosting a holder and being answered by a
support service the same choice (`snd-D1`).
"""

from __future__ import annotations

import os

import pytest

from plumb.transport import Destination, for_capability


def _env(monkeypatch, **pairs):
    for name in ("PLUMB_ENDPOINT", "PLUMB_CREDENTIAL", "PLUMB_ENROLMENT",
                 "PLUMB_SERIES_ENDPOINT", "PLUMB_SERIES_CREDENTIAL",
                 "PLUMB_SUPPORT_ENDPOINT", "PLUMB_SUPPORT_CREDENTIAL"):
        monkeypatch.delenv(name, raising=False)
    for name, value in pairs.items():
        monkeypatch.setenv(name, value)


@pytest.mark.proves("snd1", depth="unit")
def test_two_capabilities_reach_two_different_hosts(monkeypatch, tmp_path):
    """`snd-D1` — a destination belongs to a capability, not to the machine.

    With one endpoint for everything, self-hosting a holder and being answered by a support
    service were the same decision. They are two now, and a runner can express both.
    """
    _env(monkeypatch,
         PLUMB_SERIES_ENDPOINT="https://holder.ourteam.internal",
         PLUMB_SERIES_CREDENTIAL="held-by-us",
         PLUMB_SUPPORT_ENDPOINT="https://support.example.com",
         PLUMB_SUPPORT_CREDENTIAL="answered-by-them",
         PLUMB_ENROLMENT=str(tmp_path / "absent.json"))

    series = for_capability("series")
    support = for_capability("support")
    assert series.url == "https://holder.ourteam.internal" and series.credential == "held-by-us"
    assert support.url == "https://support.example.com"
    assert series.url != support.url


@pytest.mark.proves("snd2", depth="unit")
def test_no_destination_is_the_ordinary_state_and_never_an_error(monkeypatch, tmp_path):
    """`snd2-sr1`. Absence is what makes *nothing leaves without being told where* a guarantee."""
    _env(monkeypatch, PLUMB_ENROLMENT=str(tmp_path / "absent.json"))
    assert for_capability("series") is None
    assert for_capability("support") is None


@pytest.mark.proves("snd1", depth="unit")
def test_the_machine_wide_pair_still_serves_every_capability(monkeypatch, tmp_path):
    """One address for everything stays workable — it stops being the only thing expressible."""
    _env(monkeypatch, PLUMB_ENDPOINT="https://one.example.com", PLUMB_CREDENTIAL="shared",
         PLUMB_ENROLMENT=str(tmp_path / "absent.json"))
    assert for_capability("series").url == "https://one.example.com"
    assert for_capability("support").url == "https://one.example.com"


@pytest.mark.proves("snd1", depth="unit")
def test_a_capabilitys_own_pair_is_preferred_over_the_machines(monkeypatch, tmp_path):
    _env(monkeypatch, PLUMB_ENDPOINT="https://one.example.com", PLUMB_CREDENTIAL="shared",
         PLUMB_SERIES_ENDPOINT="https://holder.ourteam.internal",
         PLUMB_SERIES_CREDENTIAL="held-by-us",
         PLUMB_ENROLMENT=str(tmp_path / "absent.json"))
    assert for_capability("series").url == "https://holder.ourteam.internal"
    assert for_capability("support").url == "https://one.example.com", "the rest keep the machine's"


@pytest.mark.proves("snd1", depth="unit")
def test_an_enrolment_file_still_names_a_destination_for_everything(monkeypatch, tmp_path):
    """`ch6-6` was expressed as a file, and a file that already exists keeps working.

    The enrolment is one relationship with one service, which is the shape this replaces — so it
    answers for every capability that has nothing more specific, and never overrides one that has.
    """
    written = tmp_path / "enrolment.json"
    written.write_text('{"relationship": "self", "credential": "from-a-file",'
                       ' "endpoint": "https://filed.example.com", "subject": "ours"}')
    _env(monkeypatch, PLUMB_ENROLMENT=str(written))

    assert for_capability("series").url == "https://filed.example.com"
    assert for_capability("series").subject == "ours"

    monkeypatch.setenv("PLUMB_SERIES_ENDPOINT", "https://holder.ourteam.internal")
    monkeypatch.setenv("PLUMB_SERIES_CREDENTIAL", "held-by-us")
    assert for_capability("series").url == "https://holder.ourteam.internal", "the specific wins"
    assert for_capability("support").url == "https://filed.example.com", "and the rest are unmoved"


@pytest.mark.proves("snd1", depth="unit")
def test_a_destination_says_nothing_about_a_relationship():
    """`snd1-sr2` — who the sender is to a service is the service's to decide.

    The client's claim was advisory anyway: the enrolment it came from says the service overwrites
    it from the credential it authenticated. A field nobody downstream trusts is one the core has
    no business carrying.
    """
    assert not hasattr(Destination("series", "https://x.example.com", "c"), "relationship")


def test_a_destination_must_be_reachable_and_carry_something_to_send_with():
    for bad, why in ((("series", "holder.example.com", "c"), "no scheme"),
                     (("series", "https://x.example.com", "  "), "no credential"),
                     (("", "https://x.example.com", "c"), "no capability")):
        with pytest.raises(ValueError):
            Destination(*bad), why


@pytest.mark.proves("snd1", depth="unit")
def test_a_capability_name_becomes_the_variable_a_runner_sets(monkeypatch, tmp_path):
    """`snd1-ur3` — every field readable from the environment, because a runner can set one."""
    from plumb.transport import variables

    assert variables("series") == ("PLUMB_SERIES_ENDPOINT", "PLUMB_SERIES_CREDENTIAL",
                                  "PLUMB_SERIES_SUBJECT")
    assert variables("run-history")[0] == "PLUMB_RUN_HISTORY_ENDPOINT", "a dash is not a variable"


@pytest.mark.proves("snd1", depth="wiring")
def test_a_series_is_pushed_to_the_address_its_own_capability_names(monkeypatch, tmp_path, capsys):
    """`snd1-ur1`, `snd1-ur3`, through `plumb series push`.

    Every citation here used to call `for_capability` directly. That proves the resolver and says
    nothing about the command an adopter runs — and the story is that *hosting my own history costs
    me nothing about who answers my questions*, which is a claim about where a push lands.

    The machine-wide pair is set to somewhere else on purpose: the specific winning over the
    general is the whole of `snd1`, and a test with only one address named cannot tell the two
    apart.
    """
    from plumb import cli, transmit
    from plumb.core.manifest import Citation, Manifest, Story
    from plumb.core.series import append

    for name in [k for k in os.environ if k.startswith("PLUMB_") or k.startswith("XDG_")]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "nothing-configured"))
    monkeypatch.setenv("PLUMB_ENDPOINT", "https://whoever-answers-support.example")
    monkeypatch.setenv("PLUMB_CREDENTIAL", "the-machine-wide-one")
    monkeypatch.setenv("PLUMB_SERIES_ENDPOINT", "https://holder.ourteam.internal")
    monkeypatch.setenv("PLUMB_SERIES_CREDENTIAL", "held-by-us")
    monkeypatch.setenv("PLUMB_SERIES_SUBJECT", "ours")

    store = tmp_path / "history.jsonl"
    append(store, Manifest(stories={"S-1": Story(citations=(
        Citation(test="t::a", depth="unit", result="passed", grounding="inert",
                 when="2026-08-01T09:00:00Z"),))}))

    reached = {}

    class Accepted:
        status = 200

        def read(self):
            return b'{"accepted": 1}'

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def urlopen(request, *a, **k):
        reached.setdefault("urls", []).append(request.full_url)
        reached["auth"] = request.headers.get("Authorization")
        return Accepted()

    monkeypatch.setattr(transmit.urllib.request, "urlopen", urlopen)

    assert cli.main(["series", "push", str(store)]) == 0, capsys.readouterr().err

    assert reached.get("urls"), f"nothing was sent: {capsys.readouterr().out}"
    assert all(url.startswith("https://holder.ourteam.internal") for url in reached["urls"]), (
        f"the history went somewhere the series capability did not name: {reached['urls']}")
    assert reached["auth"] == "Bearer held-by-us", (
        "it went with the machine-wide credential rather than this capability's")
