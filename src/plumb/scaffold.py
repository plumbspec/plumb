"""``plumb init`` — get a project from nothing to a board it can run (``dev00-1-2``, ``dev00-1-3``).

Adoption was measured and found to cost a reading of this repository. The expensive part was never
the concepts; it was working out what to *write down* — which classes count as production, where
the compiled tests live, what a classpath file is for. This detects what it can, writes the one
config file, and says what to do next in commands rather than prose.

**It completes, and never overwrites** (``dev00-1-2``). What is missing is written, what is already
there is left exactly as it is, and both are reported. Adopting in pieces is the observed failure
mode, so finishing a partial adoption is the common path — and a tool that destroys work when run
twice is a tool nobody dares run once.

What this does **not** do, and will not, is emit a spec — no claim vocabulary, no first chapter, no
integrity gates. That was once described as the unbuilt half of adoption; it is better read as a
capability this tool does not have. A project does not need a spec to get a board, because story
ids are opaque and Plumb keeps no catalog (``dev07-3-2``), and how a project writes its subjects down
is not something a tool gets to settle for it.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from plumb.config import CONFIG_NAME, JAVA, PYTHON


@dataclass(frozen=True)
class Detected:
    """What the project looks like, and what it would therefore be told to declare."""

    adapter: str
    production: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    entry_points: tuple[str, ...] = ()
    options: dict = None
    notes: tuple[str, ...] = ()
    #: Which build tool writes this project's runtime, where one does. Carried explicitly rather
    #: than inferred downstream from a path that happens to start `target/`: what to tell an
    #: adopter to run differs completely between the two, and reading it back off a filename is a
    #: second home for a fact this already knows.
    build_tool: str | None = None


def detect(root: Path) -> Detected:
    """Guess from the layout, and be obvious about what is a guess.

    Never silent: every value this cannot work out is emitted as a commented placeholder with the
    question spelled out, because a config file that looks complete and is wrong costs more than
    one that is visibly unfinished.
    """
    if (root / "pom.xml").is_file() or (root / "build.gradle").is_file() \
            or (root / "build.gradle.kts").is_file():
        return _java(root)
    return _python(root)


#: The two build tools `plumb init` accepts for a JVM project, named rather than spelled out at
#: each use — the string reaches `plumb.toml` comments and the printed next steps.
MAVEN, GRADLE = "maven", "gradle"


def _java(root: Path) -> Detected:
    maven = (root / "pom.xml").is_file()
    tests = "target/test-classes" if maven else "build/classes/java/test"
    production = tuple(f"{p}.*" for p in _java_packages(root / "src" / "main" / "java")) \
        or ("com.example.*",)
    packages = [p for p in production if p != "com.example.*"]
    notes = () if packages else (
        "no src/main/java found — `production` is a placeholder, set it to your own packages",)
    return Detected(
        adapter=JAVA,
        production=production,
        sources=("src/main/java",),
        entry_points=(),
        options={"tests": tests, "classpath_file": "target/plumb-classpath.txt" if maven
                 else "build/plumb-classpath.txt"},
        build_tool=MAVEN if maven else GRADLE,
        notes=notes + (
            "entry_points is empty: nothing can be checked for reaching the wired system until "
            "you name at least one",
            "classpath_file must exist before `plumb board` runs — with Maven: "
            "mvn -q test-compile dependency:build-classpath "
            "-Dmdep.outputFile=target/plumb-classpath.txt"
            if maven else
            "classpath_file must exist before `plumb board` runs — with Gradle, register the "
            "plumbClasspath task below and run `gradle test plumbClasspath`",
            "add junit-platform-launcher as a test dependency — Surefire supplies it internally, "
            "so it is missing from the dependency classpath and the adapter cannot start without it",
        ),
    )


def _java_packages(source_dir: Path) -> list[str]:
    """The deepest package prefix that still covers everything.

    Stopping at the first directory would emit `com.*`, which matches every library in the
    classpath as well as the project — and the observer filters production classes by that
    pattern, so an over-broad one turns a narrow probe into a whole-program trace. Descend while
    there is exactly one way down and no source yet.
    """
    if not source_dir.is_dir():
        return []
    found = []
    for top in sorted(p for p in source_dir.iterdir() if p.is_dir()):
        node, parts = top, [top.name]
        while True:
            children = [c for c in node.iterdir() if c.is_dir()]
            if list(node.glob("*.java")) or len(children) != 1:
                break
            node = children[0]
            parts.append(node.name)
        found.append(".".join(parts))
    return found


def _python(root: Path) -> Detected:
    src = root / "src"
    candidates = [p for p in (src.iterdir() if src.is_dir() else []) if (p / "__init__.py").is_file()]
    if not candidates:
        candidates = [p for p in root.iterdir()
                      if p.is_dir() and (p / "__init__.py").is_file() and not p.name.startswith(".")]
    production = tuple(str(p.relative_to(root)) for p in sorted(candidates)) or ("src/myapp",)
    return Detected(
        adapter=PYTHON, production=production, sources=production, entry_points=(),
        options={},
        notes=(() if candidates else ("no package found — `production` is a placeholder",)) + (
            "entry_points is empty: nothing can be checked for reaching the wired system until "
            "you name at least one",
        ),
    )


def render(found: Detected) -> str:
    """The config file, with the reasoning inline. Comments are the cheapest documentation there
    is: they arrive with the thing they explain and cannot be looked for and not found.

    **Durable reasoning only.** A note is a fact about the project at the moment `plumb init` looked
    at it — *you have named no entry points*, *this file does not exist yet* — and the config is the
    very thing the adopter then changes. Writing one into the file makes a second home for a fact
    whose first home is the line above it, and it goes stale the moment they act on it.

    Observed: a `plumb.toml` carried *"entry_points is empty: nothing can be checked
    for reaching the wired system until you name at least one"* directly above two named entry
    points, and *"add junit-platform-launcher"* above a pom that already declared it. Everything the
    tool had asked for had been done, and the file still said it had not — so the one artifact an
    adopter reads to learn whether they are set up told them they were not.

    The notes are still *printed* (``cli.cmd_init``), which is their right home: they describe the
    moment, and a moment does not need a copy kept.
    """
    lines = [
        "# What this project declares about itself. One file, read by Plumb for every language.",
        f'adapter = "{found.adapter}"',
        "",
        "# What counts as production code, in your language's own spelling.",
        f"production   = {_toml_list(found.production)}",
        ("# Where that code's source lives — mutation needs the files, not the compiled form."
         if found.adapter == JAVA else
         "# Where that code's source lives. Read only by Java mutation; a Python run ignores it."),
        f"sources      = {_toml_list(found.sources)}",
        "",
        "# Where the wired system begins: the handful of places a real request enters.",
        "# A story is only checked for reaching the wired system if at least one is named.",
        f"entry_points = {_toml_list(found.entry_points)}",
        "",
        "# Off because it is slow, not because it is optional. `plumb board --mutation` for a run.",
        "mutation = false",
    ]
    if found.options:
        lines += ["", f"[{found.adapter}]"]
        lines += [f'{key:<14} = "{value}"' for key, value in sorted(found.options.items())]
    return "\n".join(lines) + "\n"


def _toml_list(values) -> str:
    return "[" + ", ".join(f'"{v}"' for v in values) + "]"


@dataclass(frozen=True)
class Outcome:
    written: tuple[str, ...]
    kept: tuple[str, ...]
    detected: Detected

    @property
    def anything_written(self) -> bool:
        return bool(self.written)


#: The published Maven coordinate for the JAVA citation vocabulary. Prefixed because this module
#: serves every language: Python needs none of it — a pytest marker is a string, with nothing to
#: publish and nothing to declare — and a third adapter will bring its own package manager and its
#: own naming. An unqualified `GROUP_ID` in a language-neutral file reads as though there is one.
JAVA_GROUP_ID = "org.plumbspec"
JAVA_ARTIFACT_ID = "plumb-annotations"

#: Versioned INDEPENDENTLY of the tool, and deliberately. The annotation is a handful of classes
#: and a handful of members; the tool moves weekly. Tying them together meant every tool release forced a new
#: publication of byte-identical content, and Central has no delete — an adopter would collect
#: versions that differ in nothing. What actually binds them is COMPATIBILITY: the adapter reads
#: `@Proves` at runtime, so a member added or renamed here must move the adapter too. Semver says
#: that; a shared number says something false. Bump this only when `Proves.java` changes, and keep
#: it equal to the annotations pom — `tools/publish-annotations.sh` checks that they agree.
JAVA_ANNOTATIONS_VERSION = "0.2.0"


def init(root: Path | str = ".") -> Outcome:
    """Write the declaration, and nothing else (``dev00-1-2``, ``dev00-1-2``).

    What adoption may write is the project's declaration: which adapter, what counts as production
    code, where the wired system begins. Everything past it — where a subject is written down, what
    runs it, whether prose is recorded at all — is the project's own business, and a tool that
    writes it is choosing somebody's workflow for them. This once emitted six Python modules, which
    in a Java project is a second language, a second test runner, and a set of gates that never ran.

    It also once wrote a line pointing at a **list of subjects** for the board to answer against.
    That is the same error wearing a config key: a list handed over is a copy of a list the project
    owns, it desynchronises the moment theirs moves, and nothing here can detect that it has
    (`dev07-3-2`). A board answers for the ids a run's tests cited, and stops there.
    """
    root = Path(root)
    found = detect(root)
    written, kept = [], []

    config = root / CONFIG_NAME
    if config.exists():
        kept.append(CONFIG_NAME)
        found = _as_declared(found, config)
    else:
        config.write_text(render(found))
        written.append(CONFIG_NAME)

    # Java needs one thing Python does not: `@Proves` is an annotation, so it must be on the
    # COMPILE classpath before a citation will build. That is the language's asymmetry, not a
    # design choice — and it is left to the adopter deliberately. Editing somebody's pom means
    # owning parents, profiles, dependencyManagement and formatting forever, and an aggregator
    # pom silently takes an inert dependency and reports success. One paste is cheaper than that,
    # for them and for us. `next_steps` prints exactly what to paste.
    return Outcome(written=tuple(written), kept=tuple(kept), detected=found)



#: The next action, in commands (``dev00-1-3``). A capability nobody is told to reach for is a
#: capability nobody uses, and "handed a directory" is not the same as "handed a method".
_CITE = {
    JAVA: ('    import org.plumbspec.Proves;\n\n'
           '    @Test\n'
           '    @Proves(value = "APP-1", depth = "wiring")\n'
           '    void ordersAreRouted() { ... }'),
    PYTHON: ('    import pytest\n\n'
             '    @pytest.mark.proves("APP-1", depth="wiring")\n'
             '    def test_orders_are_routed(): ...'),
}


#: How each build tool is asked for the classpath the suite will run on.
#:
#: **They are not the same instruction, and the difference is not cosmetic.** Maven has no way to
#: hand over its own test runtime, so this reconstructs one and every reconstruction is a chance to
#: be short of it. Gradle *does* — `sourceSets.test.runtimeClasspath` is the classpath its own
#: `test` task uses — so the honest instruction there is to stop reconstructing (`dev07-1-1`).
_CLASSPATH_STEP = {
    MAVEN: [
        "    mvn -q test-compile dependency:build-classpath "
        "-Dmdep.outputFile=target/plumb-classpath.txt",
        "    printf ':target/classes:target/test-classes' >> target/plumb-classpath.txt",
        "",
        "The second line is not optional: `build-classpath` resolves DEPENDENCIES, so it never",
        "includes the module's own compiled output — without it the run finds no tests. **If this",
        "build has more than one module, append every module's**, not just this one's: a sibling",
        "resolves to whatever is installed in ~/.m2, where your build uses the classes it just",
        "compiled, and the two are different bytes.",
        ""],
    GRADLE: [
        "    // build.gradle",
        "    tasks.register('plumbClasspath') {",
        "        doLast { file('build/plumb-classpath.txt').text = "
        "sourceSets.test.runtimeClasspath.asPath }",
        "    }",
        "",
        "    gradle test plumbClasspath",
        "",
        "That hands over the classpath Gradle's own `test` task runs on, rather than rebuilding",
        "one — which is why it is four lines and why nothing here can be short of it. It matters",
        "most for resources: Gradle keeps `build/resources/test` OUT of the compiled-class",
        "directories, so a hand-assembled classpath silently loses every migration, fixture and",
        "property file your suite loads.",
        ""],
}



#: A note whose truth the adopter can already have settled, and how to ask whether they have.
#: Each is a fact about *this moment* — the whole reason notes are printed rather than written into
#: the file — and a moment that has passed is a note that must not be printed either.
_SETTLED = (
    ("entry_points is empty", lambda found, root: bool(found.entry_points)),
    ("add junit-platform-launcher", lambda found, root: _declares_launcher(root)),
    ("classpath_file must exist", lambda found, root: _classpath_written(found, root)),
)


def _as_declared(found: Detected, config: Path) -> Detected:
    """`found`, corrected by what the project's own `plumb.toml` already says.

    **`detect` reads the filesystem and never the config**, because its job is to propose one. So
    every note it carries describes a project that has declared nothing — which is true the first
    time and false every time after, and `plumb init` is a command adopters run again.

    Observed: `still to do: entry_points is empty` printed directly above a file naming two, on the
    same run that said `kept plumb.toml (left exactly as it is)`. The one command an adopter runs
    to find out whether they are set up told them they were not, about the file it had just read
    and declined to change. `render`'s docstring records the same defect being fixed for the file
    itself; this is the half that was still being printed.
    """
    from plumb.config import Config, InvalidConfig

    try:
        declared = Config.parse(config.read_text(encoding="utf-8"), root=config.parent)
    except (OSError, UnicodeDecodeError, InvalidConfig):
        # A config this cannot read is one `plumb board` will refuse by name and at length. Saying
        # so a second time here, in a command whose job is the declaration rather than the run,
        # would be a worse copy of a better message.
        return found
    corrected = replace(found, entry_points=tuple(declared.entry_points))
    root = config.parent
    return replace(corrected, notes=tuple(
        note for note in corrected.notes
        if not any(note.startswith(head) and settled(corrected, root)
                   for head, settled in _SETTLED)))


def _declares_launcher(root: Path) -> bool:
    """Whether the build already puts `junit-platform-launcher` on the test classpath.

    A substring of the build file, because that is the granularity the advice is at: the note says
    *add this dependency*, and a project whose build names it has added it.
    """
    for build in ("pom.xml", "build.gradle", "build.gradle.kts"):
        path = root / build
        if path.is_file() and "junit-platform-launcher" in path.read_text(
                encoding="utf-8", errors="replace"):
            return True
    return False


def _classpath_written(found: Detected, root: Path) -> bool:
    where = (found.options or {}).get("classpath_file")
    return bool(where) and (root / where).is_file()


def next_steps(found: Detected) -> str:
    """What is left to do, numbered over what is left rather than over the full list.

    A step the project has already taken is dropped rather than shown as done: this prints on
    every `plumb init`, including the ones an adopter runs after following it, and *name where
    your wired system begins* above a file naming two is the same false report the notes carried.
    Numbering the remainder is what makes the list a thing to work through.
    """
    steps = []
    if not found.entry_points:
        steps.append([
            "Name where your wired system begins, in plumb.toml:", "",
            '       entry_points = ["com.myapp.Api#handleRequest"]' if found.adapter == JAVA
            else '       entry_points = ["myapp.cli:main"]'])
    steps.append(["Cite a story from a test. The id is yours — Plumb keeps no catalog of them:", "",
                  _CITE[found.adapter]])
    steps.append(["Run it:", "", "       plumb board"])

    lines = ["", "Next:", ""]
    for number, step in enumerate(steps, start=1):
        lines += [f"  {number}. {step[0]}", *step[1:], ""]
    if found.adapter == JAVA:
        lines += ["`@Proves` is on Maven Central — the citation vocabulary alone, no dependencies.",
                  "", "    <dependency>",
                  f"      <groupId>{JAVA_GROUP_ID}</groupId>",
                  f"      <artifactId>{JAVA_ARTIFACT_ID}</artifactId>",
                  f"      <version>{JAVA_ANNOTATIONS_VERSION}</version>",
                  "      <scope>test</scope>",
                  "    </dependency>", "",
                  "…or Gradle:", "",
                  f"    testImplementation '{JAVA_GROUP_ID}:{JAVA_ARTIFACT_ID}:{JAVA_ANNOTATIONS_VERSION}'", "",
                  "Then write your test classpath to a file:", ""]
        lines += _CLASSPATH_STEP.get(found.build_tool, _CLASSPATH_STEP[MAVEN])
        lines += [
            "Plumb checks this before it launches anything and refuses rather than observing a run",
            "your build does not perform — a divergence would arrive as a test that fails here and",
            "passes for your build, which reads as your defect and is not one.",
            "If the launcher then reports a missing TestExecutionListener, add",
            "`org.junit.platform:junit-platform-launcher` as a test dependency; Surefire",
            "supplies it internally, so a conventional project never declares it and it is",
            "absent from the resolved classpath.",
            ""]
    return "\n".join(lines)
