"""Taking away what the tool wrote for one project, and putting it back (``ado4``).

One archive, restorable, holding what a repository does not already carry. **The exclusions are the
claim, not the contents.** The naive shape — everything under the tool's directories — is wrong in
both directions at once, and each direction has a different victim:

*Too much.* An account is shared across every project pushing to one holder (``ado4-ur4``), so
sweeping it into a per-project archive and restoring it elsewhere rebinds an identity that was never
this project's. *A secret.* The file form of an enrolment carries a credential (``ado4-ur4``), and an
archive is precisely the artifact that gets attached to a ticket and left in a downloads directory.
*Too little.* The irreplaceable things are the ones nobody lists: untransmitted friction, which
exists nowhere else until it reaches a holder, and a series, which is lossless only while every
transition survives.

**What is left travels in the archive.** An archive that silently omitted a credential and one that
never had anything to omit are otherwise the same bytes, and whoever finds out is whoever is
restoring after a disk failure.

**Carried means version-controlled, not located in the tree.** A series inside the project is the
irreplaceable artifact *and* is commonly ignored by git, so deciding by location would drop exactly
the file this exists to protect. So the question asked of each in-project path is whether git is
tracking it, and a project with no version control at all has everything taken.
"""

import json
import subprocess
import tarfile
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from plumb import __version__, footprint

#: The archive's own contract. Read before anything is unpacked, so a newer archive is refused with
#: its version named rather than half-restored (``dev07-3-2``'s posture, in a file that outlives the run).
BACKUP_VERSION = 1

MANIFEST_NAME = "plumb-backup.json"
PROJECT_DIR = "project"
FRICTION_DIR = "friction"
USER_DIR = "user"

#: What an archive is created as once it carries a credential. The same reasoning as every other
#: file that holds one: the default is the tight one, and it is set at creation rather than after,
#: so there is no window where the secret is world-readable.
SECRET_FILE_MODE = 0o600


class Unreadable(Exception):
    """Not a Plumb archive, or one this version does not know how to read."""


@dataclass(frozen=True)
class Held:
    """One thing taken, and where it came from."""

    where: str
    what: str


@dataclass(frozen=True)
class Left:
    """One thing deliberately not taken, and why. This is the half that has to be written down."""

    where: str
    why: str
    #: Whether a restore is incomplete without somebody supplying it by hand. A cache left behind
    #: is not a gap; a credential left behind is, and the two must not read alike.
    needed: bool = False


@dataclass
class Plan:
    """What an archive would hold and what it would refuse, before anything is written."""

    taken: list[Held] = field(default_factory=list)
    left: list[Left] = field(default_factory=list)
    files: list[tuple[Path, str]] = field(default_factory=list)
    records: list = field(default_factory=list)
    queued: set = field(default_factory=set)
    #: Whether anything taken must never be readable. It changes the archive's own mode and every
    #: line the tool prints about it, so it is tracked rather than re-derived at each use.
    secret: bool = False


def _tracked(repo: Path, path: Path) -> bool:
    """Whether version control already carries this file — the only sense of *carried* that counts.

    A project that is not a repository at all tracks nothing, so everything is taken; that is the
    right answer rather than a fallback, because an unversioned project's declaration exists in
    exactly one place.
    """
    try:
        done = subprocess.run(
            ["git", "-C", str(repo), "ls-files", "--error-unmatch", str(path)],
            capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0


def _identity(config, project: Path) -> str:
    """What this project calls itself, for deciding which friction records are its own."""
    return config.subject or Path(project).resolve().name


def plan(config, project: Path, credentials: bool = False) -> Plan:
    """Decide what belongs in the archive before opening one (``ado4``).

    ``credentials`` is off by default and is the only way a secret or a shared identity enters an
    archive. What is refused is a *silent* inclusion rather than the inclusion itself: moving a
    machine is a real thing to want, and a tool that made it impossible would be routed around with
    `tar` — which produces the same archive with none of the marking. So asking is answered, and the
    answer changes how the archive describes and protects itself.
    """
    from plumb.cli import DEFAULT_STORE
    from plumb.store import SupportStore

    project = Path(project)
    made = Plan()

    for wrote in footprint.in_project(config, project):
        source = project / wrote.where
        if not source.exists():
            continue
        if _tracked(project, Path(wrote.where)):
            made.left.append(Left(wrote.where, "your version control already carries it"))
            continue
        made.files.append((source, f"{PROJECT_DIR}/{wrote.where}"))
        made.taken.append(Held(wrote.where, wrote.what))

    mine = _identity(config, project)
    store = SupportStore(DEFAULT_STORE)
    records, unreadable = store.all()
    waiting = set(store.queued())
    others = 0
    for record in records:
        if record.project == mine:
            made.records.append(record)
            if record.id in waiting:
                made.queued.add(record.id)
        else:
            others += 1
    if made.records:
        made.taken.append(Held(str(DEFAULT_STORE),
                               f"{len(made.records)} friction record(s) filed against {mine}, "
                               f"{len(made.queued)} of them still waiting to be transmitted"))
    if others:
        made.left.append(Left(str(DEFAULT_STORE),
                              f"{others} friction record(s) belonging to another project or to "
                              f"none — one store holds them all, and this archive is one "
                              f"project's"))
    for bad in unreadable:
        # Said rather than skipped: a record that cannot be parsed is still somebody's, and an
        # archive that quietly dropped it would be the silent loss `ado4-ur5` refuses.
        made.left.append(Left(str(bad.path), f"could not be read — {bad.reason}", needed=True))

    for wrote in footprint.user_level():
        if not wrote.keep:
            made.left.append(Left(wrote.where, "rebuilt on demand"))
        elif not (wrote.secret or wrote.shared):
            continue
        elif not credentials:
            made.left.append(Left(
                wrote.where,
                "carries a credential, and an archive is the wrong place for one — supply it "
                "again by hand, or ask for it with --with-credentials" if wrote.secret else
                "shared with every project that pushes to the same holder, so restoring it for "
                "one would rebind an identity that was never this project's — --with-credentials "
                "takes it anyway", needed=True))
        elif Path(wrote.where).exists():
            made.files.append((Path(wrote.where), f"{USER_DIR}/{Path(wrote.where).name}"))
            made.taken.append(Held(wrote.where, wrote.what))
            made.secret = made.secret or wrote.secret
        else:
            made.left.append(Left(wrote.where, "asked for, and not on this machine"))
    return made


def manifest_of(made: Plan, config, project: Path) -> dict:
    """What the archive says about itself, including whether it is now a secret."""
    return {
        "backup_version": BACKUP_VERSION,
        "plumb": __version__,
        "when": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "project": {"root": str(Path(project).resolve()), "subject": _identity(config, project)},
        "taken": [asdict(h) for h in made.taken],
        "left": [asdict(l) for l in made.left],
        # Stated in the archive itself, because whoever finds this file later is exactly the person
        # who cannot tell from the outside whether it is safe to pass on.
        "carries_credentials": made.secret,
    }


def write(archive: Path, config, project: Path, credentials: bool = False) -> dict:
    """One archive, and the record of what it refused, inside it."""
    made = plan(config, project, credentials)
    record = manifest_of(made, config, project)
    archive = Path(archive)
    archive.parent.mkdir(parents=True, exist_ok=True)
    if made.secret:
        # Created narrow *before* anything is written into it, so the secret is never briefly
        # readable by everybody — the window is the whole of what a later chmod would leave open.
        archive.touch(mode=SECRET_FILE_MODE)
        archive.chmod(SECRET_FILE_MODE)

    with tarfile.open(archive, "w:gz") as bundle:
        with tempfile.TemporaryDirectory() as staging:
            written = Path(staging) / MANIFEST_NAME
            written.write_text(json.dumps(record, indent=2) + "\n")
            bundle.add(written, arcname=MANIFEST_NAME)
            for source, arcname in made.files:
                bundle.add(source, arcname=arcname)
            for held in made.records:
                where = Path(staging) / f"{held.id}.json"
                where.write_text(held.to_json())
                bundle.add(where, arcname=f"{FRICTION_DIR}/{held.id}.json")
            for record_id in sorted(made.queued):
                marker = Path(staging) / "queued"
                marker.write_text("")
                bundle.add(marker, arcname=f"{FRICTION_DIR}/outbox/{record_id}")
    return record


def read_manifest(archive: Path) -> dict:
    """What this archive says it is, before anything is unpacked."""
    try:
        with tarfile.open(archive, "r:gz") as bundle:
            found = bundle.extractfile(MANIFEST_NAME)
            if found is None:
                raise Unreadable(f"{archive} carries no {MANIFEST_NAME} — not a Plumb archive")
            said = json.loads(found.read().decode())
    except (OSError, tarfile.TarError, ValueError) as bad:
        raise Unreadable(f"{archive} could not be read — {bad}") from bad
    version = said.get("backup_version")
    if version != BACKUP_VERSION:
        raise Unreadable(
            f"{archive} is a version {version} archive and this is plumb {__version__}, which "
            f"reads version {BACKUP_VERSION}. Refused rather than half-restored.")
    return said


#: The only top-level names an archive of ours carries. The layout is this format's, so the legal
#: members are enumerable — which is what lets unpacking be strict rather than merely careful.
_LEGAL = (MANIFEST_NAME, PROJECT_DIR, FRICTION_DIR, USER_DIR)


def _named_legally(name: str) -> bool:
    """Whether a member name is one this format defines, and cannot escape where it is written."""
    parts = PurePosixPath(name).parts
    return bool(parts) and not PurePosixPath(name).is_absolute() and ".." not in parts \
        and parts[0] in _LEGAL


def _unpack(bundle: tarfile.TarFile, into: Path) -> list[str]:
    """Write out only the members this format defines, and nothing a member can name for itself.

    ``extractall``'s own ``filter="data"`` does this and is deliberately not used: it arrived in
    3.12 and reached 3.11 only as a point-release backport, so against the ``>=3.11`` floor this
    package declares it is a defence on some interpreters and a ``TypeError`` on others — the worst
    of the three possible outcomes, because it fails where it is least tested. Checking here is
    version-independent and stricter than any filter, since an archive of ours has a known shape:
    regular files only, no absolute paths, no ``..``, and nothing outside the four known roots.
    """
    refused = []
    for member in bundle.getmembers():
        if not member.isfile() or not _named_legally(member.name):
            # Named rather than dropped. A member we do not recognise is either another tool's
            # archive or somebody's attempt, and both are worth saying out loud.
            refused.append(member.name)
            continue
        target = into / member.name
        target.parent.mkdir(parents=True, exist_ok=True)
        source = bundle.extractfile(member)
        if source is not None:
            target.write_bytes(source.read())
    return refused


@dataclass
class Restored:
    put_back: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    records: int = 0
    moved: bool = False


def restore(archive: Path, project: Path, force: bool = False) -> tuple[dict, Restored]:
    """Put back what was taken, and refuse to overwrite what is already there.

    Not overwriting is the default because a restore is most often run *beside* live work rather
    than onto bare ground, and a silent overwrite there costs exactly what a backup was for.
    """
    from plumb.cli import DEFAULT_STORE
    from plumb.support import SupportRecord
    from plumb.store import SupportStore

    said = read_manifest(archive)
    project = Path(project)
    done = Restored(moved=said.get("project", {}).get("root") != str(project.resolve()))
    store = SupportStore(DEFAULT_STORE)

    with tempfile.TemporaryDirectory() as staging:
        with tarfile.open(archive, "r:gz") as bundle:
            for name in _unpack(bundle, Path(staging)):
                done.skipped.append(f"{name} — not something this archive format defines")
        unpacked = Path(staging)

        for source in sorted((unpacked / PROJECT_DIR).rglob("*")) if (
                unpacked / PROJECT_DIR).is_dir() else []:
            if source.is_dir():
                continue
            relative = source.relative_to(unpacked / PROJECT_DIR)
            target = project / relative
            if target.exists() and not force:
                done.skipped.append(str(relative))
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            done.put_back.append(str(relative))

        # Resolved on *this* machine rather than taken from the archive: the recorded path is the
        # source machine's, and an XDG variable set differently here would otherwise restore a
        # credential to a directory nothing reads.
        targets = {Path(w.where).name: Path(w.where) for w in footprint.user_level()}
        for source in sorted((unpacked / USER_DIR).glob("*")) if (
                unpacked / USER_DIR).is_dir() else []:
            target = targets.get(source.name)
            if target is None:
                done.skipped.append(f"{USER_DIR}/{source.name} — this version writes no such file")
                continue
            if target.exists() and not force:
                # Never silently: overwriting the account this machine is already using would swap
                # an identity out from under whatever else pushes with it (`ado4-ur4`).
                done.skipped.append(f"{target} — already here, and not overwritten")
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
            target.chmod(SECRET_FILE_MODE)
            done.put_back.append(str(target))

        friction = unpacked / FRICTION_DIR
        queued = {p.name for p in (friction / "outbox").iterdir()} if (
            friction / "outbox").is_dir() else set()
        for source in sorted(friction.glob("*.json")) if friction.is_dir() else []:
            held = SupportRecord.from_json(source.read_text())
            store.file(held, queue=held.id in queued)
            done.records += 1
    return said, done
