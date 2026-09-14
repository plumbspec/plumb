"""How a decision's standing is *said* — `dev07-4-3`.

Separate from the corpus checks, which ask whether a record is well-formed. This asks the only
question that matters once it is: **what does the board say about it, and in whose words.**

The vocabulary is a projection over what the gate already derived — every word below
comes from a status plus a condition the derivation already carried, so nothing here can say what
the run did not. That is what stops a lexicon becoming somewhere standing is quietly authored.
"""

import pytest

from plumb.core.gate import derive, label
from plumb.core.manifest import (
    FAILED,
    INERT,
    PASSED,
    SKIPPED,
    STRUCTURAL,
    WORST,
    Citation,
    Story,
)

DECISION = "decision"


def evidence(result=PASSED):
    """One citing test's facts. Inert, because a decision's checks read rather than run."""
    return Citation(test="t::a", depth="", result=result, grounding=INERT)


def standing(*citations) -> str:
    """What a decision carrying these citations is called."""
    story = Story(archetype=STRUCTURAL, reduce=WORST, citations=citations)
    return label(derive("D", story), DECISION)


@pytest.mark.proves("dev07-4-3", depth="component")
def test_an_evaluated_trigger_reads_holding_or_breached_and_never_proven():
    """*Proven* is the wrong word for a claim about the future. A decision can only be
    un-falsified **so far**, so `holding` is the strongest thing it may ever say — and a tool that
    said `proven` would be promising something no evidence about the past can support."""
    assert standing(evidence()) == "holding"
    assert standing(evidence(FAILED)) == "breached", "the check ran and the condition was true"
    assert standing(evidence(SKIPPED)) == "unwatched", (
        "and a check that never ran is not a breach — the distinction chores need, and the one "
        "this test itself got wrong before `evidence.not-observed` existed")


@pytest.mark.proves("dev07-4-3", depth="component")
def test_a_decision_nobody_is_watching_is_surfaced_rather_than_read_as_healthy():
    """**The silence is the finding.** A decision that has received no measurement looks exactly
    like one that is fine, and did: every decision in this corpus read UNPROVEN alongside the ones
    nothing had ever examined, with nothing on the board to tell them apart.

    `silent` and `breached` are the same *status* — both unproven — and opposite situations. For
    code the two readings of unproven are one thing; here one means nobody is looking and the
    other means the condition has fired.
    """
    assert standing() == "silent"
    assert standing() != standing(evidence(FAILED)), "silence is not a breach"
    assert standing() != standing(evidence(SKIPPED)), "nor is a check that did not run"


@pytest.mark.proves("dev07-4-3", depth="component")
def test_a_breach_informs_and_does_not_fail_anything():
    """Turning a breach into a build failure is how it gets suppressed rather than read, and it
    would be this tooling deciding for an owner what their own decision costs them. They may
    choose to fail on it, exactly as they may choose to fail on an unproven story.

    Mechanically: a breach is a *word on a board*, and producing it raises nothing. The suite
    running this assertion is itself the evidence — it carries a decision whose falsifier has
    fired, as a strict xfail, and it is green.
    """
    assert standing(evidence(FAILED)) == "breached", "it is said"
    # No exception, no non-zero anything: the call above simply returned a string.
