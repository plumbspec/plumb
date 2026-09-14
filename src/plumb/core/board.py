"""Chapter 5's outbound edge: the board.

The core's derived, tool-facing report — per story, its status, its achieved depth vector, and
whatever the run could not check (``dev07-5-1``). **The manifest is internal; the board is the public
contract**, so this is the thing other tools are allowed to depend on.

Emitted in a documented, neutral JSON serialization (``dev07-5-3``) under an explicit
``board_version``, because external tools depend on the shape: it evolves compatibly and a
breaking change is a new version, never a silent shift (``dev07-5-3``). The version is deliberately
its own, separate from the manifest's — one is a public contract and the other is an internal
one, and tying them would make an internal refactor look like a breaking change.

Nothing here decides anything. It renders what the gate derived, so the number a consumer reads
is the number the gate produced.
"""

import json
import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone

from plumb.core.gate import (
    Verdict,
    derive_all,
    label,
    prose,
    run_conditions,
    unlocks,
)
from plumb.core.manifest import Manifest

BOARD_VERSION = 3

_DIGITS = re.compile(r"(\d+)")


def natural_key(story_id: str) -> tuple:
    """Order ids the way a reader expects: ``flow-2`` before ``flow-10``.

    Presentation only. It never affects a status, and it **requires** no shape — digit runs
    compare as numbers and everything else as text, so ``PROJ-7`` and ``SHEET-42`` order
    sensibly too. That keeps ``dev07-3-2``'s promise intact: the id stays opaque and no catalog is
    needed. Lexical ordering is the alternative, and it puts ``flow-10`` in the middle of the
    single digits, which reads as a bug in the board rather than a property of sorting.
    """
    return tuple(
        (1, int(part)) if part.isdigit() else (0, part)
        for part in _DIGITS.split(story_id)
        if part
    )


def _mutation(fact) -> dict | None:
    """A score the consumer can put in proportion, never a word it has to interpret."""
    if fact is None:
        return None
    # `survived` is the count and `survivors` the names. Both, because a consumer that only wants
    # the shortfall should not have to length-check a list, and an adapter that reports the
    # shortfall without naming it leaves the names empty while the count still answers (`dev07-5-1`).
    return {"total": fact.total, "killed": fact.killed, "survived": fact.survived,
            # Survivors nobody reached, said apart. A mutant on a line this story's tests never
            # enter is not a missing assertion, and a ratio that mixes the two answers neither
            # question (`dev07-2-4`).
            "unreached": fact.unreached,
            "survivors": [{"operator": s.operator, "where": s.where, "file": s.file,
                           "line": s.line, "reached": s.reached}
                          for s in fact.survivors]}


def _signal(code: str, n: int | None = None) -> dict:
    """Emit a code's tagged parts. An unknown code still emits, carrying only itself — a
    consumer keying off the code is not broken by prose it has never seen (``dev07-5-2``).

    Resolved against the whole vocabulary rather than against the registry the caller happens to
    be iterating (``dev07-5-2``). Passing the registry in was the defect: a story's conditions were
    looked up in ``CONDITIONS``, and the three commonest of them are defined among the run-level
    ones, so every unproven story emitted its reason as a code with three empty strings beside it.
    """
    known = prose(code)
    fill = (lambda s: s.format(n=n)) if n is not None else (lambda s: s)
    return {
        "code": code,
        "what": fill(known.what) if known else "",
        "next_step": known.next_step if known else "",
        "example": known.example if known else "",
    }


def _rendered_at() -> str:
    """The moment this document was written, spelled as the adapters spell a measurement."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class Board:
    """The rendered result, ready to emit (``dev07-5-1``)."""

    verdicts: dict[str, Verdict] = field(default_factory=dict)
    manifest: Manifest = field(default_factory=Manifest)
    board_version: int = BOARD_VERSION
    #: The story-id namespaces this project declared (`dev07-3-2`), so an id belonging to none can be
    #: named rather than left looking authoritative (`dev07-4-1`).
    namespaces: tuple = ()
    #: Adapters this project declares that did not run (`dev07-3-3`). A board missing a language is
    #: part of an answer, and saying so is what stops it reading as the whole one.
    absent_adapters: tuple = ()
    #: Adapters that ran and produced a manifest with their observer dead (`dev07-1-3`). The suite's
    #: results stand; the wiring question went unasked, and for a reason that is not the project's.
    blind_adapters: tuple = ()
    #: What wrote this document, and when (`dev07-5-3`). Render time, never measurement time: a board is
    #: rendered once by one tool however many runs' facts it carries, so these are true of the
    #: document itself where a single `when` would be `dev07-3-1`'s false claim one field over.
    #: `rendered_by` is handed in rather than read: the core knows no version of its own, and
    #: reaching for one is exactly the import that stops it being language-blind (`dev07-3-3`).
    rendered_by: str | None = None
    rendered_at: str | None = None

    @classmethod
    def render(cls, manifest: Manifest, namespaces=(), absent_adapters=(),
               blind_adapters=(), scope: str | None = None,
               rendered_by: str | None = None, rendered_at: str | None = None) -> "Board":
        """Derive, and show the part asked for.

        **Scope narrows the verdicts and never the manifest** (`dev07-5-1`). The caller used to filter
        the document and hand the smaller one over, which made every run-level fact a fact about
        the *view*: the first such fact to read the story set — `dev07-5-2`'s *tests ran and nothing
        was cited* — then fired on any scope that matched nothing, telling a project with a hundred
        citations that it had none. The run observed what it observed whatever you asked to see.
        """
        shown = manifest if scope is None else replace(
            manifest, stories={sid: story for sid, story in manifest.stories.items()
                               if sid.startswith(scope)})
        return cls(verdicts=derive_all(shown), manifest=manifest,
                   namespaces=tuple(namespaces), absent_adapters=tuple(absent_adapters),
                   blind_adapters=tuple(blind_adapters),
                   rendered_by=rendered_by, rendered_at=rendered_at or _rendered_at())

    def as_dict(self) -> dict:
        return {
            "board_version": self.board_version,
            # What produced this document and when — `dev07-5-3`. `board_version` describes the shape
            # and says nothing about the producer, so without these a consumer holding a file has
            # nothing to date it by. Render time, not measurement time: measurement stays on the
            # fact, below, for `dev07-3-1`'s reason.
            "rendered_by": self.rendered_by,
            "rendered_at": self.rendered_at,
            # Which instruments made these measurements — plural, because a board may carry facts
            # from more than one adapter and two facts are comparable only when the same kind of
            # observer produced them (`dev07-3-1`, `dev07-3-1`). Empty means none was reported.
            "observers": [
                {"adapter": o.adapter, "version": o.version,
                 "runtime": o.runtime, "mechanism": o.mechanism}
                for o in sorted({c.observer for s in self.manifest.stories.values()
                                 for c in s.citations if c.observer is not None},
                                key=lambda o: (o.adapter, o.version, o.runtime, o.mechanism))
            ],
            # How much the run actually saw, carried through as the fact rather than only as the
            # conclusion drawn from it — evidence, not opinion (`dev07-3-2`, `dev07-5-1`). `null` is *not
            # reported* and a consumer must not read it as none.
            "observed_tests": self.manifest.observed_tests,
            # What this run says about itself. Distinct from a story's conditions because it
            # attaches to the run, which is the only place the "nothing was observed" fact can
            # live — there is no story to hang it on (`dev07-5-2`).
            "conditions": [_signal(c) for c in
                           run_conditions(self.manifest, self.namespaces,
                                          self.absent_adapters, self.blind_adapters)],
            "stories": {
                sid: {
                    "status": v.status,
                    # The word a reader sees, beside the code a consumer keys off (`dev07-5-2`).
                    # Never a second status: it is derived from the one above plus a condition
                    # already carried, so nothing here can say what the derivation did not.
                    "label": label(v, self.manifest.stories[sid].lexicon),
                    "achieved": list(v.achieved),
                    # Each surfaced condition carries its stable code beside its prose, and
                    # the prose is split into what happened, what to do, and what that looks
                    # like. The code is the promise; the rest may be reworded (`dev07-5-2`).
                    "conditions": [_signal(c) for c in v.conditions],
                    # A subject with several aspects has no single status, and says so with
                    # `aspects.per-aspect` — which is an instruction to read *these*. Without
                    # them the code told a consumer to go and look at something the machine
                    # readable board did not carry, so the text board showed three decisions'
                    # worth of detail and `--json` showed one word and a dead end. `null` where
                    # the subject has one aspect, which is every ordinary story (`dev07-3-1`).
                    "aspects": None if not v.aspects else {
                        aspect: {"status": per.status,
                                 "label": label(per, self.manifest.stories[sid].lexicon),
                                 "conditions": [_signal(c) for c in per.conditions]}
                        for aspect, per in v.aspects.items()
                    },
                    # `null` where the opt-in was off, which is *not asked* rather than a pass —
                    # a capability whose result the board never shows is one a reader has to go
                    # and find in the manifest (`dev07-2-4`, `dev07-3-3`).
                    "mutation": _mutation(self.manifest.stories[sid].mutation),
                    # Evidence, not opinion: what was proven and *how*, so a reviewer can act
                    # on it rather than take the verdict on trust (`dev07-5-1`).
                    "evidence": [
                        {
                            "test": c.test,
                            "depth": c.depth,
                            "result": c.result,
                            "grounding": c.grounding,
                            # Which declared entry point this test came in through, outermost
                            # (`dev07-1-4`). `grounding` says it reached the wired system; this says
                            # where it came in, which a flat project-wide entry-point set cannot
                            # otherwise answer. `null` is *not reported*, never *entered by none*.
                            "entered_through": (list(c.entered_through)
                                                if c.entered_through is not None else None),
                            # When this fact was measured, which is not when the board was
                            # rendered (`dev07-5-3`). Recorded by the adapter and dropped here until
                            # major 3. `null` is *not reported* and is never read as now.
                            "when": c.when,
                            "ref": c.ref,
                            # Which aspect this citation is about (`dev07-3-1`). `null` means the
                            # only one there is, which is the ordinary story. Dropping it made
                            # the per-aspect verdicts above unauditable — a reader could see
                            # that `falsifier` was unproven and not which test said so.
                            "about": c.about,
                        }
                        for c in self.manifest.stories[sid].citations
                    ],
                }
                for sid, v in sorted(self.verdicts.items(), key=lambda kv: natural_key(kv[0]))
            },
            # What this run has earned the right to suggest next, derived from the run itself
            # rather than advertised (`dev07-5-2`).
            "unlocks": [
                _signal(code, n)
                for code, n in sorted(unlocks(self.verdicts, self.manifest).items())
            ],
        }

    def to_json(self, indent: int | None = 2) -> str:
        # Not ``sort_keys``: that would re-impose the lexical order this deliberately avoids.
        # Insertion order is already deterministic, so emitted boards still diff cleanly.
        return json.dumps(self.as_dict(), indent=indent)

    def summary(self) -> dict[str, int]:
        """Counts per status — an aggregate that asserts nothing the source does not."""
        counts: dict[str, int] = {}
        for v in self.verdicts.values():
            counts[v.status] = counts.get(v.status, 0) + 1
        return counts
