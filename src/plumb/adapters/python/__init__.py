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
