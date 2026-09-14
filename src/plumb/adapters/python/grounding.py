"""Chapter 3's fact: did the citing test drive the real system? (``dev07-1-4``)

Deliberately separate from :mod:`plumb.adapters.python.trace`. The trace reports **observations** — which
production frames ran, which files were read as data, whether anything ran under a declared
entry point. This module turns those into the single ``grounding`` value the manifest carries
and the gate reasons over. Keeping them apart is what let the vocabulary be reconsidered
without touching the tracer, and the vocabulary is still the unsettled part (``dev07-1-4``).

The order of questions is fixed by ``dev07-1-4`` and is not an implementation preference:
**inertness is asked first**, because it needs no entry points. A project whose spec is entirely
structural declares no production surface at all, and must still get a real fact rather than
``not-checked``.
"""

from plumb.core.manifest import (DISPATCHED, GROUNDED, INERT, NOT_CHECKED, UNGROUNDED,
                                 UNTOUCHED)
from plumb.adapters.python.surface import ProductionSurface
from plumb.adapters.python.trace import Trace

def fact(trace: Trace, surface: ProductionSurface) -> str:
    """Derive the grounding fact for one citing test.

    ``inert`` is not a weaker ``ungrounded``: it is a different answer to a different question.
    ``ungrounded`` means production code ran and reached no declared entry point — the
    orphaned-"done" fake. ``inert`` means the test **read** the artifact and ran none of it, which
    is what inspecting something as data looks like, and is the positive proof a structural story
    needs (``dev07-4-2``).

    **The read is half the claim, and it used to be missing.** `dev07-4-2` asks for a test that *read
    it rather than ran it*, and this returned ``inert`` for *ran none of it* alone — an absence,
    which `assert True` satisfies. A mirror of a presence has to be another presence, so a test
    that touched the artifact in no way at all is ``untouched`` and proves nothing.
    """
    if not surface.declares_production_code:
        # `dev07-1-4` says inertness needs no *entry points*, and that is true — but it does need
        # **roots**. With none declared, no frame is ever recognised as production, so an empty
        # call tree means "nobody said what production code is", not "the test ran none". Those
        # are different answers and only one of them is `inert`; reporting inert here would hand
        # every structural story a free pass on a project that declared nothing at all.
        return NOT_CHECKED
    if not trace.executed:
        # `inert` is a positive claim about the whole program, and this tracer is per-thread. With
        # other threads live, an empty call tree means "nothing ran *here*" — a different and much
        # weaker statement (`dev07-1-4`). Saying `inert` anyway would hand a passing grade to a
        # structural story whose test dispatched its work somewhere unwatched.
        if not trace.accounted_for_all_threads:
            return DISPATCHED
        # Asked **after** the thread question and before `inert` is granted. The order matters: a
        # test that dispatched its work has an unreliable read count too, so `untouched` would be
        # as much of an invention there as `inert` is.
        return UNTOUCHED if trace.touched_nothing else INERT
    if not surface.declares_entry_points:
        # Production code ran, but nothing says where the real system begins, so the question
        # cannot be asked. Surfaced, never silently skipped (`dev07-1-4`).
        return NOT_CHECKED
    # Deliberately NOT degraded to `dispatched`, and the asymmetry with the branch above is the
    # whole point. This adapter's evidence that work escaped is coarse — "some other thread was
    # alive" — which is sound for withholding `inert`, a *positive* proof that can grant a
    # structural story a pass it did not earn. Applied here it would mean any process with a
    # background thread could never report `ungrounded`, and `ungrounded` is `dev07-1-4`: orphaned
    # code cannot ground. Destroying the tool's headline check to fix a narrower error is the
    # wrong trade.
    #
    # The residual gap is real and bounded: a test that runs some production code locally *and*
    # dispatches its entry-point work elsewhere reads `ungrounded`, which overstates what was
    # observed. It costs a story its status and can never grant one. Closing it needs a *precise*
    # dispatch signal — a hand-off actually seen — which this tracer has no way to obtain and an
    # adapter observing `Executor.submit` would (`dev07-1-4`).
    return GROUNDED if trace.ran_under_entry_point else UNGROUNDED
