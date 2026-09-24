"""Everything this tool writes, and which of it is worth taking away (``ado4``).

The question this answers is *what do I back up, and what may I safely lose* — which nobody could
answer before, because the answer was spread across five modules and a reader had to find each
default by reading source. That is the shape of every inventory that goes stale: a list somebody
maintains beside the thing it describes.

So the list is **here, beside the code that writes**, and the documentation is a view of it rather
than a second copy (``ado4``). What each entry carries is not a path but a *disposition* — whether
it can be rebuilt, whether the repository already has it, whether it belongs to this project alone,
and whether it carries a credential — because those are the four facts anybody deciding what to
protect needs, and none of them is derivable from a filename.

Each states what the entry **is**, never what to do about it (``ado4-nfr3``). *Must never leave the
machine* was one of them, and it instructed a reader whose threat model, infrastructure and
obligations this tool cannot see.
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
    #: Carries a credential (``ado4-ur2``). What follows from that is the reader's: their threat
    #: model, their infrastructure and their obligations are not things this tool can see, so it
    #: names what the file is and stops (``ado4-nfr3``).
    secret: bool = False
    #: Nothing else holds this. **Stated, never derived** (``ado4-ur3``): a series lives inside the
    #: project and is commonly git-ignored, so deciding by location marks everything in the tree as
    #: carried and drops the one file most worth naming. Irreplaceability is a property of the
    #: artifact — a run that was not recorded cannot be recovered from a later one — and not of
    #: which directory it landed in.
    irreplaceable: bool = False


def _home(variable: str, fallback: str) -> Path:
    return Path(os.environ.get(variable) or Path.home() / fallback)


def _support_store() -> Path:
    """Where records actually live, asked of the module that resolves it.

    Imported here rather than at module scope because `cli` imports this one; the cycle is real
    and the lazy import is what keeps one answer to the question rather than two.
    """
    from plumb.cli import default_store

    return default_store()


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
        # Read off the one place that decides it, never recomputed here. This carried its own copy
        # of the rule and the copy went stale: it honoured only the superseded `PLUMB_FRICTION_DIR`
        # and pointed at `plumb/friction`, a directory the tool stopped writing to — so `plumb
        # footprint` named somewhere that does not exist and missed the store that does. What is
        # irreplaceable is exactly what a footprint must not get wrong.
        Wrote(str(_support_store()),
              "support records, and an outbox of what has not reached a holder yet — nothing "
              "else holds an untransmitted record",
              keep=True, irreplaceable=True),
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
                           "the history: every transition, losslessly — a run that is not "
                           "recorded cannot be recovered from a later one",
                           keep=True, in_repo=True, irreplaceable=True))
        found.append(Wrote(str(series.sent_mark(Path(config.series))),
                           "how far that history has been transmitted", keep=True, in_repo=True))
    return tuple(found)


def from_modules() -> tuple[Wrote, ...]:
    """What mounted modules declare they write (``mod2-ur2``, ``ado5-ur5``).

    Imported lazily because `modules` reads this module for the entry type, and a footprint that
    could not be built without discovering modules would make the core's own answer depend on what
    happened to be installed.

    A module that declares nothing contributes nothing; there is no entry saying so, because a
    module with no state is the ordinary case rather than a finding. A module the core **refused**
    contributes nothing either — what it said about itself was not accepted, and printing it here
    would put unchecked text in the one list somebody protects a machine from.

    ``reserved`` is empty because a verb collision is the CLI's question and not this one: a module
    refused a name still wrote what it wrote, and an inventory that dropped it would be wrong about
    the disk.
    """
    from plumb.modules import discover

    return tuple(wrote for module in discover(reserved=set())
                 if module.declaration and not module.refused
                 for wrote in module.declaration.writes)


def everything(config, project: Path = Path(".")) -> tuple[Wrote, ...]:
    """Everything the **core** writes. Modules are not in it: `from_modules()` is composed beside
    this one, where it can be named as theirs, so a core answer never varies with what is installed.
    """
    return in_project(config, project) + user_level()
