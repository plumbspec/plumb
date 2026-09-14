"""What the project declares about itself: where its production code lives, and where the
wired system begins (``dev07-1-3``).

Deliberately small and stable. This is *not* a per-story map of code — that is the artifact
that rots and the reason grounding is computed from a call tree instead.
"""

from dataclasses import dataclass
from pathlib import Path
from types import CodeType


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
        """``/…/pkg/mod.py`` + ``fn`` → ``pkg.mod:fn`` — the citable name of a frame."""
        path = Path(code.co_filename)
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
                return f"{root.stem}:{code.co_qualname}"
            if resolved.is_relative_to(root):
                rel = resolved.relative_to(root).with_suffix("")
                parts = [root.name, *rel.parts]
                if parts[-1] == "__init__":
                    parts.pop()
                return f"{'.'.join(parts)}:{code.co_qualname}"
        return f"{path.stem}:{code.co_qualname}"
