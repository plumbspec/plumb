"""How the CLI discovers a contributed module and links its verbs in (``mod1``–``mod4``).

**The core owns the parser.** A module hands over a *declaration* — what it is called, what
surfaces it speaks, what verbs it mounts, what it writes, whether it reaches the network — and the
core builds the parser from it. It is never handed the parser to mutate.

That follows from ``mod2`` rather than from taste: an adopter's decision to trust a module has to
be "over a list rather than a hope". A module that mounts by running code against an argparse
object cannot be listed before it runs, cannot be refused for naming a core verb, and can shadow
anything already there. Reading a declaration first is what makes refusing one possible at all.

**What the core promises back** is the set of surfaces it publishes, each with its own version
(``mod1-ur2``) — the board and the series interface today. A module declares the version it speaks
per surface, and one it cannot be given is refused by name rather than discovered at runtime by a
verb that half works.

**Nothing here probes.** A module that cannot reach what it needs is inert by ``mod1-ur3``: its
verbs mount, run, and report their own standing. The core cannot tell a service being down from a
credential being wrong, and a core that guessed would report the wrong one.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Callable

#: The entry-point group an installed package declares to be discovered. Installing is the whole of
#: enabling (``mod4-ur1``): there is no register step and no key that turns a module on, because a
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
    """What a module says about itself, before any of it is mounted (``mod2``).

    ``surfaces`` maps a surface the core publishes to the version this module speaks. ``writes``
    names every place it writes, so ``plumb footprint``, backup and restore stay honest about what
    modules added (``mod2-ur2``). ``network`` is declared so the install's trust decision is over
    verbs, writes and reach together (``mod2-ur4``).
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
    said so (``mod2-ur1``); it is not silently renamed and it does not win.

    **One broken extension never costs the tool.** A module whose import raises is reported as an
    install fault and every other module still mounts, so a half-installed environment degrades to
    the tool minus one capability rather than to no tool.
    """
    found = []
    for entry in sorted(_entry_points(), key=lambda e: e.name):
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
    return found


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
    taken = sorted(verb.name for verb in declared.verbs if verb.name in reserved)
    # Only the names a module OWNS collide — a command under its own group is its own business,
    # so `series push` never competes with `support push` and neither has to know the other exists.
    if taken:
        return Mounted(declared.name, declared,
                       f"mounts {', '.join(taken)}, which the core already owns — a module's verbs "
                       f"are its own (`mod2-ur1`)")
    return Mounted(declared.name, declared)


def mount(groups, reserved, say=None) -> list:
    """Link every module that will mount, and say why of every one that will not.

    ``groups`` is the CLI's own subparser action, so a module's verb is indistinguishable from a
    core verb once mounted — which is the whole of ``mod4``'s *the one CLI grows a verb*.
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
        for where in declared.writes:
            lines.append(f"      writes {where}")
    return "\n".join(lines)
