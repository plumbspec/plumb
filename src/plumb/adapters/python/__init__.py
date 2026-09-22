"""The Python/pytest adapter.

Named for the *language* rather than the runner: the trace is CPython's own, and only the plugin
is pytest-shaped. Everything import-specific to Python stops here — what leaves is the neutral
manifest (`docs/adapter-contract.md`).

Deliberately **empty of imports**. Re-exporting the plugin here made importing *anything* under
this package execute ``adapter.py``, which imports ``pytest`` at module scope — so a **Java**
project's run, which reaches in only for ``archetypes`` (pure core, no runner), pulled a Python
test framework in behind it and died with ``ModuleNotFoundError: No module named 'pytest'`` on any
machine with no reason to have one.

That is ``dev07-3-3`` failing at the seam it names: the core is language-blind and the adapter is
language-bound, and a convenience facade quietly made the Java path depend on the Python one. The
re-exports bought nothing — every caller already imports from the concrete module — so the fix is
to stop paying for them.

A package that costs an unrelated dependency to import is not a namespace, it is a side effect.
"""

#: The oldest CPython this adapter runs on (`dev07-3-1`). It runs in the *project's* interpreter,
#: not the tool's, so this is a separate declaration from `requires-python` — raising the tool's
#: floor must not ask a project to raise the one its tests run under.
#:
#: A tuple and not a string: it is read by a gate that compares it, and a gate that has to parse a
#: version before it can check one has two ways to be wrong.
#:
#: A project down here brings pytest 8 — pytest 9 does not reach 3.9 — and that is the project's
#: business rather than ours. `dependencies = []` is what makes it so: the runner is theirs, the
#: plugin attaches to whichever one they have, and this floor is a claim about *our* code.
FLOOR = (3, 9)
