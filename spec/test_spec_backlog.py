"""The gold-spec backlog, printed by ``pytest`` — no external tooling.

A subject and the one line saying what it claims come from the same place. There was a second home
— a ``def chN_M():`` in a chapter module holding the id again — and joining the two was all this
file did. Status is derived and lives in neither, so a backlog is the ideal awaiting the tests that
will prove it.

**Where that place is depends on the chapter's shape, and both are read.** In the older shape the
subject is a trace row and its claim is the rest of that row. In the node format the subject *is*
the node, and the claim is its story — the blockquote under the heading, which is what the trace
row's claim became. Reading only one would empty the backlog of every chapter written in the other,
and a corpus is half converted for as long as converting takes.
"""

import re
from pathlib import Path

from goldspec import conventions_for
from goldspec.nodes import read as read_nodes

SPEC_DIR = Path(__file__).parent
CONV = conventions_for(SPEC_DIR)
DIAGRAMS = SPEC_DIR / CONV.flow_dir
# A trace row: the id, then what the subject claims. Nested sub-stories carry more segments and
# are rows like any other. Read through the same conventions the guardrail reads, so the backlog
# and the gate cannot disagree about which files are the spec.
TRACE_ROW = re.compile(rf"^\|\s*`({CONV.namespace}\d+(?:-\d+)+)`\s*\|\s*(.+?)\s*\|", re.MULTILINE)


def flow_files() -> list[Path]:
    return sorted(DIAGRAMS.glob(CONV.flow_glob))


def claims_in(md: Path) -> list[tuple[str, str]]:
    """One chapter's subjects and claims, in flow order, whichever shape it is written in."""
    converted = read_nodes(md)
    if converted is not None:
        return [(node.id, node.story or node.title) for node in converted.nodes]
    return [(subject, text.replace("**", "").strip())
            for subject, text in TRACE_ROW.findall(md.read_text())]


def backlog() -> list[tuple[str, str]]:
    """Every subject in flow order, with its claim. One read, so the two cannot disagree."""
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    for md in flow_files():
        for subject, claim in claims_in(md):
            if subject not in seen:
                seen.add(subject)
                found.append((subject, claim))
    return found


def test_print_backlog(capsys):
    found = backlog()
    out = [
        "",
        "══════ GOLD-SPEC BACKLOG ══════",
        f"{len(found)} stories · all UNPROVEN until a citing test passes Plumb's gates",
        "",
    ]
    out += [f"  · {subject} — {claim}" for subject, claim in found]
    out.append("═══════════════════════════════")

    with capsys.disabled():
        print("\n".join(out))

    assert found, "expected trace-table rows in the chapter flows"
