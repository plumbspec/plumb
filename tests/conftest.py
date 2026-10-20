"""What every test in this directory is given, whether it asks or not.

The suite builds real projects in temporary directories and runs real boards over them. Anything
the tool writes *outside* a project therefore lands in the developer's own home unless it is
pointed somewhere else first — and a test that leaves its droppings on the machine that ran it is
one nobody notices until the machine is somebody else's.
"""

import os

import pytest


@pytest.fixture(autouse=True)
def _cache_in_the_tmp_dir(monkeypatch, tmp_path):
    """The adapter's scratch, per test rather than per developer.

    ``launch._scratch`` keys a project's run file and manifest by path under ``XDG_CACHE_HOME``,
    so every temporary project a test builds earns a directory of its own that nothing will ever
    read again. One suite run left 67 of them in a real ``~/.cache`` before this existed.

    Autouse because the tests that need it are exactly the ones that do not mention it: a board is
    driven through ``cli.main`` several layers above the scratch, and asking each of them to
    remember is how a cleanup rule ends up applied to the tests that already pass.
    """
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))


@pytest.fixture(autouse=True)
def _config_in_the_tmp_dir(monkeypatch, tmp_path):
    """The developer's own credential, kept out of reach of the suite.

    The same rule as the scratch above, applied to the half that is not scratch. An enrolment lives
    outside any project, under ``XDG_CONFIG_HOME``, and is a file the tool writes that is **not**
    disposable.

    The environment variable alone does not do it. The default is a module constant resolved at
    **import**, so a test process that has already imported it keeps the developer's path whatever
    the environment says afterwards. The constant is therefore pointed at the temporary directory
    as well, and a test that redirects it itself still wins — monkeypatch is undone in reverse.
    """
    config = tmp_path / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    from plumb import enrolment

    monkeypatch.setattr(enrolment, "DEFAULT_ENROLMENT", config / "plumb" / "enrolment.json")


@pytest.fixture
def runnable_tmp(tmp_path, request):
    """A temporary directory a test may *execute* from, which ``tmp_path`` is not always.

    ``/tmp`` is mounted ``noexec`` on some hosts — including the one this is written on — and
    pytest builds its temporary tree under ``TMPDIR``. Everything a test writes there behaves
    normally right up to the moment something tries to run it, and then ``os.access(…, X_OK)`` is
    ``False`` for a file whose mode bits plainly say otherwise. The installer test read that as
    *the installer did not mark the binary executable*, which is a real defect and was not this
    one.

    Skipping instead would be worse than the confusion: `ado1`'s whole claim is that the artifact
    **runs** in an environment of the adopter's own, and a test that quietly stops checking on the
    hosts where it is hardest to check is not evidence of anything. So the fallback is a directory
    beside the checkout, on a filesystem the repository is already known to be executable from,
    removed afterwards whichever branch is taken.
    """
    import shutil
    import stat
    import tempfile
    from pathlib import Path

    probe = tmp_path / ".exec-probe"
    probe.write_text("#!/bin/sh\ntrue\n")
    probe.chmod(probe.stat().st_mode | stat.S_IXUSR)
    runnable = os.access(probe, os.X_OK)
    probe.unlink()
    if runnable:
        return tmp_path

    here = Path(__file__).resolve().parent.parent / ".pytest-exec"
    here.mkdir(exist_ok=True)
    mine = Path(tempfile.mkdtemp(dir=here, prefix=request.node.name[:40] + "-"))
    request.addfinalizer(lambda: shutil.rmtree(mine, ignore_errors=True))
    return mine
