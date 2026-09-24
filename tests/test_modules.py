"""How the CLI discovers a module and links its verbs in (``mod1``–``mod4``).

**Asserted as a difference.** Each test builds a declaration that mounts and then breaks exactly
one thing, because a mount that refuses everything passes a suite as readily as one that refuses
the right thing. The clean declaration is asserted mounted first.

The refusals are the half worth proving. A mount that links whatever it is handed cannot support
`mod2`'s claim that trusting a module is a decision over a list — the list is only worth reading if
something is checked against it.
"""

from __future__ import annotations

import argparse

import pytest

from plumb.footprint import Wrote
from plumb.modules import (Argument, Declaration, Mounted, Verb, _checked, mount, published,
                           render)


def _declaration(**changed) -> Declaration:
    fields = dict(
        name="example", version="1.0.0", surfaces={"series": published()["series"]},
        verbs=(Verb("example", "an example module", verbs=(
            Verb("run", "do the thing", lambda args: 0,
                 (Argument(("--loudly",), {"action": "store_true"}),)),
        )),),
        writes=(Wrote("~/.local/share/example", "records the example kept", keep=True),),
        network=False)
    fields.update(changed)
    return Declaration(**fields)


def test_a_clean_declaration_mounts():
    assert _checked(_declaration(), reserved={"board"}).refused == ""


@pytest.mark.proves("mod2", depth="unit")
def test_a_module_may_not_mount_a_verb_the_core_owns():
    """`mod2-ur1`. It is refused and named, never silently renamed, and it never wins.

    The core's set is only complete once every core verb is added, which is why the mount runs
    last — a mount placed earlier would let whichever module loaded first take a name the core was
    about to add, and the collision would surface as the core's verb having vanished.
    """
    refused = _checked(_declaration(verbs=(Verb("board", "shadow the board", lambda a: 0),)),
                       reserved={"board", "series"}).refused
    assert "board" in refused and "the core already owns" in refused


def test_a_command_under_a_modules_own_group_never_collides():
    """Only the names a module OWNS can collide. `series push` and `support push` coexist."""
    declared = _declaration(verbs=(Verb("example", "a group", verbs=(
        Verb("board", "a command named like a core group, under our own name", lambda a: 0),)),))
    assert _checked(declared, reserved={"board"}).refused == ""


def test_a_surface_the_core_does_not_publish_is_refused():
    refused = _checked(_declaration(surfaces={"telemetry": 1}), reserved=set()).refused
    assert "telemetry" in refused and "publishes no version of" in refused


@pytest.mark.proves("mod1", depth="unit")
def test_a_surface_version_the_core_cannot_give_is_refused():
    """`mod1-ur2` — a version per surface, refused by name rather than half-working at runtime."""
    refused = _checked(_declaration(surfaces={"series": published()["series"] + 41}),
                       reserved=set()).refused
    assert "series" in refused and str(published()["series"]) in refused


@pytest.mark.proves("mod1", depth="unit")
def test_the_core_publishes_a_version_for_every_surface_it_names():
    """A surface with no version is one nobody can refuse by name."""
    assert all(isinstance(v, int) and v > 0 for v in published().values()), published()
    assert {"board", "series"} <= set(published())


@pytest.mark.proves("mod4", depth="wiring")
def test_a_mounted_group_reaches_its_callable_through_the_parser(capsys):
    """The point of the whole thing: a module's verb is indistinguishable from a core verb."""
    parser = argparse.ArgumentParser(prog="plumb")
    groups = parser.add_subparsers(dest="group", required=True)
    groups.add_parser("board")

    reached = {}

    def run(args) -> int:
        reached["loudly"] = args.loudly
        return 0

    declared = _declaration(verbs=(Verb("example", "a group", verbs=(
        Verb("run", "do it", run, (Argument(("--loudly",), {"action": "store_true"}),)),)),))

    for verb in declared.verbs:
        from plumb.modules import _bind
        _bind(groups, verb, declared.name)

    args = parser.parse_args(["example", "run", "--loudly"])
    assert args.func(args) == 0
    assert reached == {"loudly": True}


@pytest.mark.proves("mod4", depth="wiring")
@pytest.mark.proves("mod1", depth="wiring")
def test_the_one_cli_grows_the_verb(tmp_path, capsys):
    """`mod4` — through `plumb` itself, and this is the only test that proves the thing claimed.

    Every other mount test builds its own `ArgumentParser`, which proves `_bind` and says nothing
    about the CLI an adopter runs: the discovery, the check against the published surfaces and the
    binding all sit between that parser and this one. *A module's verb is indistinguishable from a
    core verb* is a claim about `plumb`, so it is asserted against `plumb`.
    """
    from plumb.cli import main
    from plumb.core.manifest import Citation, Manifest, Story
    from plumb.core.series import append

    store = tmp_path / "series.jsonl"
    append(store, Manifest(stories={"S-1": Story(citations=(
        Citation(test="t::a", depth="unit", result="passed", grounding="inert",
                 when="2026-08-01T09:00:00Z"),))}))

    # `series` is declared by a distribution and named nowhere in `plumb.cli`; reaching it here
    # means discovery, the surface check and the bind all ran inside the tool's own entry point.
    assert main(["series", "show", str(store)]) == 0
    assert "S-1" in capsys.readouterr().out


def test_a_bare_group_is_not_a_command():
    """argparse's default accepts a group name alone and hands back no `func` at all."""
    parser = argparse.ArgumentParser(prog="plumb")
    groups = parser.add_subparsers(dest="group", required=True)
    from plumb.modules import _bind
    _bind(groups, Verb("example", "a group", verbs=(Verb("run", "do it", lambda a: 0),)), "example")

    with pytest.raises(SystemExit):
        parser.parse_args(["example"])


@pytest.mark.proves("mod2", depth="unit")
def test_render_says_what_a_module_adds_and_what_it_reaches():
    """`mod2` — the trust decision is over verbs, writes and reach together."""
    shown = render([Mounted("example", _declaration(network=True))])
    assert "example (run)" in shown
    assert "series 1" in shown
    assert "network: yes" in shown
    # The whole line, because the path is a substring of the entry's `repr` too — asserting it
    # loosely is how this passed while the listing printed `Wrote(where='...', what='...', ...)`.
    assert "writes ~/.local/share/example" in shown, shown


@pytest.mark.proves("mod2", depth="unit")
def test_a_write_that_is_not_a_footprint_entry_refuses_the_module():
    """`mod2-ur1`, `mod2-ur2`. The field is what `plumb footprint` reads, so a module that fills it
    with something else is refused here rather than printing a dataclass repr at an adopter."""
    refused = _checked(_declaration(writes=("~/.local/share/example",)), reserved={"board"}).refused
    assert "not footprint entries" in refused, refused


@pytest.mark.proves("mod2", depth="unit")
def test_a_refused_module_contributes_nothing_to_the_footprint(monkeypatch):
    """What it said about itself was not accepted; the one list somebody protects a machine from is
    not where unchecked text belongs."""
    from plumb import footprint

    declared = _declaration()
    monkeypatch.setattr("plumb.modules.discover",
                        lambda reserved: [Mounted("example", declared, refused="speaks `telemetry`")])
    assert footprint.from_modules() == ()


def test_a_refused_module_is_named_in_the_listing_rather_than_missing():
    shown = render([Mounted("example", _declaration(), refused="speaks `telemetry`")])
    assert "example" in shown and "NOT MOUNTED" in shown and "telemetry" in shown


def test_no_modules_is_an_ordinary_state_and_says_so():
    assert "installing one is the whole of enabling it" in render([])


@pytest.mark.proves("mod4", depth="wiring")
def test_a_module_from_outside_this_tree_is_discovered(tmp_path, monkeypatch):
    """The case that matters: a package plumb never heard of, mounting because it is installed.

    Everything else here hands `_checked` a declaration directly. This goes through
    `importlib.metadata`, which is the only part a third party actually relies on — and the part
    that cannot be exercised by a module shipped inside this distribution, because that one would
    mount even if discovery read a hardcoded list.
    """
    package = tmp_path / "stranger"
    package.mkdir()
    (package / "__init__.py").write_text(
        "from plumb.modules import Declaration, Verb\n"
        "DECLARATION = Declaration(name='stranger', version='0.1.0', surfaces={},\n"
        "                          verbs=(Verb('stranger', 'from outside', lambda a: 0),))\n",
        encoding="utf-8")
    dist = tmp_path / "stranger-0.1.0.dist-info"
    dist.mkdir()
    (dist / "METADATA").write_text("Metadata-Version: 2.1\nName: stranger\nVersion: 0.1.0\n",
                                   encoding="utf-8")
    (dist / "entry_points.txt").write_text(
        "[plumb.modules]\nstranger = stranger:DECLARATION\n", encoding="utf-8")

    monkeypatch.syspath_prepend(str(tmp_path))
    from plumb.modules import discover

    found = {m.name: m for m in discover(reserved={"board"})}
    assert "stranger" in found, f"a module installed outside the tree was not discovered: {found}"
    assert found["stranger"].refused == "", found["stranger"].refused
    assert found["stranger"].declaration.verbs[0].name == "stranger"


def test_a_module_that_will_not_import_is_named_and_the_rest_still_mount(tmp_path, monkeypatch):
    """`module-contract`: one broken extension never costs the tool.

    A half-installed environment has to degrade to the tool minus one capability rather than to no
    tool, so the failure is reported against the module that caused it and discovery carries on.
    """
    (tmp_path / "broken.py").write_text("raise RuntimeError('half installed')\n", encoding="utf-8")
    dist = tmp_path / "broken-0.1.0.dist-info"
    dist.mkdir()
    (dist / "METADATA").write_text("Metadata-Version: 2.1\nName: broken\nVersion: 0.1.0\n",
                                   encoding="utf-8")
    (dist / "entry_points.txt").write_text(
        "[plumb.modules]\nbroken = broken:DECLARATION\n", encoding="utf-8")

    monkeypatch.syspath_prepend(str(tmp_path))
    from plumb.modules import discover

    found = {m.name: m for m in discover(reserved=set())}
    assert "failed to import" in found["broken"].refused
    assert "half installed" in found["broken"].refused
    # The one this distribution ships is still there beside it.
    assert "series" in found and found["series"].refused == ""


@pytest.mark.proves("mod2", depth="unit")
def test_a_modules_declared_writes_reach_the_footprint(tmp_path, monkeypatch):
    """`mod2-ur2`, `ado5-ur5`. A module's state is invisible to whoever is deciding what to protect.

    It matters most at a handover: the release that moves a capability out of the core is the one
    where the core stops naming what that capability wrote, and the store does not stop existing.
    """
    from plumb import footprint
    from plumb.footprint import Wrote
    from plumb.modules import Declaration, Mounted, Verb

    declared = Declaration(
        name="example", version="1.0.0", surfaces={},
        verbs=(Verb("example", "a verb", lambda a: 0),),
        writes=(Wrote("~/.local/share/example", "records nothing else holds",
                      keep=True, irreplaceable=True),))
    monkeypatch.setattr("plumb.modules.discover", lambda reserved: [Mounted("example", declared)])

    found = footprint.from_modules()
    assert [w.where for w in found] == ["~/.local/share/example"]
    assert found[0].irreplaceable, "a module's disposition travels with its entry"


def test_a_module_that_writes_nothing_adds_no_section(tmp_path, monkeypatch):
    """A module with no state is the ordinary case, not a finding worth a heading."""
    from plumb import footprint
    from plumb.modules import Declaration, Mounted, Verb

    bare = Declaration(name="example", version="1.0.0", surfaces={},
                       verbs=(Verb("example", "a verb", lambda a: 0),))
    monkeypatch.setattr("plumb.modules.discover", lambda reserved: [Mounted("example", bare)])
    assert footprint.from_modules() == ()


@pytest.mark.proves("ado5", depth="wiring")
@pytest.mark.proves("mod2", depth="wiring")
def test_the_command_prints_what_modules_declared(tmp_path, capsys):
    """Through `plumb footprint`, because calling `from_modules()` proves only that it computes.

    The first version of this asserted the function's return value and passed with the function
    wired into nothing — every citation green, and `plumb footprint` printing no module at all.
    That is the shape of failure this tool was built to find, and it found it here.
    """
    from plumb import cli

    (tmp_path / "plumb.toml").write_text('adapter = "python"\nproduction = ["src"]\n')
    assert cli.main(["footprint", "--project", str(tmp_path)]) == 0
    shown = capsys.readouterr().out

    assert "added by modules" in shown, "the command does not print what modules declared"
    assert "the series file named on the command line" in shown, (
        "the series module's own declared write is not in the footprint the command prints")


def test_the_series_module_names_what_it_writes():
    """The one module this distribution ships declares its own history, and marks it."""
    from plumb_series import DECLARATION

    assert DECLARATION.writes, "the series module declares nothing it writes"
    assert any(w.irreplaceable for w in DECLARATION.writes), (
        "a history nothing else holds is not marked as such")
