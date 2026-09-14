"""Chapter 4's operators: a minimal in-house AST mutation (``dev07-2-3``).

Three source mutations, applied to Python's own parse tree — flip a comparison, negate a branch,
swap a return. No PIT, no mutmut, no engine to take a version on: the same principle as the
grounding tracer (``dev07-1-3``), for the same reason. Plumb needs one narrow answer, and a
dependency that answers a hundred is a surface it then has to carry.

Nothing here runs anything. This module turns source into *mutated source*; deciding whether a
citing test notices is :mod:`plumb.adapters.python.mutation`. Keeping them apart is what lets the
operator set be argued over — it is a cost/catch tradeoff and openly unsettled (``dev07-2-3``) —
without touching the part that runs tests.

Mutation is **scoped to named functions** (``dev07-2-1``), never to a whole file. The names are the
ones the trace already produced, so what gets mutated is the code the citing test was observed to
run, and nothing else.
"""

import ast
from dataclasses import dataclass
from typing import Iterator

FLIP_COMPARISON = "flip-comparison"
NEGATE_BRANCH = "negate-branch"
SWAP_RETURN = "swap-return"

#: The whole set (``dev07-2-3``). Small on purpose: these three catch the assert-nothing test, which
#: is the residue mutation exists to dent (``dev07-4-2``). A larger set catches more at more cost,
#: and where that line sits is not fixed here (``dev07-2-3``).
OPERATORS = (FLIP_COMPARISON, NEGATE_BRANCH, SWAP_RETURN)

#: Each comparison paired with its negation, so the mutant is a real behavioural change rather
#: than a neighbouring one. ``<`` becomes ``>=`` and not ``>``: swapping for a *neighbour* leaves
#: the boundary case behaving identically, which is an equivalent mutant on exactly the input a
#: test is most likely to use (``dev07-2-4``).
_FLIPPED = {
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq,
    ast.Lt: ast.GtE, ast.GtE: ast.Lt,
    ast.Gt: ast.LtE, ast.LtE: ast.Gt,
    ast.In: ast.NotIn, ast.NotIn: ast.In,
    ast.Is: ast.IsNot, ast.IsNot: ast.Is,
}

#: The frame name CPython gives module-level code. A test that imports production code during the
#: traced window grounds into this, so it is a mutable scope like any other.
MODULE_SCOPE = "<module>"

#: A nested function and a nested class are separate scope units with their own qualified names,
#: so they are mutated only when separately grounded. A lambda is not — it has no frame the trace
#: names, so it belongs to the function that encloses it.
_OWN_SCOPE = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


@dataclass(frozen=True)
class Mutant:
    """One mutated rendering of a module, and where the change was made.

    ``source`` is the whole module, not a patch: what runs a mutant is a file on disk and a
    fresh interpreter, so a mutant that cannot be written out is no mutant at all.
    """

    operator: str
    where: str
    line: int
    source: str


def mutants(source: str, *, module: str, scope: tuple[str, ...]) -> Iterator[Mutant]:
    """Every mutant of ``source`` within the named functions, one site at a time.

    Sites are enumerated from a fresh parse each time rather than by copying a tree, so a mutant
    can never carry a previous mutant's change — one mutant, one difference, or a survivor means
    nothing.
    """
    for index, (operator, _, _, where, line) in enumerate(_sites(ast.parse(source), module, scope)):
        working = ast.parse(source)
        _, node, at, _, _ = _sites(working, module, scope)[index]
        _apply(operator, node, at)
        yield Mutant(operator=operator, where=where, line=line,
                     source=ast.unparse(ast.fix_missing_locations(working)))


def site_count(source: str, *, module: str, scope: tuple[str, ...]) -> int:
    """How many mutants :func:`mutants` would yield, for one parse instead of one per mutant.

    The count is what a cost estimate is made of, and an estimate that costs as much as the run
    it is estimating is not an estimate.
    """
    return len(_sites(ast.parse(source), module, scope))


def _sites(tree: ast.Module, module: str, scope: tuple[str, ...]) -> list[tuple]:
    """``(operator, node, at, where, line)`` for every mutable point, in a stable order.

    Order matters more than it looks: it is the only thing tying a site found in one parse to the
    same site in the next, and a mutant applied to the wrong node is a silent false result.
    """
    wanted = frozenset(scope)
    found = []
    for qualname, unit in _scopes(tree):
        if qualname not in wanted:
            continue
        for node in _own_nodes(unit):
            found.extend(
                (operator, node, at, f"{module}:{qualname}", node.lineno)
                for operator, at in _mutable(node)
            )
    return found


def _mutable(node: ast.AST) -> Iterator[tuple[str, int]]:
    """Which operators apply to this node, and at which sub-position."""
    if isinstance(node, ast.Compare):
        yield from (
            (FLIP_COMPARISON, at)
            for at, op in enumerate(node.ops)
            if type(op) in _FLIPPED
        )
    elif isinstance(node, (ast.If, ast.While)):
        yield NEGATE_BRANCH, 0
    elif isinstance(node, ast.Return):
        yield SWAP_RETURN, 0


def _apply(operator: str, node: ast.AST, at: int) -> None:
    if operator == FLIP_COMPARISON:
        node.ops[at] = _FLIPPED[type(node.ops[at])]()
    elif operator == NEGATE_BRANCH:
        node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
    else:
        node.value = _swapped(node.value)


def _swapped(value: ast.expr | None) -> ast.expr:
    """A different value, not merely a missing one.

    A bare ``return`` and ``return None`` become ``return True`` rather than the reverse: swapping
    a returned value for ``None`` when it already was ``None`` is the definition of an equivalent
    mutant, and every one of those costs a full test run to learn nothing (``dev07-2-4``).
    """
    if value is None or (isinstance(value, ast.Constant) and value.value is None):
        return ast.Constant(True)
    if isinstance(value, ast.Constant) and isinstance(value.value, bool):
        return ast.Constant(not value.value)
    return ast.Constant(None)


def _scopes(tree: ast.Module) -> Iterator[tuple[str, ast.AST]]:
    """``(qualified name, node)`` for module-level code and every function under it.

    The names are built the way CPython builds ``co_qualname`` — ``Class.method``, and
    ``outer.<locals>.inner`` for a closure — because the trace reports what the *runtime* called a
    frame, and a scope this cannot name is a scope that can never be mutated.
    """
    yield MODULE_SCOPE, tree
    yield from _functions(tree, "")


def _functions(node: ast.AST, prefix: str) -> Iterator[tuple[str, ast.AST]]:
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.ClassDef):
            yield from _functions(child, f"{prefix}{child.name}.")
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield f"{prefix}{child.name}", child
            yield from _functions(child, f"{prefix}{child.name}.<locals>.")
        else:
            yield from _functions(child, prefix)


def _own_nodes(unit: ast.AST) -> Iterator[ast.AST]:
    """Every node belonging to this scope unit, stopping at anything that owns its own."""
    for child in ast.iter_child_nodes(unit):
        if isinstance(child, _OWN_SCOPE):
            continue
        yield child
        yield from _own_nodes(child)
