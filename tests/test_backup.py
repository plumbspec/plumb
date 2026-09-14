"""Taking away what the tool wrote for one project, and putting it back (`ado4`).

The exclusions are what these exercise, because the exclusions are the claim. An archive's contents
are the easy half and the easy half is not where the loss happens: what costs somebody is a secret
that travelled, an identity that got rebound, or an irreplaceable file that was quietly judged to be
somebody else's problem.
"""

import json
import subprocess
import tarfile
from pathlib import Path

import pytest

from plumb import backup, cli
from plumb.config import Config


def _git(where, *args):
    subprocess.run(["git", "-C", str(where), *args], check=True, capture_output=True)


def _project(tmp_path, monkeypatch, *, tracked=("plumb.toml",), subject="demo"):
    """A project with a declaration git carries and a history git does not.

    That split is the point: the series is the irreplaceable artifact *and* is the one most often
    ignored by version control, so a backup deciding by location would drop it.
    """
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.delenv("PLUMB_ACCOUNT", raising=False)
    monkeypatch.delenv("PLUMB_FRICTION_DIR", raising=False)

    # The env vars above cannot reach the friction store, and the isolation was fictional until
    # this line. `cli.DEFAULT_STORE` is a module-level constant evaluated at *import*, so it is
    # already bound to the developer's real `~/.local/share/plumb/friction` by the time any of this
    # runs. `backup.plan` reads it, so these tests inspected the real store; one of them wrote two
    # records into it with `queue=True`, which staged fake data for transmission to the live
    # receiver on every run of the suite. They were withdrawn by hand and came back with the next
    # run, which is how it was finally noticed.
    #
    # Patched as an attribute rather than by env var because that is what the deferred
    # `from plumb.cli import DEFAULT_STORE` inside `backup.py` actually reads at call time.
    monkeypatch.setattr(cli, "DEFAULT_STORE", tmp_path / "data" / "plumb" / "friction")

    root = tmp_path / "proj"
    root.mkdir()
    (root / "plumb.toml").write_text(
        f'subject = "{subject}"\nseries = "history.jsonl"\n')
    (root / "history.jsonl").write_text('{"seq": 1}\n')
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "user.name", "t")
    for name in tracked:
        _git(root, "add", name)
    _git(root, "commit", "-qm", "in")
    return root


def _credentials(tmp_path, secret="SECRET-VALUE"):
    where = tmp_path / "cfg" / "plumb"
    where.mkdir(parents=True, exist_ok=True)
    (where / "account.json").write_text(
        json.dumps({"endpoint": "https://r.invalid", "public": "ab12", "counter": 3}))
    (where / "enrolment.json").write_text(
        json.dumps({"endpoint": "https://r.invalid", "credential": secret}))
    return where


# -- what it refuses to take (`ado4`) ----------------------------------------------------------

@pytest.mark.proves("ado4", depth="component")
def test_what_version_control_already_carries_is_left_and_what_it_does_not_is_taken(tmp_path,
                                                                                   monkeypatch):
    """*Carried* means tracked, not located in the tree — a series sits inside the project and is
    commonly ignored, so deciding by location would drop the one irreplaceable file."""
    root = _project(tmp_path, monkeypatch)
    made = backup.plan(Config.find(root), root)

    taken = {held.where for held in made.taken}
    assert "history.jsonl" in taken, "untracked and irreplaceable"
    assert "plumb.toml" not in taken, "tracked, so git holds it better than an archive would"
    assert any("version control already carries it" in left.why for left in made.left)


@pytest.mark.proves("ado4", depth="component")
def test_an_unversioned_project_has_everything_taken(tmp_path, monkeypatch):
    """A project with no version control tracks nothing, and its declaration then exists in exactly
    one place — which is an answer rather than a fallback."""
    root = _project(tmp_path, monkeypatch)
    for leftover in (root / ".git",):
        subprocess.run(["rm", "-rf", str(leftover)], check=True)

    taken = {held.where for held in backup.plan(Config.find(root), root).taken}
    assert {"plumb.toml", "history.jsonl"} <= taken


@pytest.mark.proves("ado4", depth="component")
def test_a_credential_and_a_shared_identity_are_left_by_default(tmp_path, monkeypatch):
    """An archive is the artifact that gets attached to a ticket, and an account is shared with
    every project pushing to one receiver."""
    root = _project(tmp_path, monkeypatch)
    _credentials(tmp_path)

    made = backup.plan(Config.find(root), root)
    left = " ".join(entry.why for entry in made.left)
    assert "enrolment.json" in " ".join(entry.where for entry in made.left)
    assert "carries a credential" in left
    assert "rebind an identity" in left
    assert all("enrolment" not in held.where for held in made.taken), "and neither was taken"
    assert not made.secret


@pytest.mark.proves("ado4", depth="component")
def test_a_record_belonging_to_another_project_is_left_and_counted(tmp_path, monkeypatch):
    """One store holds every project's friction, and this archive is one project's."""
    from plumb.support import SupportRecord
    from plumb.store import SupportStore

    root = _project(tmp_path, monkeypatch, subject="demo")
    store = SupportStore(cli.DEFAULT_STORE)
    for project in ("demo", "somebody-else"):
        store.file(SupportRecord(id=f"r-{project}", observed_at="2026-08-05T00:00:00Z",
                                  source="self", observation=f"o for {project}",
                                  implication="i", project=project), queue=True)

    made = backup.plan(Config.find(root), root)
    assert [held.id for held in made.records] == ["r-demo"]
    assert any("belonging to another project" in entry.why for entry in made.left)


# -- what it says it left (`ado4`) -------------------------------------------------------------

@pytest.mark.proves("ado4", depth="component")
def test_the_archive_carries_the_record_of_what_it_refused(tmp_path, monkeypatch):
    """An archive that silently omitted a credential and one with nothing to omit are otherwise the
    same bytes, and whoever finds out is whoever is restoring after a disk failure."""
    root = _project(tmp_path, monkeypatch)
    _credentials(tmp_path)
    where = tmp_path / "out.tgz"

    backup.write(where, Config.find(root), root)
    with tarfile.open(where) as bundle:
        inside = json.loads(bundle.extractfile(backup.MANIFEST_NAME).read().decode())

    assert inside["backup_version"] == backup.BACKUP_VERSION
    assert not inside["carries_credentials"]
    needed = [entry for entry in inside["left"] if entry["needed"]]
    assert needed, "and it names what a restore will have to be given by hand"
    assert any("enrolment.json" in entry["where"] for entry in needed)


@pytest.mark.proves("ado4", depth="component")
def test_an_archive_from_a_version_this_one_cannot_read_is_refused_whole(tmp_path, monkeypatch):
    """Refused rather than half-restored: a partial restore is the state nobody can reason about."""
    root = _project(tmp_path, monkeypatch)
    where = tmp_path / "out.tgz"
    backup.write(where, Config.find(root), root)

    rewritten = tmp_path / "future.tgz"
    with tarfile.open(where) as old, tarfile.open(rewritten, "w:gz") as new:
        for member in old.getmembers():
            if member.name == backup.MANIFEST_NAME:
                continue
            new.addfile(member, old.extractfile(member))
        ahead = tmp_path / backup.MANIFEST_NAME
        ahead.write_text(json.dumps({"backup_version": backup.BACKUP_VERSION + 1}))
        new.add(ahead, arcname=backup.MANIFEST_NAME)

    with pytest.raises(backup.Unreadable) as refused:
        backup.read_manifest(rewritten)
    assert str(backup.BACKUP_VERSION) in str(refused.value), "it names which version it reads"


# -- asking for the credentials anyway (`ado4`) ------------------------------------------------

@pytest.mark.proves("ado4", depth="component")
def test_asking_for_the_credentials_takes_them_and_makes_the_archive_a_secret(tmp_path,
                                                                             monkeypatch):
    """What is refused is the silence, not the inclusion: moving a machine is a real thing to want,
    and a tool that forbade it would be routed around with `tar` — same archive, none of the care."""
    root = _project(tmp_path, monkeypatch)
    _credentials(tmp_path)
    where = tmp_path / "secret.tgz"

    record = backup.write(where, Config.find(root), root, credentials=True)

    assert record["carries_credentials"] is True, "the archive says so in itself"
    assert where.stat().st_mode & 0o777 == backup.SECRET_FILE_MODE, "and is narrow from creation"
    assert any("enrolment.json" in held["where"] for held in record["taken"])
    assert not any(entry["needed"] for entry in record["left"]), "nothing is owed by hand now"


@pytest.mark.proves("ado4", depth="component")
def test_asking_for_a_credential_that_is_not_on_this_machine_is_said(tmp_path, monkeypatch):
    """Asked for and absent is not the same as not asked for, and an archive that read alike for
    both would be one nobody could check."""
    root = _project(tmp_path, monkeypatch)

    made = backup.plan(Config.find(root), root, credentials=True)
    assert any("not on this machine" in entry.why for entry in made.left)
    assert not made.secret, "nothing secret was taken, so nothing about the archive changes"


# -- putting it back (`ado4`) ------------------------------------------------------------------

@pytest.mark.proves("ado4", depth="component")
def test_a_restore_puts_back_what_was_taken_and_overwrites_nothing(tmp_path, monkeypatch):
    root = _project(tmp_path, monkeypatch)
    where = tmp_path / "out.tgz"
    backup.write(where, Config.find(root), root)

    into = tmp_path / "restored"
    into.mkdir()
    (into / "history.jsonl").write_text("mine, and newer\n")
    _, done = backup.restore(where, into)

    assert done.skipped == ["history.jsonl"], "what is already there is kept and named"
    assert (into / "history.jsonl").read_text() == "mine, and newer\n"

    _, forced = backup.restore(where, into, force=True)
    assert forced.put_back == ["history.jsonl"]
    assert (into / "history.jsonl").read_text() == '{"seq": 1}\n'


@pytest.mark.proves("ado4", depth="component")
def test_a_credential_is_restored_where_this_machine_keeps_one(tmp_path, monkeypatch):
    """The recorded path belongs to the machine that wrote the archive. Honouring it would put a
    credential wherever *that* machine kept one, which here is a directory nothing reads."""
    root = _project(tmp_path, monkeypatch)
    _credentials(tmp_path, secret="THE-CREDENTIAL")
    where = tmp_path / "secret.tgz"
    backup.write(where, Config.find(root), root, credentials=True)

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "other-machine"))
    _, done = backup.restore(where, tmp_path / "restored")

    landed = tmp_path / "other-machine" / "plumb" / "enrolment.json"
    assert landed.is_file(), "resolved here, not read out of the archive"
    assert "THE-CREDENTIAL" in landed.read_text()
    assert landed.stat().st_mode & 0o777 == backup.SECRET_FILE_MODE


@pytest.mark.proves("ado4", depth="component")
def test_restoring_somewhere_else_says_the_session_scratch_is_orphaned(tmp_path, monkeypatch):
    """Stated rather than discovered — a delta that cannot be computed is otherwise a surprise at
    the next close."""
    root = _project(tmp_path, monkeypatch)
    where = tmp_path / "out.tgz"
    backup.write(where, Config.find(root), root)

    _, same = backup.restore(where, root, force=True)
    assert not same.moved

    _, moved = backup.restore(where, tmp_path / "elsewhere")
    assert moved.moved


@pytest.mark.proves("ado4", depth="component")
def test_an_archive_cannot_write_outside_where_it_is_unpacked(tmp_path, monkeypatch):
    """`extractall`'s own `filter="data"` reached 3.11 only as a point-release backport, so against
    this package's floor it is a defence on some interpreters and a TypeError on others. The layout
    is ours, so the legal members are enumerable and checking them here is stricter than a filter.
    """
    root = _project(tmp_path, monkeypatch)
    where = tmp_path / "hostile.tgz"
    backup.write(where, Config.find(root), root)

    outside = tmp_path / "escaped.txt"
    payload = tmp_path / "payload"
    payload.write_text("written where it should not be")
    hostile = tmp_path / "hostile-rebuilt.tgz"
    with tarfile.open(where) as good, tarfile.open(hostile, "w:gz") as bundle:
        for member in good.getmembers():
            bundle.addfile(member, good.extractfile(member))
        for name in ("../escaped.txt", f"{backup.PROJECT_DIR}/../../escaped.txt",
                     str(outside), "unknown/thing.txt"):
            bundle.add(payload, arcname=name)

    _, done = backup.restore(hostile, tmp_path / "into")

    assert not outside.exists(), "nothing was written where a member asked to go"
    assert len([s for s in done.skipped if "format defines" in s]) == 4, "and each was named"


# -- wired (`ado4`) ----------------------------------------------------------------------------

@pytest.mark.proves("ado4", depth="standards-integration")
def test_the_whole_round_trip_from_the_command_line(tmp_path, monkeypatch, capsys):
    """Taken, said, and put back — driven the way somebody moving a machine drives it."""
    root = _project(tmp_path, monkeypatch)
    _credentials(tmp_path, secret="MOVED-CREDENTIAL")
    where = tmp_path / "move.tgz"

    assert cli.main(["backup", "--project", str(root), "--out", str(where),
                     "--with-credentials"]) == 0
    made = capsys.readouterr().out
    assert "carries a credential" in made and "0600" in made, "said when it is made"
    assert "MOVED-CREDENTIAL" not in made, "and the secret itself is never printed"

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "new-machine"))
    into = tmp_path / "new-checkout"
    assert cli.main(["restore", str(where), "--project", str(into)]) == 0
    back = capsys.readouterr().out

    assert "this archive carries a credential" in back
    assert (into / "history.jsonl").read_text() == '{"seq": 1}\n', "the irreplaceable file"
    assert "MOVED-CREDENTIAL" in (
        tmp_path / "new-machine" / "plumb" / "enrolment.json").read_text()
    assert "wrap-up" in back, "and the orphaned scratch is named rather than left to be found"


@pytest.mark.proves("ado4", depth="standards-integration")
def test_a_dry_run_says_what_it_would_take_and_writes_nothing(tmp_path, monkeypatch, capsys):
    root = _project(tmp_path, monkeypatch)
    _credentials(tmp_path)

    assert cli.main(["backup", "--project", str(root), "--dry-run"]) == 0
    said = capsys.readouterr().out

    assert "would take" in said and "history.jsonl" in said
    assert "--with-credentials" in said, "the flag is named where its absence is felt"
    assert not list(Path.cwd().glob("plumb-backup-*.tgz")), "and nothing was written"


@pytest.mark.proves("ado4", depth="standards-integration")
def test_something_that_is_not_an_archive_is_refused_by_name(tmp_path, monkeypatch, capsys):
    _project(tmp_path, monkeypatch)
    (tmp_path / "notes.txt").write_text("this is not a backup")

    assert cli.main(["restore", str(tmp_path / "notes.txt"), "--project", str(tmp_path)]) == 1
    assert "could not be read" in capsys.readouterr().err
