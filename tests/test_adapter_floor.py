"""The floor an adapter declares, held against what it ships (``dev07-3-1``).

An adapter runs in the *project's* runtime. The floor it declares is therefore a promise to an
adopter about their machine, and a promise nothing checks is one the next commit breaks. These
read the artifact rather than running it, so lowering a floor is a red test until the code that
holds at it exists.

**Scoped to what the adapter loads in the project's runtime and nothing beyond it**
(``dev07-3-1-sr2``): the tool's own modules run in the tool's own interpreter and are none of the
project's business. For Python that scope is an import closure; for Java it is the shipped jars.

Uncited on purpose. One execution yields one grounding fact, so an inert test can only prove a
structural subject (``dev07-4-2``), and the floor requirements are behavioural — an adapter
*refusing* a runtime below its floor is something a run does. These hold the artifact; the
refusal wants its own test when it is built.
"""

# `X | None` in a signature is evaluated at import on 3.9, so without this the module does not
# collect at the floor this project declares — which is the floor this module exists to hold.
from __future__ import annotations

import ast
import re
import struct
import zipfile
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src"
JAVA = Path(__file__).resolve().parent.parent / "adapters" / "java"

#: The Python version each name arrived in. A name is refused when it arrived *after* the floor.
#: Dotted where the bare name is ambiguous — `sys.gettrace` is ancient and `threading.gettrace`
#: is 3.10, and a table that cannot tell them apart reports a defect that is not there.
#:
#: **Known to be incomplete, and that is what it is for.** This is the fast check that narrows the
#: work before anyone starts; running the suite under the floor is the complete one. Every entry
#: below `threading.gettrace` was found by static reading, and that one was found by a 3.9
#: interpreter after the reading said the module was clean.
ARRIVED = {
    "tomllib": (3, 11),
    "co_qualname": (3, 11),
    "ExceptionGroup": (3, 11),
    "BaseExceptionGroup": (3, 11),
    "StrEnum": (3, 11),
    "threading.gettrace": (3, 10),
    "threading.settrace_all_threads": (3, 12),
    "itertools.pairwise": (3, 10),
    "ast.unparse": (3, 9),
}


def _module_path(name: str) -> Path | None:
    flat = SRC / (name.replace(".", "/") + ".py")
    if flat.exists():
        return flat
    package = SRC / name.replace(".", "/") / "__init__.py"
    return package if package.exists() else None


def _imports(tree: ast.Module) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module)
            found.update(f"{node.module}.{alias.name}" for alias in node.names)
    return found


def closure() -> dict[str, Path]:
    """Every plumb module the adapter subprocess loads, read as source and never imported."""
    seen: dict[str, Path] = {}
    queue = ["plumb.adapters.python.__main__"]
    while queue:
        name = queue.pop()
        if name in seen:
            continue
        path = _module_path(name)
        if path is None:
            continue
        seen[name] = path
        for imported in _imports(ast.parse(path.read_text(encoding="utf-8"))):
            if imported.startswith("plumb") and imported not in seen:
                queue.append(imported)
    assert "plumb.adapters.python.adapter" in seen, "the closure did not reach the adapter itself"
    return seen


def tool_floor() -> tuple[int, int]:
    """`requires-python` out of the project's own metadata.

    The tool's floor and the adapter's are separate declarations (`dev07-3-1-ur13`) and happen to
    be the same number: a project then needs ONE Python, for its tests and for the tool that
    watches them. Separate still, because only one of them is the adopter's to satisfy.
    """
    found = re.search(r'requires-python\s*=\s*">=(\d+)\.(\d+)"',
                      (SRC.parent / "pyproject.toml").read_text(encoding="utf-8"))
    assert found, "the project declares no requires-python"
    return int(found.group(1)), int(found.group(2))


def shipped() -> dict:
    """Every module the artifact carries, vendored code included — it ships, so it must hold."""
    found = {}
    for path in sorted((SRC / "plumb").rglob("*.py")):
        if "__pycache__" in str(path):
            continue
        found[str(path.relative_to(SRC))] = path
    assert len(found) > 20, f"only {len(found)} modules found — has the layout moved?"
    return found


def test_everything_the_artifact_carries_parses_at_the_tool_floor():
    floor = tool_floor()
    refused = []
    for name, path in sorted(shipped().items()):
        try:
            ast.parse(path.read_text(encoding="utf-8"), feature_version=floor)
        except SyntaxError as bad:
            refused.append(f"{name}:{bad.lineno} {bad.msg}")
    assert not refused, f"syntax newer than the declared floor {floor}: {refused}"


def test_nothing_the_artifact_carries_uses_an_api_newer_than_the_tool_floor():
    """The vendored parser is in scope. It is carried rather than installed, so it ships."""
    floor = tool_floor()
    late = []
    for name, path in sorted(shipped().items()):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            used = None
            if isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name):
                    used = f"{node.value.id}.{node.attr}"
                if used not in ARRIVED:
                    used = node.attr
            elif isinstance(node, ast.Name):
                used = node.id
            elif isinstance(node, ast.alias):
                used = node.name.split(".")[0]
            if used in ARRIVED and ARRIVED[used] > floor:
                # `tomllib` is reached through a guarded import, with the vendored copy behind it.
                if used == "tomllib" and "except ModuleNotFoundError" in path.read_text():
                    continue
                late.append(f"{name}:{getattr(node, 'lineno', '?')} {used}")
    assert not late, f"newer than the declared floor {floor}: {sorted(set(late))}"


def declared_floor() -> tuple[int, int]:
    """`FLOOR` out of the adapter package, read rather than imported."""
    tree = ast.parse((SRC / "plumb/adapters/python/__init__.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "FLOOR" for t in node.targets):
            return tuple(ast.literal_eval(node.value))
    raise AssertionError("the Python adapter declares no FLOOR (dev07-3-1-ur12)")


def test_every_module_the_adapter_loads_parses_at_the_declared_floor():
    floor = declared_floor()
    refused = []
    for name, path in sorted(closure().items()):
        try:
            ast.parse(path.read_text(encoding="utf-8"), feature_version=floor)
        except SyntaxError as bad:
            refused.append(f"{name}:{bad.lineno} {bad.msg}")
    assert not refused, f"syntax newer than the declared floor {floor}: {refused}"


def test_nothing_the_adapter_loads_uses_an_api_newer_than_the_floor():
    floor = declared_floor()
    late = []
    for name, path in sorted(closure().items()):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            used = None
            if isinstance(node, ast.Attribute):
                # `threading.gettrace` before `gettrace`, so an ancient `sys.gettrace` is not
                # mistaken for the 3.10 one that shares its last segment.
                if isinstance(node.value, ast.Name):
                    used = f"{node.value.id}.{node.attr}"
                if used not in ARRIVED:
                    used = node.attr
            elif isinstance(node, ast.Name):
                used = node.id
            elif isinstance(node, ast.alias):
                used = node.name.split(".")[0]
            if used in ARRIVED and ARRIVED[used] > floor:
                late.append(f"{name}:{getattr(node, 'lineno', '?')} {used} (needs {ARRIVED[used]})")
    assert not late, f"newer than the declared floor {floor}: {sorted(set(late))}"


def test_annotations_are_postponed_wherever_the_floor_predates_them():
    """`X | None` is evaluated at definition time unless the module postpones annotations."""
    floor = declared_floor()
    if floor >= (3, 10):
        pytest.skip(f"floor {floor} evaluates `X | None` natively")
    missing = []
    for name, path in sorted(closure().items()):
        text = path.read_text(encoding="utf-8")
        if "| None" in text and "from __future__ import annotations" not in text:
            missing.append(name)
    assert not missing, f"`X | None` without postponed annotations below {floor}: {missing}"


# ---- the JVM adapter ------------------------------------------------------------------------

JARS = ("plumb-java.jar", "plumb-boot.jar")
needs_jars = pytest.mark.skipif(
    not all((JAVA / "build" / jar).is_file() for jar in JARS),
    reason="the adapter jars are not built — `mvn -f adapters/java/pom.xml package` first")


def declared_release() -> int:
    """`maven.compiler.release` out of the adapter's own pom."""
    pom = (JAVA / "adapter" / "pom.xml").read_text(encoding="utf-8")
    found = re.search(r"<maven\.compiler\.release>(\d+)</maven\.compiler\.release>", pom)
    assert found, "the Java adapter declares no maven.compiler.release (dev07-3-1-ur12)"
    return int(found.group(1))


@needs_jars
def test_every_shipped_class_holds_at_the_declared_release():
    """A class file states the JVM it needs. The declaration and the artifact cannot disagree."""
    release = declared_release()
    over = []
    for jar in JARS:
        with zipfile.ZipFile(JAVA / "build" / jar) as archive:
            for entry in archive.namelist():
                if not entry.endswith(".class"):
                    continue
                head = archive.read(entry)[:8]
                if head[:4] != b"\xca\xfe\xba\xbe":
                    continue
                needs = struct.unpack(">H", head[6:8])[0] - 44
                if needs > release:
                    over.append(f"{jar}!{entry} needs Java {needs}")
    assert not over, f"newer than the declared release {release}: {sorted(set(over))}"


def test_every_vendored_licence_is_declared_as_package_data():
    """Code that ships under someone else's licence ships with it (`ado4`).

    `packages.find` collects modules and nothing else, so the notice beside a vendored parser is
    left out of the wheel while the code it covers goes in — a licence fault rather than a missing
    convenience, and invisible from the zipapp, which carries whole directories and was never
    short of it.
    """
    declared = (SRC.parent / "pyproject.toml").read_text(encoding="utf-8")
    missing = []
    for licence in sorted(SRC.rglob("_vendor/*/LICENSE")):
        owner = ".".join(licence.parent.relative_to(SRC).parts)
        if f'"{owner}"' not in declared or "LICENSE" not in declared:
            missing.append(owner)
    assert missing == [], (
        f"vendored under a licence the wheel would not carry: {missing} — name the package "
        f"under [tool.setuptools.package-data] with LICENSE among its files")


@pytest.mark.proves("dev07-3-1", depth="unit")
def test_the_published_module_can_be_built_at_the_declared_floor():
    """`dev07-3-1-ur12`. The floor is Java 8, and that governs building as well as running.

    A cut died here. `--no-fonts` was configured on javadoc to drop the ~4 MB of web fonts a
    modern JDK bundles, and the release javadoc answered `invalid flag` — nothing signed, nothing
    shipped. The option was never needed: javadoc on 8 bundles no fonts, so the jar is 35 KB at
    the floor and 4.1 MB above it.

    Two things have to hold for the floor to be real rather than declared:

    * **no javadoc option newer than 8**, because the publisher builds at the floor.
    * **the floor is not a `maven.compiler.release` property here.** The javadoc plugin reads that
      property and passes a release flag that 8 does not have, so declaring the floor that way is
      what made the floor unbuildable at the floor. It sits on the compiler plugin instead.

    Read rather than built: producing the javadoc jar needs a populated local repository, and this
    has to fail on a machine with no network.
    """
    pom = (JAVA / "annotations" / "pom.xml").read_text(encoding="utf-8")

    options = re.findall(r"<additionalOption>([^<]*)</additionalOption>", pom)
    assert not options, (
        f"javadoc is passed {options}, and the publisher builds at Java 8 — an option 8 does not "
        f"have stops the cut rather than the test")

    assert "<maven.compiler.release>" not in pom, (
        "the floor is declared as a property the javadoc plugin also reads, so javadoc is handed "
        "a release flag Java 8 has no such option for; put it on the compiler plugin")
    assert re.search(r"<release>\s*8\s*</release>", pom), "and the compiler still holds it at 8"
