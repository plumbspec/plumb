"""The integrity gates, run against this repository's own spec.

**They are not implemented here.** They are `specgate.py`, beside this file and outside anything
that is packaged. It points them at `spec/` and fails the run if they find anything.

They check **ours and only ours**. This was once a copy of the gates emitted into every adopting
project, which forks on landing, reaches nobody with the next fix, and arrives in a language the
project may not speak. The answer after that was to ship one copy behind a command — which fixed
the forking and kept the mistake underneath it, that somebody else's spec is ours to read and
check. It is not. Plumb reads a manifest; what a project writes down, and whether anything holds it
honest, is that project's own business.
"""

from pathlib import Path

from goldspec import check_spec_directory, conventions_for

REPO = Path(__file__).resolve().parent.parent
SPEC = REPO / "spec"


def test_the_spec_directory_is_consistent_with_itself():
    """Every subject declared once, placed in its process flow, every open unknown in both of its
    homes, every flow able to render, and no test citing a subject nobody wrote down.

    `cited_from` is the repository, which is what makes the last of those worth running: it holds
    the spec against something authored independently of it. The check it replaced compared the
    trace tables to a second copy of the same ids in `chapter_*.py`, and two copies of one list
    agreeing is not evidence of anything.

    The conventions come from `spec/goldspec.toml`, which is also what `goldspec spec` reads. They
    were typed here until 2026-08-16, and the corpus extent with them — so this test resolved the
    cross-repository references and the command did not, and the two reported different faults about
    the same bytes. A gate and a command disagreeing about one spec is the second home this method
    exists to remove, arriving through the tooling rather than through the corpus.
    """
    conv = conventions_for(SPEC)
    # The corpus spans repositories (`ent2`): chapter 0 consumes `spec`, which the methodology's
    # own chapter 7 defines. A sibling is read for the names it defines and never checked here.
    assert conv.siblings and all(Path(s).is_dir() for s in conv.siblings), (
        f"a sibling spec named in {SPEC}/goldspec.toml is not on disk: {conv.siblings}. This check "
        "resolves cross-repository references against it, and without it four correct references "
        "read as defined nowhere")
    report = check_spec_directory(SPEC, conv, cited_from=REPO)
    assert report.ok, "the spec is not consistent with itself:\n  " + "\n  ".join(report.problems)
    assert report.checked, "a run that checked nothing is not a pass"
