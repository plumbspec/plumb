"""The trigger conditions that ship with the tool (``ch6-10``).

An agent files nothing it has to go looking for, so the instruction telling it *when* to file
travels with the capability rather than living in a wiki nobody opens. These are concrete
conditions, not an exhortation to be observant: each one is a thing that either happened in the
last few minutes or did not.

Emitted by ``plumb friction why`` so an agent can read it without leaving the tool.
"""

TRIGGERS = (
    ("re-read", "A spec section had to be re-read to be understood. The first reading failing is "
                "the observation — not that the text is bad, but that it did not land."),
    ("abandoned", "An attempt was started, abandoned, and retried differently. The abandoned path "
                  "is the record; nobody remembers it an hour later."),
    ("interpreted", "A board message, error or condition code needed interpreting before it could "
                    "be acted on. If it needed a translator, it is not yet an interface."),
    ("worked-around", "Something was done a longer way because the short way did not exist. This "
                      "is the one that most reliably goes unfiled, because it feels like progress."),
    ("surprised", "Behaviour differed from what the spec led you to expect — either is a defect: "
                  "the code, or the spec that set the expectation."),
    ("asked", "A question had to be asked of a person because no artifact answered it. The gap is "
              "in the artifact, and it closes the moment the answer is given and lost."),
)

BAR = (
    "A record must say what the rub implies FOR THE METHOD. If you cannot state the "
    "implication, do not file: an observation without one is an anecdote, and a tireless filer "
    "buries the signal for everyone. The bar is deliberate, and it is the same shape as the proof "
    "gate — no claim without the thing that makes it real."
)


def instruction() -> str:
    """The shipped instruction, as an agent should read it."""
    lines = [
        "FILE A FRICTION RECORD WHEN — any of these, at the moment it happens:",
        "",
    ]
    lines += [f"  {name:<14} {text}" for name, text in TRIGGERS]
    lines += [
        "",
        "THE BAR",
        "",
        f"  {BAR}",
        "",
        "HOW",
        "",
        "  plumb friction file --observation '...' --implication '...' [--story APP-142]",
        "                      [--code PATH:START-END] [--tag NAME]",
        "",
        "Capture is local by default and never transmits unless this installation was enrolled",
        "Filing writes nothing to the project you are working in.",
    ]
    return "\n".join(lines)
