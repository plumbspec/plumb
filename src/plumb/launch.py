"""The launcher: a project's declaration in, a manifest out, whichever language the artifact is.

``plumb`` is not a Python tool that grew a Java mode. It is a **launcher over a language-neutral
core** (``dev07-3-3``): it reads the one config, runs the adapter that config names, and hands the
resulting manifest to the gate. A third language is a new branch here and nothing else — the gate,
the board and the manifest do not change, and none of them learns a language.

Everything an adapter needs arrives **resolved**. The Python adapter is called in-process with a
:class:`ProductionSurface`; the Java adapter is handed a run file of already-decided facts and
parses no configuration format at all. That is what keeps one config file honest across two
languages: there is one reader, and it is here.

This module knows adapter names, which is exactly why it is not in :mod:`plumb.core`.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Callable

from plumb import runfile
from plumb.config import DOTNET, JAVA, PYTHON, Config, InvalidConfig
from plumb.core.manifest import GROUNDING, Manifest, merge

#: The resolved facts handed to a non-Python adapter. One `kind<TAB>value…` per line, because an
#: adapter reading its own configuration is an adapter that has to agree with every other one
#: about a format — and the Java side hand-writes its JSON precisely to avoid taking on parsers.
RUN_FILE = "plumb-run.tsv"


class LaunchFailed(RuntimeError):
    """The adapter could not be run. Distinct from a manifest saying a story failed: this is the
    tool being unable to ask, and it must never read as an answer."""


def produce(config: Config, *, pytest_args: list[str] | None = None,
            mutation: bool = False,
            report: Callable[[str], None] | None = None,
            tests: bool = False
            ) -> tuple[Manifest, tuple[str, ...], tuple[str, ...]]:
    """Run every adapter the project declares: one manifest, what did not run, and what ran blind.

    A second language is a second *manifest* and nothing else (`dev07-3-3`, `dev07-3-3`), so this loops
    and merges rather than branching: the core learns no language here either.

    **A failing adapter does not take the board with it, and does not hide either** (`dev07-3-3`).
    With one adapter its failure is the run's failure and is raised. With several, the others
    still have something true to say, so the board is produced from what ran and names what did
    not — a board missing a language is part of an answer, and saying so is what stops it reading
    as the whole one (`dev07-5-1`).
    """
    declared = config.adapters()
    produced, absent, blind = [], [], []
    for one in declared:
        try:
            manifest, unobserved = _run_adapter(one, pytest_args or [], mutation, report,
                                                tests=tests)
        except LaunchFailed as failed:
            if len(declared) == 1:
                raise
            absent.append(one.adapter)
            if report:
                report(f"{one.adapter}: did not run — {failed}")
            continue
        produced.append(manifest)
        # Ran and produced a manifest, with the instrument that answers the wiring question dead.
        # Distinct from `absent` for the reason `dev07-1-3` gives: an adapter that did not run has said
        # nothing, and one that ran blind has said everything except one thing.
        if unobserved:
            blind.append(one.adapter)
    if not produced:
        raise LaunchFailed(
            f"no adapter produced a manifest ({', '.join(absent)}) — there is nothing to board")
    return _scope(config, merge(*produced), report), tuple(absent), tuple(blind)


def _run_adapter(config: Config, pytest_args: list, mutation: bool,
                 report: Callable[[str], None] | None,
                 *, tests: bool = False) -> tuple[Manifest, bool]:
    """One adapter's manifest, and whether its observation failed while producing it (`dev07-1-3`)."""
    if config.adapter == JAVA:
        return _java(config, mutation=mutation or config.mutation, report=report, tests=tests)
    if config.adapter == DOTNET:
        return _dotnet(config, report=report, tests=tests)
    if config.adapter == PYTHON:
        return _python(config, pytest_args, mutation=mutation or config.mutation, report=report,
                       tests=tests), False
    raise LaunchFailed(f"no adapter named {config.adapter!r}")


def _scope(config: Config, manifest: Manifest, report: Callable[[str], None] | None) -> Manifest:
    """Say what this board answers for, and apply the facts a run cannot observe (``dev07-3-2``).

    **Nothing is added to the manifest here.** A board covers the subjects the run's citations
    named, and there is no second set to union it with: a list handed over is a copy of a list the
    project owns, it desynchronises the moment theirs moves, and nothing here could detect that it
    had. What used to happen at this seam — constructing a subject out of an entry nothing cited —
    was the enumeration, and it is gone.

    What remains is a lookup: an *archetype* is a fact about how to judge a subject and no run can
    observe it, so a project whose spec its runner cannot execute declares it in ``plumb.toml``
    keyed by id (``dev07-4-2``, ``dev07-3-2``). Silence means behavioral, which is right for almost every
    subject, and an entry for an id nothing cites is inert rather than a phantom row on a board.
    """
    # What a board covers is stated on the board itself rather than here (`dev07-3-2`). It was said in
    # this run's chatter, which `dev07-5-2`'s argument already rejects for run-level facts: what a
    # reader keeps, pastes into a ticket or scrolls back to is the board, and a fact that lives only
    # in the progress output is one the board still fails to state. Saying it in both places is
    # worse than either — one claim with two homes is what drifts.
    tables = (("archetype", config.archetypes), ("aspects", config.aspects),
              ("reduce", config.reduce), ("lexicon", config.lexicon))
    if not any(table for _, table in tables):
        return manifest

    stories = dict(manifest.stories)
    for field_name, table in tables:
        for sid, value in table.items():
            # Only for an id this run actually saw. An entry for anything else is inert, which is
            # the whole reason a property table may live here where a list may not.
            if sid not in stories or getattr(stories[sid], field_name) == value:
                continue
            # Loud, never silent (`dev07-5-1`). The manifest carries the default whether a spec said so
            # or nothing did, and those are different claims we cannot tell apart — so an override
            # is reported rather than quietly applied.
            if report:
                report(f"stories: {sid} declares {field_name}={value!r} in plumb.toml, overriding "
                       f"{getattr(stories[sid], field_name)!r} from the run")
            stories[sid] = replace(stories[sid], **{field_name: value})
    return replace(manifest, stories=dict(sorted(stories.items())))


def _python(config: Config, pytest_args: list[str], *, mutation: bool,
            report: Callable[[str], None] | None, tests: bool = False) -> Manifest:
    """Always the project's own interpreter, over a run file, out to a manifest.

    The adapter imports the project's code and its test framework, so it has to run where those
    live. While Plumb is a checkout on the path that happens to be this interpreter; installed as
    its own artifact it is emphatically not, and running the adapter here would fail to import the
    project — or worse, import a *different* copy of it that happens to be on the path.

    **The same shape as the JVM adapter, and now for the same reason.** An adapter is a separate
    program the launcher hands already-resolved values to (`dev07-3-3`), and one the launcher can also
    *import* is a privileged one. That privilege is where a language's assumptions get in: the
    archetype was collected from an executing Python spec for months and no other language could
    have offered it, which is the shape a second home takes when one adapter can do what the
    others cannot.

    There was an in-process fast path taken when the interpreter matched. It went unmeasured here
    by construction — `_shadowing_root` sends any project supplying a package by the tool's own
    name out of process — so the branch this project ran was never the branch its adopters ran,
    which is the standing objection to shipping a path no board can see.
    """
    interpreter = _interpreter(config)
    say = report or (lambda line: None)
    work = _scratch(config)
    manifest_path = work / "manifest.json"
    _clear_stale(manifest_path)
    run_file = runfile.write(config, work / RUN_FILE,
                             pytest_args=tuple(pytest_args), mutation=mutation)
    say(f"python: {interpreter}")
    # The child's chatter is relayed by this process rather than handed the descriptor. Letting it
    # inherit stdout corrupts the neutral format (`dev07-5-3`), because `contextlib.redirect_stdout`
    # rebinds only Python's `sys.stdout` and a subprocess writes straight onto the channel `--json`
    # is emitted on. Handing it `sys.stderr` instead traded that for a narrower fault: a caller
    # whose `sys.stderr` is not a real file — a test harness capturing it, an embedding host — has
    # no `fileno` to give, and the run dies in `subprocess` rather than saying anything. Relaying
    # costs one loop and works for both, and it is read line by line so the suite's progress still
    # arrives while it runs rather than in one block at the end.
    child = subprocess.Popen(
        [str(interpreter), "-m", "plumb.adapters.python", str(run_file), str(manifest_path)],
        cwd=config.root, env={**os.environ, "PYTHONPATH": _subprocess_path(config, say)},
        text=True, bufsize=1, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    with child:
        for line in child.stdout or ():
            print(line.rstrip("\n"), file=sys.stderr, flush=True)
    if child.returncode != 0 or not manifest_path.is_file():
        raise LaunchFailed(
            f"the Python adapter failed under {interpreter} (exit {child.returncode})")
    manifest = Manifest.read(manifest_path)
    if tests:
        # The per-test fact, named — what a reader needs when a board is not what they expected
        # (`dev07-3-2`), the same as the Java path gives.
        seen = {}
        for story in manifest.stories.values():
            for cited in story.citations:
                seen.setdefault(cited.test, cited.grounding)
        for test, grounding in sorted(seen.items()):
            say(f"python: {grounding:<11} {test}")
    return manifest


def _scratch(config: Config) -> Path:
    """The adapter's run file and manifest, outside the project — always.

    They are one run's input and output: rebuilt every time, meaningless between runs, and worth
    nothing to keep. Written into the project they made `plumb board` dirty somebody's repository,
    which `plumb session wrap-up` then refused (`dev10-1`) — the tool tripping its own gate on its
    own output — and `dev00-1-2` refuses writing into an adopter's tree to begin with. The escapes from
    there are a `.gitignore` the tool may not write or a gate taught to skip a path it recognises,
    and `session.py` already rejected both for the session reading and moved it out. This is the
    same decision, for the file the tool writes on *every* run rather than one command's.

    Keyed by the project's resolved path, because one tool serves many checkouts and two of them
    sharing a manifest would answer for whichever ran last. Cache rather than state: losing it
    costs nothing at all, where a lost reading at least costs a session its delta.
    """
    import hashlib

    cache = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    key = hashlib.blake2b(str(config.root.resolve()).encode(), digest_size=8).hexdigest()
    return cache / "plumb" / "runs" / key


def _interpreter(config: Config) -> Path:
    """The interpreter the *project* runs under, which is not necessarily the tool's.

    Declared beats discovered beats current. The discovery is deliberately dumb — a venv in the
    usual place, or one already active — because guessing harder is how a tool picks the wrong
    Python and reports a project's own code missing.
    """
    declared = config.options.get("interpreter") if config.adapter == PYTHON else None
    if declared:
        return _absolute(config.root / declared)
    active = os.environ.get("VIRTUAL_ENV")
    candidates = [Path(active) / "bin" / "python"] if active else []
    candidates += [config.root / ".venv" / "bin" / "python", config.root / "venv" / "bin" / "python"]
    for candidate in candidates:
        if candidate.is_file():
            return _absolute(candidate)
    return Path(sys.executable)


def _absolute(path: Path) -> Path:
    """Absolute, and deliberately **not** resolved.

    A virtualenv's ``bin/python`` is a symlink to the base interpreter, and Python works out
    ``sys.prefix`` from the path it was *invoked* by. Following the link therefore runs the base
    interpreter with none of the venv's packages — the project's own test framework included.

    This passed a first test anyway, because the machine happened to have pytest installed
    globally too: the venv was destroyed and the run succeeded on the wrong interpreter's
    packages. A resolved path is the kind of tidiness that silently answers a different question.
    """
    return Path(os.path.abspath(path))


def _own_path() -> str:
    """Where this code lives, so a subprocess under another interpreter can import it.

    A zipapp is a zip, and Python imports out of a zip on ``sys.path`` — so the artifact adds
    itself to ``PYTHONPATH`` and needs nothing installed into the project's environment. That
    only works because the core has no dependencies: there is nothing else to bring along.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        # Inside a zipapp the package sits under the archive itself, which is a file, not a dir.
        if parent.is_file():
            return str(parent)
    return str(here.parent.parent)


def _import_roots(config: Config) -> tuple[str, ...]:
    """Where the *project's* own code is imported from. A declared production path names the
    code; the directory Python imports it *from* is its parent when it is a package, and itself
    when it is not."""
    roots: list[str] = []
    for path in config.resolved(*config.production):
        root = path.parent if (path / "__init__.py").is_file() else path
        if root.is_dir() and str(root) not in roots:
            roots.append(str(root))
    return tuple(roots)


def _shadowing_root(config: Config) -> str | None:
    """The project's import root that supplies a package by *our* top-level name, if any.

    Only one project has ever had one — Plumb — which is precisely why it went unnoticed: the
    reference project is the single case the defect can reach, and it reaches it in the direction
    that flatters.
    """
    ours = __name__.split(".")[0]
    return next((r for r in _import_roots(config) if (Path(r) / ours / "__init__.py").is_file()),
                None)


def _subprocess_path(config: Config, say: Callable[[str], None]) -> str:
    """The child's ``PYTHONPATH``: **the project first, the artifact last**, inherited kept.

    The artifact puts itself on the path so a foreign interpreter can import the adapter
    (:func:`_own_path`), and for almost every project that is invisible — the artifact carries one
    top-level package, ``plumb``, and a project does not have one.

    A project supplying a package by the tool's own name is the case that exposes this. Putting
    the artifact first shadowed the project's own package: ``-m plumb.adapters.python`` binds
    ``sys.modules['plumb']`` at interpreter startup, before pytest applies any path configuration
    of its own, so every ``import plumb`` in the suite resolved to the *shipped* copy instead of
    the tree. Nothing then ran under a declared production root, grounding read `inert` for every
    behavioural story, and the board reported the tool as almost entirely unproven while the same
    commit run from source read 41 proven. It failed silently and in the flattering direction —
    a passing suite over the wrong code.

    Ordering the project ahead of the artifact is also the honest semantic: a run is supposed to
    exercise the code in the tree. Inherited ``PYTHONPATH`` is preserved rather than discarded,
    because a project entitled to set it is entitled to have it survive.
    """
    roots = _import_roots(config)
    inherited = (p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p)
    own = _own_path()
    shadow = _shadowing_root(config)
    if shadow:
        # Surfaced rather than silent (`dev07-5-1`): which copy of itself the tool just ran is the one
        # thing a reader cannot recover from the board afterwards.
        say(f"python: the project supplies its own 'plumb' package from {shadow} — using it")
    return os.pathsep.join([*roots, *inherited, own])


# ---- Java ---------------------------------------------------------------------------------

def _java(config: Config, *, mutation: bool, report: Callable[[str], None] | None,
          tests: bool = False) -> Manifest:
    """Three processes, orchestrated here rather than in a shell script.

    The script this replaces had to be run by hand, in the right order, with its own copy of the
    classpath — which is the *"run two shell scripts, then point plumb at a file"* that made Java
    adoption cost a reading of this repository.

    Grounding needs the suite under JDWP with the observer attached, and the observer needs the
    port the suite chose. That handshake is the reason this cannot simply be one command.
    """
    say = report or (lambda line: None)
    options = config.options
    # **The same scratch the Python adapter uses, and for the same reason.** This defaulted to
    # `build/plumb` *inside* the adopter's repository, which is the thing `dev00-1-2` refuses — one file
    # is written into a project and it is the declaration. The run file and the manifest are one
    # run's input and output, rebuilt every time and worth nothing to keep, and writing them into
    # somebody's tree is what made `plumb board` dirty a repository that `plumb session wrap-up`
    # then refused (`dev10-1`). The Python adapter was moved out; this one was not, and nothing
    # compared them until the adapters were asked the same question.
    #
    # The override stays, because an adopter who set it meant it.
    work = ((config.root / options["work"]).resolve() if options.get("work")
            else _scratch(config))
    work.mkdir(parents=True, exist_ok=True)
    manifest_path = work / "manifest.json"
    _clear_stale(manifest_path)

    java = shutil.which("java") or "java"
    classpath = _classpath(config)
    # Before anything is launched. A divergence found afterwards arrives as somebody else's
    # stacktrace, and reads as their defect (`dev07-1-1`).
    _classpath_parity(config, classpath, say)
    tests_root, roots = _test_roots(config, options)

    agent = _surface_agent(config, roots, scoping=mutation)
    if config.production and not agent:
        say("java: the production surface is declared but the agent that reports it is not "
            "available — grounding will not assert `inert` this run")
    runfile.write(config, work / RUN_FILE, mutation=mutation, surface=bool(agent))

    command = [java, "-ea"]
    if agent:
        command.append(agent)
    command += ["-cp", classpath, "org.plumbspec.PlumbRunner", str(tests_root), str(manifest_path),
                str(work / RUN_FILE)]

    out = (work / "run.out").open("w")
    # ONE PROCESS. There is no debugger to attach, no port to agree on and nothing to wait for the
    # suite on its behalf (`dev07-1-3`): grounding is observed where it happens, by probes the agent
    # inserted, and the runner ends its own process when the manifest is written. What used to be
    # here — a free port, a handshake on a log line, an attach retried against a deadline, and a
    # `terminate()` because a suite holding a non-daemon executor could not be waited on — was all
    # the cost of watching from outside.
    # The runner rewrites this on every test; the heartbeat reads it. Cleared first, so a
    # position reported here was produced by THIS run — a stale one would have the heartbeat
    # confidently counting down the previous run's suite.
    progress = work / "progress.txt"
    progress.unlink(missing_ok=True)
    stop, watcher = _heartbeat("suite", say, progress)
    try:
        suite = subprocess.Popen(command, cwd=config.root, stdout=out, stderr=subprocess.STDOUT)
        suite.wait(timeout=SUITE_TIMEOUT)
    finally:
        stop.set()
        watcher.join(timeout=1)
        out.close()
    log = (work / "run.out").read_text() if (work / "run.out").is_file() else ""
    # The runner's own report, surfaced. It shares a stdout with the suite — which on a real project
    # is thousands of lines of the project's logging — so this matches the shapes the runner emits
    # rather than passing the stream through. The observer used to have a stdout of its own and this
    # is what replaces it; losing the per-test grounding is not a price worth paying for one process.
    # COUNTED, NOT LISTED. On a mature suite the citing tests are a small minority, so the
    # per-test grounding is the least interesting output printed at the greatest length — measured
    # at several hundred lines above a one-line verdict a team adopts a tool to
    # see. The board's output should scale with the SPEC, not with the suite. `--tests` still
    # enumerates, because the per-test fact is what a reader needs when a board is not what they
    # expected, and losing it was never the point (`dev07-3-2`).
    tally: dict[str, int] = {}
    for line in log.splitlines():
        grounding = PER_TEST.match(line)
        if grounding:
            tally[grounding.group(1)] = tally.get(grounding.group(1), 0) + 1
            if tests:
                say(f"java: {line}")
        elif GROUNDING_LINE.match(line) or line.startswith("plumb: "):
            say(f"java: {line}")
    if tally and not tests:
        say("java: " + " · ".join(f"{count} {word}" for word, count in sorted(tally.items()))
            + "   (--tests names them)")
    observation_failed = NOTHING_INSTRUMENTED in log

    if mutation:
        # REFUSED WHERE THE SCOPE CANNOT BE COLLECTED, rather than run over a scope of nothing.
        # `dev07-2-1` mutates what a test drove under a *declared entry point*; with none declared there
        # is no window, every story reports `nothing to mutate` and that reads as a finding about
        # the project when it is this tool having had nothing to look through.
        if not config.entry_points:
            raise LaunchFailed(
                "mutation needs at least one declared entry point, and this project declares "
                "none.\n\nChapter 4 mutates only the code your tests drove *through* an entry "
                "point — never the whole call tree, which pulls in every helper a test brushed "
                "past. Without one there is no scope to mutate, and a run would report every "
                "story clean without having looked.\n\n"
                "  Declare where the wired system begins:\n\n"
                "    [java]\n"
                '    entry_points = ["com.myapp.Service#handle"]')
        if not agent:
            raise LaunchFailed(
                "mutation needs the bytecode agent, and it is not available in this "
                "installation.\n\nThe scope chapter 4 mutates is collected by probes the agent "
                "weaves into the production surface; nothing else knows which methods a test "
                "drove.")
        # `Mutate` compiles a mutant with `javac -d <classes>`, so it needs one writable output
        # directory and cannot be handed several. Refused by name rather than silently writing one
        # module's mutants into another's build output.
        if len(roots) > 1:
            raise InvalidConfig(
                "plumb.toml: mutation needs a single `tests` root, because a mutant is compiled "
                f"into it — this project names {len(roots)}. Run the board without --mutation, or "
                "name one root while mutating")
        # THE LONG PHASE, and so the one that most needs to say where it is (`dev07-1-3`). It writes
        # the same `<done> <total> <millis>` the suite phase does, into the same file, so the
        # launcher reads one contract rather than learning a second — and cleared first, or the
        # heartbeat spends its first tick counting down the suite's finished 1937-of-1937.
        progress.unlink(missing_ok=True)
        _run(java, ["-cp", _compiling_classpath(java, classpath), "org.plumbspec.Mutate",
                    str((config.root / (config.sources[0] if config.sources else ".")).resolve()),
                    str(tests_root), classpath, str(work)],
             cwd=config.root, say=say, what="mutation", stream=True, progress=progress,
             # THE UNIT IS THE PHASE'S OWN. This counter reported `2/252 tests` for a phase that
             # runs no tests of its own — it compiles and runs mutants — and a progress line whose
             # noun is wrong is a progress line the reader has to decode.
             unit="mutants")

    if not manifest_path.is_file():
        log = (work / "run.out").read_text() if (work / "run.out").is_file() else ""
        if "org/junit/platform/launcher" in log:
            # Surefire supplies the launcher internally, so an ordinary Maven project never
            # declares it and `dependency:build-classpath` — the command this tool tells people
            # to run — leaves it out. The failure surfaces as a class the adopter never heard of.
            raise LaunchFailed(
                "the Java adapter needs junit-platform-launcher on the classpath, and your build "
                "does not put it there. Maven's Surefire supplies it internally, so it is absent "
                "from `dependency:build-classpath`. Add it as a test dependency and rebuild the "
                "classpath file:\n\n"
                "    <dependency>\n"
                "      <groupId>org.junit.platform</groupId>\n"
                "      <artifactId>junit-platform-launcher</artifactId>\n"
                "      <scope>test</scope>\n"
                "    </dependency>")
        raise LaunchFailed(
            f"the Java adapter produced no manifest at {manifest_path} — see {work / 'run.out'}")
    # Whether the instrument worked is a fact about the run and travels as one. A board whose
    # grounding is `not-checked` otherwise tells a project that already declared its entry points
    # to declare them — `dev07-1-4`'s objection exactly: the reader's next move differs, so the two
    # reasons cannot share one sentence (`dev07-1-3`).
    return Manifest.read(manifest_path), observation_failed


#: Printed by the runner when a declared surface or entry point was never reached by the agent
#: (``PlumbRunner.NOTHING_INSTRUMENTED``). `dev07-1-3`'s fact with the cause it has now: the instrument
#: did not attach to the project, which is a different `not-checked` from nobody having declared
#: anything, and the reader's next move differs. Matched as a prefix, so the sentence beside it can
#: be reworded without breaking the read.
NOTHING_INSTRUMENTED = "plumb: nothing was instrumented"

#: What the runner prints about each test, and the count above it. Matched rather than streamed,
#: because the runner shares its stdout with the suite and a project's own logging is most of it.
#: Built from the manifest's own vocabulary rather than typed out. It was spelled by hand here for
#: the FOURTH time, and `untouched` was in none of them — so an adapter that had learned to tell
#: *read it and ran none of it* from *touched it in no way at all* had the second answer dropped
#: on the floor by the reader, silently, in the core rather than in either adapter.
_FACTS = "|".join(re.escape(word) for word in sorted(GROUNDING))
GROUNDING_LINE = re.compile(rf"^(grounded \d+ test\(s\)|   (?:{_FACTS})\s)")

#: One test's grounding, with the word captured so the run can be counted by it rather than
#: recited. The count is what a mature suite wants; `--tests` recovers the recital.
PER_TEST = re.compile(rf"^   ({_FACTS})\s")

#: How long a Java suite may run before the launcher stops waiting. The runner ends its own process
#: when the manifest is written (`dev07-1-3`), so reaching this means the suite itself did not finish.
SUITE_TIMEOUT = 3600


def _clear_stale(manifest: Path) -> None:
    """Remove any manifest before the run, so one found afterwards was produced BY the run.

    `is_file()` was the only evidence a run produced anything, and a manifest left by an earlier
    run satisfies it. A board derived from that reports the previous run's stories as proven now,
    which is `dev05`'s "derived from something that ran" quietly reading a different something.

    It is also how a failure that reproduced on every clean checkout stayed invisible on every
    developer machine: the observer died, the manifest from the last working run answered in its
    place, and the board came back green — on the one tree where the evidence was already there.
    CI was the first environment with nothing left over, so CI was where it finally showed.
    """
    manifest.unlink(missing_ok=True)


def _classpath(config: Config) -> str:
    """The project's own test classpath, plus wherever Plumb's Java classes live.

    The adapter's own jar is appended by the tool, never configured: it ships *inside* the
    artifact, so where it lives is Plumb's business and not a setting anybody has to keep correct.
    ``plumb_classpath`` remains only for a checkout driving compiled classes directly.
    """
    from_file = ""
    if config.options.get("classpath_file"):
        # What a build tool can actually produce — `mvn dependency:build-classpath` writes one,
        # and a classpath pasted into config goes stale the first time a dependency moves.
        path = (config.root / config.options["classpath_file"]).resolve()
        if not path.is_file():
            raise InvalidConfig(f"plumb.toml: [java] classpath_file {path} does not exist — "
                                "the project has not been built yet, or the path is wrong")
        from_file = path.read_text().strip()
    parts = [config.options.get("classpath", ""), from_file,
             os.environ.get("PLUMB_JAVA_CLASSPATH", ""),
             config.options.get("plumb_classpath", ""), _bundled_jar()]
    joined = ":".join(p for p in parts if p)
    if not joined:
        raise InvalidConfig("plumb.toml: [java] needs `classpath` — the project's compiled "
                            "classes and its test framework, as `java -cp` would take them")
    _require_adapter_on(joined, config.root)
    return joined


#: Maven's own namespace, because a POM is namespaced and ``find("modules")`` on one silently
#: returns nothing — which reads exactly like a single-module project and is the failure this
#: whole check exists to catch, one level down.
POM_NS = {"m": "http://maven.apache.org/POM/4.0.0"}


def _maven_outputs(root: Path) -> list[tuple[Path, str]]:
    """Every directory a Maven reactor compiles into, as ``(directory, module)``.

    Read off the POMs rather than obtained by running Maven. Running it would be more faithful and
    costs an adopter a resolution pass — often against a network — before a board that has not
    started yet, and what is needed here is only *which directories the build writes*.

    Two per module and no more: Maven copies ``src/*/resources`` **into** ``target/classes`` and
    ``target/test-classes``, so those two carry the resources as well as the code. Gradle does not,
    which is why the two build tools cannot share this list.
    """
    import xml.etree.ElementTree as ET

    found: list[tuple[Path, str]] = []
    seen: set[Path] = set()
    pending = [root]
    while pending:
        here = pending.pop(0)
        pom = here / "pom.xml"
        if here in seen or not pom.is_file():
            continue
        seen.add(here)
        try:
            parsed = ET.parse(pom).getroot()
        except ET.ParseError:
            # A POM this cannot read is not a reason to refuse a run. It is a reason to say less.
            continue
        named = parsed.find("m:artifactId", POM_NS)
        module = named.text.strip() if named is not None and named.text else here.name
        # TEST OUTPUTS FIRST, because that is Surefire's own order and this list is what the
        # remedy is written from. Maven copies `src/*/resources` into both, so `application.
        # properties` exists in each — and whichever comes first wins. Emit them the other way
        # round and the tool hands the adopter a classpath in which the main config shadows the
        # test config, silently, in a run that is supposed to mirror their build.
        for built in ("target/test-classes", "target/classes"):
            found.append((here / built, module))
        for declared in parsed.findall("m:modules/m:module", POM_NS):
            if declared.text:
                pending.append((here / declared.text.strip()).resolve())
    return found


#: ``include ':core'``, ``include("core", "web")``, ``include ":app:api"`` — Groovy and Kotlin DSL,
#: one form each for the quote style and one for the optional parentheses. A colon is Gradle's path
#: separator, so ``:app:api`` is the directory ``app/api``.
GRADLE_INCLUDE = re.compile(r"""include\s*\(?\s*((?:['"][^'"]+['"]\s*,?\s*)+)\)?""")
GRADLE_PROJECT = re.compile(r"""['"]([^'"]+)['"]""")
#: The root project's own name, which is its directory's only by default. Read because it is what a
#: jar of this project is named after, and naming the wrong thing in a refusal sends the reader
#: looking for a file that does not exist.
GRADLE_ROOT_NAME = re.compile(r"""rootProject\.name\s*=\s*['"]([^'"]+)['"]""")


def _gradle_outputs(root: Path) -> list[tuple[Path, str]]:
    """Every directory a Gradle build writes, as ``(directory, project)``.

    **Gradle keeps resources apart from classes**, and that is the whole reason this matters more
    here than under Maven. ``build/resources/test`` is its own classpath entry rather than something
    copied in beside the code, so a classpath assembled out of the compiled-class directories alone
    loses every migration, fixture and property file the suite loads — by default, on a
    conventional project, rather than as an edge case.

    The language directory is globbed rather than named: ``build/classes/java``, ``.../kotlin``,
    ``.../groovy`` and ``.../scala`` are all Gradle's own layout, and naming one of them would make
    this check quietly Java-only inside an adapter that is already only about the JVM.
    """
    settings = next((root / name for name in ("settings.gradle", "settings.gradle.kts")
                     if (root / name).is_file()), None)
    declared = settings.read_text() if settings is not None else ""
    named = GRADLE_ROOT_NAME.search(declared)
    projects = [(root, named.group(1) if named else root.name)]
    if settings is not None:
        for listed in GRADLE_INCLUDE.findall(declared):
            for path in GRADLE_PROJECT.findall(listed):
                here = root.joinpath(*[p for p in path.strip(":").split(":") if p])
                projects.append((here, here.name))
    found: list[tuple[Path, str]] = []
    for directory, name in projects:
        for language in sorted((directory / "build" / "classes").glob("*")):
            for phase in ("main", "test"):
                found.append((language / phase, name))
        for phase in ("main", "test"):
            found.append((directory / "build" / "resources" / phase, name))
    return found


#: What writes this project's runtime, and how to ask it again. ``None`` where nothing does — a
#: project with no build tool has no second answer for this check to hold it against.
def _maven_fix(outputs: list) -> str:
    """The remedy, written from the directories this project actually builds, in runtime order.

    Generated rather than templated because the order is the whole point, and a hint that says
    *<each directory above>* leaves the reader to choose one — which is how the wrong one gets
    chosen.
    """
    listed = ":".join(str(one) for one, _ in outputs) or "target/test-classes:target/classes"
    return ("    mvn -q test-compile dependency:build-classpath "
            "-Dmdep.outputFile=target/plumb-deps.txt\n"
            f"    {{ printf '%s:' '{listed}'; cat target/plumb-deps.txt; }} "
            "> target/plumb-classpath.txt\n\n"
            "  Test outputs FIRST, then main outputs, then the dependencies — Surefire's own\n"
            "  order. Both directories carry the resources Maven copied into them, so whichever\n"
            "  comes first wins, and `application.properties` is the one that bites.")


BUILD_TOOLS = (
    # PREPENDED, IN BUILD ORDER, and this is a correction. The hint used to say to APPEND the
    # output directories — `printf ':%s' … >> file` — which yields `deps:classes:test-classes`
    # while Maven's own runtime order is the reverse. Measured: the main
    # `application.properties` shadowed the test one, a Flyway location vanished, the shared
    # Spring context died, and every `@SpringBootTest` citation sharing it read *did not pass*
    # for tests that are green under Surefire. The guard exists to prevent exactly that
    # divergence, and its own remedy was manufacturing it.
    ("pom.xml", _maven_outputs, _maven_fix),
    ("settings.gradle", _gradle_outputs, None),
    ("settings.gradle.kts", _gradle_outputs, None),
    ("build.gradle", _gradle_outputs, None),
    ("build.gradle.kts", _gradle_outputs, None),
)

#: Gradle can hand over the exact classpath it runs tests on, so the answer for it is not *append
#: the directories we found* — it is *stop reconstructing*. `dev07-1-1` prefers borrowing the build's
#: own runtime to matching it, and this is the one build tool that makes borrowing a four-line task.
GRADLE_FIX = """    // in build.gradle — Gradle's own test runtime, written out verbatim
    tasks.register('plumbClasspath') {
        doLast { file('build/plumb-classpath.txt').text = sourceSets.test.runtimeClasspath.asPath }
    }

    gradle test plumbClasspath"""


def _classpath_parity(config: Config, classpath: str, say: Callable[[str], None]) -> None:
    """Refuse to observe a run the build tool would not perform (``dev07-1-1``).

    Only asks the one question it can answer without running the build tool, and that question is
    the one that was actually wrong: **is everything this build writes present on the classpath we
    are about to run?**

    Under Maven, a sibling module resolves through ``dependency:build-classpath`` to whatever is
    installed in the local repository, while Surefire uses the classes it has just compiled. Those
    are different bytes whenever the sibling has changed and is not installed — the ordinary state
    of a working tree — and can be no bytes at all. What that produced, measured: a secondary tier
    of Flyway migrations that existed for Surefire and did not exist for the observed run, failing a
    Spring context the build boots green. The board would have reported that as the project's.

    Under Gradle the same failure is the *default* rather than an edge case, because Gradle keeps
    resources in their own output directory instead of copying them in beside the code. A classpath
    built from the compiled-class directories alone loses every resource the suite loads, and
    nothing about the resulting stacktrace says so.

    **Missing is refused; extra is said.** A run narrower than the build's manufactures failures the
    build does not have. A run wider than it cannot, so it is surfaced and left alone (``dev07-5-1``).
    """
    build = next(((reader, fix) for marker, reader, fix in BUILD_TOOLS
                  if (config.root / marker).is_file()), None)
    if build is None:
        return                       # no build tool declares a runtime; nothing to hold this to
    reader, fix = build
    if not config.options.get("check_classpath", True):
        say("java: classpath parity not checked — [java] check_classpath = false")
        return

    # ORDERED, not a set. Two classpaths with equal members are not the same classpath: Maven
    # copies `src/main/resources` and `src/test/resources` into `target/classes` and
    # `target/test-classes` respectively, so a project can have `application.properties` in both,
    # and the classpath decides which one the suite loads. A guard that compares membership passes
    # a classpath that quietly runs the wrong configuration.
    order = [str((config.root / entry).resolve()) for entry in classpath.split(":") if entry]
    on = set(order)
    jars = [entry for entry in order if entry.endswith(".jar")]
    missing = []
    for output, module in reader(config.root):
        # Written by this build, rather than merely conventional for it. An output directory that
        # does not exist or holds nothing is a phase this project does not have, and demanding it
        # would refuse every project without test resources for not having any.
        if not output.is_dir() or not any(f.is_file() for f in output.rglob("*")):
            continue
        if str(output.resolve()) in on:
            continue
        # Named as *what answered instead*, because "add this directory" and "your classpath is
        # serving you a built jar of your own module" send a reader to different places.
        instead = next((j for j in jars if f"/{module}/" in j or
                        Path(j).name.startswith(module + "-")), None)
        where = output.resolve()
        shown = where.relative_to(config.root) if where.is_relative_to(config.root) else where
        missing.append(f"{shown}" + (f" — answered instead by {instead}" if instead else ""))
    if not missing:
        shadowed = _shadowed(order, reader(config.root))
        if shadowed:
            raise LaunchFailed(
                "the classpath Plumb would observe has your build's outputs in the wrong order, "
                "and the run it produces is not the run your build performs.\n\n"
                "  Test outputs must come before main outputs. Maven copies the resources of each "
                "into the directory beside the code, so a project with `application.properties` "
                "in both loads whichever comes first — and with main ahead of test, the observed "
                "run silently uses your production configuration.\n\n"
                "  Out of order:\n    " + "\n    ".join(shadowed)
                + "\n\n" + fix(list(reader(config.root)))
                + "\n\n  If this is wrong for your project, turn it off with "
                  "`check_classpath = false` under [java].")
        say("java: classpath parity ok — everything this build writes is on the classpath, "
            "in the order your build runs it")
        return
    raise LaunchFailed(
        "the classpath Plumb would observe is not the one your build runs on, and observing it "
        "would charge your project with failures your build does not have.\n\n"
        "  This build writes these, and they are not on the classpath:\n    "
        + "\n    ".join(missing)
        + "\n\n" + (fix(list(reader(config.root))) if fix else GRADLE_FIX)
        + "\n\n  If this is wrong for your project, turn it off with `check_classpath = false` "
          "under [java] — and read the board knowing the run behind it is not the run your build "
          "performs.")


def _shadowed(order: list[str], outputs) -> list[str]:
    """Where a module's main output sits ahead of its own test output on the classpath.

    Only within one module, and only where both are present: that is the comparison Maven's own
    order settles, and anything wider would be this tool inventing a convention and refusing
    projects for not following it. A sibling module's jar ahead of another module's classes is a
    different question, and not one an ordering rule can answer from here.
    """
    at = {entry: i for i, entry in enumerate(order)}
    found = []
    by_module: dict[str, dict[str, str]] = {}
    for directory, module in outputs:
        kind = "test" if directory.name.startswith("test-") or directory.name == "test" else "main"
        by_module.setdefault(module, {})[kind] = str(directory.resolve())
    for module, kinds in sorted(by_module.items()):
        test, main = kinds.get("test"), kinds.get("main")
        if test in at and main in at and at[main] < at[test]:
            found.append(f"{module}: main outputs at position {at[main] + 1}, "
                         f"test outputs at {at[test] + 1} — the test outputs must come first")
    return found


#: The class the suite is launched as. If a classpath cannot supply it, no JVM started with that
#: classpath can do anything except fail to find its main class. It used to be the observer's, which
#: was the same argument about a process that no longer exists (`dev07-1-3`).
RUNNER_CLASS = "org/plumbspec/PlumbRunner.class"


def _require_adapter_on(classpath: str, root: Path) -> None:
    """Refuse before launching a JVM that cannot possibly work.

    Resolved against ``root``, because that is the JVM's working directory — a relative entry
    like ``target/classes`` means the project's, and checking it against Plumb's own would refuse
    a working project, which is a worse failure than the one this prevents.

    Plumb's own Java classes reach the classpath one of three ways: the bundled jar, a checkout's
    build output, or a project putting them there itself. When none of them do, ``_bundled``
    returns an empty string and the entry is dropped — so the tool launches an observer whose main
    class is absent and reports ``observer failed (1)``, in about a tenth of a second, with the
    JVM's explanation on a stderr nobody read.

    That is Plumb's own installation being broken, and it is indistinguishable from the adopter's
    project being broken, which is the worse of the two to be wrongly told. The reference project
    cannot catch it: its classpath carries ``build/adapter``, so it supplies the observer itself
    and passes whatever the bundle does.
    """
    import zipfile

    for entry in classpath.split(":"):
        candidate = root / entry
        if candidate.is_dir() and (candidate / RUNNER_CLASS).is_file():
            return
        if candidate.is_file() and zipfile.is_zipfile(candidate):
            with zipfile.ZipFile(candidate) as archive:
                if RUNNER_CLASS in archive.namelist():
                    return
    raise LaunchFailed(
        "Plumb cannot find its own Java adapter, so there is nothing to run your suite with. "
        "This is Plumb's installation, not your project.\n\n"
        "The adapter ships inside the artifact and is extracted to a cache on first use. It is "
        "missing when Plumb was installed in a way that does not carry it — a wheel or "
        "`pip install` rather than the published zipapp — or when the extracted copy was removed "
        "or truncated.\n\n"
        "Reinstall from https://plumb.plumbspec.org/install.sh, or set PLUMB_JAVA_CLASSPATH to a "
        "plumb-java.jar you already have.")


def _surface_agent(config: Config, roots, *, scoping: bool = False) -> str | None:
    """``-javaagent`` over the declared production surface (``dev07-1-3``), or nothing to declare.

    The surface reports its own execution instead of being watched for it, because watching it is
    what a debugger cannot afford: measured at hours on one suite and at over 2,700 seconds on
    seventeen test classes of another, under the two instruments a debugger offers, each ruinous
    exactly where the other was cheap.

    **The test roots are passed so the agent can exclude them by origin.** Maven puts tests in the
    same package tree as the code they test, so a surface of ``com.myapp.*`` matches
    ``com.myapp.FooTest`` too — and a transformer, unlike a class-name filter, is told where a class
    was loaded from and can answer the question properly rather than guess at it.

    A project that declares no production surface gets no agent: there is nothing to instrument, and
    `inert` is not assertable without a declaration anyway (``dev07-1-4``).
    """
    # An entry point alone is enough: `dev07-1-3` reads grounding from a probe on it, and a project
    # may declare where the wired system begins without declaring a production surface at all.
    if not config.production and not config.entry_points:
        return None
    jar = _bundled_jar()
    # `Boot-Class-Path: plumb-boot.jar` is resolved by the JVM relative to the agent jar, so the
    # probe has to be sitting beside it before the agent starts. Materialised here rather than
    # left to whoever asks for it first: without it the dispatch primitives are instrumented with a
    # call the bootstrap loader cannot resolve, and every `Thread.start` in the VM throws — which a
    # Spring suite does constantly. Measured: a 41-second board became 584 seconds of failing
    # threads and reported a proven story as unproven.
    _bundled("plumb-boot.jar")
    if not jar:
        # The observer's own absence is refused loudly by `_require_adapter_on`. This is the same
        # installation fault reaching a different flag, and it degrades rather than refuses: without
        # the agent nothing sets the flag, so every test reports having run no production code —
        # which `verdictFor` would read as `inert`, the strongest claim, asserted where nothing
        # looked. Better to carry no surface at all and let `dev07-1-4` withhold it.
        return None
    surface = ",".join(config.production)
    excluded = ",".join(str(Path(root).resolve()) for root in roots)
    entries = ",".join(config.entry_points)
    # The fourth field, and a set rather than one word: `scope` is what chapter 4 asks for and
    # `edges` is what chapter 3 does on every run. Mutation is opt-in because naming every
    # production method costs a constant and a call per site, where the bit `inert` reads costs a
    # store — so a board that is not mutating does not pay for a fact it will not read. `edges` is
    # not opt-in, because `trace.edges` is cardinality 1: an adapter emits it or it is not emitting
    # what the chapter says it emits.
    #
    # Four fields, and there was briefly a fifth carrying production PATHS so a read could be told
    # from any other file a test opened. The surface already declared on the first field answers
    # that against the path, so the protocol keeps the width it had.
    modes = ",".join(part for part in ("scope" if scoping else "", "edges") if part)
    return f"-javaagent:{jar}={surface}|{excluded}|{entries}|{modes}"


def _bundled_jar() -> str:
    """The Java adapter that shipped with this tool, made reachable to a `java -cp`."""
    return _bundled("plumb-java.jar")


def _bundled_annotations() -> str:
    """The citation vocabulary alone (``dev00-1-1``) — what an adopter *compiles* against.

    Deliberately not ``_bundled_jar``: that one carries the observer, the mutator and the runner,
    and none of it belongs on somebody else's compile path just so they can write one citation.
    """
    return _bundled("plumb-annotations.jar")


def _bundled(name: str) -> str:
    """A jar that shipped inside this tool, made reachable to a `java -cp`.

    Inside the artifact the jar is a member of a zip, and a JVM cannot read it there — so it is
    extracted once, to a cache keyed by version. Keyed by version because the alternative is an
    upgrade that silently keeps running the previous adapter, which is a wrong answer rather than
    a stale one.

    Never configured. The jars ship *inside* the artifact, so where they live is Plumb's business
    and not a setting an adopter has to keep correct.
    """
    from plumb import __version__

    here = Path(__file__).resolve()
    archive = next((parent for parent in here.parents if parent.is_file()), None)
    if archive is None:
        # A checkout keeps the jar where the build script leaves it, which is NOT where the
        # artifact carries it. Looking only at the packaged location made this return nothing
        # from a source tree — and the caller then did nothing, quietly.
        for candidate in (here.parent / "adapters" / "java" / name,
                          here.parents[2] / "adapters" / "java" / "build" / name):
            if candidate.is_file():
                return str(candidate)
        return ""

    import zipfile

    cached = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "plumb" / __version__
    jar = cached / name
    # `is_file()` was the whole check, so a jar left truncated by an interrupted run was a file
    # and therefore trusted — permanently, and on CI where ~/.cache is commonly restored from a
    # cache action, shared with every later run. A JVM given a truncated jar reports the main
    # class as missing, which reads as a broken project rather than a broken download.
    if not (jar.is_file() and zipfile.is_zipfile(jar)):
        member = f"plumb/adapters/java/{name}"
        with zipfile.ZipFile(archive) as bundle:
            if member not in bundle.namelist():
                return ""
            cached.mkdir(parents=True, exist_ok=True)
            # Written whole, then moved into place: an interrupted extraction leaves a partial
            # file under a name nothing looks for, instead of a partial jar under the one name
            # everything trusts. Same-directory rename, so it is atomic on every POSIX filesystem.
            partial = jar.with_suffix(jar.suffix + f".{os.getpid()}.part")
            partial.write_bytes(bundle.read(member))
            partial.replace(jar)
    return str(jar)


#: The variables a JVM reads BEFORE its command line. An agent named in one of them is processed
#: ahead of every flag Plumb passes, which is the one placement the launcher cannot correct.
PREPENDED = ("JAVA_TOOL_OPTIONS", "_JAVA_OPTIONS", "JDK_JAVA_OPTIONS")


def _agent_before_jdwp() -> str:
    """Name the cause when a suite dies during VM startup with an agent ahead of the debugger.

    A `-javaagent` processed before `-agentlib:jdwp` kills the VM during init: JDWP's own early
    setup fails with a JNI error and the process is gone before a line of the suite runs. Any agent
    doing ordinary work in `premain` does it — reproduced with one whose transformer returns null
    for every class — so it is a property of the pair and not of anybody's instrumentation.

    Plumb orders its own flags correctly. It cannot order these: the JVM reads them first by
    definition. So the tool's own diagnosis — *the suite exited before it began listening* — is
    exactly right and reads as the adopter's project being broken, when the cause is one variable.
    """
    named = [v for v in PREPENDED if "-javaagent" in os.environ.get(v, "")]
    if not named:
        return ""
    return (
        "\n\n" + " and ".join(named) + " names a `-javaagent`, and a JVM reads those before the "
        "command line — so that agent is processed ahead of the debugger Plumb attaches, which "
        "kills the VM during startup. It is not your project and not that agent: any agent in that "
        "position does it.\n\n"
        "  Run the board with it unset, or move the agent onto the build's own JVM arguments "
        "where it lands after Plumb's.")


#: How long an observed run goes quiet before it starts saying so, and how often after that.
#: Observation costs wall time in proportion to what a test *calls* rather than what it claims, so a
#: suite touching a driver or a migration engine can take minutes where it took seconds. That is a
#: cost, and a cost said out loud is a different thing from a hang: measured: a board
#: that had been running for ten minutes and printed nothing was read as broken and abandoned twice.
HEARTBEAT_SECONDS = 20


def _heartbeat(what: str, say, progress: Path | None = None, unit: str = "tests") -> "tuple":
    """Say where a long run has got to, so an operator can decide whether to wait.

    **A heartbeat that only repeats itself explains why a run is slow and never where it is.**
    Measured: 9h46m in which position could only be had by grepping the raw output,
    remaining time was unestimable at every point, and the run was killed at a scheduling cap —
    possibly minutes from the evidence it was about to produce. An operator who cannot estimate
    completion will kill correct runs, and the method loses its answer at the moment it had one.

    So the contract is *done / discovered*, plus a rate and an estimate once there is enough to
    compute one. The estimate is deliberately arithmetic and unqualified — tests are not uniform
    and it will be wrong — because a wrong estimate that moves is decidable and no estimate is not.
    """
    import threading
    import time

    started, stop = time.monotonic(), threading.Event()

    def position() -> str:
        return _position(progress, time.monotonic() - started, unit)

    def tick():
        while not stop.wait(HEARTBEAT_SECONDS):
            waited = int(time.monotonic() - started)
            where = position()
            if where:
                say(f"java: {what} running, {waited}s{where}")
            elif progress is not None:
                # A position was expected and has not arrived. The run is still starting up —
                # discovering tests, or building the plan — and saying so is better than a fraction
                # nobody measured.
                say(f"java: {what} running, {waited}s — starting up")
            else:
                # NO POSITION IS EXPECTED AT ALL, which is not the same as one not having arrived.
                # This said "discovering tests" for both, so a phase that discovers nothing —
                # mutation, which is compiling and running mutants — reported an activity it was
                # not performing, in the phase that runs longest and is least able to afford it.
                say(f"java: {what} running, {waited}s")

    watcher = threading.Thread(target=tick, daemon=True)
    watcher.start()
    return stop, watcher


def _position(progress: Path | None, elapsed: float, unit: str) -> str:
    """How far a phase has got, or nothing when it has not said yet.

    A free function so it can be checked without waiting out a heartbeat interval: the formatting
    is the part that is easy to get wrong — a phase counting mutants and saying *tests*, or a rate
    rounding to `0.1` where the useful fact is `~4.3s each` — and a test that has to sleep twenty
    seconds to see it is a test that gets skipped instead of run.
    """
    if progress is None:
        return ""
    try:
        done, discovered, _ = progress.read_text().split()
    except (OSError, ValueError):
        # Not written yet, or caught mid-write. Either way this tick has no position to add.
        return ""
    done, discovered = int(done), int(discovered)
    if discovered < 1:
        return ""
    share = f"{done}/{discovered} {unit} ({done * 100 // discovered}%)"
    if done < 1 or elapsed < 1:
        return f" — {share}"
    left = (discovered - done) * elapsed / done
    # RATE OR PACE, whichever reads. A suite runs tests at tens per second and a rate is the
    # natural form; a mutation phase spends seconds on each one, and `0.1 mutants/s` is a rounding
    # of a number nobody wanted — `~4.3s each` is the same fact, legible.
    rate = done / elapsed
    pace = f"{rate:.1f} {unit}/s" if rate >= 1 else f"~{elapsed / done:.1f}s each"
    return f" — {share}, ~{_duration(left)} left at {pace}"


def _duration(seconds: float) -> str:
    """Coarse on purpose: `~2h` is what a decision to wait or not is made on, and `~1h58m12s`
    invites a precision this estimate does not have."""
    seconds = int(seconds)
    if seconds < 90:
        return f"{seconds}s"
    if seconds < 5400:
        return f"{seconds // 60}m"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


def _run(java: str, args: list[str], *, cwd: Path, say, what: str, stream: bool = False,
         progress: Path | None = None, unit: str = "tests") -> subprocess.CompletedProcess:
    # `stream` still means "let it through as it happens", but onto stderr — never stdout, which
    # is the channel the board is emitted on.
    stop, watcher = _heartbeat(what, say, progress, unit)
    try:
        completed = subprocess.run([java, *args], cwd=cwd, text=True, capture_output=not stream,
                                   **({} if not stream else {"stdout": sys.stderr}))
    finally:
        stop.set()
        watcher.join(timeout=1)
    if not stream and completed.stdout:
        for line in completed.stdout.splitlines():
            say(f"java: {line}")
    if completed.returncode != 0:
        # Never silent. A failed observer means grounding is `not-checked` rather than wrong, and
        # a reader has to be told which of those they are looking at (`dev07-1-4`).
        say(f"java: {what} failed ({completed.returncode}) — the board reports what it could get")
        # And told *why*. A JVM puts its exception on stderr, which this captured and then never
        # read: the one artifact naming the cause was produced, discarded, and the reader left
        # with an exit code. It cost a consumer's first cold CI run — `observer failed (1)` and
        # nothing else, on a runner whose workspace leaves with it — and the cause had to be
        # reconstructed by hand, off the machine that had already been told what it was.
        for line in (completed.stderr or "").splitlines():
            say(f"java: {what}: {line}")
    return completed



def _compiling_classpath(java: str, classpath: str) -> str:
    """The classpath mutation compiles on, with the JDK's own compiler where it needs finding.

    Mutation reads and rewrites a parse tree with the compiler the JDK already ships. From Java 9
    that is an exported package of `jdk.compiler` and already reachable; below it, the same classes
    are in `tools.jar` beside the runtime and on nobody's classpath. Added when it is there, which
    is the only version it is (`dev07-3-1-sr3` — the capability holds at the floor, and what it
    takes to hold there is ours to arrange, not the adopter's).
    """
    tools = Path(java).resolve().parent.parent / "lib" / "tools.jar"
    return f"{classpath}{os.pathsep}{tools}" if tools.is_file() else classpath

def _test_roots(config, options) -> tuple[str, list]:
    """Where the runner discovers tests, as one argument and as the list behind it.

    **A path or a list of them.** A spec does not stop at a module boundary — one chapter can
    describe a system whose pieces compile separately — so a repository with two Maven modules and
    one spec must be able to board both. Naming a single root means the board answers for a subset
    of what it observed while presenting itself as answering for all of it — `dev07-3-2`'s boundary,
    arriving here as a configuration question rather than a reporting one.

    Joined with the platform's path separator rather than passed as extra arguments, because the
    runner's remaining arguments are positional and a variable-length list in front of them is a
    contract that breaks the first time somebody adds a root.

    A list used to reach `config.root / tests` and die in a TypeError about PosixPath and list. The
    config reader refuses an unknown adapter by name; this path had no such standard and now does.
    """
    import os

    from plumb.config import InvalidConfig

    tests = options.get("tests")
    if not tests:
        raise InvalidConfig("plumb.toml: [java] needs `tests` — the classpath root holding the "
                            "compiled test classes, which is what the runner discovers from")
    # The type is checked before anything is done with it: `list(7)` raises a TypeError of its own,
    # which is the same unhandled traceback this function exists to replace, one line further on.
    named = [tests] if isinstance(tests, str) else tests
    if not isinstance(named, list) or not named or not all(isinstance(o, str) for o in named):
        raise InvalidConfig(
            "plumb.toml: [java] `tests` is a path, or a list of paths for a project whose modules "
            f"compile separately — got {tests!r}")
    roots = [(config.root / one).resolve() for one in named]
    missing = [str(r) for r in roots if not r.exists()]
    if missing:
        raise InvalidConfig(
            "plumb.toml: [java] `tests` names " + ", ".join(missing) + ", which does not exist. "
            "A root is a compiled output directory, so it appears after the module is built")
    return os.pathsep.join(str(r) for r in roots), roots



# ---- .NET ---------------------------------------------------------------------------------

#: The collector VSTest loads into the testhost, by the name its own assembly declares. A string,
#: because VSTest matches it whole — a short name finds nothing and initialises nothing, silently.
DOTNET_COLLECTOR = "PlumbSpec.Collector, PlumbSpec.Adapter, Version=1.0.0.0, Culture=neutral, " \
                   "PublicKeyToken=null"


def _dotnet(config: Config, *, report: Callable[[str], None] | None,
            tests: bool = False) -> tuple[Manifest, bool]:
    """A copy of the build's output, run by VSTest with plumb's collector in the testhost.

    **A copy, made afresh, outside the project's tree** (`dev07-1-3-sr11`). The .NET host settles
    which assemblies it loads from the build's `deps.json` before any code of ours runs, so the
    weave that observes production has to be in the files the host loads — and those files are the
    adopter's build output, which this never writes to. The copy is where the weave will happen; in
    this slice nothing is woven yet and the copy is run as it was built.

    **VSTest, not a framework.** The collector hears every test start and end from VSTest itself, so
    xUnit, NUnit and MSTest are one road, and the test SDK the project already references is all a
    run needs (`dev00-1-1-ur8`).
    """
    say = report or (lambda line: None)
    built = _dotnet_tests(config)
    work = _scratch(config)
    manifest_path = work / "manifest.json"
    _clear_stale(manifest_path)
    (work / "report.txt").unlink(missing_ok=True)

    collector = _bundled_collector()
    if not collector:
        # The tool's own install is the fault, so it is named as that (`dev00-1-1-ur7`).
        raise LaunchFailed(
            "the .NET adapter's collector is not in this installation, which was built "
            "without it. In a checkout, build it with `dotnet build adapters/dotnet/adapter`")

    copy = work / "output"
    shutil.rmtree(copy, ignore_errors=True)
    shutil.copytree(built.parent, copy)

    # Nothing observes grounding yet, so the surface is not named to the collector: `inert` is read
    # from an absence, and an absence nothing watched for proves nothing (`runfile.write`).
    run_file = runfile.write(config, work / RUN_FILE, surface=False)
    settings = work / "plumb.runsettings"
    settings.write_text(_runsettings(collector, manifest_path, run_file, work / "results"))

    dotnet = shutil.which("dotnet") or "dotnet"
    say(f"dotnet: {built.name}, a copy at {copy}")
    with (work / "run.out").open("w") as out:
        try:
            subprocess.run([dotnet, "test", str(copy / built.name), "--settings", str(settings)],
                           cwd=config.root, stdout=out, stderr=subprocess.STDOUT,
                           timeout=SUITE_TIMEOUT)
        except subprocess.TimeoutExpired:
            raise LaunchFailed(f"the .NET suite did not finish in {SUITE_TIMEOUT}s — see "
                               f"{work / 'run.out'}") from None

    if not manifest_path.is_file():
        raise LaunchFailed(
            f"the .NET adapter produced no manifest at {manifest_path} — see {work / 'run.out'}")

    said = (work / "report.txt").read_text() if (work / "report.txt").is_file() else ""
    tally: dict[str, int] = {}
    for line in said.splitlines():
        grounding = PER_TEST.match(line)
        if grounding:
            tally[grounding.group(1)] = tally.get(grounding.group(1), 0) + 1
            if tests:
                say(f"dotnet: {line}")
        elif GROUNDING_LINE.match(line) or line.startswith("plumb: "):
            say(f"dotnet: {line}")
    if tally and not tests:
        say("dotnet: " + " · ".join(f"{count} {word}" for word, count in sorted(tally.items()))
            + "   (--tests names them)")

    # Declared and not watched is a run that went blind, which is a different `not-checked` from
    # nobody having declared anything, and the reader's next move differs (`dev07-1-4-ur5`).
    blind = bool(config.entry_points or config.production)
    if blind:
        say("dotnet: entry points and production are declared, and this adapter does not observe "
            "grounding yet — every citation reads not-checked")
    return Manifest.read(manifest_path), blind


def _dotnet_tests(config: Config) -> Path:
    """The built test assembly `[dotnet] tests` names, refused by name when it is not there."""
    tests = config.options.get("tests")
    if not isinstance(tests, str) or not tests:
        raise InvalidConfig("plumb.toml: [dotnet] needs `tests` — the test project's built "
                            "assembly, as `dotnet build` leaves it, e.g. "
                            '"tests/bin/Debug/net8.0/MyApp.Tests.dll"')
    built = (config.root / tests).resolve()
    if not built.is_file():
        raise InvalidConfig(f"plumb.toml: [dotnet] `tests` names {built}, which does not exist — "
                            "the project has not been built yet, or the path is wrong")
    return built


def _runsettings(collector: str, manifest: Path, run_file: Path, results: Path) -> str:
    """The run settings that load the collector and tell it where the run's files are."""
    from xml.sax.saxutils import quoteattr, escape

    return (
        "<RunSettings>\n"
        f"  <RunConfiguration><ResultsDirectory>{escape(str(results))}</ResultsDirectory>"
        "</RunConfiguration>\n"
        "  <InProcDataCollectionRunSettings><InProcDataCollectors>\n"
        '    <InProcDataCollector friendlyName="plumb" uri="InProcDataCollector://plumbspec/1" '
        f"assemblyQualifiedName={quoteattr(DOTNET_COLLECTOR)} enabled=\"True\" "
        f"codebase={quoteattr(collector)}>\n"
        f"      <Configuration><Manifest>{escape(str(manifest))}</Manifest>"
        f"<RunFile>{escape(str(run_file))}</RunFile></Configuration>\n"
        "    </InProcDataCollector>\n"
        "  </InProcDataCollectors></InProcDataCollectionRunSettings>\n"
        "</RunSettings>\n")


def _bundled_collector() -> str:
    """The .NET collector that shipped with this tool, or nothing.

    A checkout keeps it where `dotnet build` leaves it. Inside the artifact it is not carried yet,
    so an installation without it says so rather than looking anywhere else.
    """
    here = Path(__file__).resolve()
    if any(parent.is_file() for parent in here.parents):
        return ""
    candidate = here.parents[2] / "adapters" / "dotnet" / "build" / "PlumbSpec.Adapter.dll"
    return str(candidate) if candidate.is_file() else ""
