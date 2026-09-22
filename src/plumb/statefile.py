"""Replacing a file another reader may open mid-write.

The reading a session opens from and the cursor a session leaves are both replaced whole, and both
are read by a later process that trusts what it finds — so replacement is atomic, because a reader
that re-reads can otherwise catch half a file (``dev10-4-sr2``).

**Atomic is not the whole of it.** A replacement creates a *new* file, so it carries the creating
process's ownership and umask rather than the replaced file's. A command run under `sudo`
therefore leaves a `root:root` file where a user's used to be, and the next reader — who is not
root — can no longer open state that is theirs.

So a replacement carries the ownership and mode of what it replaced, and where there was nothing to
replace it is created narrow.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

#: What a state file is created as when there was no predecessor to copy from. The tight default,
#: because nothing here is anybody else's to read.
NEW_FILE_MODE = 0o600


def replace(path: Path | str, body: str) -> Path:
    """Write ``body`` to ``path`` atomically, keeping whoever owned it able to read it."""
    path = Path(path)
    try:
        before = path.stat()
        owner, mode = (before.st_uid, before.st_gid), before.st_mode & 0o777
    except OSError:
        owner, mode = None, NEW_FILE_MODE

    path.parent.mkdir(parents=True, exist_ok=True)
    handle, staged = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(handle, "w") as writing:
            writing.write(body)
            writing.flush()
            os.fsync(writing.fileno())
        os.chmod(staged, mode)
        if owner is not None:
            try:
                os.chown(staged, *owner)
            except PermissionError:
                # Not root and not the owner: the replacement would strand the reader, so refuse
                # rather than write a file the service cannot open. A command that half-succeeds
                # here is one whose effect is invisible until something else goes wrong.
                raise PermissionError(
                    f"{path} is owned by uid {owner[0]}, and this process cannot write it back that "
                    f"way — run this as that user or as root, or the holder will stop being able "
                    f"to read its own state") from None
        os.replace(staged, path)
    except BaseException:
        Path(staged).unlink(missing_ok=True)
        raise
    return path


def replace_json(path: Path | str, value) -> Path:
    """The same, for the JSON these files actually hold."""
    return replace(path, json.dumps(value, indent=2, sort_keys=True) + "\n")
