"""``dev07-4-3`` — enforce proof, not workflow. A **structural** story.

The claims here are about the core's *shape*, not its behaviour: there is no policy machinery in
it to run, and no path from it to a language. So they are proved by inspection, and the citing
tests must be **inert** — they read the source as data and never invoke it (``dev07-4-2``). That is
not a weaker check than grounding, it is the mirror of it: a "structural" test whose execution ran
production code would fail here.

Reading files rather than importing modules is deliberate. An import executes module-level code,
which would put production frames in the call tree and make these tests *grounded* — failing the
very story they cite (``dev07-1-4``).

**Only ``dev07-4-3`` is cited here, and that is a constraint rather than an oversight.** One execution
yields one grounding fact (``dev07-4-2``), so an inert test can only ever prove a structural story.
``dev07-3-3`` says the same thing about the seam and is *behavioral*; it is proven by a manifest
crossing a process boundary in ``test_end_to_end.py``, which is the right kind of evidence for a
claim about what the core can be handed.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src" / "plumb"
CORE = SRC / "core"

#: Vocabulary that would mean the core had opinions about how a team works, rather than about
#: whether a claim is proven. `dev07-4-3` says these are opt-in policy and never imposed.
WORKFLOW = ("priority", "required_depth", "sprint", "estimate", "assignee", "due", "deadline")


def core_modules() -> list[Path]:
    found = sorted(p for p in CORE.glob("*.py") if p.name != "__init__.py")
    assert found, f"no core modules under {CORE} — has the layout moved?"
    return found


def names_in(path: Path) -> set[str]:
    """Every identifier the module defines or references — read, never run."""
    tree = ast.parse(path.read_text())
    return {
        node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute)
        else node.name if isinstance(node, (ast.FunctionDef, ast.ClassDef)) else ""
        for node in ast.walk(tree)
        if isinstance(node, (ast.Name, ast.Attribute, ast.FunctionDef, ast.ClassDef))
    }


def imports_in(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    modules = {
        node.module for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    modules |= {
        alias.name for node in ast.walk(tree)
        if isinstance(node, ast.Import) for alias in node.names
    }
    return modules


@pytest.mark.proves("dev07-4-3", depth="unit")
def test_the_core_carries_no_workflow_vocabulary():
    """Forcing an unverifiable workflow only manufactures new fakery — the failure Plumb exists
    to catch — so the core must have nothing to force with."""
    offenders = {
        module.name: sorted(found)
        for module in core_modules()
        if (found := {n for n in names_in(module) if n.lower() in WORKFLOW})
    }
    assert not offenders, f"the core gained workflow vocabulary it cannot verify: {offenders}"


@pytest.mark.proves("dev07-4-3", depth="unit")
def test_no_core_module_reaches_outside_the_core():
    """The package boundary *is* the claim. `dev07-3-3` says the core is language-blind and
    that it reads only the manifest — so a single import from the core into an adapter would
    make both false, and would do it silently.

    Checked across the whole package rather than one module, because a seam that holds for
    `gate.py` and not for `board.py` is not a seam.
    """
    escapes = {
        module.name: sorted(outside)
        for module in core_modules()
        if (outside := {
            m for m in imports_in(module)
            if m.startswith("plumb") and not m.startswith("plumb.core")
        })
    }
    assert not escapes, (
        "the core imported something outside itself, so it is no longer language-blind "
        f"(dev07-3-3): {escapes}"
    )


@pytest.mark.proves("dev07-4-3", depth="unit")
def test_the_adapter_depends_on_the_core_and_not_the_reverse():
    """The asymmetry is the whole design. An adapter knowing the core is correct; the core
    knowing an adapter would mean a new language was a core change."""
    adapters = sorted((SRC / "adapters").rglob("*.py"))
    assert adapters, "no adapter modules found — has the layout moved?"
    assert any(
        m.startswith("plumb.core") for module in adapters for m in imports_in(module)
    ), "an adapter that never mentions the core is not adapting anything"


@pytest.mark.proves("dev07-4-3", depth="unit")
def test_nothing_shipped_imports_the_methodology():
    """`goldspec` is a methodology this project happens to use, and nothing shipped may import it.
    One import would end that: the core would begin assuming a spec, and a project that adopted no
    methodology would start being told about artifacts it does not have.

    **What this does not forbid, and used to.** The rule was once that plumb must never *learn* the
    methodology exists, which took the specs citing one another with it. That was withdrawn: it was
    drawn when the two vocabularies were not separate enough to tell a citation from a dependency,
    and its cost was that a flow spanning both had nowhere to live. What is checked here is
    the import, which is what actually reaches an adopter's machine.

    The danger is not theoretical — `status.py`, `conventions.py`, `specgate.py` and `flowcheck.py`
    lived *inside* this repository until they moved out, and `stories.csv` is what came of the same
    proximity the last time. What makes the split real is that nothing here can reach back for them.

    Checked across everything shipped rather than the core alone: an adapter importing the method
    would put it in the artifact just as surely, and `dev08` makes adapters plural.

    Structural, and inert by construction — the modules are read as source, never imported, because
    importing them is the thing being forbidden.
    """
    reaching = {
        module.relative_to(SRC).as_posix(): sorted(m for m in imports_in(module) if m.split(".")[0] == "goldspec")
        for module in sorted(SRC.rglob("*.py"))
        if any(m.split(".")[0] == "goldspec" for m in imports_in(module))
    }
    assert not reaching, (
        "something shipped imports the methodology, so plumb now requires a spec and the "
        f"boundary is gone (dev07-4-3): {reaching}"
    )


def test_a_citation_crosses_a_spec_boundary_outward_only():
    """A spec may cite a story of the spec it extends; the base never cites its extension. Not a
    licensing rule but a dependency one — a base that cites upward cannot be read, built or
    shipped without the thing built on it. Stated elsewhere for what is built on top; this
    holds it for any pair of specs rather than the pair that happened to exist first.

    Structural: read as source, so it needs no run and therefore always runs.

    **Widened after it missed the thing it exists to catch.** It read the spec files for one
    hard-coded namespace, so two citations to a *different* private spec — from `tests/`, which it
    never looked at — sat in the public repository proving stories that do not exist in it. A
    stranger cloning this got two board rows for ids found nowhere in the tree.

    So the rule is stated the other way round: a citation to a namespace this repository does not
    *declare* is upward by definition. That needs no list of private namespaces to keep in step
    with a repository this one cannot see.

    It also must not name the namespaces it does own. It did — `OWNED = "ch"` — on the premise that
    there is exactly one, and that premise expired the day the decision engine moved here as a base
    capability. A constant would have failed on arrival and been *edited to pass*, which is how a
    boundary check quietly becomes a boundary announcement. The owned set is read off what the spec
    **declares** instead, so a third namespace is covered by being declared.

    That set was once collected from `story(...)` calls, which is where the ids used to live twice.
    It comes off the trace tables now, for the same reason everything else does: the declaration
    and the claim are one row, and there is no second copy to read from.
    """
    import ast
    import re

    root = Path(__file__).parent.parent
    cited: dict[str, set[str]] = {}
    # **Read through the spec's own reader, in whatever shape the spec is written.** This scanned
    # for a trace-table row — `| `dev07-4-2` | …` — and the corpus has since converted to the node
    # format, where a subject is a heading. Not one row matched, so `declared` was empty, every
    # namespace read as unowned, and the check reported all 160-odd citations as boundary
    # violations rather than saying it could no longer see the spec. A gate that carries its own
    # copy of what it checks decays into one that fails for the wrong reason.
    from goldspec.nodes import read as read_nodes

    declared: set[str] = set()
    for flow in (root / "spec").rglob("*.md"):
        converted = read_nodes(flow)
        if converted is not None:
            declared |= {node.id for node in converted.nodes}
        else:
            # The older shape, still readable, for a chapter that has not converted.
            declared |= set(re.findall(r"^\|\s*`([A-Za-z]+\d+(?:-\d+)+)`\s*\|",
                                       flow.read_text(), re.M))
    assert declared, (
        "no subject was found in spec/ at all, so this check can see nothing to "
        "hold citations against — which is the shape it fails in when the spec's format moves")
    for source in [*(root / "tests").glob("*.py"), *(root / "spec").rglob("*.py"),
                   *(root / "src").rglob("*.py")]:
        for node in ast.walk(ast.parse(source.read_text())):
            # A citation is a *call* — `proves("dev07-4-2")`, `informs("D4")`. Prose naming a private
            # id is a dangling reference for a reader and not a build dependency, which is a
            # different defect and not this story's.
            if not (isinstance(node, ast.Call) and node.args):
                continue
            named = getattr(node.func, "attr", getattr(node.func, "id", None))
            first = node.args[0]
            if named in ("proves", "informs") and isinstance(first, ast.Constant) \
                    and isinstance(first.value, str):
                cited.setdefault(first.value, set()).add(source.name)

    def namespace(story_id: str) -> str:
        found = re.match(r"[A-Za-z]+", story_id)
        return found.group(0) if found else story_id

    owned = {namespace(sid) for sid in declared}
    upward = {sid: sorted(where) for sid, where in cited.items() if namespace(sid) not in owned}

    assert not upward, (
        "this repository cites a story it does not own, which makes the base unreadable without "
        f"the spec built on it, and unresolvable for anyone who has only this one: {upward}"
    )
