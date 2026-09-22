"""What a project declares about itself, in one file, read once by the core.

``plumb.toml`` is the single home. The **core owns configuration** and every adapter receives
resolved values, which is what makes one command work across languages: the launcher decides what
to run and how, and an adapter never learns a config format. That direction is deliberate — the
Java adapter hand-writes its JSON rather than take a dependency, and asking it to parse TOML as
well would buy a second format nobody needs.

This module sits **outside** ``plumb.core`` on purpose. It knows adapter names, and the core may
not (``dev07-3-3``, ``dev07-4-3``): the gate reads a manifest and nothing else, so a language named here
must never be a language named there. Launcher knowledge belongs beside the launcher.

The values are deliberately **adapter-native** (``dev07-1-3``). ``App#handleRequest`` and
``myapp.cli:main`` name the same idea in two languages, and flattening them into one invented
spelling would mean every adapter translating out of a form none of them use.
"""

from __future__ import annotations

try:
    import tomllib
except ModuleNotFoundError:
    # Below 3.11 the same parser rides inside the artifact rather than being installed beside it
    # (`plumb._vendor`). One reading of an adopter's file on every version Plumb runs on.
    from plumb._vendor import tomli as tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path

PYTHON, JAVA = "python", "java"
ADAPTERS = (PYTHON, JAVA)

CONFIG_NAME = "plumb.toml"


class InvalidConfig(ValueError):
    """Refused where it is read, naming the file and what it should say. The reader of these is
    somebody adopting the tool, so a refusal costs them one sentence and a guess costs them a
    board that is quietly wrong."""


@dataclass(frozen=True)
class Config:
    """One project's declaration. Absent everywhere means an empty one, never an error —
    the lowest input level still produces a real board (``dev07-5-1``)."""

    adapter: str = PYTHON
    #: Where the wired system begins, in the adapter's own spelling (``dev07-1-3``).
    entry_points: tuple[str, ...] = ()
    #: What counts as production code, in the adapter's own spelling.
    production: tuple[str, ...] = ()
    #: Where that code's **source** lives. Distinct from ``production`` because the two are not
    #: the same question in every language: Python names directories and can mutate what it
    #: traced, while Java names classes and mutation needs the ``.java`` files behind them.
    sources: tuple[str, ...] = ()
    #: ``dev07-2-2`` — off unless asked for.
    mutation: bool = False
    #: The series holder this project hands its history to. **Configuration, not a secret** — the
    #: address is the field worth seeing in a diff, and holding it here is what lets a wrong
    #: address fail as a wrong address (``ado6-sr4``). Anything secret never appears in this file
    #: and never in any file the working tree can sweep into a build artifact.
    endpoint: str = ""
    #: What this project calls its series. A name *inside* the store that holds it, never an
    #: access boundary (``dev07-6-2-ur8``) — so it is the project's to choose, is configuration
    #: rather than a secret, and is not something an operator has to issue.
    subject: str = ""
    #: The story-id namespaces this repository carries, longest-prefix wins (``dev07-3-2``). A spec is
    #: a namespace, never a directory: a directory belongs to whichever runner collects it, so it
    #: differs per language and vanishes the moment two languages share a repository.
    specs: tuple[str, ...] = ()
    #: ``[[adapters]]`` blocks, when a repository carries more than one language (``dev08``).
    extra_adapters: tuple = ()
    #: Where the handoff between two sessions lives (``dev03-1``). A path rather than a fixed
    #: location, because the two projects this was drawn from keep it in different places and one
    #: of them keeps it outside the repository entirely — which is policy, and policy is declared
    #: (``dev03``).
    cursor: str = ".plumb/next-session.txt"
    #: Which trees a session spans (``dev03``). One is the ordinary case and is the default; a
    #: project whose work routinely touches a sibling repository names both, and the ground is
    #: confirmed across all of them (``dev03-2``).
    repos: tuple[str, ...] = (".",)
    #: Where this project keeps its history, if it keeps one (``dev07-6-1``). Declaring it is the
    #: opt-in: a session brackets the history it finds here and appends the run it closed with,
    #: and a project that declares nothing keeps no history and loses nothing else (``dev10-3``).
    series: str = ""
    #: ``story id -> archetype`` (``dev07-4-2``, ``dev07-3-2``) — and below it, the other three facts a run
    #: cannot observe. Nothing enumerates a project's subjects, so these are the whole of what the
    #: tool is told about one, and they are **property tables rather than a list**: keyed by id,
    #: consulted when that id turns up in a run, and silent about every id it does not mention.
    #:
    #: Two things make that a distinction rather than a loophole, and both must hold. **Silence is
    #: correct** — a missing entry means the default, and an entry for an id nothing cites is inert
    #: rather than a phantom row on a board, so nothing here can desynchronise from a set the way a
    #: handed-over list does. And **the fact is ours, not theirs**: each says how to *judge* a
    #: subject, never what the subject says. A claim or a title would fail the second test — it
    #: restates what the project's own tracker owns, and drifts the moment they reword it.
    #:
    #: The earlier objection to naming an archetype here — *a second home for one fact, and second
    #: homes drift* — was true while the tool also read it from an executing spec. It reads one
    #: home now.
    archetypes: dict = field(default_factory=dict)
    #: ``story id -> (aspect, …)`` (``dev07-3-1``). A subject with several aspects has no single
    #: status, and no run can discover that it has them: an adapter sees citations, and a citation
    #: naming an aspect is not the subject declaring one.
    aspects: dict = field(default_factory=dict)
    #: ``story id -> reduction`` — how a subject's citations combine (`dev07-4-3-ur05`). A story takes the
    #: best of its citations; a decision must take the worst, because one clause of a falsifier
    #: firing breaches it whatever the others say.
    reduce: dict = field(default_factory=dict)
    #: ``story id -> lexicon`` — the words a subject says its status in. `proven` is the wrong word
    #: for a claim about the future, and a decision or a parameter is not a story.
    lexicon: dict = field(default_factory=dict)
    #: The adapter's own table, passed through untouched. Nothing here is interpreted, so a new
    #: adapter needs no change to this module.
    options: dict = field(default_factory=dict)
    #: The directory the config was found in; every relative path is relative to it, not to the
    #: caller's working directory.
    root: Path = field(default_factory=Path)

    @classmethod
    def find(cls, start: Path | str = ".") -> "Config":
        """Read ``plumb.toml`` from ``start``, or return an empty config.

        No upward search. A tool that walks parent directories will eventually find *somebody's*
        config, and a board derived from a file the user did not know they had is worse than one
        that says nothing was declared.
        """
        start = Path(start)
        path = start / CONFIG_NAME
        if not path.is_file():
            _refuse_stale_pyproject(start)
            return cls(root=start)
        return cls.parse(path.read_text(), root=start)

    @classmethod
    def parse(cls, text: str, root: Path | str = ".") -> "Config":
        try:
            table = tomllib.loads(text)
        except tomllib.TOMLDecodeError as bad:
            raise InvalidConfig(f"{CONFIG_NAME} is not valid TOML — {bad}") from bad

        # A top-level `adapter` beside `[[adapters]]` blocks is refused rather than resolved, and
        # the reason is that resolving it silently is what this used to do: the blocks were taken as
        # the complete list and the top-level declaration was dropped, so a project declaring Java
        # and adding a Python block got a board covering half of itself — `dev08`'s quietly-short
        # answer, reaching the config. Both readings are defensible, which is exactly why the file
        # has to say which it means: guessing here is how the loss happened.
        if "adapter" in table and table.get("adapters"):
            raise InvalidConfig(
                f"{CONFIG_NAME} declares `adapter = {table['adapter']!r}` and also [[adapters]] "
                f"blocks, and those mean different things. Put every adapter in a block — including "
                f"{table['adapter']!r} — and remove the top-level line. A project with one adapter "
                f"keeps writing it the ordinary way.")
        _refuse_misplaced_keys(table)
        adapter = table.get("adapter", PYTHON)
        if adapter not in ADAPTERS:
            raise InvalidConfig(
                f"{CONFIG_NAME}: adapter {adapter!r} is not one of {list(ADAPTERS)}"
            )
        production = _strings(table, "production")
        return cls(
            adapter=adapter,
            entry_points=_strings(table, "entry_points"),
            production=production,
            # Python names directories for both, so defaulting is right there and merely
            # convenient elsewhere — an adapter that needs them apart says so.
            sources=_strings(table, "sources") or production,
            mutation=bool(table.get("mutation", False)),
            endpoint=str(table.get("endpoint", "")),
            subject=str(table.get("subject", "")),
            specs=_strings(table, "specs"),
            cursor=str(table.get("cursor", ".plumb/next-session.txt")),
            repos=_strings(table, "repos") or (".",),
            series=str(table.get("series", "")),
            extra_adapters=tuple(table.get("adapters", ())),
            archetypes=dict(table.get("archetypes", {})),
            # Tuples, because the manifest's own field is one and a list here would make the two
            # halves of one fact differ by container.
            aspects={k: tuple(v) for k, v in dict(table.get("aspects", {})).items()},
            reduce=dict(table.get("reduce", {})),
            lexicon=dict(table.get("lexicon", {})),
            options=table.get(adapter, {}),
            root=Path(root),
        )

    def adapters(self) -> tuple["Config", ...]:
        """One config per adapter this project declares (``dev08``).

        Production code and entry points are adapter-native (``dev07-1-3``) — a Java package and a
        Python module path are not the same kind of name — so they cannot be shared across
        languages and each adapter gets its own block. The config grows a repeated table rather
        than a second file, because one ``plumb.toml`` is the single home and two would be two
        sources of truth about one project.

        A project declaring one adapter the ordinary way gets itself back, so nothing about the
        single-language path changes.
        """
        if not self.extra_adapters:
            return (self,)
        return tuple(
            replace(self, adapter=block.get("adapter", PYTHON),
                    entry_points=tuple(block.get("entry_points", ())),
                    production=tuple(block.get("production", ())),
                    sources=tuple(block.get("sources", ())) or tuple(block.get("production", ())),
                    options=block.get(block.get("adapter", PYTHON), {}),
                    extra_adapters=())
            for block in self.extra_adapters
        )

    def resolved(self, *paths: str) -> tuple[Path, ...]:
        """Project-relative paths made absolute against the config's own directory."""
        return tuple((self.root / p).resolve() for p in paths)

    @property
    def marker(self) -> str:
        """What this project calls a citation. A convention, not a mechanism — a project citing
        315 requirements under its own name should not have to rewrite them all before the tool
        will read any of them."""
        return self.options.get("marker", "proves")

    @property
    def declares_anything(self) -> bool:
        return bool(self.entry_points or self.production)


def _strings(table: dict, key: str) -> tuple[str, ...]:
    value = table.get(key, ())
    if isinstance(value, str) or not all(isinstance(v, str) for v in value):
        raise InvalidConfig(f"{CONFIG_NAME}: {key} must be a list of strings, got {value!r}")
    return tuple(value)


#: Keys that belong at the top level and mean nothing inside a table. Listed rather than derived
#: from the dataclass, because a table may legitimately carry a key of its own with the same
#: spelling, and refusing that would be worse than the silence this replaces.
TOP_LEVEL_ONLY = ("specs", "production", "sources", "entry_points", "mutation",
                  "endpoint", "subject", "adapter")


def _refuse_misplaced_keys(table: dict) -> None:
    """A key written under a `[section]` belongs to that section, and is never looked for again.

    TOML has no way to say *I meant this at the top level*, and the emitted config ends with an
    adapter section — so appending `specs = ["REQ"]` at the end, which is where anyone would append
    it, files it under `[java]` where nothing reads it. What that costs is not an error but a
    silence: the run proceeds as though the key had never been written, and the board it produces is
    indistinguishable from one where nobody meant to write it. Measured by walking into it — three
    subjects became one, with no output changed anywhere.

    So it is said instead. This is `dev07-3-3`'s rule — a board must not quietly answer for less than
    it was asked — applied one layer up, at the file that decides what it was asked.
    """
    for name, value in table.items():
        if not isinstance(value, dict):
            continue
        for key in TOP_LEVEL_ONLY:
            if key in value:
                raise InvalidConfig(
                    f"{CONFIG_NAME}: `{key}` is written inside [{name}], where nothing reads it — "
                    f"in TOML a key below a section header belongs to that section. Move it above "
                    f"the first `[` in the file.")


def _refuse_stale_pyproject(start: Path) -> None:
    """A project that declared itself the old way is told where its declaration moved.

    Silently ignoring ``[tool.plumb]`` would hand that project an empty config and a board reading
    `not-checked` for everything — technically honest, and indistinguishable from "you configured
    nothing". They configured something; it is in the wrong file, and only this knows that.
    """
    pyproject = start / "pyproject.toml"
    if not pyproject.is_file():
        return
    try:
        table = tomllib.loads(pyproject.read_text())
    except tomllib.TOMLDecodeError:
        return
    if table.get("tool", {}).get("plumb"):
        raise InvalidConfig(
            f"{pyproject} still declares [tool.plumb], and configuration now lives in "
            f"{CONFIG_NAME} beside it — one file, because the core reads it for every language "
            "and a Java project has no pyproject.toml. Move the keys across and delete the table"
        )
