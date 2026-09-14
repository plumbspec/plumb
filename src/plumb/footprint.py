"""Everything this tool writes, and which of it is worth taking away (``ado4``).

The question this answers is *what do I back up, and what may I safely lose* — which nobody could
answer before, because the answer was spread across five modules and a reader had to find each
default by reading source. That is the shape of every inventory that goes stale: a list somebody
maintains beside the thing it describes.

So the list is **here, beside the code that writes**, and the documentation is a view of it rather
than a second copy (``ado4``). What each entry carries is not a path but a *disposition* — whether
it can be rebuilt, whether the repository already has it, whether it belongs to this project alone,
and whether it must never leave the machine — because those are the four facts a backup, a
migration and an archive each need, and none of them is derivable from a filename.
"""

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Wrote:
    """One place the tool writes, and what losing it would cost."""

    where: str
    what: str
    #: ``False`` where it rebuilds itself from something else that survived. A cache and a derived
    #: key are both disposable for the same reason, and neither belongs in an archive.
    keep: bool
    #: In the project's own tree, which means the project's version control already carries it and
    #: an archive that took it again would be keeping a second copy of a thing git holds better.
    in_repo: bool = False
    #: Not this project's alone. One account serves every repository that pushes to one holder,
    #: so restoring it *for* a project silently rebinds an identity that was never that project's.
    shared: bool = False
    #: Must never leave the machine, whatever the archive is for (``ado4-ur2``).
    secret: bool = False


def _home(variable: str, fallback: str) -> Path:
    return Path(os.environ.get(variable) or Path.home() / fallback)


def user_level() -> tuple[Wrote, ...]:
    """What the tool writes outside any project — the half a repository does not carry."""
    config = _home("XDG_CONFIG_HOME", ".config") / "plumb"
    return (
        Wrote(str(Path(os.environ.get("PLUMB_ACCOUNT") or config / "account.json")),
              "the endpoint, the public half of the account, and this key's counter. No secret: "
              "the identity is derived from your passphrase and is never written down",
              keep=True, shared=True),
        Wrote(str(config / "enrolment.json"),
              "an operator-issued enrolment — the file form, which carries a credential",
              keep=True, shared=True, secret=True),
        Wrote(str(Path(os.environ.get("PLUMB_FRICTION_DIR")
                       or _home("XDG_DATA_HOME", ".local/share") / "plumb" / "friction")),
              "friction records, and an outbox of what has not reached a holder yet. "
              "Irreplaceable — nothing else holds an untransmitted record",
              keep=True),
        Wrote(str(_home("XDG_STATE_HOME", ".local/state") / "plumb"),
              "the opening reading of a session, keyed by project path. Scratch: a session that "
              "loses it is told its delta cannot be computed, and nothing else changes",
              keep=False),
        Wrote(str(_home("XDG_CACHE_HOME", ".cache") / "plumb"),
              "a per-version cache the tool rebuilds when it is missing, and under `runs/` each "
              "project's run file and manifest, keyed by its path — one board's input and output, "
              "rewritten by the next one", keep=False),
    )


def in_project(config, project: Path = Path(".")) -> tuple[Wrote, ...]:
    """What the tool writes inside one project, given what that project declared."""
    from plumb.config import CONFIG_NAME
    from plumb.core import series

    found = [
        Wrote(CONFIG_NAME, "your declaration — the whole of what `plumb init` may write",
              keep=True, in_repo=True),
    ]
    if config.cursor:
        found.append(Wrote(config.cursor, "the handoff between two sessions",
                           keep=True, in_repo=True))
    if config.series:
        found.append(Wrote(config.series,
                           "the history: every transition, losslessly. Irreplaceable — a run that "
                           "is not recorded cannot be recovered from a later one",
                           keep=True, in_repo=True))
        found.append(Wrote(str(series.sent_mark(Path(config.series))),
                           "how far that history has been transmitted", keep=True, in_repo=True))
    return tuple(found)


def everything(config, project: Path = Path(".")) -> tuple[Wrote, ...]:
    return in_project(config, project) + user_level()
