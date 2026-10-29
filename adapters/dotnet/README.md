# The .NET adapter

A VSTest run in, a manifest out (`dev07-3-3`). The core reads the manifest and derives every status
from it, so nothing here decides anything.

    dotnet build adapters/dotnet/adapter      # the collector, into build/ — the publisher's step
    dotnet build adapters/dotnet/sample/Tests # the sample's own build — the adopter's step
    plumb board --project adapters/dotnet     # one command, as for any project

**Your build, then a copy of it.** Plumb does not build your project. It copies the test project's
build output to its own scratch, outside your tree, weaves the copy, and runs VSTest over it
(`dev07-1-3-sr11`). Your `bin/` is never written to. It has to be a copy: the .NET host settles which
assemblies it loads from `deps.json` before any code of plumb's could run.

The copy sits at the end of a mirror of the path to your output: each directory on that path is a
real directory in plumb's scratch, and everything beside it is a link to yours. So a test that goes
up from `AppContext.BaseDirectory`, or from its working directory, to reach `../../../TestData`
finds your files exactly as under `dotnet test` (`dev07-1-3-sr14`). Writing is where the two differ:
a file written into a directory on the path to your output — `../../../out.txt` — lands in the
mirror, not in your tree, and one written into anything beside that path goes through the link
into your tree, as it would under `dotnet test`. Whether the links hold on Windows is not yet measured (`dev07-1-3-u9`).

**Your build's runtime, checked first** (`dev07-1-1`). Before anything is copied, the build's own
`<tests>.deps.json` is read: an assembly it declares that is not in the output is refused by name,
and so is a referenced project rebuilt after the tests — `dotnet test` would build first and run the
new one, so plumb would otherwise observe code that is no longer yours. The remedy is
`dotnet build` of the test project. `check_runtime = false` under `[dotnet]` turns it off.

**One collector, every framework.** An in-process data collector rides in the testhost and hears
each test start and end from VSTest itself, so xUnit, NUnit and MSTest are one road. It needs only
the `Microsoft.NET.Test.Sdk` your test project already references (`dev00-1-1-ur8`), and it is
compiled against the oldest object model that has the in-process collector, so it binds to whichever
one your test SDK brings.

Three parts: `annotations` — the citation vocabulary alone, `PlumbSpec.Annotations` — `adapter`,
the weaver, the collector and the probe in one assembly, and `sample`, the fixtures `tests/test_the_dotnet_adapter.py` boards: an xUnit suite
under `sample/Tests` with `App` as its production, and `NUnitTests` and `MSTestTests`, each citing
one test per way its framework spells a result. All target
`net6.0`, the floor, so the sample's tests run on the floor runtime whatever SDK built them;
`global.json` pins the SDK that builds them to 10.0.

## Citing

    [Fact]
    [Proves("ORD-1", "wiring", Ref = "JIRA-4412")]
    public void OrdersAreRouted() { ... }

`[Proves(id, depth)]` on a test, or on its class to cite for every test the class holds; repeatable.
`[Informs(id, About = …)]` for a decision or a parameter, with no depth. The collector reads both by
name, so a project's copy of the vocabulary is read whatever version it is.

A skip is "specified, not built", whichever framework spells it — xUnit's `Skip`, NUnit's and
MSTest's `[Ignore]`, and both their `Assert.Inconclusive`. Each row of a theory or data-driven
test is a citation of its own, named by its arguments, so a failing row never hides behind a
passing one.

## Declaring

    adapter = "dotnet"
    entry_points = ["MyApp.Api.Handle"]   # Namespace.Type.Method; a nested type as Outer+Inner
    production   = ["MyApp", "MyApp.*"]   # assemblies, by assembly name

    [dotnet]
    tests = "tests/MyApp.Tests/bin/Debug/net8.0/MyApp.Tests.dll"

Production is named by **assembly**, because where code was loaded from is what tells it from a
test (`dev07-1-3-sr04`); the test assembly is the one `tests` names.

## Grounding

The weave is the adapter's own, on the runtime's own metadata reader (`dev07-1-3-sr12`). In the copy:

- every production method's first instruction reports that it ran;
- each declared entry point is wrapped in `try { … } finally { … }`, so its window closes on a throw
  as on a return. The window is kept per logical flow, not per thread (`dev07-1-3-sr05`): an async
  entry point's `finally` runs when it first yields and closes the window only for its caller, and
  the work it awaits stays inside it until that work is done, on whichever thread resumes it;
- each test's first instruction opens the test's own window;
- each async step (`MoveNext` of a compiler-made state machine) says whose flow it resumes;
- each call to a hand-off primitive is pointed at a shim that sees it and carries the window.

The window rides the test's logical flow, an `AsyncLocal` that .NET carries into whatever the test
awaits, starts or queues (`dev07-1-3-sr05`). It is opened by the test and not by VSTest, because
VSTest reports a test from another thread than the one running it under xUnit and NUnit, and xUnit
runs test classes at once (`dev07-1-3-sr13`).

A test then reads `grounded` (its own flow entered an entry point), `dispatched` (work it handed to
another thread entered one, or a hand-off was seen leaving), `ungrounded` (it ran production and no
entry point), or `untouched` (it ran none). Beside it, each citation names the outermost entry points
the test's work came in through (`entered_through`, `dev07-1-4-ur3`) and says whether it also ran
production with no window open (`reached_outside_entry`, `ur4`); where no window could be read,
both are `null`, not reported.

## Following a hand-off

.NET carries a test's flow to every thread it reaches, across an `await` and across a hand-off
alike, so the flow alone cannot say whether the test is still the one running. Two aspects tell
them apart:

- **The hand-off, at the call.** .NET's primitives are in its own libraries, which are not in the
  copy, so the aspect goes on the call: `Task.Run`, `TaskFactory.StartNew`, `new Thread(…)` and
  `ThreadPool.QueueUserWorkItem` (and `UnsafeQueueUserWorkItem`) in woven code call a shim instead,
  matched on the exact signature. The shim marks the window as having sent work and wraps the
  delegate, which carries the window, says it is handed-off work across its own awaits, and restores
  the thread on every way out (`dev07-1-4-sr2`). A task the runtime runs inline on the test's own
  thread is still the hand-off's.
- **The await, at the step.** A step of the project's own async code resuming the test's flow is the
  test's own, on whatever thread it resumes (`dev07-1-3-sr05`).

Anything else reaching an entry point with the test's flow — a timer, or a hand-off a library made —
is work the test sent somewhere, and reads `dispatched` (`dev07-1-4-sr4`). A hand-off a library makes
whose work never arrives is not seen (`dev07-1-4-u5`). `inert` is never said: a read of the artifact is not
observed yet (`dev07-1-3-u7`), and `inert` is not claimed from an absence. A test whose body never ran
— skipped, or marked by a test attribute the weave does not know — reads `not-checked`.

**What is woven is appended, never re-encoded.** New names, signatures and rows go after what is
there, so every existing offset and token keeps its meaning; new bodies and metadata go in one added
section. An assembly that would need an index widened, that is ReadyToRun or mixed-mode, or a
method that uses `jmp`, is left exactly as built and named on the run (`dev07-1-3-nfr3`).

## Not yet

Reads (`inert`), setup code run before a test's own window opens (`dev07-1-3-u8`), progress
(`dev07-1-5`), mutation, plumb coverage, and the adapter riding inside the shipped artifact. Until it does, an installed plumb refuses a .NET project by naming its
own install.
