"""The Python adapter, run out of process: resolved facts in, a manifest out.

The same contract the Java adapter has, and it exists for the same reason. Once Plumb is installed
as its own artifact, **the interpreter running the tool is not the interpreter running the
project** — the adapter has to import the project's code and its test framework, so it must run
where those live. That is a subprocess, and a subprocess needs a file rather than an object.

Symmetry is the point rather than a tidiness. Both adapters are handed the same file and answer
with the same document, so the launcher's job is identical in both directions and a third language
is a third reader of this file.

Usage: ``python -m plumb.adapters.python <run-file> <manifest-out>``
"""

from __future__ import annotations

import sys
from pathlib import Path

from plumb import runfile
from plumb.adapters.python import archetypes
from plumb.adapters.python.adapter import SuiteAborted, collect
from plumb.adapters.python.mutation import OptIn
from plumb.adapters.python.surface import ProductionSurface


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if len(args) < 2:
        print("usage: python -m plumb.adapters.python <run-file> <manifest-out>", file=sys.stderr)
        return 2

    facts = runfile.read(Path(args[0]))
    out = Path(args[1])

    # The only source. Nothing in the run can declare over the top, because the tool reads no spec
    # (`dev07-4-2`) — so this is where every language's archetype comes from, resolved by the launcher.
    for story, kind in (fact[:2] for fact in facts.get(runfile.ARCHETYPE, ()) if len(fact) >= 2):
        archetypes.declare(story, kind)

    surface = ProductionSurface.of(
        *runfile.values(facts, runfile.PRODUCTION),
        entry_points=runfile.values(facts, runfile.ENTRY_POINT),
    )
    mutation = runfile.values(facts, runfile.MUTATION) == ("true",)

    # Everything this prints is progress, and the manifest is the product. They go to different
    # places so a caller reading one is never handed the other (`dev07-5-3`).
    marker = runfile.values(facts, runfile.MARKER)
    try:
        manifest = collect(list(runfile.values(facts, runfile.PYTEST_ARG)),
                           surface=surface,
                           marker=marker[0] if marker else "proves",
                           mutation=OptIn(enabled=mutation),
                           report=lambda line: print(line, file=sys.stderr, flush=True),
                           edges_to=Path(out).with_name("edges.tsv"))
    except SuiteAborted as aborted:
        # No manifest is written: the launcher treats a missing one as the adapter being unable
        # to answer, which is exactly what this is.
        print(str(aborted), file=sys.stderr)
        return 2
    manifest.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
