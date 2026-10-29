# The .NET adapter

A VSTest run in, a manifest out (`dev07-3-3`). The core reads the manifest and derives every status
from it, so nothing here decides anything.

    dotnet build adapters/dotnet/adapter      # the collector, into build/ — the publisher's step
    dotnet build adapters/dotnet/sample/Tests # the sample's own build — the adopter's step
    plumb board --project adapters/dotnet     # one command, as for any project

**Your build, then a copy of it.** Plumb does not build your project. It copies the test project's
build output to its own scratch, outside your tree, and runs VSTest over the copy
(`dev07-1-3-sr11`). Your `bin/` is never written to. The copy is where production will be woven,
because the .NET host settles which assemblies it loads from `deps.json` before any code of plumb's
could run.

**One collector, every framework.** An in-process data collector rides in the testhost and hears
each test start and end from VSTest itself, so xUnit, NUnit and MSTest are one road. It needs only
the `Microsoft.NET.Test.Sdk` your test project already references (`dev00-1-1-ur8`), and it is
compiled against the oldest object model that has the in-process collector, so it binds to whichever
one your test SDK brings.

Three parts: `annotations` — the citation vocabulary alone, `PlumbSpec.Annotations` — `adapter`,
the collector, and `sample`, the fixtures `tests/test_the_dotnet_adapter.py` boards: an xUnit suite
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
    entry_points = ["MyApp.Api.Handle"]   # Namespace.Type.Method
    production   = ["MyApp"]

    [dotnet]
    tests = "tests/MyApp.Tests/bin/Debug/net8.0/MyApp.Tests.dll"

## Not yet

Grounding. Nothing is woven yet, so every citation reads `not-checked` and the board says the run
went blind (`observation.failed`) rather than asking you to declare entry points you declared.
After that: the runtime check against `deps.json` (`dev07-1-1`), progress (`dev07-1-5`), mutation,
plumb coverage, and the collector riding inside the shipped artifact. Until it does, an installed
plumb refuses a .NET project by naming its own install.
