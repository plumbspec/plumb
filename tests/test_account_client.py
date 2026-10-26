"""The account is an address (D50): a person opens one by mail and redeems the link for a
credential, and the install holds no key of its own."""

import importlib.util
import json

import pytest


class _Answer:
    def __init__(self, said):
        self._said = json.dumps(said).encode()

    def read(self):
        return self._said

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_opening_an_account_hands_over_an_address_and_nothing_else(monkeypatch, capsys):
    """No root to make first and nothing signed: the body is the address, and the service mails
    the link that proves it."""
    from plumb import cli

    sent = []

    def answer(request, timeout=None):
        sent.append(request)
        return _Answer({"state": "pending", "expires_at": "soon"})

    monkeypatch.setattr("urllib.request.urlopen", answer)

    assert cli.main(["account", "open", "--email", "someone@example.org",
                     "--endpoint", "https://support.example.invalid/"]) == 0

    [request] = sent
    assert request.full_url == "https://support.example.invalid/account"
    assert json.loads(request.data) == {"email": "someone@example.org"}
    headers = {name.lower() for name in request.headers}
    assert not {"plumb-signature", "plumb-key", "plumb-timestamp"} & headers, (
        "an address is the whole of what opening an account presents")
    assert "redeem" in capsys.readouterr().out


def test_opening_an_account_names_where_when_nothing_says(monkeypatch, capsys):
    """With no `--endpoint` and no `PLUMB_ENDPOINT`, there is nowhere to send the address; the
    refusal says which two things would have answered."""
    from plumb import cli

    monkeypatch.delenv("PLUMB_ENDPOINT", raising=False)
    assert cli.main(["account", "open", "--email", "someone@example.org"]) == 1
    said = capsys.readouterr().err
    assert "--endpoint" in said and "PLUMB_ENDPOINT" in said


def test_the_install_holds_no_identity():
    """The key, its derivations and the commands that made and exported it left together."""
    from plumb import cli

    assert importlib.util.find_spec("plumb.identity") is None
    assert importlib.util.find_spec("plumb.account_client") is None
    for gone in ("create", "export", "show"):
        with pytest.raises(SystemExit):
            cli.build_parser().parse_args(["account", gone])


@pytest.mark.proves("dev07-6-2", depth="component")
def test_what_would_be_sent_carries_the_adopters_names_as_written(tmp_path):
    """A preview built by the push's own path shows the records exactly; nothing replaces a name."""
    from plumb import transmit

    store = tmp_path / "history.jsonl"
    store.write_text(json.dumps({"seq": 1, "subject": "acme-api", "test": "tests/t.py::t",
                                 "about": "the refund", "result": "passed",
                                 "grounding": "grounded", "when": None}) + "\n")

    records, _ = transmit.wire_form(store)
    [record] = records
    assert record["test"] == "tests/t.py::t" and record["about"] == "the refund"


def test_a_service_that_cannot_be_reached_is_named_not_thrown(monkeypatch, capsys):
    """An address nobody answers at is a sentence and an exit code, never a traceback."""
    import urllib.error

    from plumb import cli

    def unreachable(request, timeout=None):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", unreachable)
    code = cli.main(["account", "open", "--email", "someone@example.org",
                     "--endpoint", "https://support.example.invalid/"])
    said = capsys.readouterr().err
    assert code == 2 and "unreachable" in said and "support.example.invalid" in said, said
