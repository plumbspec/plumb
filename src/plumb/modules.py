"""How the CLI discovers a contributed module and links its verbs in (``dev08-1-1``–``dev08-1-4``).

**The core owns the parser.** A module hands over a *declaration* — what it is called, what
surfaces it speaks, what verbs it mounts, what it writes, whether it reaches the network — and the
core builds the parser from it. It is never handed the parser to mutate.

That follows from ``dev08-1-2`` rather than from taste: an adopter's decision to trust a module has to
be "over a list rather than a hope". A module that mounts by running code against an argparse
object cannot be listed before it runs, cannot be refused for naming a core verb, and can shadow
anything already there. Reading a declaration first is what makes refusing one possible at all.

**What the core promises back** is the set of surfaces it publishes, each with its own version
(``dev08-1-1-ur2``) — the board, the series interface and transport today. A module declares the version it speaks
per surface, and one it cannot be given is refused by name rather than discovered at runtime by a
verb that half works.

**Nothing here probes.** A module that cannot reach what it needs is inert by ``dev08-1-1-ur3``: its
verbs mount, run, and report their own standing. The core cannot tell a service being down from a
credential being wrong, and a core that guessed would report the wrong one.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Callable

#: The entry-point group an installed package declares to be discovered. Installing is the whole of
#: enabling (``dev08-1-4-ur1``): there is no register step and no key that turns a module on, because a
#: mount somebody has to remember to enable is a mount that is off in production.
GROUP = "plumb.modules"


@dataclass(frozen=True)
class Argument:
    """One argument of a verb, as data. ``options`` is passed to ``add_argument`` unchanged."""

    flags: tuple
    options: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Verb:
    """One command the module mounts. ``run`` is called with the parsed arguments.

    A verb carrying ``verbs`` is a **group** rather than a command: one name the module owns, with
    commands under it, which is the shape the core's own groups already have. Without it every
    module would flatten to one top-level name per command — `series-push` and its siblings — and
    no module could be given a name of its own to hang things from.

    The example is spelled without the tool's name in front of it on purpose: a scan looks for what
    this tool tells a reader to run, and a command-shaped string in a comment is indistinguishable
    from one.
    """

    name: str
    help: str
    run: Callable | None = None
    arguments: tuple = ()
    #: Commands under this one, when it is a group.
    verbs: tuple = ()


@dataclass(frozen=True)
class Declaration:
    """What a module says about itself, before any of it is mounted (``dev08-1-2``).

    ``surfaces`` maps a surface the core publishes to the version this module speaks. ``writes``
    holds `footprint.Wrote` entries, so `plumb footprint` names what a module added and with what
    disposition (``dev08-1-2-ur2``, ``dev00-1-5-ur5``) — a module's state is invisible to the person deciding
    what to protect otherwise, and the core stops being able to answer for it the moment a
    capability moves out. ``network`` is declared so the install's trust decision is over verbs,
    writes and reach together (``dev08-1-2-ur4``).
    """

    name: str
    version: str
    surfaces: dict
    verbs: tuple
    writes: tuple = ()
    network: bool = False


@dataclass(frozen=True)
class Mounted:
    """A module the core found, and what it made of it."""

    name: str
    declaration: Declaration | None = None
    #: Why it did not mount. Empty when it did.
    refused: str = ""


def published() -> dict:
    """The surfaces the core publishes, and the version of each.

    Read off the modules that own them rather than restated here: a version with two homes is two
    versions, and the one that drifts is the copy a module is checked against.
    """
    from plumb.core.board import BOARD_VERSION
    from plumb.core.series import SERIES_VERSION
    from plumb.transport import TRANSPORT_VERSION

    return {"board": BOARD_VERSION, "series": SERIES_VERSION, "transport": TRANSPORT_VERSION}


def _entry_points():
    """Every entry point in our group, across the Python versions the floor spans.

    ``entry_points(group=...)`` arrived at 3.10 and this tool runs at 3.9, where the call returns a
    mapping of group to entry points instead. Discovery is therefore by group name alone — there is
    nothing to select on but the group, which is a constraint on the contract and not a detail.
    """
    from importlib.metadata import entry_points

    try:
        return list(entry_points(group=GROUP))
    except TypeError:
        return list(entry_points().get(GROUP, ()))


def discover(reserved) -> list:
    """Every installed module, mounted or refused, in a stable order.

    ``reserved`` is the set of verb names the core already owns. A module naming one is refused and
    said so (``dev08-1-2-ur1``); it is not silently renamed and it does not win.

    **One broken extension never costs the tool.** A module whose import raises is reported as an
    install fault and every other module still mounts, so a half-installed environment degrades to
    the tool minus one capability rather than to no tool.
    """
    found = []
    seen = set()
    for entry in sorted(_entry_points(), key=lambda e: e.name):
        # **One distribution found twice is not two modules.** An editable install and that same
        # tree's `src/` on `PYTHONPATH` — the setup CONTRIBUTING asks for — puts the dist-info and
        # the egg-info both on the path, and the same entry point is read from each. It listed the
        # module twice and printed its writes twice, and once `_uncontested` existed it read as two
        # modules fighting over a name and refused the only one there was.
        #
        # Same name and same target is the same code by the only definition available here.
        where = (entry.name, getattr(entry, "value", None))
        if where in seen:
            continue
        seen.add(where)
        try:
            declared = entry.load()
        except Exception as broke:                      # noqa: BLE001 - any import failure at all
            found.append(Mounted(entry.name, refused=f"failed to import — {broke}"))
            continue
        declared = declared() if callable(declared) and not isinstance(declared, Declaration) \
            else declared
        if not isinstance(declared, Declaration):
            found.append(Mounted(entry.name, refused="declared no module declaration"))
            continue
        found.append(_checked(declared, reserved))
    return _uncontested(found)


def _uncontested(found: list) -> list:
    """Every module held against the others, which no single declaration can see (``dev08-1-2-ur5``).

    ``_checked`` compares one declaration against the core's verbs. Two modules claiming one name
    pass it individually and collide at the parser, and what happened then depended on the
    interpreter: at the floor argparse took the second silently, so a verb the adopter never chose
    answered; at 3.13 it raised out of building the parser and took unrelated commands with it.

    **A contested name mounts for nobody.** The core cannot know which one was meant, and the
    alternative is picking by discovery order — the entry point's name, a string neither author
    chose for this and no adopter reads (``dev08-1-2-nfr1``). A verb answering from somewhere the
    adopter did not choose writes their data somewhere they did not choose.

    Only the contested name is lost. Everything else mounts (``dev08-1-2-sr2``).
    """
    claims: dict = {}
    for module in found:
        if module.refused or not module.declaration:
            continue
        for verb in module.declaration.verbs:
            claims.setdefault(verb.name, []).append(module.name)
    contested = {verb: names for verb, names in claims.items() if len(names) > 1}
    if not contested:
        return found
    settled = []
    for module in found:
        theirs = sorted(verb for verb, names in contested.items()
                        if not module.refused and module.declaration
                        and module.name in names)
        if not theirs:
            settled.append(module)
            continue
        said = "; ".join(
            f"`{verb}` is also claimed by {', '.join(n for n in contested[verb] if n != module.name)}"
            for verb in theirs)
        settled.append(Mounted(module.name, module.declaration,
                               f"{said} — a contested name mounts for nobody, because the core "
                               f"cannot know which was meant (`dev08-1-2-ur5`)"))
    return settled


def _checked(declared: Declaration, reserved) -> Mounted:
    """A declaration held to what the core can actually give it, before anything is bound."""
    surfaces = published()
    for surface, speaks in sorted(declared.surfaces.items()):
        if surface not in surfaces:
            return Mounted(declared.name, declared,
                           f"speaks `{surface}`, which the core publishes no version of — "
                           f"it publishes {', '.join(sorted(surfaces))}")
        if speaks != surfaces[surface]:
            return Mounted(declared.name, declared,
                           f"speaks `{surface}` {speaks} and the core publishes "
                           f"{surfaces[surface]}")
    from plumb.footprint import Wrote

    # Checked here so it is refused by name rather than found later by whatever reads the field.
    # `dev08-1-2` is that trusting a module is a decision over a list; a list with something unreadable
    # in it is the failure that argument exists to prevent.
    unreadable = [w for w in declared.writes if not isinstance(w, Wrote)]
    if unreadable:
        return Mounted(declared.name, declared,
                       f"declares {len(unreadable)} write(s) that are not footprint entries — "
                       f"`writes` holds `footprint.Wrote`, so `plumb footprint` can say what "
                       f"losing each place would cost")
    taken = sorted(verb.name for verb in declared.verbs if verb.name in reserved)
    # Only the names a module OWNS collide — a command under its own group is its own business,
    # so `series push` never competes with `support push` and neither has to know the other exists.
    if taken:
        return Mounted(declared.name, declared,
                       f"mounts {', '.join(taken)}, which the core already owns — a module's verbs "
                       f"are its own (`dev08-1-2-ur1`)")
    return Mounted(declared.name, declared)


def mount(groups, reserved, say=None) -> list:
    """Link every module that will mount, and say why of every one that will not.

    ``groups`` is the CLI's own subparser action, so a module's verb is indistinguishable from a
    core verb once mounted — which is the whole of ``dev08-1-4``'s *the one CLI grows a verb*.
    """
    found = discover(reserved)
    for module in found:
        if module.refused:
            if say:
                say(f"plumb: module {module.name} did not mount — {module.refused}")
            continue
        for verb in module.declaration.verbs:
            _bind(groups, verb, module.declaration.name)
    return found


def _bind(groups, verb: Verb, module_name: str) -> None:
    """One verb, or one group and everything under it."""
    parser = groups.add_parser(verb.name, help=verb.help)
    for argument in verb.arguments:
        parser.add_argument(*argument.flags, **argument.options)
    if verb.verbs:
        # `required=True` for the same reason the core's groups set it: a bare group name is not a
        # command, and argparse's default is to accept it and hand back no `func` at all.
        under = parser.add_subparsers(dest=f"{module_name}_command", required=True)
        for child in verb.verbs:
            _bind(under, child, module_name)
        return
    parser.set_defaults(func=verb.run)


def render(found: list) -> str:
    """What `plumb modules` prints: what is mounted, what it adds, and what it reaches."""
    if not found:
        return ("no modules installed — a module is an ordinary package, and installing one is the "
                "whole of enabling it")
    lines = []
    for module in found:
        declared = module.declaration
        if module.refused:
            lines.append(f"  {module.name}  NOT MOUNTED — {module.refused}")
            continue
        verbs = ", ".join(
            f"{verb.name} ({'|'.join(c.name for c in verb.verbs)})" if verb.verbs else verb.name
            for verb in declared.verbs)
        speaks = ", ".join(f"{s} {v}" for s, v in sorted(declared.surfaces.items()))
        lines.append(f"  {declared.name} {declared.version}"
                     f"  verbs: {verbs}"
                     f"  speaks: {speaks or 'nothing'}"
                     f"  network: {'yes' if declared.network else 'no'}")
        for wrote in declared.writes:
            # The place only. What losing it would cost is `plumb footprint`'s answer, and saying
            # it twice is how the two copies come to disagree.
            lines.append(f"      writes {wrote.where}")
    return "\n".join(lines)
