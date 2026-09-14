"""The launcher's resolved facts: written here, read by whichever adapter was chosen.

``kind<TAB>value…`` per line, and deliberately not a config format. The launcher has already
decided everything — which entry points, which production code, which stories are structural — so
what crosses this boundary is answers, not questions. An adapter that needs a parser has been
given the wrong job, which is why the Java side's reader is one ``split("\\t")``.

It exists because **an adapter may not run in this process**. Java never does; Python does not
either once the tool is installed as an artifact and the project has its own interpreter. A file
is what survives that boundary, and using the same one for both keeps the two adapters honest
about being the same shape.
"""

from pathlib import Path

from plumb import __version__

ENTRY_POINT, PRODUCTION, ARCHETYPE, PYTEST_ARG, MUTATION, VERSION = (
    "entrypoint", "production", "archetype", "pytest", "mutation", "version")
MARKER = "marker"


def write(config, path: Path, *, pytest_args: tuple[str, ...] = (), mutation: bool = False,
          surface: bool = True) -> Path:
    """Resolve everything an adapter could need and write it down.

    Archetypes are included because resolving them is the **core's** job (``dev07-3-2``): they are
    declared on the story in the spec, and an adapter keeping its own copy is a second home for
    something one home owns. A run that executed the spec has been told them directly; anything
    else takes them from config, which is the interim the archetype question has not settled.

    ``surface`` says whether the production surface is actually being *watched* this run. It is not
    the same question as whether one was declared, and conflating them makes the strongest available
    claim in the case where nothing looked: `inert` is asserted from the **absence** of a production
    hit (``dev07-1-4``), so an adapter told a surface exists while nothing reports execution against it
    reads every test as having run no production code. Where the instrument is not running the
    surface is not named, and `inert` is withheld for want of a declaration — which is the answer
    `dev07-1-4` already gives, arrived at honestly.
    """
    from plumb.adapters.python import archetypes

    resolved = {**config.archetypes, **archetypes.declared()}
    lines = [f"{ENTRY_POINT}\t{e}" for e in config.entry_points]
    lines += [f"{PRODUCTION}\t{p}" for p in config.production] if surface else []
    lines += [f"{ARCHETYPE}\t{story}\t{kind}" for story, kind in sorted(resolved.items())]
    lines += [f"{PYTEST_ARG}\t{a}" for a in pytest_args]
    lines.append(f"{MUTATION}\t{'true' if mutation else 'false'}")
    # The tool's own version, so an adapter never carries a second copy of it. The jar ships
    # inside the artifact, so a hardcoded version there is a claim about *this* tool made by a
    # file that cannot see it — and it goes stale on the first release that forgets to edit it.
    lines.append(f"{VERSION}\t{__version__}")
    lines.append(f"{MARKER}\t{config.marker}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    return path


def read(path: Path) -> dict[str, list[list[str]]]:
    """Facts by kind. A missing file reads as nothing declared, never as an error (``dev07-5-1``)."""
    found: dict[str, list[list[str]]] = {}
    path = Path(path)
    if not path.is_file():
        return found
    for line in path.read_text().splitlines():
        fields = line.split("\t")
        if len(fields) > 1:
            found.setdefault(fields[0], []).append(fields[1:])
    return found


def values(facts: dict[str, list[list[str]]], kind: str) -> tuple[str, ...]:
    return tuple(fact[0] for fact in facts.get(kind, ()))
