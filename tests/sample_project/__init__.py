"""A stand-in production package for tracing against.

Module-level work runs on import on purpose: that is the case ``dev07-1-4`` is about, and the
case that made the fact order-dependent.
"""

IMPORTS = []
IMPORTS.append("module body ran")


def handle_request(n):
    """The declared production entry point."""
    return _double(n) + 1


def _double(n):
    return n * 2


def orphan(n):
    """Real production code that no entry point reaches."""
    return n - 1
