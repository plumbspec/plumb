"""What the project declares about itself: where its production code lives, and where the
wired system begins (``dev07-1-3``).

Deliberately small and stable. This is *not* a per-story map of code — that is the artifact
that rots and the reason grounding is computed from a call tree instead.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import CodeType


#: Segments CPython invents for an expression that declares nothing of its own. Whether one gets a
#: frame is the runtime's choice, and the runtime has changed its mind: comprehensions had frames
#: until 3.12 inlined them, so a name carrying one moves when the interpreter does
#: (``dev07-1-3-ur09``).
INVENTED = frozenset({"<lambda>", "<listcomp>", "<setcomp>", "<dictcomp>", "<genexpr>"})

#: What CPython puts between a definition and one nested inside it. Structural rather than
#: invented — the definitions either side of it are both declared in the source.
NESTED = "<locals>"

#: The frame name module-level code runs under, and what a definition folds to when nothing
#: encloses it.
MODULE = "<module>"


def definition(qualname: str) -> str:
    """The source definition a frame belongs to (``dev07-1-3-ur08``).

    Truncated at the **first** invented segment rather than the last: an expression cannot contain
    a declaration, so everything past one is inside it, and the nearest thing the source declares
    is what precedes it. A lambda at module level folds to ``<module>`` — it is still somewhere.

    **What this widens.** A generator resumed somewhere its definition never ran — stashed outside
    a door and consumed inside one — now reports the definition that created it, so that definition
    counts as having run wired. Mutation then scopes to all of it, and the part no citing test
    entered comes back as ``unreached``, which is the category that answers for scope being per
    definition rather than per line (``dev07-2-4``). Every runtime reports it the same way, which
    is what this rule is for.
    """
    parts = qualname.split(".")
    for at, part in enumerate(parts):
        if part in INVENTED:
            kept = parts[:at]
            while kept and kept[-1] == NESTED:
                kept.pop()
            return ".".join(kept) or MODULE
    return qualname

def qualname_of(code: CodeType) -> str:
    """A frame's qualified name, from the runtime where it reports one and from the source where
    it does not (``dev07-1-3-ur08``).

    ``co_qualname`` arrived in 3.11. Below it a code object carries only its bare ``co_name``, so
    the name is read out of the file the frame came from — which is where the definitions were
    declared in the first place, and the only account of them that does not vary by interpreter.

    What comes back below 3.11 is already the **enclosing definition**: a runtime that cannot name
    a comprehension cannot be asked to, and the definition containing it is the answer either way.
    :func:`definition` is idempotent, so both paths pass through it unchanged.
    """
    reported = getattr(code, "co_qualname", None)
    return reported if reported is not None else _from_source(code)


def _starts(node) -> int:
    """Where the runtime says a definition begins.

    ``co_firstlineno`` is the **first decorator** where there is one and the ``def`` where there is
    not, while the parse tree puts ``lineno`` on the ``def`` in both cases. Indexing from the ``def``
    alone therefore misses every decorated definition — silently, and on exactly the definitions a
    project is most likely to have declared as a door.
    """
    return min([node.lineno, *(d.lineno for d in node.decorator_list)])


@lru_cache(maxsize=None)
def _definitions(filename: str) -> tuple:
    """``(first line, last line, qualified name)`` for every definition a file declares.

    Named the way CPython names them — ``Class.method``, and ``outer.<locals>.inner`` for a
    closure — because this stands in for what the runtime would have reported.
    """
    try:
        tree = ast.parse(Path(filename).read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError, ValueError):
        return ()
    found: list = []

    def walk(node, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                name = prefix + child.name
                found.append((_starts(child), child.end_lineno, name))
                walk(child, name + ".")
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + child.name
                found.append((_starts(child), child.end_lineno, name))
                walk(child, name + ".<locals>.")
            else:
                walk(child, prefix)

    walk(tree, "")
    return tuple(found)


def _from_source(code: CodeType) -> str:
    """The innermost definition whose lines contain this frame's, or ``<module>`` outside them."""
    line, best = code.co_firstlineno, None
    for start, end, name in _definitions(code.co_filename):
        if start <= line <= end and (best is None or start >= best[0]):
            best = (start, name)
    return best[1] if best is not None else MODULE

@dataclass(frozen=True)
class ProductionSurface:
    """The declared surface: production roots, and the entry points within them.

    ``entry_points`` are ``"module.path:function"`` strings — the form is the adapter's to
    choose (``dev07-1-3``); the core never sees it, only the resulting fact.
    """

    roots: tuple[Path, ...]
    entry_points: frozenset[str] = frozenset()

    @classmethod
    def of(cls, *roots: Path | str, entry_points: tuple[str, ...] = ()) -> "ProductionSurface":
        return cls(
            roots=tuple(Path(r).resolve() for r in roots),
            entry_points=frozenset(entry_points),
        )

    @classmethod
    def from_config(cls, config) -> "ProductionSurface":
        """Take the surface from the project's declaration, already read (``dev07-1-3``).

        Config rather than a decorator on entry functions, which was the other candidate
        (``dev07-1-3``). A decorator makes production code **import the verifier**, so the artifact
        under test carries a dependency on the thing judging it — a real adoption cost, and
        backwards for a tool whose whole claim is that it observes from outside. Config costs
        the project nothing at runtime and leaves the source untouched.

        The file is read by the launcher, not here: one reader for every language is what lets a
        Java project be configured the same way, and an adapter that reads its own config is an
        adapter that has to agree with all the others about the format.

        A project declaring nothing gets an empty surface, which is `not-checked` rather than an
        error: absent input degrades and surfaces (``dev07-5-1``).
        """
        return cls(
            roots=config.resolved(*config.production),
            entry_points=frozenset(config.entry_points),
        )

    @property
    def declares_production_code(self) -> bool:
        """False means nothing here can be judged: with no roots, no frame is ever *ours*, so
        an empty call tree means "we were told nothing", not "the test ran nothing"."""
        return bool(self.roots)

    @property
    def declares_entry_points(self) -> bool:
        """False means grounding cannot be computed — the `not-checked` case (``dev07-1-4``)."""
        return bool(self.entry_points)

    def owns(self, filename: str) -> bool:
        """Is this file production code? Path containment, not import machinery."""
        if not filename or filename.startswith("<"):
            return False
        try:
            path = Path(filename).resolve()
        except (OSError, ValueError):
            return False
        return any(path.is_relative_to(root) for root in self.roots)

    def is_entry_point(self, code: CodeType) -> bool:
        return self.qualify(code) in self.entry_points

    def locate(self, name: str) -> Path | None:
        """``pkg.mod:fn`` → ``/…/pkg/mod.py`` — :meth:`qualify` run backwards.

        It lives beside its inverse because the naming scheme is one decision, not two, and a
        reader who changes ``qualify`` has to be looking at the thing that undoes it. ``None``
        means the name came from outside the declared roots, which :meth:`qualify` renders with a
        bare stem and cannot be resolved back to a file.
        """
        module = name.partition(":")[0].split(".")
        for root in self.roots:
            # The file-root case, run backwards: `friction_api:main` names the root itself, so
            # there is no directory to walk into and the stem is the whole module part.
            if root.is_file():
                if module == [root.stem]:
                    return root
                continue
            if module[0] != root.name:
                continue
            rest = module[1:]
            for candidate in (root.joinpath(*rest).with_suffix(".py") if rest else None,
                              root.joinpath(*rest, "__init__.py")):
                if candidate is not None and candidate.is_file():
                    return candidate
        return None

    def qualify(self, code: CodeType) -> str:
        """``/…/pkg/mod.py`` + ``fn`` → ``pkg.mod:fn`` — the citable name of a frame.

        The frame half is the **definition** it belongs to, never whatever the runtime happened to
        give a frame of its own (``dev07-1-3-ur08``). This is the one place a frame becomes a name,
        so the rule reaches the trace, the edges, the door match and mutation's scope alike
        (``dev07-1-3-sr08``).
        """
        path = Path(code.co_filename)
        named = definition(qualname_of(code))
        # Resolve once: this runs per traced frame, and resolving is a syscall.
        resolved = path.resolve()
        for root in self.roots:
            # A root may be a **file**, not only a directory. A project whose tests sit beside its
            # code has to name files — declaring the directory would put the tests inside a
            # production root, where every test frame counts as production and a structural story
            # can never read `inert`. That is a legitimate declaration, and it used to crash here:
            # a frame in the root itself made `relative_to` yield `.`, whose empty stem raises. It
            # surfaced as *every test touching that file failed*, which read on the board as
            # evidence that had failed rather than a tool that had fallen over.
            if resolved == root:
                return f"{root.stem}:{named}"
            if resolved.is_relative_to(root):
                rel = resolved.relative_to(root).with_suffix("")
                parts = [root.name, *rel.parts]
                if parts[-1] == "__init__":
                    parts.pop()
                return f"{'.'.join(parts)}:{named}"
        return f"{path.stem}:{named}"
