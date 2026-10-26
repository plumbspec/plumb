"""One config file, read once by the core, for every language (chapter 3, chapter 0)."""

from pathlib import Path

import pytest

from plumb.config import JAVA, PYTHON, Config, InvalidConfig


@pytest.mark.proves("dev07-1-3", depth="component")
@pytest.mark.proves("dev00-1-2", depth="component")
def test_a_project_declares_itself_in_one_file_whatever_language_it_is(tmp_path):
    """The same reader serves both adapters, which is the only thing that makes one command
    possible: a Java project has no `pyproject.toml`, so a Python-shaped home could never have
    been the shared one."""
    (tmp_path / "plumb.toml").write_text(
        'adapter = "java"\n'
        'entry_points = ["App#handleRequest"]\n'
        'production = ["App"]\n'
        'sources = ["src/main/java"]\n'
        "[java]\ntests = \"build/classes\"\n"
    )
    config = Config.find(tmp_path)

    assert config.adapter == JAVA
    assert config.entry_points == ("App#handleRequest",)
    assert config.options == {"tests": "build/classes"}


@pytest.mark.proves("dev07-1-3", depth="unit")
@pytest.mark.proves("dev00-1-2", depth="unit")
def test_the_declared_values_stay_in_the_adapters_own_spelling():
    """`App#handleRequest` and `myapp.cli:main` name one idea in two languages (`dev07-1-3`).
    Inventing a third spelling would make every adapter translate out of a form none of them
    use, and the core never reads these — it reads the manifest."""
    java = Config.parse('adapter = "java"\nentry_points = ["a.b.C#run"]\n')
    python = Config.parse('entry_points = ["a.b:run"]\n')

    assert java.entry_points == ("a.b.C#run",)
    assert python.entry_points == ("a.b:run",)
    assert python.adapter == PYTHON, "the common case needs no declaration"


@pytest.mark.proves("dev07-5-1", depth="unit")
def test_a_project_that_declares_nothing_gets_an_empty_config_not_an_error(tmp_path):
    empty = Config.find(tmp_path)
    assert not empty.declares_anything
    assert empty.adapter == PYTHON and empty.mutation is False


@pytest.mark.proves("dev07-1-3", depth="unit")
def test_sources_default_to_production_where_the_two_are_the_same_question():
    """Python names directories for both. Java names classes for one and files for the other, so
    the split exists for the language that needs it rather than for all of them."""
    assert Config.parse('production = ["src/app"]\n').sources == ("src/app",)
    assert Config.parse('production = ["App"]\nsources = ["src"]\n').sources == ("src",)


def test_a_project_configured_the_old_way_is_told_where_it_moved(tmp_path):
    """Not a story claim — a migration. Silently ignoring `[tool.plumb]` would hand the project
    an empty config and a board reading `not-checked` for everything, which is indistinguishable
    from "you configured nothing" and is the one thing they did not do."""
    (tmp_path / "pyproject.toml").write_text('[tool.plumb]\nroots = ["src/app"]\n')

    told = Config.find(tmp_path).ignored
    assert any("[tool.plumb]" in note and "plumb.toml" in note for note in told), told

    (tmp_path / "plumb.toml").write_text('production = ["src/app"]\n')
    assert Config.find(tmp_path).production == ("src/app",), "with the new home present, it reads"


def test_a_malformed_declaration_is_refused_where_it_is_read(tmp_path):
    with pytest.raises(InvalidConfig, match="not valid TOML"):
        Config.parse("adapter = [unclosed\n")
    with pytest.raises(InvalidConfig, match="adapter"):
        Config.parse('adapter = "cobol"\n')
    with pytest.raises(InvalidConfig, match="list of strings"):
        Config.parse('entry_points = "a.b:run"\n')


@pytest.mark.proves("dev07-3-3", depth="component")
def test_the_launcher_picks_the_adapter_and_the_core_never_learns_which(tmp_path):
    """A third language is a branch in the launcher and nothing else — and the check that bites
    is on what the core *says*, not on what it imports.

    Every condition the gate can raise is printed to whoever ran the command, whatever language
    they are in. This caught the core telling a Java user to write a pytest marker: advice they
    cannot act on, and nothing about it revealed it was meant for somebody else.
    """
    from plumb.core.gate import CONDITIONS, UNLOCKS

    # Syntax that belongs to one language and would be nonsense in another.
    PARTICULAR = ("pytest", "@proves", ".py", ".java", "junit", "productionsurface", "def ")
    leaked = [
        (signal.code, field, token)
        for registry in (CONDITIONS, UNLOCKS)
        for signal in registry.values()
        for field in (signal.what, signal.next_step, signal.example)
        for token in PARTICULAR
        if token in field.lower()
    ]
    # And a *value* in one adapter's spelling, which no token list catches. `dev07-1-3` puts the file
    # in the core's vocabulary and the values in the adapter's, which is what lets one hint serve
    # every language — so a hint that shows a value has to show both. Found by boarding a real Java
    # project: `unlock.grounding` fired and handed a Java reader a Python module path, and every
    # word-based scan had said the prose was clean.
    leaked += [
        (signal.code, signal.example, "one language's entry-point spelling")
        for registry in (CONDITIONS, UNLOCKS)
        for signal in registry.values()
        if "entry_points = [" in signal.example and "#" not in signal.example
    ]
    assert not leaked, (
        "the core speaks to every adapter's users, so its prose may not name one language's "
        f"syntax: {leaked}"
    )


@pytest.mark.proves("dev07-3-3", depth="unit")
def test_an_unknown_adapter_fails_as_a_launch_not_as_a_verdict():
    """`LaunchFailed` and a failing story are different things: one is the tool unable to ask,
    the other is an answer. A board must never show the first as the second."""
    from plumb.launch import LaunchFailed, produce

    with pytest.raises(LaunchFailed, match="no adapter"):
        produce(Config(adapter="fortran"))


@pytest.mark.proves("dev08", depth="unit")
def test_declaring_an_adapter_both_ways_is_refused_rather_than_resolved():
    """Silently dropping one is how a board came to cover half a project.

    Blocks were taken as the complete list, so a top-level `adapter` beside them vanished — and a
    board covering one of two languages reads exactly like a board covering the project. Both
    readings of the file are defensible, so the file has to say which it means.
    """
    with pytest.raises(InvalidConfig) as refused:
        Config.parse('adapter = "java"\n\n[[adapters]]\nadapter = "python"\n')
    said = str(refused.value)
    assert "java" in said and "[[adapters]]" in said, "it names what is in conflict"
    assert "remove the top-level line" in said, "and what to write instead"


@pytest.mark.proves("dev08", depth="unit")
def test_both_unambiguous_forms_still_work():
    """The refusal is narrow: one adapter the ordinary way, or every adapter in a block."""
    blocks = Config.parse('[[adapters]]\nadapter = "java"\n\n[[adapters]]\nadapter = "python"\n')
    assert [a.adapter for a in blocks.adapters()] == ["java", "python"]
    assert [a.adapter for a in Config.parse('adapter = "java"\n').adapters()] == ["java"]


@pytest.mark.proves("dev07-1-4", depth="component")
def test_a_java_project_whose_modules_compile_separately_names_every_root(tmp_path):
    """A spec does not stop at a module boundary.

    One chapter can describe a system whose pieces compile separately, so a repository with two
    Maven modules and one spec must board both. Naming a single root means the board answers for a
    subset of what it observed while presenting itself as answering for all of it — `dev07-3-2`'s
    boundary, arriving from the other direction.
    """
    import os

    from plumb.launch import _test_roots

    for name in ("alpha", "beta"):
        (tmp_path / name).mkdir()
    config = Config.parse('adapter = "java"\n', root=tmp_path)

    one, roots = _test_roots(config, {"tests": "alpha"})
    assert len(roots) == 1 and one.endswith("alpha"), "a single path is unchanged"

    joined, roots = _test_roots(config, {"tests": ["alpha", "beta"]})
    assert len(roots) == 2
    assert joined.split(os.pathsep) == [str(tmp_path / "alpha"), str(tmp_path / "beta")], \
        "joined the way a classpath is, so the runner's other arguments stay positional"


@pytest.mark.proves("dev07-1-4", depth="unit")
def test_a_tests_key_that_is_not_a_path_is_refused_by_name(tmp_path):
    """`config.root / tests` died in a TypeError about PosixPath and list.

    The config reader refuses an unknown adapter by name, so the standard existed and this path
    had missed it — and a stack trace sends a reader into our source rather than to their file.
    """
    from plumb.launch import _test_roots

    (tmp_path / "alpha").mkdir()
    config = Config.parse('adapter = "java"\n', root=tmp_path)

    for bad in (7, ["alpha", 3], [], {"a": 1}):
        with pytest.raises(InvalidConfig) as refused:
            _test_roots(config, {"tests": bad})
        assert "`tests`" in str(refused.value), f"named the key for {bad!r}"

    with pytest.raises(InvalidConfig) as missing:
        _test_roots(config, {"tests": ["alpha", "gamma"]})
    assert "does not exist" in str(missing.value), "and an unbuilt module is said, not guessed at"
