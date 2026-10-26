"""How the CLI discovers a module and links its verbs in (``dev08-1-1``–``dev08-1-4``).

**Asserted as a difference.** Each test builds a declaration that mounts and then breaks exactly
one thing, because a mount that refuses everything passes a suite as readily as one that refuses
the right thing. The clean declaration is asserted mounted first.

The refusals are the half worth proving. A mount that links whatever it is handed cannot support
`dev08-1-2`'s claim that trusting a module is a decision over a list — the list is only worth reading if
something is checked against it.
"""

from __future__ import annotations

import argparse

import pytest

from plumb.footprint import Wrote
from plumb.modules import (Argument, Declaration, Mounted, Verb, _checked, mount, published,
                           render)



class _entry:
    """One entry point, as `importlib.metadata` hands them over: a name and something to load."""

    def __init__(self, name, declared, value=""):
        self.name, self._declared = name, declared
        #: Where the entry point points. Two registrations of one distribution share it.
        self.value = value or f"{name}:declaration"

    def load(self):
        return self._declared


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


@pytest.mark.proves("dev08-1-2", depth="unit")
def test_a_module_may_not_mount_a_verb_the_core_owns():
    """`dev08-1-2-ur1`. It is refused and named, never silently renamed, and it never wins.

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


@pytest.mark.proves("dev08-1-1", depth="unit")
def test_a_surface_version_the_core_cannot_give_is_refused():
    """`dev08-1-1-ur2` — a version per surface, refused by name rather than half-working at runtime."""
    refused = _checked(_declaration(surfaces={"series": published()["series"] + 41}),
                       reserved=set()).refused
    assert "series" in refused and str(published()["series"]) in refused


@pytest.mark.proves("dev08-1-1", depth="unit")
def test_the_core_publishes_a_version_for_every_surface_it_names():
    """A surface with no version is one nobody can refuse by name."""
    assert all(isinstance(v, int) and v > 0 for v in published().values()), published()
    assert {"board", "series"} <= set(published())


@pytest.mark.proves("dev08-1-4", depth="wiring")
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


@pytest.mark.proves("dev08-1-4", depth="wiring")
@pytest.mark.proves("dev08-1-1", depth="wiring")
def test_the_one_cli_grows_the_verb(tmp_path, capsys):
    """`dev08-1-4` — through `plumb` itself, and this is the only test that proves the thing claimed.

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


@pytest.mark.proves("dev08-1-2", depth="unit")
def test_render_says_what_a_module_adds_and_what_it_reaches():
    """`dev08-1-2` — the trust decision is over verbs, writes and reach together."""
    shown = render([Mounted("example", _declaration(network=True))])
    assert "example (run)" in shown
    assert "series 1" in shown
    assert "network: yes" in shown
    # The whole line, because the path is a substring of the entry's `repr` too — asserting it
    # loosely is how this passed while the listing printed `Wrote(where='...', what='...', ...)`.
    assert "writes ~/.local/share/example" in shown, shown


@pytest.mark.proves("dev08-1-2", depth="unit")
def test_a_write_that_is_not_a_footprint_entry_refuses_the_module():
    """`dev08-1-2-ur1`, `dev08-1-2-ur2`. The field is what `plumb footprint` reads, so a module that fills it
    with something else is refused here rather than printing a dataclass repr at an adopter."""
    refused = _checked(_declaration(writes=("~/.local/share/example",)), reserved={"board"}).refused
    assert "not footprint entries" in refused, refused


@pytest.mark.proves("dev08-1-2", depth="unit")
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


@pytest.mark.proves("dev08-1-4", depth="wiring")
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


@pytest.mark.proves("dev08-1-2", depth="unit")
def test_a_modules_declared_writes_reach_the_footprint(tmp_path, monkeypatch):
    """`dev08-1-2-ur2`, `dev00-1-5-ur5`. A module's state is invisible to whoever is deciding what to protect.

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


@pytest.mark.proves("dev00-1-5", depth="wiring")
@pytest.mark.proves("dev08-1-2", depth="wiring")
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


@pytest.mark.proves("dev08-1-2", depth="unit")
def test_a_name_two_modules_claim_mounts_for_neither(monkeypatch):
    """`dev08-1-2-ur5`. Nothing checked this: `_checked` holds a declaration against the CORE's verbs
    and against nothing else, so two modules claiming one name were both accepted.

    What followed depended on the interpreter. At the floor argparse took the second silently and
    a verb the adopter never chose answered; at 3.13 it raised `conflicting subparser` out of
    building the parser, so `plumb board` — an unrelated command — died with a traceback.
    """
    from plumb.modules import discover

    def claimant(name):
        return Declaration(name=name, version="1.0.0", surfaces={},
                           verbs=(Verb("chores", "do the chores", lambda a: 0),))

    monkeypatch.setattr("plumb.modules._entry_points", lambda: [
        _entry("a-chores", claimant("a-chores")), _entry("z-chores", claimant("z-chores"))])

    found = {module.name: module for module in discover(reserved={"board"})}
    assert all(module.refused for module in found.values()), (
        f"a contested name mounted for somebody: "
        f"{[(n, m.refused) for n, m in found.items()]}")
    for name, module in found.items():
        other = "z-chores" if name == "a-chores" else "a-chores"
        assert other in module.refused, f"{name} is not told who else claims it: {module.refused}"


@pytest.mark.proves("dev08-1-2", depth="unit")
def test_an_uncontested_verb_is_untouched_by_somebody_elses_collision(monkeypatch):
    """The tool answers for every verb that is not contested (`dev08-1-2-sr2`). One bad pair of modules
    taking an unrelated third one down is the failure the refusal exists to avoid."""
    from plumb.modules import discover

    def claiming(module_name, verb):
        return Declaration(name=module_name, version="1.0.0", surfaces={},
                           verbs=(Verb(verb, "a verb", lambda a: 0),))

    monkeypatch.setattr("plumb.modules._entry_points", lambda: [
        _entry("a-chores", claiming("a-chores", "chores")),
        _entry("z-chores", claiming("z-chores", "chores")),
        _entry("ledger", claiming("ledger", "ledger"))])

    found = {module.name: module for module in discover(reserved={"board"})}
    assert not found["ledger"].refused, "an uncontested module lost its verb to somebody else"


@pytest.mark.proves("dev08-1-2", depth="wiring")
def test_the_listing_is_what_the_tool_mounted(monkeypatch, capsys):
    """`dev08-1-2-sr3`, through `plumb modules`.

    It called `discover(reserved=set())`, so the listing could never refuse anything for naming a
    core verb — and printed a module as mounted, with its verbs and writes, while every invocation
    of the tool refused it. Found by mounting a real contributed module that claims `support`:
    `plumb modules` said it was mounted and `plumb support` answered from the core.
    """
    from plumb.cli import main

    shadow = Declaration(name="shadow", version="0.1.0", surfaces={},
                         verbs=(Verb("board", "a module claiming a core verb", lambda a: 0),))
    monkeypatch.setattr("plumb.modules._entry_points", lambda: [_entry("shadow", shadow)])

    assert main(["modules"]) == 0
    shown = capsys.readouterr().out
    assert "NOT MOUNTED" in shown, (
        f"the listing claims a module is mounted that the tool refuses:\n{shown}")
    assert "the core already owns" in shown


@pytest.mark.proves("dev08-1-2", depth="unit")
def test_one_distribution_found_twice_is_not_two_modules(monkeypatch):
    """An editable install plus that tree's `src/` on `PYTHONPATH` — what CONTRIBUTING asks for —
    puts dist-info and egg-info both on the path and the same entry point is read from each.

    It listed the module twice and printed its writes twice. Once a contested name was refused, the
    same duplicate read as two modules fighting and took the only real one down with it: at the
    floor `plumb series` simply stopped existing.
    """
    from plumb.modules import discover

    declared = Declaration(name="series", version="1.0.0", surfaces={},
                           verbs=(Verb("series", "the real one", lambda a: 0),))
    twice = [_entry("series", declared), _entry("series", declared)]
    monkeypatch.setattr("plumb.modules._entry_points", lambda: twice)

    found = discover(reserved={"board"})
    assert len(found) == 1, f"one distribution was counted {len(found)} times"
    assert not found[0].refused, f"and it was refused for colliding with itself: {found[0].refused}"


# -- the handover (`dev08-1-5`) ------------------------------------------------------------------------

@pytest.mark.proves("dev08-1-5", depth="wiring")
def test_the_core_has_given_the_name_up():
    """`dev08-1-5-ur3`. The core keeps no copy against which the module could be said to be wrong.

    Asserted against the parser an adopter meets, because *the core no longer offers this* is a
    claim about the CLI and not about which files are in the tree.
    """
    from plumb.cli import build_parser

    groups = build_parser()._subparsers._group_actions[0].choices
    assert "support" not in groups, (
        "the core still owns `support`, so the module that took it is refused on every invocation")


@pytest.mark.proves("dev08-1-5", depth="wiring")
def test_a_module_may_now_take_the_name(monkeypatch, capsys):
    """`dev08-1-5-ur1`. The whole point: an adopter's verb keeps working across the release that moves
    it, so where the capability is built is not a thing they have to notice."""
    from plumb.cli import main

    reached = {}
    theirs = Declaration(
        name="support", version="0.1.0", surfaces={"transport": 1},
        verbs=(Verb("support", "ask, report or suggest", verbs=(
            Verb("file", "open a case", lambda a: (reached.update(ran=True), 0)[1]),)),),
        network=True)
    monkeypatch.setattr("plumb.modules._entry_points", lambda: [_entry("support", theirs)])

    assert main(["support", "file"]) == 0, capsys.readouterr().err
    assert reached.get("ran"), "the module's verb did not answer `plumb support file`"


@pytest.mark.proves("dev08-1-5", depth="unit")
def test_what_the_module_builds_on_did_not_leave_with_the_capability():
    """`dev08-1-5-sr2`. A module cannot speak a version of something the core stopped having, and a
    holder somebody runs themselves must not come to depend on whoever answers support."""
    from plumb.modules import published
    from plumb.transport import TRANSPORT_VERSION, for_capability  # noqa: F401 - it must import

    assert published().get("transport") == TRANSPORT_VERSION, (
        "the surface the support module declares it speaks went out with the capability")
