"""What kind of claim each subject makes, handed over already resolved (``dev07-4-2``).

The archetype is never on the test, which would let the thing being judged pick its own gate, and
never inferred, which would make it guesswork. It arrives from ``[archetypes]`` in the project's
``plumb.toml``, seeded by :mod:`plumb.adapters.python.__main__` from the run file before the suite
starts. Silence means behavioral, so a project that never mentions archetypes is unchanged.

**It is not collected from an executing spec, and the reason is the whole design.** A spec authored
as Python modules could be collected by the run and hand this over, and for a while one did; no
other language has such a moment. Taking it from there made one fact reachable in one language and unreachable in every
other, and would mean the tool read a spec — which it does not (``dev07-4-2``, closed 2026-08-06). One
home, read the same way for every adapter, is what makes a structural claim provable on the JVM at
all.

This is process-global on purpose. It mirrors the runner's own lifecycle rather than threading a
registry through every caller, and :func:`reset` exists so a test can assert on a clean one.
"""

from plumb.core.manifest import ARCHETYPES, BEHAVIORAL, InvalidManifest

_declared: dict[str, str] = {}


def declare(story_id: str, archetype: str = BEHAVIORAL) -> None:
    """Record a subject's archetype. Called with what the project's config declared."""
    if archetype not in ARCHETYPES:
        raise InvalidManifest(
            f"{story_id}: archetype {archetype!r} is not one of {ARCHETYPES} — "
            "non-functional is not a third kind (dev07-4-2)"
        )
    _declared[story_id] = archetype


def declared() -> dict[str, str]:
    """Every archetype this run was given, as a snapshot."""
    return dict(_declared)


def archetype_of(story_id: str) -> str:
    """Behavioral is the default, so silence is a valid and complete answer."""
    return _declared.get(story_id, BEHAVIORAL)


def reset() -> None:
    _declared.clear()
