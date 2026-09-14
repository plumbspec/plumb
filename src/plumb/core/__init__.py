"""The language-blind core: the manifest, the gate, and the board.

Nothing here may import an adapter. That is ``dev07-3-3`` expressed as a package
boundary rather than as a convention — the core reads only the manifest, so a new language is a
new adapter and nothing else. ``tests/test_core_is_policy_free.py`` asserts it by inspection.
"""
