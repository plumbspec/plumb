"""Code this artifact carries rather than installs.

``dependencies = []`` is a runtime claim and it stays exactly true: nothing here is fetched,
resolved or installed, and a `pip install` of Plumb pulls in no more than it ever did. What is
here is carried *inside* the single file, for the same reason the Java adapter's jars are — the
artifact has to work on a machine with no package index and no account.

Nothing is vendored for convenience. The bar is: the standard library answers it on the versions
that have it, nothing answers it on the versions that do not, and getting it partly right would
be worse than not offering it.
"""
