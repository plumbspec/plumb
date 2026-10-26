"""``dev00-1-1`` — the documentation is checked against the tool it describes.

The release gate already checks that links resolve, that anchors exist and that markup is
well-formed. That verifies the docs as a **structure** and leaves them entirely unverified as a set
of **claims**: a page can be perfectly well-formed and say something the tool does not do, exactly
as a suite can be perfectly green and prove nothing.

Scope is narrow on purpose. This compares only vocabularies with **one home in the source**, so it
can say "this flag exists and no document mentions it" and can never say whether the sentence beside
it is any good. Everything here is a source scan — no build, no network, no rendering — which is
what lets it run every time — a pure source scan, pointed at the docs.
"""

import argparse
import re
from pathlib import Path

import pytest

from plumb import cli
from plumb.core.gate import ALL_CODES

DOCS = Path(__file__).resolve().parent.parent / "docs"
#: The pages that document a command surface. Two, because the tool has two audiences and they are
#: separate jobs — an adopter's commands and the operator's. One page was the assumption here until
#: the receiver grew a surface worth its own guide, and the gate then read a correctly documented
#: flag as an undocumented one. The fix a reader reaches for when a gate is wrong like that is to
#: delete the documentation, which is why widening it matters more than it looks.
REFERENCE_PAGES = (DOCS / "command-line.md", DOCS / "running-a-series-holder.md")


class _Reference:
    """The documented command surface, joined. Reads like one page to every check below."""

    @staticmethod
    def read_text() -> str:
        return "\n".join(p.read_text() for p in REFERENCE_PAGES if p.is_file())


REFERENCE = _Reference()

#: argparse mints this for every parser and subparser. It is not a flag anyone documents, and
#: demanding it would bury the eight real omissions this check exists to find under twelve fake ones.
GENERATED = {"--help"}


def all_docs() -> str:
    return "\n".join(sorted(p.read_text() for p in DOCS.glob("*.md")))


def flags() -> list[tuple[str, str]]:
    """Every ``--flag`` the CLI accepts, paired with the command path that accepts it.

    Read off the built parser rather than scraped out of ``cli.py``: the parser is what a user
    actually meets, and a regex over the source would miss a flag added through any route but the
    literal one it was written for — which is the same drift this check exists to catch, one level
    down.
    """
    def walk(parser, path=()):
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for name, sub in action.choices.items():
                    yield from walk(sub, path + (name,))
                continue
            for option in action.option_strings:
                if option.startswith("--") and option not in GENERATED:
                    yield " ".join(path), option

    from plumb import series_holder as receiver

    # The reference documents two entry points, because `plumb registry` moved to the receiver's
    # own command (`dev00-1-1-nfr2`) — managing a registry is the operator's, and the client could not
    # perform it. So the check follows it there. Otherwise a correctly documented flag reads as one
    # the tool does not accept, and the fix somebody reaches for is deleting the documentation.
    return sorted(set(walk(cli.build_parser())) | set(walk(receiver.build_parser())))


def subcommands() -> list[str]:
    def walk(parser, path=()):
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for name, sub in action.choices.items():
                    yield " ".join(path + (name,))
                    yield from walk(sub, path + (name,))

    from plumb import series_holder as receiver

    # The reference documents two entry points, because `plumb registry` moved to the receiver's
    # own command (`dev00-1-1-nfr2`) — managing a registry is the operator's, and the client could not
    # perform it. So the check follows it there. Otherwise a correctly documented flag reads as one
    # the tool does not accept, and the fix somebody reaches for is deleting the documentation.
    return sorted(set(walk(cli.build_parser())) | set(walk(receiver.build_parser())))


def receiver_flags() -> set[str]:
    """The receiver's own flags, which the reference now documents too.

    `plumb registry` moved to the receiver's command (`dev00-1-1-nfr2`), because managing a registry is the
    operator's and the client could not perform it. The reference follows it there, so this check
    has to follow it as well — otherwise the gate reads a correctly documented flag as one the tool
    does not accept, and the fix somebody reaches for is deleting the documentation.
    """
    import contextlib
    import io

    from plumb import series_holder as receiver

    captured = argparse.ArgumentParser()
    found = set()
    with contextlib.redirect_stderr(io.StringIO()), contextlib.suppress(SystemExit):
        # Built by `main`, which is where the parser lives; parsing nothing raises SystemExit after
        # the parser is fully constructed, so the actions are reachable from the exception path.
        receiver.main(["--collect-flags-does-not-exist"])
    for source in (receiver, captured):
        pass
    return found


@pytest.mark.proves("dev00-1-1", depth="unit")
def test_every_flag_the_tool_accepts_is_in_the_reference():
    """`command-line.md` summarises itself as *every command and option*, which is a claim.

    The evidence for this check is that the claim was false by eight flags, and stayed false
    through a documentation review because finding it meant extracting the list by hand.
    """
    reference = REFERENCE.read_text()
    missing = [f"{cmd or 'plumb'} {opt}" for cmd, opt in flags() if opt not in reference]
    assert not missing, (
        "these flags exist and the command-line reference never mentions them — a reference that "
        f"calls itself complete and is not is worse than one that admits its scope: {missing}"
    )


#: Flags a page names on purpose without the tool offering them. Each is a claim about something
#: ELSE, and a scan that reads a flag out of a code block cannot tell whose command it belongs to.
#:
#: Kept as a list with reasons rather than a set of strings, because the next addition will be
#: somebody silencing a real finding and the reason is what makes that visible.
NOT_OURS = {
    # Named as a flag that does NOT exist — the claim is about its absence, and it stays true.
    "--no-mutation": "command-line.md says explicitly that there is no such flag",
    # pytest's own, in a sentence about running pytest directly rather than through plumb.
    "--strict-markers": "writing-a-citation.md, about invoking pytest and not this tool",
}


@pytest.mark.proves("dev00-1-1", depth="unit")
def test_no_flag_any_page_documents_has_been_removed_from_the_tool():
    """The other direction, and the one that rots silently: a flag deleted from the CLI leaves its
    paragraph behind, and the paragraph is what a reader tries.

    **Every page, not only the reference.** A flag named in a how-to misleads exactly as much as one
    named in the reference, and it is likelier to be read — `--passphrase` sat against a subcommand
    that never took it, in the usage block at the top of the page.

    Handed over by the team who run the releases: they had a release-time gate scraping the built
    artifact for this, and it belongs on every commit in front of whoever broke it rather than in
    front of whoever is cutting.
    """
    known = {opt for _, opt in flags()} | GENERATED
    # SCANNED, not tokenised. Splitting on whitespace and stripping TRAILING punctuation missed
    # every flag written `[--flag …]`, which is the shape a usage block is written in — so the
    # check read 24 of the 43 flags on these pages and passed on the strength of it. A leading `[`
    # or a backtick was enough to make a flag invisible, and `--passphrase` sat documented against
    # a subcommand that never took it.
    #
    # `--` alone and a markdown rule `---` do not match, because a flag's shape is a letter first.
    stale = {}
    for page in sorted(DOCS.glob("*.md")):
        for flag in sorted(set(re.findall(r"--[a-z][\w-]*", page.read_text())) - known - set(NOT_OURS)):
            stale.setdefault(flag, []).append(page.name)
    assert not stale, (
        "these pages document flags the tool does not accept: "
        + "; ".join(f"{flag} in {', '.join(where)}" for flag, where in sorted(stale.items()))
        + ". A reader tries the paragraph, not the parser")


@pytest.mark.proves("dev00-1-1", depth="unit")
def test_every_subcommand_is_in_the_reference():
    """The WHOLE path, not its last word.

    Matching on the last word alone is satisfied by coincidence: `friction pull` shipped
    undocumented and this passed, because `series pull` is documented and the word `pull` appears.
    A gate a sibling command can satisfy on your behalf is not holding anything (`dev00-1-1`).
    """
    reference = REFERENCE.read_text()
    missing = [c for c in subcommands() if c not in reference]
    assert not missing, f"subcommands absent from the reference: {missing}"


@pytest.mark.proves("dev07-5-2", depth="unit")
@pytest.mark.proves("dev00-1-1", depth="unit")
def test_every_condition_code_the_board_can_emit_is_documented():
    """`dev07-5-2` makes the code the promise a consumer branches on, and says the set is finite and
    knowable. Knowable requires somewhere to read it: as filed, the set was discoverable only by
    triggering it, so a reader could not tell a state with no message from one they had not
    reached."""
    documented = all_docs()
    missing = sorted(c for c in ALL_CODES if c not in documented)
    assert not missing, (
        "the board can emit these codes and no shipped document lists them — the set is only "
        f"knowable if it is written down somewhere: {missing}"
    )


@pytest.mark.proves("dev07-5-3", depth="unit")
@pytest.mark.proves("dev00-1-1", depth="unit")
def test_every_exit_code_is_documented_with_its_number():
    """The exit code is the one part of a board a machine reads by default, so leaving it to be
    discovered by running the tool is leaving the contract unstated (`dev07-5-3`)."""
    reference = REFERENCE.read_text()
    codes = {name: value for name, value in vars(cli).items() if name.startswith("EXIT_")}
    assert codes, "the exit vocabulary moved; this check is pointed at nothing"
    missing = sorted(name for name, value in codes.items() if f"`{value}`" not in reference)
    assert not missing, (
        f"these exit codes are not stated in the reference by number: {missing}"
    )


@pytest.mark.proves("dev07-3-3", depth="component")
def test_a_java_run_never_needs_the_python_runner():
    """``dev07-3-3`` — the core is language-blind and the adapter is language-bound.

    Run in a subprocess with ``pytest`` made unimportable, because this suite *is* pytest: every
    test in this repository runs in a process where the import already succeeded, so nothing here
    can observe the failure by importing normally. That is exactly why it shipped — twice.

    The path exercised is the one that broke: ``runfile.write`` is what a Java board calls, and it
    reaches into the Python adapter package for ``archetypes`` alone.
    """
    import os
    import subprocess
    import sys
    import textwrap

    import plumb

    # `find_spec`, not `find_module` — the legacy finder API was removed in 3.12, so a finder
    # defining only `find_module` is silently ignored and the probe passes by importing pytest
    # perfectly well. A guard that cannot fail proves nothing, which is this file's whole subject.
    probe = textwrap.dedent("""
        import sys
        class NoPytest:
            def find_spec(self, name, path=None, target=None):
                if name == "pytest" or name.startswith("pytest."):
                    raise ImportError("pytest is not installed on this machine")
        sys.meta_path.insert(0, NoPytest())
        import plumb.runfile
        from plumb.adapters.python import archetypes
        assert "pytest" not in sys.modules, "the Java path imported the Python runner"
        print("ok")
    """)
    # The child inherits no path from this runner, so point it at the package under test rather
    # than at whatever happens to be installed.
    src = str(Path(plumb.__file__).resolve().parent.parent)
    done = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True,
                          env={**os.environ, "PYTHONPATH": src})
    assert done.returncode == 0, (
        "a Java project's board must not require a Python test framework — this is what a "
        f"Java-only adopter meets on a stock install:\n{done.stderr}"
    )


@pytest.mark.proves("dev00-1-1", depth="unit")
def test_both_adapters_declare_the_manifest_shape_the_contract_documents():
    """The two shipped adapters must spell `schema_version` the same way, and the way the contract
    fixes it.

    They did not. The Java adapter carried `int SCHEMA_VERSION = 7` and emitted a bare JSON number
    while the Python adapter emitted the string `"7.0"`, which is what `docs/adapter-contract.md`
    publishes. Nothing went red, because a bare integer is the **pre-6 spelling** the core still
    accepts for majors 1-5: every Java manifest parsed through the legacy branch with its minor
    silently dropped. A disagreement between two manifests about the same field is `dev07-3-3`'s
    refusal, and `--manifest` becoming repeatable is what made it reachable rather than theoretical.

    Found in a foreign artifact — a consumer's manifest — and not by this repository's suite, which
    is the structural part: the sample project runs one adapter at a time, so neither run has ever
    had the other's spelling in front of it.

    A source scan, so it needs no JVM and therefore always runs.
    """
    from plumb.core.manifest import SCHEMA_MAJOR, SCHEMA_MINOR

    java = (Path(__file__).resolve().parents[1] / "adapters" / "java" / "adapter" / "src" / "main"
            / "java" / "org" / "plumbspec" / "Manifest.java").read_text()

    found = {name: re.search(rf"SCHEMA_{name}\s*=\s*(\d+)\s*;", java)
             for name in ("MAJOR", "MINOR")}
    missing = sorted(name for name, hit in found.items() if hit is None)
    assert not missing, (
        f"the Java adapter declares no SCHEMA_{' or SCHEMA_'.join(missing)} — the shape is spelled "
        "`major.minor`, and a single `SCHEMA_VERSION` integer is the pre-6 spelling that cannot "
        "carry a minor")
    declared = {name: int(hit.group(1)) for name, hit in found.items()}

    # **A version the core accepts, and a lag that is written down.** Equality was the original
    # assertion and it was the right one while both adapters could make the same claims. Major 8
    # splits `inert` into *read it* and *touched nothing*, which the JVM observer cannot tell apart
    # — so the Java adapter emitting 8 would be asserting a read it never watched for. It lags on
    # purpose, and what this holds is that the lag is *declared* rather than discovered: a version
    # outside the window is the failure, and an undeclared one is how it sat at 5 for two majors.
    from plumb.core.manifest import SUPPORTED_VERSIONS, _SHIPPED_ADAPTER_EMITS

    assert declared["MINOR"] == SCHEMA_MINOR
    assert declared["MAJOR"] in SUPPORTED_VERSIONS, (
        f"the Java adapter writes schema {declared['MAJOR']} and a run accepts "
        f"{sorted(SUPPORTED_VERSIONS)} — every project in that language would be refused")
    if declared["MAJOR"] != SCHEMA_MAJOR:
        assert declared["MAJOR"] in _SHIPPED_ADAPTER_EMITS, (
            f"the Java adapter lags at {declared['MAJOR']} and nothing records it, so retiring "
            f"that major would look like an ordinary retirement and break every Java project")

    assert '\\"schema_version\\": \\"' in java, (
        "the Java adapter emits schema_version unquoted — a bare integer is the pre-6 spelling, so "
        "the minor is silently lost and the manifest is read through the legacy branch")

    documented = re.search(r'"schema_version":\s*"(\d+\.\d+)"',
                           (DOCS / "adapter-contract.md").read_text())
    assert documented, "the adapter contract no longer shows a `major.minor` schema_version"
    assert documented.group(1) == f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}", (
        f"the contract documents schema_version {documented.group(1)} and the adapters write "
        f"{SCHEMA_MAJOR}.{SCHEMA_MINOR}")


def test_the_documented_maven_recipe_is_the_order_the_guard_demands():
    """The tutorial's classpath line, held against the remedy the tool prints for the same fault.

    `getting-started.md` taught `printf ':target/classes:target/test-classes' >> …` for a year —
    main ahead of test, which is the exact order `launch._shadowed` refuses and which
    `BUILD_TOOLS` records as the correction the tool's own hint had to make. A reader following
    the page produced a classpath the tool was written to reject, and the failure it produces on
    a project without the guard is a suite that loads production configuration under test.

    Asserted against the generated remedy rather than a string typed here, so the page cannot
    drift from the tool by either of them moving.
    """
    from plumb.launch import _maven_fix

    page = (DOCS / "getting-started.md").read_text(encoding="utf-8")
    remedy = _maven_fix([])

    for line in ("target/test-classes:target/classes", "dependency:build-classpath"):
        assert line in remedy, f"the tool's own remedy stopped saying {line!r}"
        assert line in page, (
            f"the tutorial's Maven recipe no longer matches the remedy the tool prints — it is "
            f"missing {line!r}, and a reader following it builds the classpath the guard refuses")

    assert "target/classes:target/test-classes" not in page, (
        "the tutorial is back to main-before-test: Maven copies the resources of each into the "
        "directory beside the code, so whichever comes first wins and the observed run uses "
        "production configuration")


def test_the_board_reference_spells_every_status_the_way_the_gate_does():
    """A consumer keys off these strings, so a page spelling one in prose is a page that misleads.

    `consuming-the-board.md` offered `passed — wiring not verified`, with spaces and an em dash,
    for a value the gate emits as `passed-wiring-not-verified` — and left `not-passed` out
    entirely. Tooling written from that page matches nothing and reports every partly-proven
    subject as a status it does not recognise.
    """
    from plumb.core.gate import NOT_PASSED, PASSED_WIRING_NOT_VERIFIED, PROVEN, UNPROVEN

    page = (DOCS / "consuming-the-board.md").read_text(encoding="utf-8")
    for status in (PROVEN, UNPROVEN, PASSED_WIRING_NOT_VERIFIED, NOT_PASSED):
        assert f"`{status}`" in page, (
            f"the board reference does not spell {status!r} — a consumer keys off this string, "
            f"and a value they cannot find is a value they will write by hand from the prose")


def test_no_subcommand_in_the_reference_has_been_removed_from_the_tool():
    """The other direction, which nothing held.

    `test_every_subcommand_is_in_the_reference` asks that everything the tool accepts is written
    down. It says nothing about the reverse, so `plumb account add-key` and `remove-key` sat in the
    reference through the release that replaced them with `export`, and a reader following the page
    got `invalid choice`. A reference naming a command that does not exist is worse than one that
    is merely short: the reader believes the tool is broken rather than the page.

    Scoped to the second word of a documented `{a|b|c}` group, because that is the shape the
    reference lists subcommands in and the shape that went stale.
    """
    import re

    reference = REFERENCE.read_text()
    real = set(subcommands())
    stale = []
    for line in reference.splitlines():
        found = re.match(r"\s+plumb(?:-series-holder)?\s+(\w[\w-]*)\s", line)
        group = re.search(r"\{([a-z|_-]+)\}", line)
        if not (found and group):
            continue
        for word in group.group(1).split("|"):
            if f"{found.group(1)} {word}" not in real and word not in real:
                stale.append(f"{found.group(1)} {word}")

    assert not stale, (
        f"the reference documents subcommands the tool does not accept: {sorted(set(stale))}. "
        f"A reader following it gets `invalid choice` and concludes the tool is broken")


def test_the_schema_versions_in_the_docs_are_the_ones_this_release_reads():
    """Four majors have each been "current" in a transcript on one of these pages.

    A transcript is the most quotable thing in a reference and the least likely to be revisited,
    so `schema 5 -> 7.0` sat through the releases that took the chain to 9 — and a reader matching
    their own output against it concludes their file is older than it is.

    Asserted as *the old numbers are gone*, not as the new ones being present: a page may legitimately
    discuss a version it no longer reads, but not while showing it as what this Plumb answers with.
    """
    from plumb.core.manifest import PARSEABLE_VERSIONS, SCHEMA_MAJOR, SCHEMA_VERSION

    pages = "\n".join(p.read_text() for p in (DOCS / "command-line.md",
                                              DOCS / "adapter-contract.md"))
    assert f"schema {SCHEMA_VERSION}" in pages or f"-> {SCHEMA_VERSION}" in pages, (
        f"neither reference transcript shows the version this release writes ({SCHEMA_VERSION})")

    reads = ", ".join(f"{v}.x" for v in sorted(PARSEABLE_VERSIONS))
    assert f"(reads: {reads})" in pages, (
        f"the contract's refusal transcript does not name the versions this Plumb reads: {reads}")

    for gone in range(1, SCHEMA_MAJOR - 2):
        assert f"already at schema {gone}." not in pages, (
            f"a transcript still shows schema {gone} as current; this release writes "
            f"{SCHEMA_VERSION} and reads {reads}")


def test_every_command_the_tool_prints_is_a_command_the_tool_has():
    """What the tool tells you to run, held against what it accepts.

    The documentation is checked both ways by the tests above; the tool's own *output* was not, and
    `plumb support why` went on printing `plumb friction file --observation …` through the release
    that renamed the verb. That line exists to be copied — it is the one an agent is told to run —
    so the rename left a worked example that fails with `invalid choice`, in the one place a reader
    is least likely to doubt.

    Scanned across the whole shipped tree rather than that one string, because a verb is named in
    docstrings, hints and error remedies too, and the next rename will land somewhere else.
    """
    import re

    real = {path.split()[0] for path in subcommands()}
    stale = {}
    for source in sorted((Path(__file__).resolve().parent.parent / "src").rglob("*.py")):
        for found in re.finditer(r"plumb(?:-series-holder)?[ ]+([a-z][a-z-]{2,})",
                                 source.read_text(encoding="utf-8")):
            verb = found.group(1)
            # `from plumb import …` is the language, not an invocation.
            if verb != "import" and verb not in real:
                stale.setdefault(verb, set()).add(source.name)

    assert not stale, (
        "the tool prints commands it does not accept: "
        + "; ".join(f"`plumb {verb}` in {sorted(where)}" for verb, where in sorted(stale.items()))
        + ". A reader copies that line and is told `invalid choice`")


#: A spec's own ids — `dev07-6-2`, `dev07-4-1-ur5`, `D38` — are the implementation's words. A
#: reader of `--help` has not read the spec and cannot act on one.
SPEC_ID = re.compile(r"\bdev\d\d(?:-\d+)*(?:-[a-z]+\d+)?\b|\bD\d+\b")


def _help_texts(parser, path=("plumb",)):
    """Everything `--help` prints at every level: descriptions, option help and subcommand help."""
    yield " ".join(path), parser.description or ""
    for action in parser._actions:
        yield " ".join(path) + f" {'/'.join(action.option_strings) or action.dest}", \
            action.help or ""
        if isinstance(action, argparse._SubParsersAction):
            for choice in action._choices_actions:
                yield " ".join(path + (choice.dest,)), choice.help or ""
            for name, sub in action.choices.items():
                yield from _help_texts(sub, path + (name,))


@pytest.mark.proves("dev00-1-1", depth="unit")
def test_help_speaks_to_its_reader_and_never_cites_the_spec():
    """A newcomer reading `--help` met `dev07-6-2-…` and could do nothing with it."""
    from plumb import series_holder

    found = [(where, text) for parser, root in ((cli.build_parser(), ("plumb",)),
                                                (series_holder.build_parser(),
                                                 ("plumb-series-holder",)))
             for where, text in _help_texts(parser, root) if SPEC_ID.search(text)]
    assert not found, f"help that cites the spec rather than saying what it means: {found}"


@pytest.mark.proves("dev00-1-1", depth="unit")
def test_the_holder_s_help_shows_the_bounds_it_enforces_and_their_defaults():
    """It enforces a reserve, a pool and a compaction ratio; its help said it enforced one bound
    and showed the default of only one."""
    from plumb import series_holder

    said = " ".join(series_holder.build_parser().format_help().split())
    assert "the only bound" not in said, said
    said = said[said.index("-h, --help"):]
    for flag, default in (("--reserve", series_holder.DISK_HEADROOM_BYTES // (1024 * 1024)),
                          ("--pool", series_holder.POOL_BYTES // (1024 * 1024)),
                          ("--compact-above", series_holder.COMPACT_ABOVE)):
        start = said.index(flag + " ")
        rest = said[start:]
        following = rest.index(" --", 1) if " --" in rest[1:] else len(rest)
        assert f"default: {default}" in rest[:following], (flag, rest[:following])


def test_every_page_carries_the_front_matter_the_docs_index_is_built_from():
    """The published index is generated from each page's front matter — kind, role, summary — and
    the publish step refuses a page the index does not list. A page without it is shipped and
    unreachable, which is what happened to running-a-series-holder.md."""
    import re
    from pathlib import Path

    kinds = {"tutorial", "how-to", "reference", "explanation"}
    roles = {"exec", "pm-ba", "engineer", "programmer", "qa", "devops"}
    docs = Path(__file__).resolve().parent.parent / "docs"
    wrong = []
    for page in sorted(docs.glob("*.md")):
        if page.name.lower() in ("readme.md", "changelog.md"):
            continue
        found = re.match(r"---\n(.*?)\n---\n", page.read_text(encoding="utf-8"), re.S)
        if not found:
            wrong.append(f"{page.name}: no front matter")
            continue
        fields = dict(line.split(":", 1) for line in found.group(1).splitlines() if ":" in line)
        kind = fields.get("kind", "").strip()
        said = {r.strip() for r in fields.get("role", "").strip().strip("[]").split(",") if r.strip()}
        if kind not in kinds:
            wrong.append(f"{page.name}: kind {kind!r} is not one of {sorted(kinds)}")
        if not said or not said <= roles:
            wrong.append(f"{page.name}: role {sorted(said)} is not drawn from {sorted(roles)}")
        if not fields.get("summary", "").strip():
            wrong.append(f"{page.name}: no summary")
    assert not wrong, wrong
