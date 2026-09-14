"""``ado1`` — the documentation is checked against the tool it describes.

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
    # own command (`ado1-nfr2`) — managing a registry is the operator's, and the client could not
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
    # own command (`ado1-nfr2`) — managing a registry is the operator's, and the client could not
    # perform it. So the check follows it there. Otherwise a correctly documented flag reads as one
    # the tool does not accept, and the fix somebody reaches for is deleting the documentation.
    return sorted(set(walk(cli.build_parser())) | set(walk(receiver.build_parser())))


def receiver_flags() -> set[str]:
    """The receiver's own flags, which the reference now documents too.

    `plumb registry` moved to the receiver's command (`ado1-nfr2`), because managing a registry is the
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


@pytest.mark.proves("ado1", depth="unit")
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


@pytest.mark.proves("ado1", depth="unit")
def test_no_flag_in_the_reference_has_been_removed_from_the_tool():
    """The other direction, and the one that rots silently: a flag deleted from the CLI leaves its
    paragraph behind, and the paragraph is what a reader tries."""
    known = {opt for _, opt in flags()} | GENERATED
    # A markdown horizontal rule is `---`, and a naive "starts with --" reads it as an option. The
    # shape of a real flag is what distinguishes them, so match that rather than stripping the one
    # counter-example that happened to appear.
    documented = {
        token for token in (t.rstrip(".,)`|:") for t in REFERENCE.read_text().split())
        if re.fullmatch(r"--[a-z][\w-]*", token)
    }
    # `--` alone is the pass-through separator and names no option; `--no-mutation` is named
    # explicitly as a flag that does NOT exist, which is a claim about absence and stays true.
    stale = sorted(documented - known - {"--no-mutation"})
    assert not stale, (
        f"the reference documents flags the tool does not accept: {stale}"
    )


@pytest.mark.proves("ado1", depth="unit")
def test_every_subcommand_is_in_the_reference():
    """The WHOLE path, not its last word.

    Matching on the last word alone is satisfied by coincidence: `friction pull` shipped
    undocumented and this passed, because `series pull` is documented and the word `pull` appears.
    A gate a sibling command can satisfy on your behalf is not holding anything (`ado1`).
    """
    reference = REFERENCE.read_text()
    missing = [c for c in subcommands() if c not in reference]
    assert not missing, f"subcommands absent from the reference: {missing}"


@pytest.mark.proves("dev07-5-2", depth="unit")
@pytest.mark.proves("ado1", depth="unit")
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
@pytest.mark.proves("ado1", depth="unit")
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


@pytest.mark.proves("ado1", depth="unit")
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
