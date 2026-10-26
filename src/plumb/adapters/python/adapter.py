"""The Python/pytest adapter: a test run in, a manifest out.

This is the **language-bound** half of ``dev07-3-3``. Everything pytest-shaped stops here — node
ids, marks, report phases — and what leaves is the neutral manifest the core reads. The core
imports none of this, and importing it from :mod:`plumb.core.gate` or :mod:`plumb.core.board` would
collapse the seam that makes a second language a second adapter and nothing else.

It reports **facts, not verdicts** (``dev07-3-1``): what each citing test claimed and how the runner
finished it. It never decides proven from unproven, so no adapter can grant or revoke a status.

Grounding is computed here because the trace and the entry-point declarations are both
language-specific (``dev07-1-3``, ``dev07-1-4``); the core reads only the resulting fact. Tracing is
scoped to the **call** phase deliberately — a module's imports run at collection, so keeping the
window to the test body is what stops import-time frames being mistaken for the test executing
production code (``dev07-1-4``).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field, replace

from datetime import datetime, timezone

import pytest

from plumb.adapters.python.archetypes import archetype_of
from plumb.adapters.python.grounding import fact
from plumb.adapters.python.mutation import RECOVERED, OptIn, fill, restore
from plumb.core.manifest import (
    FAILED,
    Provenance,
    NOT_CHECKED,
    PASSED,
    SKIPPED,
    Citation,
    Manifest,
    Story,
)
from pathlib import Path
from plumb.adapters.python.surface import ProductionSurface
from plumb.adapters.python.trace import tracing, watching_reads

#: The default name. It is a **convention**, not a mechanism, so a project that already cites its
#: requirements under another name says so in config rather than rewriting every call site.
#: Adoption cost is measured from the project somebody already has.
MARKER = "proves"

#: The second citation marker, for a subject that is never *done* (`dev07-4-3-nfr4`, `dev07-4-3-ur05`).
#:
#: A decision is a claim about the future and a parameter is a decision with a model, so neither
#: can be *proven* — only informed, repeatedly, by evidence that keeps arriving. Reusing `proves`
#: would import the doneness reading into the one place it must not be, which is the same leak the
#: board's own vocabulary has (`dev07-4-3-ur05`) arriving one layer earlier, at the API.
#:
#: Separate rather than a parameter of the first, because a reader scanning a test file learns the
#: thing they act on from the tag alone: *that is not my code's test*.
#:
#: It carries **no depth**. Depth is a claim the run refutes (`dev07-4-2` checks a claimed rung against
#: grounding); the analogue for a decision would be authored and uncheckable, which is `dev07-4-3-nfr3`'s
#: prohibition wearing a new name. So an `informs` citation reports no rung and the board shows it
#: none, rather than carrying a number nothing could contradict.
INFORMS = "informs"

#: What this adapter is, for the manifest to carry beside its facts (``dev07-3-1``). The mechanism
#: is named because it is what decides whether a fact here is comparable with one from elsewhere:
#: ``sys.settrace`` watches the calling thread only, so this adapter's `inert` rests on a
#: per-thread call tree and its `dispatched` on a coarse "another thread was alive".
ADAPTER_NAME = "plumb-python"
MECHANISM = "sys.settrace (per-thread call tree)"


def _provenance() -> Provenance:
    import platform

    from plumb import __version__

    return Provenance(
        adapter=ADAPTER_NAME,
        version=__version__,
        runtime=f"{platform.python_implementation()} {platform.python_version()}",
        mechanism=MECHANISM,
    )

#: This hook brackets the test from inside its own frame, so pytest resumes it while the trace
#: is still live and it lands in the call tree it is collecting. Naming it here keeps the
#: observer out of its own observation.
_HOOK = frozenset({"PlumbAdapter.pytest_runtest_call"})


#: `eq=False`, so the plugin keeps **identity** equality and stays hashable.
#:
#: A plain `@dataclass` generates `__eq__`, which sets `__hash__ = None` — and a pytest that keeps
#: its plugins in a set then dies with `TypeError: unhashable type: PlumbAdapter`, twenty frames
#: down, under a headline telling the reader to fix their own suite. Identity is what a plugin
#: wants anyway: the session holds one, and nothing here has ever compared two.
@dataclass(eq=False)
class PlumbAdapter:
    """A pytest plugin that accumulates one manifest per session.

    Citations are read at collection and outcomes at report, because a test's *claim* and its
    *result* arrive from pytest at different moments and only the pair is a fact.
    """

    #: what the project declared about itself; an empty surface yields `not-checked` (`dev07-1-4`)
    surface: ProductionSurface = field(default_factory=ProductionSurface.of)
    #: what this project calls a citation — a convention it declares, never one we impose
    marker: str = MARKER
    #: What each test's **setup** read, joined into the call-phase trace before the fact is made.
    #: A structural test is entitled to read its artifact in a fixture (`dev07-4-2`).
    read_in_setup: dict = field(default_factory=dict)
    #: What each **fixture** read while it was being set up, by fixture name.
    #:
    #: Kept per fixture rather than per test because a fixture is cached: at `scope="module"` it
    #: opens the file once, during the first test's setup, and every later test in the module gets
    #: the value with no read of its own. Attributed to whoever *asked* for the fixture, which is
    #: the honest reading — a test that depends on a fixture depends on what that fixture read.
    read_by_fixture: dict = field(default_factory=dict)
    #: marker names seen on cited-looking tests that were not ours, so an empty board can say
    #: *why* it is empty instead of leaving the reader to guess
    foreign: set = field(default_factory=set)
    #: node id -> the (story, depth, ref) triples that test claims
    claims: dict[str, list[tuple[str, str, str | None]]] = field(default_factory=dict)
    #: node id -> normalized runner result
    outcomes: dict[str, str] = field(default_factory=dict)
    #: node id -> the grounding fact derived from its trace
    grounding: dict[str, str] = field(default_factory=dict)
    #: node id -> did it also run production code no entry point reached (`dev07-1-4`)
    reached_outside: dict[str, bool] = field(default_factory=dict)
    #: node id -> the declared entry points that test came in through, outermost (`dev07-1-4`).
    entered_through: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: node id -> the production frames it ran *under a declared entry point*, which is what
    #: mutation is scoped to (`dev07-2-1`). Kept from the same trace grounding was derived from, so
    #: mutation adds no second observation and no map of story to code.
    wired: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: Production-to-production joins, across the whole run (`dev07-1-3`). A set, and not per test:
    #: an edge is a fact about how the system is put together rather than about the test that
    #: happened to walk it, so collapsing it once is what it is for.
    edges: set = field(default_factory=set)
    #: How many tests this run observed, cited or not (`dev07-3-2`). Starts as `None` — *not
    #: reported* — and only becomes a number once collection has actually run, so a session that
    #: died before it could look says nothing rather than claiming it looked and found none. That
    #: gap is the whole reason the field exists, and defaulting it to 0 would reintroduce it.
    observed: int | None = None

    # ---- pytest hooks -------------------------------------------------------------------

    def pytest_configure(self, config):  # noqa: D401 — hook
        """Declare the marker, because a plugin that adds one and does not register it makes
        pytest warn `Unknown pytest.mark.proves - is this a typo?` on every citation — the tool
        telling the user their claim might be a mistake while quietly relying on it. Under
        ``--strict-markers``, which real projects turn on, it is a failure rather than a warning."""
        config.addinivalue_line(
            "markers",
            f"{self.marker}(id, ..., depth, ref): cite the stories this test proves, at a depth — "
            f'e.g. @pytest.mark.{self.marker}("APP-1", depth="unit"). `ref` is optional and is '
            "your own external key, which Plumb carries and never parses",
        )
        config.addinivalue_line(
            "markers",
            f"{INFORMS}(id, ..., about, ref): cite what this test informs — a decision or a "
            f'parameter, which is never *done* and so is never proven. e.g. '
            f'@pytest.mark.{INFORMS}("D27", about="falsifier"). `about` names which of the '
            "subject's aspects it bears on. No depth: it would be a claim nothing could refute",
        )

    @pytest.hookimpl(hookwrapper=True)
    def pytest_fixture_setup(self, fixturedef, request):
        """Watch what one fixture reads, once, and remember which fixture it was.

        A cached fixture reads on the first test that asks and never again, so a window around each
        *test's* setup sees the read once and calls every later test untouched. Measured on the
        sibling repository: a `scope="module"` fixture reading a script left six structural stories
        unprovable while one — whichever ran first — proved.
        """
        with watching_reads(self.surface) as recorder:
            yield
        if recorder.reads:
            held = self.read_by_fixture.setdefault(fixturedef.argname, [])
            held.extend(r for r in recorder.reads if r not in held)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_setup(self, item):
        """Watch what **setup** reads, and nothing else about it (`dev07-4-2`).

        A structural test proves by reading the artifact and is entitled to read it in a fixture —
        which is where a suite naturally puts it, one file shared by every test in the module. The
        call-phase trace cannot see that by construction, so once `inert` became the positive claim
        *the artifact was read*, a test that read it in a fixture stopped being able to prove.
        Measured on this project's sibling repository: seven structural stories went unproven with
        no change to their tests.

        Reads only. Frames stay bracketed to the call phase, because *did production code run under
        this test* is a different question and widening it would move what `grounded` means.
        """
        if item.nodeid not in self.claims:
            yield
            return
        with watching_reads(self.surface) as recorder:
            yield
        self.read_in_setup[item.nodeid] = tuple(recorder.reads)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_call(self, item):
        """Trace the test body, and only the body.

        A hookwrapper so the trace brackets exactly the call phase: setup and teardown are
        somebody else's frames, and collection-time imports have already happened. Uncited tests
        are not traced at all — tracing costs real time, and a test that claims nothing produces
        no fact anyone reads.
        """
        if item.nodeid not in self.claims:
            yield
            return
        with tracing(self.surface, ignore=_HOOK) as recorder:
            yield
        trace = recorder.sealed()
        # What a fixture opened is part of what this test did to the artifact, and the two windows
        # are joined here rather than inside the tracer so the frame trace keeps its narrower
        # meaning.
        borrowed = tuple(self.read_in_setup.get(item.nodeid, ()))
        for name in getattr(item, "fixturenames", ()):
            borrowed += tuple(self.read_by_fixture.get(name, ()))
        if borrowed:
            trace = replace(trace, reads=tuple(dict.fromkeys(trace.reads + borrowed)))
        self.grounding[item.nodeid] = fact(trace, self.surface)
        self.reached_outside[item.nodeid] = trace.ran_outside_entry_point
        self.entered_through[item.nodeid] = trace.entered_through
        self.wired[item.nodeid] = trace.executed_under_entry
        self.edges.update(trace.edges)

    def pytest_collection_modifyitems(self, items) -> None:
        # Counted here rather than at report, because the question is what the run *discovered* —
        # a suite that collects nothing never reaches a report hook at all, which is exactly the
        # run this is meant to catch (`dev07-3-2`). Before `-k`/`-m` deselection, as measured: a run
        # filtered down to nothing still counts what it collected, and its cited stories read
        # `evidence.not-observed` rather than the run reading as one that found no tests.
        self.observed = len(items)
        for item in items:
            for name in (self.marker, INFORMS):
                for mark in item.iter_markers(name):
                    if not mark.args:
                        continue
                    # `informs` carries no depth and never invents one: an empty rung is *not
                    # claimed*, which is the only honest reading, and `dev07-4-2` has nothing to
                    # refute rather than a number it must pretend to check.
                    depth = mark.kwargs.get("depth", "") if name == self.marker else ""
                    ref = mark.kwargs.get("ref")
                    # Which of the subject's aspects this citation is about (`dev07-3-1`). Absent is
                    # the ordinary case and means the subject has one — every story ever written.
                    about = mark.kwargs.get("about")
                # EVERY id, not just the first. A project writing several per marker was having
                # all but one silently discarded, which reads on the board exactly like a story
                # nobody ever claimed — the one failure this tool exists to prevent.
                    for story in mark.args:
                        self.claims.setdefault(item.nodeid, []).append((story, depth, ref, about))
            self.foreign.update(
                mark.name for mark in item.own_markers
                if mark.name not in (self.marker, INFORMS)
                and mark.args and isinstance(mark.args[0], str))

    def pytest_runtest_logreport(self, report) -> None:
        if report.nodeid not in self.claims:
            return
        self.outcomes[report.nodeid] = _worse(
            self.outcomes.get(report.nodeid), _normalize(report)
        )

    # ---- the product --------------------------------------------------------------------

    def manifest(self) -> Manifest:
        """Group the citations under their opaque story id (``dev07-3-2``), as facts."""
        stories: dict[str, list[Citation]] = {}
        instrument = _provenance()
        # One reading of the clock for the whole document. Every fact here was measured by one
        # run, so re-reading it per citation would make facts from a single observation disagree
        # about when they happened — and a series ordered on that axis would order them wrongly.
        measured_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for node, claims in self.claims.items():
            # Never reported on, or reported only for phases that cannot pass (a green setup
            # whose body never ran) — either way a claim, not proof.
            result = self.outcomes.get(node) or SKIPPED
            # A test that never reached its body has no trace, so its fact is `not-checked`
            # rather than a guess about what it would have touched.
            grounding = self.grounding.get(node, NOT_CHECKED)
            for story, depth, ref, about in claims:
                stories.setdefault(story, []).append(
                    Citation(test=node, depth=depth, result=result, about=about,
                             # Stamped once per run, not per citation: every fact in one run was
                             # measured by one run, and re-reading the clock would make facts from
                             # a single observation disagree about when it happened.
                             when=measured_at,
                             grounding=grounding, ref=ref,
                             reached_outside_entry=self.reached_outside.get(node),
                             # Which door, where grounding carries only whether (`dev07-1-4`). A test
                             # this run never observed gets None — *not reported* — rather than an
                             # empty tuple, which would claim it entered by none.
                             entered_through=self.entered_through.get(node),
                             # On the fact, not the document (`dev07-3-1`): a merged board carries
                             # facts from several instruments and each has to say which made it.
                             observer=instrument)
                )
        # The archetype enters from the project's config, not from anything this run observed — the
        # one field here that is not a measurement (`dev07-3-2`). Unmentioned means behavioral.
        return Manifest(
            stories={
                sid: Story(archetype=archetype_of(sid), citations=tuple(cs))
                for sid, cs in sorted(stories.items())
            },
            observed_tests=self.observed,
        )


def _normalize(report) -> str | None:
    """The runner's own signal, mapped without translation loss (``dev07-3-1``).

    Only the call phase can report a pass: a test whose body never ran has proved nothing, so a
    green setup is not an outcome.
    """
    if report.outcome == "failed":
        return FAILED
    if report.outcome == "skipped":
        # An **xfail is not a skip**. pytest spells both `skipped` and hands us `wasxfail` to tell
        # them apart: an xfailed test *ran and failed*, and a skipped one never ran. Collapsing
        # them is the translation loss `dev07-3-1` forbids, and it hides the one case that matters —
        # a decision whose falsifier has fired, recorded as a strict xfail so the suite stays
        # green, would otherwise be indistinguishable from a check nobody ran.
        return FAILED if hasattr(report, "wasxfail") else SKIPPED
    return PASSED if report.when == "call" else None


#: Worst-wins, so a test that passes its body and then errors in teardown is not a pass.
_SEVERITY = {None: 0, PASSED: 1, SKIPPED: 2, FAILED: 3}


def _worse(current: str | None, incoming: str | None) -> str | None:
    return current if _SEVERITY[current] >= _SEVERITY[incoming] else incoming


class SuiteAborted(RuntimeError):
    """The runner never finished looking. Distinct from a suite that ran and failed, which is the
    runner's own verdict to give and never ours (`dev07-4-3`)."""


#: Runner statuses meaning the session did not complete. Deliberately **not** ``TESTS_FAILED``: a
#: failing suite is a complete observation whose answer happens to be no, and treating it as an
#: abort is exactly the "make CI the gate" move `dev07-4-3` forbids. Deliberately not
#: ``NO_TESTS_COLLECTED`` either — that session finished and honestly saw nothing, which is
#: already `observation.none` and already exits 3.
ABORTED = frozenset({
    pytest.ExitCode.INTERRUPTED,      # collection error, or a killed run
    pytest.ExitCode.INTERNAL_ERROR,
    pytest.ExitCode.USAGE_ERROR,
})


def _whose_fault(status) -> str:
    """Who the reader should go and look at, which is not always them.

    ``INTERNAL_ERROR`` is **pytest crashing**, never a test failing, so *fix the run first* sends
    somebody to read their own conftest for a fault in the pair of programs above it. Measured: a
    system pytest against an adapter that needed a newer one produced twenty frames ending in
    `TypeError: unhashable type: PlumbAdapter`, under a headline about the reader's suite, and the
    first minutes went on `pytest.ini`.

    The runner's version is named because it is half of the pair and the half nobody thinks to
    check — Plumb runs under the interpreter the project declares, which is routinely not the one
    Plumb was installed into.
    """
    if status == pytest.ExitCode.INTERNAL_ERROR:
        return (f"pytest itself failed rather than any test — this is the runner and the adapter "
                f"disagreeing, not your suite. This run used pytest {pytest.__version__} at "
                f"{sys.executable}, which is the interpreter `[python] interpreter` names. "
                f"The trace above is pytest's own.")
    if status == pytest.ExitCode.USAGE_ERROR:
        return ("pytest refused its own arguments, so nothing was collected — check what "
                "`[python] tests` and any extra arguments add up to. The runner's output says which.")
    return "Fix the run first; the runner's own output above says why."


def collect(args: list[str] | None = None,
            surface: ProductionSurface | None = None,
            mutation: OptIn | None = None,
            report=None,
            marker: str = MARKER,
            edges_to=None) -> Manifest:
    """Run pytest under the adapter and return the manifest it produced.

    Both declarations arrive already resolved, because the launcher read them (``plumb.config``).
    Defaults exist for a caller driving this directly — a test, or a library user — and never for
    the command line, which always knows what the project declared.

    Mutation runs **after** the session and only when opted in (``dev07-2-2``) — it needs the trace
    and the outcome, and both are only complete once the run is.
    """
    # Before the runner starts, and whether or not mutation is on this time: a mutant left by a
    # killed run breaks the *test run*, so recovering after it would produce a tidy tree and a
    # manifest measured against broken code.
    recovered = restore()
    if recovered and report:
        report(RECOVERED.format(path=recovered))
    adapter = PlumbAdapter(surface=surface or ProductionSurface.of(), marker=marker)
    status = pytest.main(list(args or []), plugins=[adapter])
    if status in ABORTED:
        # The runner never finished looking, so its count is of what it had reached rather than
        # of what it saw — and a partial count is the one thing `dev07-3-2` says must not be
        # reported as an observation. Raised rather than returned: a manifest derived from a
        # session that died would read as an answer (`dev07-5-2`).
        raise SuiteAborted(
            f"the test session did not complete (pytest exit {int(status)}), so no board can be "
            f"derived from it — a story that proved last run would read UNPROVEN for want of a "
            f"run rather than for want of a test.\n  " + _whose_fault(status))
    manifest = adapter.manifest()
    if not manifest.stories and adapter.foreign and report:
        # An empty board is the question "why?", and this is the one answer the adapter has that
        # nobody else does: it saw markers, just not the one it was told to read.
        report(f"no tests cite `{marker}`, but these markers are in use: "
               f"{', '.join(sorted(adapter.foreign))}\n"
               f"If one of them is how this project cites requirements, say so in plumb.toml:\n"
               f'    [python]\n    marker = "{sorted(adapter.foreign)[0]}"')
    if edges_to is not None:
        # Written here rather than by the caller because this is where the edges are, which is the
        # same reason the Java runner writes its own beside the citations it just produced. On
        # every run, and empty when nothing joined (`dev07-1-3`).
        Path(edges_to).write_text(
            "".join(f"{caller}\t{callee}\n" for caller, callee in sorted(adapter.edges)))
    # The runner's own summary is still in stdout's buffer when this returns, while what mutation
    # reports goes straight out on stderr — so without this its first line lands on the end of the
    # runner's `[100%]` and the summary arrives after the mutation pass it preceded.
    sys.stdout.flush()
    return fill(manifest, adapter.wired, adapter.surface, mutation or OptIn(), report=report)
