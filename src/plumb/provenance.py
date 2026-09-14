"""What the tool was and did when the rub happened (``ch6-32``).

Every anchor a record carries describes the **adopter's code** — a project, a commit, a location, an
excerpt. None of them describes *this tool*, so a record used to arrive saying what rubbed and leave
the operator to ask which version, which adapter, on which runtime, and what Plumb actually printed.
By then the context that produced the rub is gone.

**Read rather than asked.** A filer who has just watched something go wrong should not be
interviewed about their own toolchain, and capture is often an agent with nobody to interview. The
last board left a manifest in the scratch, and the manifest already carries chapter 2's `observer` —
which adapter watched, with what mechanism, on which runtime. That is borrowed whole rather than
restated (`dev07-3-1`), so the two spellings cannot disagree.

**What is not known is spelled, not guessed.** A record filed at a desk with nothing running gets
`n/a`: no run applied. A field that applied to a run and was never recorded gets `unknown`. Those
are different facts and `ch6-4` is the reason they get different words — and this module is where
the distinction is easiest to get wrong, because both look like "we have no value".
"""

from pathlib import Path

from plumb.support import INAPPLICABLE, UNCAPTURED


def observed(config, scratch=None) -> dict:
    """The support facts for a record filed in this project now.

    Returns the three fields as they should be stored, absence markers included. Never raises: a
    record must be filable when the tool cannot answer anything about itself, which is exactly the
    state a badly broken run leaves behind (`dev07-5-1`).
    """
    facts = {"observer": INAPPLICABLE, "invocation": UNCAPTURED, "diagnostic": INAPPLICABLE}
    manifest = _last_manifest(config, scratch)
    if manifest is None:
        # Nothing has run here, so nothing about a run applies. `n/a` and not `unknown`: there is
        # no lost value, there was no run.
        return facts
    facts["invocation"] = _invocation(config, scratch)
    facts["observer"] = _observer(manifest)
    facts["diagnostic"] = _diagnostic(manifest)
    return facts


#: Where a board records what it was asked to do. Beside the manifest, because that is the pair a
#: reader wants: *this ran, and this is what came out*.
RAN = "ran.tsv"


def record_run(config, command, outcome: str) -> None:
    """Note what this board was asked to do and how it ended (``ch6-32``).

    Written by the board and read by a filing, because the two happen at different moments and a
    filer cannot be asked to remember the second one. `invocation` was otherwise permanently
    `unknown`, and a field that never carries a value is one a reader stops looking at.

    **Options and not arguments.** What is kept is the shape of the command — `board --mutation
    --tests` — never the values beside them, because a path or a story id is the adopter's and this
    field travels by default (`ch6-29`). Knowing that mutation was on answers most of what the
    option list is asked for; knowing which directory does not.
    """
    try:
        from plumb.launch import _scratch

        where = Path(_scratch(config))
        where.mkdir(parents=True, exist_ok=True)
        shape = " ".join(w for w in command if w.startswith("-") or w.isalpha())
        (where / RAN).write_text(f"command\t{shape}\noutcome\t{outcome}\n")
    except Exception:      # noqa: BLE001 — a board never fails because a note about it would not write
        pass


def _invocation(config, scratch=None) -> str:
    try:
        if scratch is None:
            from plumb.launch import _scratch

            scratch = _scratch(config)
        text = (Path(scratch) / RAN).read_text()
    except OSError:
        return UNCAPTURED
    said = dict(line.split("\t", 1) for line in text.splitlines() if "\t" in line)
    command, outcome = said.get("command", ""), said.get("outcome", "")
    return f"{command} — {outcome}" if command else UNCAPTURED


def _last_manifest(config, scratch=None):
    from plumb.core.manifest import Manifest

    try:
        if scratch is None:
            from plumb.launch import _scratch

            scratch = _scratch(config)
        where = Path(scratch) / "manifest.json"
        return Manifest.from_json(where.read_text()) if where.is_file() else None
    except Exception:      # noqa: BLE001 — a filing never fails because provenance would not read
        return None


def _observer(manifest) -> str:
    """Which adapter watched, from the manifest that already says so.

    A board may carry two adapters (`dev07-3-1` is why the observer is per citation rather than per
    document), so this reports every distinct one rather than the first — a record naming one of
    two observers is a record that has quietly picked a side.
    """
    seen = []
    for story in manifest.stories.values():
        for citation in story.citations:
            one = getattr(citation, "observer", None)
            if not one:
                continue
            # A dataclass, not a mapping — chapter 2 owns the shape and this borrows it whole
            # rather than re-spelling its fields (`dev07-3-1`).
            said = f"{one.adapter} {one.version} on {one.runtime}"
            if said not in seen:
                seen.append(said)
    return " · ".join(seen) if seen else UNCAPTURED


def _diagnostic(manifest) -> str:
    """What Plumb said about this run, in Plumb's own words.

    The board's conditions are the tool's own sentences about its own behaviour — coded (`dev07-5-2`)
    and already written to be read by somebody who has to act. That is why this is the one prose
    field `ch6-U1` does not reach: redacting it would be redacting our text, not the adopter's.

    Codes and not the prose beside them, because the prose is this build's wording and the code is
    the stable thing a reader can look up — the same reason a consumer branches on the code and
    never on the sentence (`dev07-5-2`).
    """
    try:
        from plumb.core.board import Board

        rendered = Board.render(manifest).as_dict()
    except Exception:      # noqa: BLE001
        return UNCAPTURED
    codes = [c.get("code") for c in rendered.get("conditions", ()) if c.get("code")]
    return ", ".join(codes) if codes else INAPPLICABLE
