"""Chapter 4's check: does the story's tests actually *check* the code? (``dev07-2-3``)

Grounding proves the code was **used** (chapter 3). This is the narrower guard on what grounding
cannot see — a test that runs the production code and asserts nothing about it, the
assertion-meaningfulness residue chapter 1 names and declines to claim (``dev07-4-2``). Break the
code; a test citing the story must notice.

**It finds real defects.** Applied to this project it has caught tests that could not fail and
code no test reached, on work that a full green suite had already signed off. So the question is
never whether to run it — it is **when**, and that is a question about cost:

* A mutant costs one **test run**, and a story's mutants are run against **only the tests citing
  that story** — not the suite (``dev07-2-1``). That is the whole reason this is affordable at all.
* Even so, the multiplier is large. Measured on Plumb itself — a small project whose tests run in
  fractions of a second — the suite takes ~11s and one full pass takes **45 minutes, 177x that**.
  Where the tests are slower, so is every one of the thousands of runs. Nothing here makes that
  cheaper; what it does is let a caller **see the price before paying it** (:func:`plan`), so the
  decision is made with a number rather than a guess.
* Which is why the honest place for it is a story or two at a desk, or a nightly pass — and why
  it is opt-in (``dev07-2-2``). Not because it is optional: because it is not a thing you leave on by
  accident.

The result is a **score**, not a verdict (``dev07-2-4``). A story's tests routinely run far more code
than they check, so "did any mutant survive?" is *yes* for almost every honest test and carries
almost no information; ``12/40`` and ``39/40`` do not mean the same thing and must not read the
same. It stays advisory whatever the numbers say (``dev07-2-4``) — an equivalent mutant is
indistinguishable from a real survivor (``dev07-2-4``).

What is not done here is limiting the pass to what *changed* since last time. That needs a
definite diff and the mechanism is open (``dev07-2-1``); it is also the single biggest lever on the
cost above, which is why it is worth naming rather than quietly omitting.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from plumb.adapters.python.mutants import Mutant, mutants, site_count
from plumb.adapters.python.surface import ProductionSurface
from plumb.core.manifest import Manifest, Mutation

#: A mutant can make a loop never terminate — negating a ``while`` condition is one of three
#: operators — so every run is bounded. A timeout counts as **killed**: the tests did not complete
#: against the broken code, which is the opposite of passing over it unmoved.
TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class OptIn:
    """``dev07-2-2`` — mutation runs when a project asks for it, and not before.

    Named rather than passed as a bare boolean so the default lives in one place and reads as the
    decision it is. Config for the same reason grounding takes its surface from config
    (``dev07-1-3``): the artifact under test never imports the thing judging it.
    """

    enabled: bool = False

    @classmethod
    def from_config(cls, config) -> "OptIn":
        """Absent means off, which is the whole of ``dev07-2-2``."""
        return cls(enabled=config.mutation)


@dataclass(frozen=True)
class Target:
    """One production file, and the functions in it the story's tests drove."""

    path: Path
    module: str
    qualnames: tuple[str, ...]


@dataclass(frozen=True)
class Plan:
    """What one story's mutation pass would run — **before** any of it runs.

    Separate from doing it because the cost is the decision. A caller that cannot ask "how much"
    without paying it can only find out by starting, and a run that takes hours is exactly the
    one nobody should start blind.
    """

    story: str
    tests: tuple[str, ...]
    targets: tuple[Target, ...]
    mutants: int

    @property
    def runnable(self) -> bool:
        return bool(self.mutants and self.tests)


def scope(wired: tuple[str, ...], surface: ProductionSurface) -> tuple[Target, ...]:
    """``dev07-2-1`` — the grounded code, grouped by the file that holds it.

    The input is the trace's ``executed_under_entry``: production frames that ran with a declared
    entry point above them. Scoping to the *whole* call tree instead was measurably wrong — it
    pulls in every helper a test brushed past, so almost every story reported a survivor and the
    fact stopped distinguishing anything.

    A project that declares no entry points therefore gets no mutants and no fact, which is the
    same answer grounding gives it (``dev07-1-4``): the question needs a wired system to be asked
    about, and saying nothing is honest where inventing an answer is not.

    It reuses the trace rather than adding a second observation, so no story-to-code map is
    written down — that is the artifact ``dev07-1-4`` refuses to keep, and mutation is not the place
    to smuggle one back in.
    """
    plan: dict[Path, tuple[str, set[str]]] = {}
    for name in wired:
        path = surface.locate(name)
        if path is None:
            continue
        module, _, qualname = name.partition(":")
        plan.setdefault(path, (module, set()))[1].add(qualname)
    return tuple(
        Target(path=path, module=module, qualnames=tuple(sorted(qualnames)))
        for path, (module, qualnames) in sorted(plan.items())
    )


def plan(story: str, tests: tuple[str, ...], wired_by_test: dict[str, tuple[str, ...]],
         surface: ProductionSurface) -> Plan:
    """Cost this story's pass without running any of it.

    The scope is the **union** across every citing test, and every mutant is then run against
    **all** of them. A mutant only one of three citing tests would catch is still caught, and
    ``survived`` comes to mean "no test of this story noticed" rather than "the test I happened
    to pick did not" — which is what the reader assumes it means anyway.
    """
    targets = scope(tuple(sorted({n for t in tests for n in wired_by_test.get(t, ())})), surface)
    return Plan(
        story=story,
        tests=tests,
        targets=targets,
        mutants=sum(site_count(t.path.read_text(), module=t.module, scope=t.qualnames)
                    for t in targets),
    )


def run(one: Plan, root: Path | str | None = None) -> Mutation | None:
    """Run every mutant in the plan against every citing test, and score it (``dev07-2-3``).

    ``None`` is *not reported* rather than a pass (``dev07-3-3``): a story whose tests drove nothing
    wired, or drove code with no mutable site in it, was never asked the question. A score of
    ``0/0`` would read like an answer.

    Every mutant runs — there is no stopping at the first survivor. Stopping is what a boolean
    could afford, and it is why a boolean was cheap: the run ended early precisely when it had
    learned the least.
    """
    if not one.runnable:
        return None
    at = Path(root) if root is not None else Path.cwd()
    killed = sum(
        _noticed(mutant, target.path, one.tests, at)
        for target in one.targets
        for mutant in mutants(target.path.read_text(), module=target.module,
                              scope=target.qualnames)
    )
    return Mutation(total=one.mutants, killed=killed)


def fill(manifest: Manifest, wired_by_test: dict[str, tuple[str, ...]],
         surface: ProductionSurface, opt_in: OptIn, root: Path | str | None = None,
         report: Callable[[str], None] | None = None) -> Manifest:
    """Populate every story's mutation slot — only when the opt-in is on (``dev07-2-2``, ``dev07-2-4``).

    Only **passing** citations are run. A failing test kills every mutant it is handed for the
    reason it was already failing, so the score would credit a test for not working — the one
    place mutation could manufacture confidence rather than check it.
    """
    if not opt_in.enabled:
        return manifest
    plans = {sid: plan(sid, tuple(sorted({c.test for c in story.citations if c.ran_and_passed})),
                       wired_by_test, surface)
             for sid, story in manifest.stories.items()}
    _announce(plans, root, report)

    # Two stories cited by the same tests over the same code face the same mutants and must get
    # the same score, so running them twice buys nothing. Stories cluster this way in practice —
    # one end-to-end test commonly cites five — and at one test run per mutant the saving is the
    # difference between a pass somebody starts and one they abandon.
    scored, seen, started = {}, {}, time.perf_counter()
    for i, (sid, one) in enumerate(sorted(plans.items()), 1):
        shape = (one.tests, one.targets)
        if shape not in seen:
            seen[shape] = run(one, root)
        scored[sid] = seen[shape]
        if report and one.runnable:
            report(f"  [{i}/{len(plans)}] {sid}: {scored[sid].killed}/{scored[sid].total} killed "
                   f"({time.perf_counter() - started:.0f}s elapsed)")
    return replace(manifest, stories={
        sid: replace(story, mutation=scored[sid]) for sid, story in manifest.stories.items()
    })


def _announce(plans: dict[str, Plan], root: Path | str | None,
              report: Callable[[str], None] | None) -> None:
    """Say what this will cost before it is spent, in units measured on this machine.

    A floor rather than a forecast, and labelled as one: it is the count times the cost of
    starting a test process here, which every mutant pays before running a single assertion. The
    real figure is higher by however long the citing tests take. Understating is the safe
    direction for a floor — nobody is talked into a run by a number that turns out to be low.
    """
    if report is None:
        return
    total = sum(p.mutants for p in plans.values())
    runnable = [p for p in plans.values() if p.runnable]
    if not total:
        report("mutation: nothing to mutate — no story drove code under a declared entry point")
        return
    floor = _process_floor(runnable[0].tests, Path(root) if root is not None else Path.cwd())
    report(f"mutation: {total} mutants over {len(runnable)} stories — at least "
           f"{_duration(total * floor)} ({floor:.2f}s process floor, measured here), plus however "
           "long the citing tests take")


def _duration(seconds: float) -> str:
    """Whichever unit a reader can act on. "0 min" is the number that stops being a warning."""
    if seconds < 90:
        return f"{seconds:.0f}s"
    if seconds < 5400:
        return f"{seconds / 60:.0f} min"
    return f"{seconds / 3600:.1f} hours"


def _process_floor(tests: tuple[str, ...], root: Path) -> float:
    """Start a test process and collect one story's tests, without running them.

    Measured against a real citing-test set rather than an empty run, because collection is where
    a project's own conftest, plugins and imports get paid, and on a large project that is most of
    the fixed cost. Timing an empty collection would understate by exactly the amount that grows
    with the project — the direction that turns a warning into a surprise.
    """
    started = time.perf_counter()
    _failed((*tests, "--collect-only", "--no-header"), root)
    return time.perf_counter() - started


#: Where the original is parked while a mutant stands in for it. Named and left in the project
#: root on purpose: if it is still there, something went wrong and the tree needs putting back.
RESCUE = ".plumb-mutation-rescue"


def _noticed(mutant: Mutant, path: Path, tests: tuple[str, ...], root: Path) -> bool:
    """Write the mutant, run the citing tests, put the file back.

    The original is restored in a ``finally``, which covers every failure Python can raise — but
    not the process being killed, and mutation runs are long enough that being killed is a normal
    way for one to end. So the original is also written to disk (:data:`RESCUE`) *before* the
    mutant goes down, and only removed once the file is whole again. A run that dies mid-mutant
    leaves that file behind, and the next run refuses to start until it is dealt with.

    This is not hypothetical: an interrupted run on a working copy silently produced a
    *measurement* that was wrong by an order of magnitude, and nothing about it looked wrong.
    In-place mutation buys the thing that matters — the tests run against the project exactly as
    it is, with its own imports, plugins and configuration — and this is its price, paid openly.
    """
    original = path.read_bytes()
    rescue = root / RESCUE
    rescue.write_bytes(str(path).encode() + b"\n" + original)
    try:
        path.write_text(mutant.source)
        return _failed(tests, root)
    finally:
        path.write_bytes(original)
        rescue.unlink(missing_ok=True)


class InterruptedRun(RuntimeError):
    """A previous mutation run died with a mutant still on disk."""


#: What a caller says when it puts a file back, so the two things a reader needs — that a run
#: died, and which file it was — arrive together and in the same words wherever it happens.
RECOVERED = "mutation: put back {path} — a previous run was interrupted mid-mutant"


def restore(root: Path | str | None = None) -> Path | None:
    """Put back whatever an interrupted run left mutated, and say which file it was.

    Called **before the tests run**, not before the next mutation pass — which is the ordering the
    obvious placement gets wrong. A leftover mutant corrupts the *test run* first of all, and by
    the time a mutation pass wants the file, every fact in the manifest was already measured
    against broken code. Recovering then puts the tree right and leaves the answer wrong.

    Automatic rather than an instruction, because the failure this guards against is silent: a
    mutated source still imports, still runs, and answers every question slightly wrong.
    """
    at = Path(root) if root is not None else Path.cwd()
    rescue = at / RESCUE
    if not rescue.is_file():
        return None
    target, _, original = rescue.read_bytes().partition(b"\n")
    path = Path(target.decode())
    path.write_bytes(original)
    rescue.unlink()
    return path


def _failed(args: tuple[str, ...], root: Path) -> bool:
    """Run pytest in a fresh interpreter. A subprocess because the mutant has to be *imported*,
    and this process already holds the original module object."""
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", *args, "-x", "-q", "-p", "no:cacheprovider"],
            cwd=root, capture_output=True, timeout=TIMEOUT_SECONDS,
            # A cached .pyc keyed to the original would be a mutant that never ran.
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
    except subprocess.TimeoutExpired:
        return True
    return completed.returncode != 0
