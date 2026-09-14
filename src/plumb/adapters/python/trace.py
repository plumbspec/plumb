"""Chapter 3's mechanism: a language-native per-test trace (``dev07-1-3``).

The runtime's own tracing around a single test — never a third-party coverage tool. Plumb
needs one narrow answer, so it owns a tiny trace and nothing more.

The trace records **two** kinds of contact with the production artifact, because the call
tree alone cannot tell a structural rule from a test that did nothing:

* **executed** frames — production code the test ran, and whether any of it ran under a
  declared entry point;
* **reads** — production files the test opened as *data*, which is what a rule over
  dependency direction, containment or format actually does.

It also records **edges** — production-to-production ``(caller, callee)`` pairs — which chapter 3
does not use and must not start using. Grounding asks whether an entry point was above a frame, and
that question is answered by the two observations above. Edges are here because the executed set
says *which* parts of the system a test touched and cannot say *how they are joined*, and nothing
else in the tool observes the joins. What consumes them is `dev07-1-3`.

Deriving the grounding fact from this (``dev07-1-4``) is deliberately *not* here. A probe showed
the current four-value vocabulary is unstable for import-touching tests, so the trace exposes
the observations and the vocabulary settles separately. Nothing here presumes the answer.
"""

import sys
import threading
import weakref
from contextlib import contextmanager
from pathlib import Path
from dataclasses import dataclass, field
from types import FrameType
from typing import Iterator

from plumb.adapters.python.surface import ProductionSurface

# The tracer's own frames, which must never appear in what it observes. Reading a file fires the
# audit hook, and the hook plus the context manager live *here* — inside any project whose
# production root contains Plumb. So a test that purely reads an artifact as data, which is the
# definition of `inert` (`dev07-1-4`), recorded `plumb.adapters.python.trace:tracing` as executed and read as
# UNGROUNDED. That broke structural stories specifically, and only when Plumb traced itself.
# An observer that shows up in its own observation is measuring the wrong thing.
_SELF = frozenset({__file__, str(Path(__file__).resolve())})

#: How far up the stack ``_note_edge`` looks for the calling production frame. Four covers a
#: decorator, a comprehension or a generator between two production frames; beyond that the caller
#: is far enough away that the edge says more about the intervening machinery than about the system.
CALLER_SEARCH_DEPTH = 4

# An audit hook cannot be removed once installed, so exactly one is added at import and it
# consults whichever recorder is active. Installing per-test would leak a hook per test.
_active: "_Recorder | None" = None
_hook_installed = False


def _audit(event: str, args: tuple) -> None:
    if _active is None or event != "open" or not args:
        return
    target = args[0]
    if isinstance(target, bytes):
        target = target.decode("utf-8", "replace")
    if isinstance(target, str):
        _active.note_read(target)


def _install_audit_hook() -> None:
    global _hook_installed
    if not _hook_installed:
        sys.addaudithook(_audit)
        _hook_installed = True


@dataclass(frozen=True)
class Trace:
    """What one test did to the production artifact — observations, not a verdict."""

    executed: tuple[str, ...]
    reads: tuple[str, ...]
    ran_under_entry_point: bool
    #: The subset of ``executed`` that ran with a declared entry point above it. Grounding needs
    #: only the *whether* above; this is the *which*, and it is what mutation is scoped to
    #: (``dev07-2-1``). The distinction is the difference between mutating the wired system a test
    #: drove and mutating every helper it happened to touch on the way past.
    executed_under_entry: tuple[str, ...] = ()
    #: Did any production frame run with *no* entry point above it? Grounding is a property of
    #: the whole test (``dev07-1-4``), so a test that drives an entry point and also exercises
    #: unreachable code still grounds — this is what makes that visible (``dev07-1-4``).
    ran_outside_entry_point: bool = False
    #: Which declared entry points this test came in through, **outermost** (``dev07-1-4``) — a door is
    #: recorded when it is entered from outside any open window, so entering one already inside
    #: another adds nothing. ``ran_under_entry_point`` above says *whether*; this says *which*, which
    #: is the question a flat project-wide ``entry_points`` set cannot otherwise answer.
    entered_through: tuple[str, ...] = ()
    #: Could this observation account for every thread? ``sys.settrace`` is per-thread, so with
    #: other threads live an empty call tree means "nothing ran *here*", which is not the same
    #: claim as "nothing ran" (``dev07-1-4``).
    accounted_for_all_threads: bool = True
    #: Production-to-production ``(caller, callee)`` pairs. Grounding needs none of this — it asks
    #: only *whether* an entry point was above the frame — so nothing here reads it. It exists
    #: because the set of executed frames says which parts of the system a test touched and cannot
    #: say how they are joined, and joins are what a seam is drawn between.
    #:
    #: **A set, and the weight is given up deliberately** (``dev07-1-3``). Repeats would say how often
    #: an edge was taken, and the Java instrument cannot count them without paying per call where it
    #: currently pays per site. Rather than let the two adapters disagree, neither counts. The loss
    #: is small: measured across this repository, how many calls arrive at a module correlates with
    #: how often that module is tested at r = 0.78, so a raw count is largely a reading of test
    #: effort. In first-observation order, which a set cannot promise and a reader diffing two runs
    #: needs.
    edges: tuple[tuple[str, str], ...] = ()

    @property
    def touched_nothing(self) -> bool:
        """Neither ran nor read production code. `assert True` lands here — and today's
        spec would call it `inert` and let it prove a structural story."""
        return not self.executed and not self.reads


@dataclass
class _Recorder:
    """Collects frames via ``sys.settrace`` and reads via the audit hook."""

    surface: ProductionSurface
    executed: list[str] = field(default_factory=list)
    reads: list[str] = field(default_factory=list)
    under_entry: list[str] = field(default_factory=list)
    #: Doors entered from outside any open window, in the order they were first used (`dev07-1-4`).
    #: A list rather than a set so a test driving two entrances reads in the order it drove them.
    entered_through: list[str] = field(default_factory=list)
    #: A dict used as an ordered set: membership is the whole of what `dev07-1-3` asks for, and
    #: insertion order is kept because a run whose output reorders for no reason cannot be diffed.
    edges: dict[tuple[str, str], None] = field(default_factory=dict)
    #: **Per thread, and a mutable box inside a `threading.local`** (`dev07-1-3`). Entry depth is
    #: walked up on entering a declared entry point and down on leaving it, which is meaningful for
    #: one call stack and meaningless shared across several: two threads interleaving inside a
    #: window leave it at a value neither produced, and `ran_under_entry_point` is read from it.
    #: The Java probe holds the same thing as a `ThreadLocal<int[]>`, for the same reason.
    _depth: "threading.local" = field(default_factory=threading.local)
    #: Threads this window is entitled to watch: the one it opened on, plus any started from a
    #: watched thread. Weak, so a finished thread is not held alive by having been observed.
    _watching: "weakref.WeakSet" = field(default_factory=weakref.WeakSet)
    _under_entry: bool = False
    _outside_entry: bool = False
    #: filename -> is this ours. `owns` resolves a path, which is a syscall, and the same
    #: handful of filenames recur for the entire run.
    _owned: dict[str, bool] = field(default_factory=dict)
    #: (filename, qualname) -> its citable name, for the same reason
    _names: dict[tuple[str, str], str] = field(default_factory=dict)
    #: set while the recorder is doing its own bookkeeping, so it never observes itself
    _busy: bool = False
    #: Set when the window closes. `sys.settrace` cannot be cleared on somebody else's thread from
    #: here, so a watched thread detaches itself on its next event instead. Without it a pooled
    #: worker stays bound to a sealed recorder and reports the next submitter's work into it.
    _closed: bool = False
    _other_threads: bool = False
    #: qualnames belonging to the machinery that *starts* the trace. A caller that brackets a
    #: test from inside its own frame — a pytest hookwrapper does exactly this — is resumed
    #: while tracing is live, so its frame lands in the very call tree it is collecting.
    _ignore: frozenset[str] = frozenset()

    def note_read(self, filename: str) -> None:
        """Record a read, without the recording itself becoming something to record.

        Python suppresses tracing *inside* the trace function, so frames it creates are safe.
        The **audit hook is a separate mechanism and gets no such protection**, so the ownership
        check this makes — which lives in :mod:`plumb.adapters.python.surface` — was being traced as production
        code the test ran. Excluding this module alone was not enough for that reason.
        """
        self._busy = True
        try:
            if self._owns(filename):
                self.reads.append(filename)
        finally:
            self._busy = False

    def _owns(self, filename: str) -> bool:
        cached = self._owned.get(filename)
        if cached is None:
            cached = self._owned[filename] = self.surface.owns(filename)
        return cached

    def watch(self, thread) -> None:
        """Take responsibility for a thread, from the side that knows (`dev07-1-3`).

        Called on the **starting** thread, before the new one runs anything — which is the only
        side that can answer whether a window was open, exactly as the Java probe marks the
        receiving thread from inside `Thread.start`.
        """
        self._watching.add(thread)

    def _here(self) -> list:
        """This thread's entry depth, as a one-element box."""
        box = getattr(self._depth, "box", None)
        if box is None:
            box = self._depth.box = [0]
        return box

    def _mine(self) -> bool:
        """Is this thread one this window may watch? Decided once, then remembered.

        `threading.settrace` installs this recorder on **every** thread created while it is set,
        which is broader than `dev07-1-3` allows. The narrowing happens here rather than there: a
        thread nobody handed work to detaches itself on its first event and costs nothing after.

        Deciding by *identity* and not by what the first frame looks like matters. A thread's first
        frames are always `threading._bootstrap`, so a rule like *detach on the first
        non-production frame* detaches from every thread before it reaches production code — which
        benchmarks beautifully and records nothing.
        """
        decided = getattr(self._depth, "mine", None)
        if decided is None:
            decided = self._depth.mine = threading.current_thread() in self._watching
        return decided

    def __call__(self, frame: FrameType, event: str, arg: object) -> "_Recorder | None":
        """The global trace hook. **Returning ``None`` is the point**, not an oversight.

        Whatever this returns becomes the *local* trace function for that frame, receiving a
        callback for every line it executes. Returning ``self`` unconditionally — which this did
        — means line-tracing the entire process for the whole traced window. Plumb needs only
        ``call`` events, which arrive here regardless of what a previous frame returned, plus
        ``return`` for entry points so their depth window can close. Everything else is
        answering a question nobody asked, and it cost a 164x slowdown when the traced window
        happened to contain a nested test session.
        """
        if self._busy:
            return None
        if self._closed or not self._mine():
            # Not ours to watch. Detach from this thread rather than filter it forever.
            sys.settrace(None)
            return None
        code = frame.f_code
        if event == "call":
            if (code.co_filename in _SELF or code.co_qualname in self._ignore
                    or not self._owns(code.co_filename)):
                return None
            self._enter(code)
            self._note_edge(frame, code)
            # Only an entry point needs its own return event.
            return self if self.surface.is_entry_point(code) else None
        if event == "return" and self.surface.is_entry_point(code):
            self._here()[0] -= 1
        return None

    def _name(self, code) -> str:
        key = (code.co_filename, code.co_qualname)
        cached = self._names.get(key)
        if cached is None:
            cached = self._names[key] = self.surface.qualify(code)
        return cached

    def _enter(self, code) -> None:
        name = self._name(code)
        self.executed.append(name)
        here = self._here()
        if self.surface.is_entry_point(code):
            # Outermost only. Depth is still 0 here, so this frame was entered from outside every
            # open window — the arrival rather than a door reached along the way (`dev07-1-4`). Taking
            # the innermost instead would let a later declaration rewrite the fact for a test that
            # never changed.
            #
            # Read from this thread's box rather than a shared counter (`dev07-1-3`): with a window
            # carried to a thread the work started, "outside every open window" is a question about
            # this call stack, and a counter shared across threads answers it for whichever
            # interleaved last.
            if here[0] == 0 and name not in self.entered_through:
                self.entered_through.append(name)
            here[0] += 1
        if here[0] > 0:
            self._under_entry = True
            self.under_entry.append(name)
        else:
            # Entered with nothing declared above it. The entry point's own frame increments the
            # depth first, so it is never counted here — only code no entry point reached.
            self._outside_entry = True

    def _note_edge(self, frame: FrameType, code) -> None:
        """Record who called this production frame, when the caller is production too.

        **Bounded, because this runs on every production call event.** The nearest production frame
        is usually the immediate parent, but a decorator, a comprehension or a generator puts one
        or two frames of somebody else's code in between, and stopping at ``f_back`` alone loses
        those edges entirely. An unbounded walk is the other error: it makes the cost of a call
        event proportional to stack depth, and this module has already paid once for letting the
        trace hook do more work than it had to.

        Recorded once per distinct pair (``dev07-1-3``), so the cost is per edge and not per call.

        A call arriving from outside the production surface — a test, a framework, the interpreter —
        records no edge. It is a real entry into the system, but its far end is not a node in the
        graph being built, and inventing one would put the test suite's own shape into a drawing of
        the system under it.
        """
        caller = frame.f_back
        for _ in range(CALLER_SEARCH_DEPTH):
            if caller is None:
                return
            parent = caller.f_code
            if parent.co_filename not in _SELF and self._owns(parent.co_filename):
                self.edges[(self._name(parent), self._name(code))] = None
                return
            caller = caller.f_back

    def sealed(self) -> Trace:
        return Trace(
            executed=tuple(self.executed),
            reads=tuple(self.reads),
            ran_under_entry_point=self._under_entry,
            executed_under_entry=tuple(self.under_entry),
            ran_outside_entry_point=self._outside_entry,
            entered_through=tuple(self.entered_through),
            accounted_for_all_threads=not self._other_threads,
            edges=tuple(self.edges),
        )

    def note_threads(self) -> None:
        """Sampled at both ends of the window rather than watched continuously.

        Deliberately conservative and deliberately cheap: a thread that lived entirely between
        the two samples is missed, and any thread that merely *existed* counts even if it did
        nothing. Both errors push toward `dispatched`, which costs a story the top status and
        never grants it — the only direction a wrong guess is allowed to go here.

        **Uniform across every supported runtime, on purpose.** Python 3.12 added
        ``threading.settrace_all_threads``, which would let this watch the pool threads and answer
        `grounded` or `inert` properly instead of withholding. Using it where available would mean
        the same test on the same code yielding a *different grounding fact* depending on the
        interpreter — into a manifest with no field naming which runtime observed it, so a board
        could mix measurements from instruments it cannot tell apart. Better answers on some
        runtimes are not worth facts that silently disagree across them. When the manifest carries
        provenance, this is the first thing to revisit.
        """
        # A thread this window started is no longer one we cannot speak for: it is watched, so it
        # is accounted for (`dev07-1-3`). Only an unwatched one still withholds toward `dispatched`.
        here = threading.current_thread()
        for other in threading.enumerate():
            if other is not here and other not in self._watching:
                self._other_threads = True
                return


@contextmanager
def _propagating(recorder: "_Recorder") -> Iterator[None]:
    """Carry the window to a thread this work starts and a task it queues (``dev07-1-3``).

    **Two primitives, and they need different answers.** A started thread is named at the moment it
    is started, so the window is filed against the *thread*. A pooled task names no thread at
    submission — the pool picks one later, and the same worker serves every submitter — so filing
    the window under a thread there would hand this test's window to whatever the pool ran next.
    That one is filed against the *task*. The Java probe splits it exactly here, for exactly this
    reason.

    Both wrappers are installed for the traced window and removed after, and each defers to what it
    replaced, so a host that has wrapped these itself is left working.
    """
    import concurrent.futures

    started, submitted = threading.Thread.start, concurrent.futures.Executor.submit

    def start(thread, *args, **kwargs):
        # On the STARTING thread, which is the only side that knows whether a window is open.
        # **Never while a pool is spinning up a worker.** A pool started inside the window would
        # otherwise have its worker marked as a thread this test started — and that worker outlives
        # the task, serves every other submitter, and is precisely what filing against the task
        # avoids. Measured: without this the recorder stayed bound to the worker after the window
        # closed, and the next thing the pool ran reported into a sealed trace.
        if recorder._mine() and not getattr(recorder._depth, "pooling", False):
            recorder.watch(thread)
        return started(thread, *args, **kwargs)

    def submit(pool, fn, /, *args, **kwargs):
        if not recorder._mine():
            return submitted(pool, fn, *args, **kwargs)
        recorder._depth.pooling = True
        try:
            return submitted(pool, _carrying(recorder, fn), *args, **kwargs)
        finally:
            recorder._depth.pooling = False

    threading.Thread.start, concurrent.futures.Executor.submit = start, submit
    try:
        yield
    finally:
        threading.Thread.start, concurrent.futures.Executor.submit = started, submitted


def _carrying(recorder: "_Recorder", task):
    """Wrap a queued callable so the window travels with it and is released on any path.

    Released in a ``finally`` **by whichever path**: a task that raises has still done the work it
    did, and a window left open would follow that worker into whatever the pool ran next — the
    imprecision this exists to remove, reintroduced by an exception.
    """
    def carried(*args, **kwargs):
        was_traced, was_mine = sys.gettrace(), getattr(recorder._depth, "mine", None)
        recorder._depth.mine = True
        sys.settrace(recorder)
        try:
            return task(*args, **kwargs)
        finally:
            sys.settrace(was_traced)
            recorder._depth.mine = was_mine

    return carried


@contextmanager
def tracing(surface: ProductionSurface,
            ignore: frozenset[str] = frozenset()) -> Iterator["_Recorder"]:
    """Trace one test. Yields the recorder; read ``.sealed()`` after the block.

    Nests by saving and restoring whatever tracer was already installed, so a host that
    traces for its own reasons is left as it was found. That now includes ``threading``'s own
    hook, which is how a thread started inside the window is traced at all: ``sys.settrace``
    binds one thread, and the hook is what a new thread consults when it bootstraps.
    """
    global _active
    _install_audit_hook()
    recorder = _Recorder(surface, _ignore=ignore)
    recorder.watch(threading.current_thread())
    previous_tracer, previous_active = sys.gettrace(), _active
    previous_hook = threading.gettrace()
    _active = recorder
    recorder.note_threads()
    threading.settrace(recorder)
    sys.settrace(recorder)
    try:
        with _propagating(recorder):
            yield recorder
    finally:
        recorder._closed = True
        sys.settrace(previous_tracer)
        threading.settrace(previous_hook)
        recorder.note_threads()
        _active = previous_active


@contextmanager
def watching_reads(surface: ProductionSurface) -> Iterator["_Recorder"]:
    """Record **reads only**, with no frame trace at all (``dev07-4-2``).

    A structural test proves by reading the artifact, and it is entitled to do that reading in a
    fixture — which is where a suite naturally puts it, because the file is the same for every test
    in the module. The call-phase trace cannot see that: setup is somebody else's frames by
    design, so a test that read its subject in a fixture reported having touched nothing, and once
    `inert` became a positive claim it stopped being provable.

    Reads only, and deliberately not frames. *Did this test inspect the artifact* is answered the
    same wherever the open happened; *did production code run under this test* is not, and widening
    the frame trace to fixtures would quietly change what `grounded` and `ungrounded` mean.
    """
    global _active
    _install_audit_hook()
    recorder = _Recorder(surface)
    previous_active = _active
    _active = recorder
    try:
        yield recorder
    finally:
        _active = previous_active


def trace_call(surface: ProductionSurface, fn, *args, **kwargs) -> Trace:
    """Run ``fn`` under the trace and return what it touched."""
    with tracing(surface) as recorder:
        fn(*args, **kwargs)
    return recorder.sealed()
