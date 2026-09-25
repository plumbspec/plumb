"""``plumb`` — the command line: the board, the session, the series and the account.

``plumb board`` runs the adapter over a test run and emits the derived result (``dev07-5-1``).

**The support verb is not here.** It was, and it left with the capability in the release that gave
the name up (``mod5``). What answers that name now is a module, mounted through the
`plumb.modules` entry point like any other — and the core keeps no copy of it, because a core that
still ships the verb is a core that still claims the capability (``mod5-ur3``, ``mod5-nfr1``). What
stayed is what a module builds on: the transport surface, the enrolment it resolves through, and
the account that signs (``mod5-sr2``).
"""

from __future__ import annotations

import argparse
import os
import json
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

from plumb import __version__, statefile

#: What ``plumb board`` returns, and the whole of it (``dev07-5-3``). The code describes the
#: **observation**, never the verdict: a board derived from a run that observed tests exits 0 even
#: when every story on it is UNPROVEN, because proof happens at the desk and a fresh, correct spec
#: is all-unproven and green (``dev07-4-3``, ``dev07-4-3``). Failing on UNPROVEN would make CI the gate
#: this tool declines to be; leaving *everything* at 0 gives a CI step that cannot fail. So exactly
#: one outcome is non-zero, and it is the one where there was nothing to derive from.
#:
#: A failing suite is deliberately not here. The runner already has an exit code for that and it is
#: the runner's to give — relaying it would put Plumb's name on a verdict it did not reach.
EXIT_OK = 0
EXIT_CANNOT_BOARD = 2
EXIT_NOTHING_OBSERVED = 3






#: Said once, because three commands offer the same flag and three wordings would drift.
ENROLMENT_HELP = "enrolment file (default: ~/.config/plumb/enrolment.json)"

#: Which project the command is *about*, which is not always the one you are standing in. The pull
#: already read this flag through `getattr` and no parser defined it, so the answer was always
#: `None` and the subject came from wherever the shell happened to be.
PROJECT_HELP = ("the project whose subject this series belongs to (default: the project the series "
                "file lives in)")


def _push_series(store: Path, enrolment: str | None, project: str | None = None) -> str:
    """Send what the service has not been given, and say what happened in one line.

    Shared by `board --push` and `series push` so there is one implementation and two triggers.
    Which one you reach for is a question about *when*, never about *what*, and two answers to
    *what* would drift.
    """
    from plumb.transmit import push_series

    outcome = push_series(store, Path(enrolment) if enrolment else None, project)
    if outcome.reason:
        return f"series: not pushed — {outcome.reason}"
    if not outcome.sent:
        return "series: nothing to push"
    return f"series: pushed {len(outcome.sent)} record(s)"


def cmd_series_push(args) -> int:
    """``dev07-6-3-sr1`` — push a series on its own, whenever the operator chooses.

    **Never fails on an unreachable holder.** A board is derived from a run and complete without
    the network, so the exit code says whether the *store* was readable rather than whether the
    network was up — otherwise a holder outage becomes a red build for a reason that has nothing
    to do with the project (`dev07-6-2-ur6`, `dev07-5-3`'s shape).
    """
    store = Path(args.file)
    if not store.is_file():
        print(f"no series at {store} — run `plumb board --series {store}` first", file=sys.stderr)
        return 1
    if getattr(args, "dry_run", False):
        from plumb.transmit import wire_form

        records, how = wire_form(store, Path(args.enrolment) if args.enrolment else None,
                                 getattr(args, "project", None))
        print(f"series: {len(records)} record(s) would be {how}\n")
        for record in records:
            print("  " + json.dumps(record, separators=(",", ": ")))
        if not records:
            print("  (nothing pending — an unchanged project has nothing to say)")
        return 0
    print(_push_series(store, getattr(args, "enrolment", None), getattr(args, "project", None)))
    return 0


def cmd_series_show(args) -> int:
    """``dev07-6-3`` — read a history back: when it changed, when we last looked, what keeps changing.

    Facts and no verdict. Status derives from a run (`dev07-4-3`), so a history that graded anything
    would be a second source of truth about it — and the two would disagree the first time somebody
    opened an old file.
    """
    from plumb.core.series import (CACHE, InvalidSeries, discarded, extent, history, overview,
                                   read, sent_mark)

    store = Path(args.file)
    if not store.is_file():
        print(f"no series at {store} — run `plumb board --series {store}` first", file=sys.stderr)
        return 1

    try:
        entries = read(store)
    except InvalidSeries as bad:
        print(f"series: {bad}", file=sys.stderr)
        return 1
    if not entries:
        # Not an error and not an empty table: a store that exists and holds nothing is a project
        # that has run once and changed nothing, which is the healthy case (`dev07-5-2`).
        print(f"{store}: no history yet")
        return 0

    for gone in discarded(entries):
        # First, and never as a footnote. A reader who scrolls past this reads the rest as the
        # whole history, which is the one thing `dev07-6-2` exists to prevent.
        print(f"discarded {gone.discarded_from}–{gone.discarded_through}"
              + (f" at {gone.when}" if gone.when else "") + f" — {gone.reason}")

    # What this copy is, and what it holds (`dev07-6-3`). Stated on every read from either end, because
    # the invariant underneath the whole hierarchy is that **no store answers a question about a
    # range it does not hold as though it held it** — and a reader with two files open has nothing
    # to correct toward unless one of them says it is derived.
    mark = sent_mark(store)
    through = int(mark.read_text().strip() or 0) if mark.is_file() else 0
    holds = extent(entries, through)
    if holds.role == CACHE:
        print(f"cache of {holds.holder or 'a holder that keeps the history'}"
              + (f", seq {holds.first}–{holds.last}" if holds.first is not None else "")
              + " — derived, not a second opinion")

    # `dev07-6-2`'s reason applied one step further out (`dev07-6-1`): a history that cannot show it began
    # here is not a short history, and a reader handed a confident small number with nothing
    # disagreeing has been told something false about a fortnight. Below the discarded lines and
    # above the table — `dev07-6-2` claims the first position outright and this claims only that a
    # reader cannot reach a count without passing it.
    if not holds.whole:
        print("history of UNKNOWN EXTENT — this file carries no origin stamp, so it cannot show "
              "whether it\n  is the whole history. A count below is a floor, never a total. A "
              "series written before\n  stamping existed reads this way; so does one restored "
              "from a partial copy.")

    if args.subject:
        for entry in history(entries, args.subject):
            went = f"{entry.result} · {entry.grounding}" if entry.result else "gone"
            print(f"  {entry.when or 'when unknown':<22}{went:<26}{entry.test}"
                  + (f" · {entry.about}" if entry.about else ""))
        return 0

    rows = sorted(overview(entries), key=lambda s: (-s.changes, s.subject))
    print(f"{'subject':<28}{'last changed':<22}{'last looked':<22}{'changes':>7}")
    for row in rows:
        print(f"{row.subject:<28}{row.changed or '—':<22}{row.checked or 'never':<22}"
              f"{row.changes:>7}")
    return 0


def cmd_series_pull(args) -> int:
    """``dev07-6-3`` — fetch the history the holder keeps for this subject, and write it down.

    The custodial half made real: a store that cannot hand it back is holding nothing for anyone
   , and until this existed the only way to see it was a hand-written `curl`. Retrieval is
    also the signal eviction ranks on, so reading your history is what keeps it.
    """
    from plumb.enrolment import NotEnrolled, load
    from plumb.transmit import _configured_subject, _signing

    # An account first, and only then an enrolment (`ch12-5`): a signed request needs no bearer
    # credential at all, so demanding one here would refuse the very route that exists to work
    # without an operator.
    account = _signing() if not args.enrolment else None
    enrolment = None
    if account is None:
        try:
            enrolment = load(Path(args.enrolment) if args.enrolment else None)
        except NotEnrolled as why:
            print(f"series: not pulled — {why}", file=sys.stderr)
            return 1
    subject = args.subject or (enrolment.subject if enrolment else "") or \
        _configured_subject(Path(args.file), getattr(args, "project", None))
    if not subject:
        print("series: no subject to ask for. Name one with `subject = \"…\"` in plumb.toml — it "
              "names a series inside the store you own, so it is yours to choose — or pass "
              "--subject", file=sys.stderr)
        return 1

    import json
    import urllib.error
    import urllib.request

    from plumb.transmit import TIMEOUT_SECONDS

    # Signed where an account is configured, bearer where one is not — two doors, one model
    # (`ch12-5`). A read returns somebody's history, so it authenticates exactly as the write that
    # put it there does, and under `ch12-21` what it returns is scoped to whoever wrote it.
    from plumb.transmit import _signing

    account = _signing()
    if account is not None:
        from plumb import account_client

        headers, advanced = account_client.signed(account, "GET", f"/series/{subject}", b"")
        account_client.save(advanced)
        endpoint = account.endpoint
    else:
        headers = {"Authorization": f"Bearer {enrolment.credential}"}
        endpoint = enrolment.endpoint
    request = urllib.request.Request(f"{endpoint.rstrip('/')}/series/{subject}", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as answer:
            held = json.loads(answer.read())
    except urllib.error.HTTPError as refused:
        try:
            explained = json.loads(refused.read().decode())
            note = explained.get("error") or ""
            for extra in ("holder", "hint", "grants"):
                if explained.get(extra) is not None:
                    note += f" [{extra}: {explained[extra]}]"
        except (ValueError, OSError):
            note = ""
        if refused.code == 404:
            print(f"series: the holder has nothing for {subject}", file=sys.stderr)
            return 1
        print(f"series: the holder said {refused.code}"
              + (f" — {note}" if note else ""), file=sys.stderr)
        return 1
    except (urllib.error.URLError, OSError, TimeoutError) as unreachable:
        print(f"series: holder unreachable: {unreachable}", file=sys.stderr)
        return 1

    # The copy says it is a copy (`dev07-6-3`). Written into the file rather than worked out later
    # from configuration, because the question is about *this file* and its answer has to survive
    # being moved, mailed, or opened somewhere the project is not. Last, so the holder's own
    # sequence is untouched and a reader diffing two copies sees the same records in the same order.
    from dataclasses import asdict
    from datetime import datetime, timezone

    from plumb.core.series import Retrieved

    records = list(held["records"])
    marker = Retrieved(seq=max((r.get("seq", 0) for r in records), default=0) + 1,
                       retrieved_from=f"{endpoint.rstrip('/')}/series/{subject}",
                       at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    out = Path(args.file)
    out.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in records)
                   + json.dumps(asdict(marker), separators=(",", ":")) + "\n")
    print(f"series: pulled {len(records)} record(s) for {subject} -> {out}")
    return 0


def cmd_manifest_migrate(args) -> int:
    """Bring a manifest forward on disk. Offered, never automatic.

    The command two of `manifest.py`'s own messages have named since before it existed, including
    the one printed to a reader whose manifest is out of the window — so until now the tool told
    them to run something it did not have.
    """
    from plumb.core.manifest import SCHEMA_VERSION, InvalidManifest, Manifest

    path = Path(args.file)
    try:
        text = path.read_text()
    except OSError as unreadable:
        print(f"cannot read {path}: {unreadable}", file=sys.stderr)
        return 1

    was = json.loads(text).get("schema_version") if text.strip().startswith("{") else None
    if str(was) == SCHEMA_VERSION:
        print(f"{path} is already at schema {SCHEMA_VERSION}")
        return 0
    try:
        climbed = Manifest.migrate(text)
    except (InvalidManifest, ValueError) as refused:
        # Named, never guessed at: a shape outside the chain cannot be inferred, and writing a
        # plausible file over the only copy of the evidence is worse than refusing (`dev07-3-1`).
        print(f"{path}: {refused}", file=sys.stderr)
        return 1

    path.write_text(climbed.to_json())
    print(f"{path}: schema {was} -> {SCHEMA_VERSION}")
    return 0


def cmd_init(args) -> int:
    """``ado2``, ``ado3`` — write what is missing, keep what is there, say what to do next."""
    from plumb.scaffold import init, next_steps

    outcome = init(args.project)
    for name in outcome.written:
        print(f"wrote    {name}")
    for name in outcome.kept:
        # Never overwritten, and never silent about it: a file the tool wrote once belongs to the
        # project the moment it lands, and the adopter has to know which half they are looking at.
        print(f"kept     {name}  (already present — left exactly as it is)")
    print(f"\ndetected {outcome.detected.adapter}")
    for note in outcome.detected.notes:
        print(f"  still to do: {note}")
    print(next_steps(outcome.detected))
    return 0


def cmd_account(args) -> int:
    """The self-provisioned route, which is the one a client can actually perform (`ado1-nfr2`).

    `plumb registry` used to sit here and could not: it manages the registry of a holder, which
    only its operator has, and a command a tool ships is a claim that the operation is the reader's
    to perform. It has moved to the service's own command, where it can be performed. What stands
    in its place is the route that was missing — the honest end of that defect was never a better
    refusal, it was this.
    """
    from plumb import account_client, identity

    path = Path(args.account) if args.account else None
    try:
        if args.command == "create":
            secret = identity.new_root()
            who = identity.Identity(secret)
            kept = account_client.save_root(secret)
            saved = account_client.save(account_client.AccountConfig(
                (args.endpoint or "").rstrip("/"), who.public,
                digest_key=identity.digest_key(secret).hex()), path)
            print("identity generated, and its public half is the account it names\n")
            print(f"    key   {who.public}\n")
            # Said about the files rather than about the secret, and positively. An earlier version
            # printed the secret and said only where it was *not* written; a reader who had just
            # been shown one took that to mean nothing had been saved, went looking for the command
            # that writes the account file, found none because `create` is it, and wrote an empty
            # one by hand (`ado6-ur2`).
            print(f"written to {saved} — the endpoint, the public half, this key's counter and the")
            print("key your history is pseudonymised under. There is nothing further to write.\n")
            print(f"The root itself is in {kept}, readable only by you. **Nothing was shown to")
            print("you and nothing needs copying**: no secret crosses a terminal here, which is")
            print("what lets this be one command.\n")
            print("For CI, or to hold a copy somewhere of your own:\n")
            print("    plumb account export\n")
            print(f"prints it as one string for {account_client.ROOT_ENV}. Lost, with no copy kept,")
            print("means the account is lost.")
            return 0

        if args.command == "open":
            # `dev07`-era recovery, live-tested 2026-09-12: open is signed by a fresh key and never
            # credentialled — a caller holding nothing has nothing to hold. The operator binds the
            # account to an existing customer out of band; opening without that binding makes a
            # new customer and recovers nothing.
            import datetime
            import hashlib
            import urllib.error
            import urllib.request
            config = account_client.load(path)
            endpoint = (args.endpoint or config.endpoint).rstrip("/")
            secret = account_client.root()
            who = identity.Identity(secret)
            body = json.dumps({"public": who.public, "email": args.email}).encode()
            headers = account_client.signed_wire2(who, "POST", "/account", body)
            headers.update({"Content-Type": "application/json",
                            "Plumb-Support-Version": "2"})
            request = urllib.request.Request(f"{endpoint}/account", data=body, method="POST",
                                             headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=10) as answered:
                    said = json.loads(answered.read() or b"{}")
            except urllib.error.HTTPError as refused:
                print(refused.read().decode(), file=sys.stderr)
                return 2
            print(f"account opened: {said.get('state', '?')}, expires {said.get('expires_at', '?')}")
            print("confirm the address from its mail, and redeem the credential link with:")
            print("\n    plumb account redeem <token>\n")
            return 0

        if args.command == "redeem":
            # The link's token is the whole credential of the redemption, and the answer comes
            # once — so this command's only other job is writing what it was answered where the
            # channel already reads.
            import urllib.error
            import urllib.request
            config = account_client.load(path)
            endpoint = (args.endpoint or config.endpoint).rstrip("/")
            request = urllib.request.Request(
                f"{endpoint}/account/credential/{args.token}", method="POST",
                headers={"Plumb-Support-Version": "2"})
            try:
                with urllib.request.urlopen(request, timeout=10) as answered:
                    said = json.loads(answered.read() or b"{}")
            except urllib.error.HTTPError as refused:
                print(refused.read().decode(), file=sys.stderr)
                return 2
            from plumb.enrolment import DEFAULT_ENROLMENT
            where = Path(DEFAULT_ENROLMENT).expanduser()
            if where.is_file():
                kept = where.with_suffix(".json.replaced")
                kept.write_text(where.read_text())
            where.parent.mkdir(parents=True, exist_ok=True)
            where.write_text(json.dumps({"relationship": "self",
                                         "credential": said["credential"],
                                         "endpoint": endpoint}))
            where.chmod(0o600)
            print(f"credential stored in {where} — filed_by stays {said.get('label', '?')},")
            print("and your cases are unchanged. The link is now spent.")
            return 0

        if args.command == "export":
            # The old posture, offered rather than imposed (`ado6-ur5`): somebody who wants the disk
            # to hold nothing exports this, deletes the file, and supplies it from the environment.
            secret = account_client.root(getattr(args, "passphrase", None))
            print(identity.encode_root(secret))
            return 0

        config = account_client.load(path)
        if args.command == "show":
            # The three stored fields are public or derivable, so they read healthy for an account
            # nobody can rebuild. Whether it can sign is the one thing here that is not written down,
            # so it is derived on every ask and never recorded (`ado6-ur3`).
            answer = account_client.can_sign(config, getattr(args, "passphrase", None))
            print(f"  endpoint  {config.endpoint}")
            print(f"  key       {config.public}")
            print(f"  counter   {config.counter}")
            print(f"  signs     {'yes' if answer.can_sign else 'no'}")
            # Two different questions, and the second is the one the file cannot answer for
            # itself. `signs` is about this invocation — is the passphrase here, now. `proved` is
            # about the account's whole life: has anyone, ever, on this install, shown the secret
            # exists. An account reading `signs no` in CI is usually an environment variable that
            # did not arrive; one that has ALSO never been proved is a passphrase printed and never
            # read, and the two do not have the same repair.
            #
            # `can_sign` derives, so a success here has just recorded itself — read the answer
            # rather than the copy loaded before it.
            proved = answer.can_sign or config.confirmed
            if config.confirmed is not None:
                print(f"  proved    {'yes' if proved else 'NEVER'}")
            if not proved and config.confirmed is not None:
                sys.stdout.flush()
                print("\nplumb: nothing has ever signed with this account, so its passphrase may "
                      "never have been captured\n  — `create` prints it once and writes it "
                      "nowhere. An account nobody can sign for cannot\n  be recovered: end it and "
                      "create another rather than building anything on it.",
                      file=sys.stderr)
            if not answer.can_sign:
                # Piped — which is every CI log — stdout is block-buffered and stderr is not, so
                # without this the reason arrives above the fields it is explaining.
                sys.stdout.flush()
                print(f"\nplumb: this account cannot sign — {answer.said}", file=sys.stderr)
                return 1
            return 0

    except (account_client.NoAccount, account_client.KeyMismatch, identity.WeakPassphrase,
            identity.Unavailable) as refused:
        print(f"{refused}", file=sys.stderr)
        return 1
    return 1


def _say_cursor(cursor, config) -> None:
    """What the last session left, or both reasons there is nothing (`dev03-1`)."""
    print(f"  cursor    {config.cursor}")
    if cursor is None:
        print("            none — either this is the first session, or the last one did not wrap.")
        print("            Not reconstructed from the log: which of the two it is is not "
              "something\n            the repository can be read to find out.")
        return
    print(f"  next      {cursor.get('NEXT_TASK') or '(unset)'}")
    print(f"  ref       {cursor.get('REF') or '(unset)'}")
    for line in textwrap.wrap(cursor.get("CONTEXT"), 76):
        print(f"            {line}")


def _say_history(config, project, seq: int) -> None:
    """Where a history stands, for the projects that keep one (`dev10-3`)."""
    from plumb import session

    if not config.series:
        return
    moved = session.volatile(config, project)
    print(f"  history   {config.series} · {seq + 1} transition(s) recorded")
    for row in moved:
        print(f"            {row.subject} has moved in {row.changes} runs — "
              f"today's move is not its first")


def cmd_session(args) -> int:
    """Open from a cursor, close by measuring against the spec (`ch13`).

    Two commands and a deliberate asymmetry: opening reports everything it finds and refuses
    nothing, because the cost of a wrong open lands on the person who can see it; closing refuses,
    because the cost of a wrong close lands on a session that cannot (`dev10-1`).
    """
    from plumb import session
    from plumb.config import Config, InvalidConfig
    from plumb.core.gate import PROVEN
    from plumb.launch import LaunchFailed

    project = Path(args.project)
    try:
        config = Config.find(project)
    except InvalidConfig as bad:
        print(f"{bad}", file=sys.stderr)
        return EXIT_CANNOT_BOARD

    cursor_path = project / config.cursor
    reading_path = session.reading_path(project)
    cursor = session.read_cursor(cursor_path)

    if args.command == "start":
        _say_cursor(cursor, config)

        unclean = session.dirty(project, config.repos)
        try:
            reading, _ = session.take_reading(config, project)
        except (LaunchFailed, InvalidConfig) as bad:
            print(f"plumb: cannot take a reading — {bad}", file=sys.stderr)
            return EXIT_CANNOT_BOARD

        print(f"  ground    {'clean' if not unclean else 'UNCOMMITTED in ' + ', '.join(unclean)}")
        if unclean:
            print("            the last session did not wrap, so the cursor may not describe "
                  "what is here")
        print(f"  board     {reading.total - reading.proven} unproven of {reading.total}")
        _say_history(config, project, reading.series_seq)
        statefile.replace(reading_path, reading.to_json())

        if cursor is not None and cursor.get("REF"):
            standing = {sid: st for sid, st in reading.statuses.items()
                        if cursor.get("REF").startswith(sid) or sid in cursor.get("REF")}
            for sid, status in sorted(standing.items()):
                print(f"  target    {sid} is {status}"
                      + (" — already proven; check the cursor is current" if status == PROVEN
                         else ""))
        print(f"\nWhen you are done:  plumb session wrap-up --next '…' --ref … --context '…'")
        return EXIT_OK

    # ── wrap-up: the gate, and it is held before anything is spent or written ──
    #
    # The order is the load-bearing part. This ran the board first, appended to the series, wrote
    # the cursor, and only then asked whether the tree was committed and the cursor filled in — so
    # a session caught by the gate had already had a cursor written to disk and a transition
    # appended to its history, and satisfying the gate meant running the whole board a second time
    # and appending a second time. The refusal is free and the reading is not, so the free half
    # goes first: nothing here is spent, and nothing is written, until the gate has passed.
    #
    # What that costs is the delta on a refused close, which is the right thing to lose — the
    # session is not over, and the number is reported on the run that actually ends it (`dev10-2`).
    intended = dict(cursor.fields) if cursor else {}
    sets_cursor = bool(args.next_task or args.ref or args.context)
    for key, value in (("NEXT_TASK", args.next_task), ("REF", args.ref),
                       ("CONTEXT", args.context)):
        if value:
            intended[key] = value

    # What this run will write, exempted from the check the same way it used to be exempted after
    # the fact: a command cannot both write a file and require it to have been committed already,
    # which would make the gate unsatisfiable in one pass (`dev10-1`). Computed from the intent
    # rather than from the act, which is the only difference — the set is identical.
    #
    # Keyed on *being given* the fields rather than on the values differing. Passing the same values
    # a second time still rewrites the file, and a cursor left uncommitted by an earlier run has to
    # stay exempt on the run that writes over it, or the gate is unsatisfiable in one pass for
    # exactly the session that already failed to close once.
    will_write = []
    if sets_cursor:
        will_write.append(config.cursor)
    if config.series:
        will_write.append(config.series)

    reasons = []
    if not intended:
        reasons.append(f"no cursor at {config.cursor} — set one with --next/--ref/--context")
    else:
        for missing in session.Cursor(intended).missing:
            reasons.append(f"cursor field {missing} is empty")

    unclean = session.dirty(project, config.repos, ignoring=will_write)
    if unclean:
        # Committing is checked and pushing is not: a remote is somebody else's availability, and a
        # gate that fails when a network does trains people to pass --force (`dev10-1`).
        reasons.append(f"uncommitted work in {', '.join(unclean)} — the reasoning lives in the "
                       f"commit message")

    if reasons:
        print("plumb: not wrapped —", file=sys.stderr)
        for reason in reasons:
            print(f"  · {reason}", file=sys.stderr)
        # Said explicitly, because the previous order made the opposite true and a reader who
        # learned it there would go looking for what to undo.
        print("\n  nothing was written and no reading was taken — fix the above and run the same "
              "command again.", file=sys.stderr)
        return 1

    try:
        reading, manifest = session.take_reading(config, project)
    except (LaunchFailed, InvalidConfig) as bad:
        print(f"plumb: cannot take a reading — {bad}", file=sys.stderr)
        return EXIT_CANNOT_BOARD

    before = None
    if reading_path.is_file():
        try:
            before = session.Reading.from_json(reading_path.read_text())
        except (OSError, ValueError):
            before = None

    print(f"  board     {reading.total - reading.proven} unproven of {reading.total}")
    if before is None:
        print("            no opening reading — this session's delta cannot be computed.\n"
              "            Differencing against something older would report a number this "
              "run does not support.")
    else:
        delta = session.difference(before, reading)
        sign = f"+{delta.moved}" if delta.moved >= 0 else str(delta.moved)
        print(f"  session   {sign} proven since {before.when}")
        for sid in delta.became:
            print(f"            + {sid}")
        for sid in delta.lost:
            # Reported exactly as readily as a gain: a proof that later fails un-proves its story,
            # and a loop that made the honest end of a hard day expensive is one people route
            # around (`dev07-4-3`, `dev10-2`).
            print(f"            - {sid} is no longer proven")

    # The gate has passed, so from here the writes happen and nothing after them can refuse.
    wrote = []
    if config.series:
        from plumb.core import series

        series.append(project / config.series, manifest)
        wrote.append(config.series)
        moved = session.since(config, project, before.series_seq if before else -1)
        print(f"  history   {len(moved)} transition(s) recorded this session → {config.series}")

    if sets_cursor:
        session.write_cursor(cursor_path, intended)
        cursor = session.read_cursor(cursor_path)
        wrote.append(config.cursor)

    print(f"  cursor    set → {cursor.get('REF')}")
    if wrote:
        # What this command cannot require committed is what it just wrote, so it is named as the
        # last step rather than left for the next close to refuse (`dev10-1`).
        print(f"\nOK — commit {', '.join(wrote)}; the next session runs: plumb session start")
    else:
        print("\nOK — the next session runs: plumb session start")
    return EXIT_OK


def cmd_footprint(args) -> int:
    """What this tool has written, where, and what losing each place would cost (`ado4`).

    Printed rather than only documented, because the reference cannot show an adopter *their* paths:
    every location honours an `XDG_*` variable and two have overrides of their own, so the answer to
    "where is my friction store" is a property of the machine and not of the manual.
    """
    from plumb import footprint
    from plumb.config import Config, InvalidConfig

    try:
        config = Config.find(args.project)
    except InvalidConfig as bad:
        print(f"{bad}", file=sys.stderr)
        return EXIT_CANNOT_BOARD

    sections = (("in this project — your repository already carries these",
                 footprint.in_project(config, Path(args.project))),
                ("outside it — the half a repository does not carry",
                 footprint.user_level()),
                # Last, and named as theirs. A module's state is invisible to whoever is deciding
                # what to protect otherwise, and the core stops being able to answer for it the
                # moment a capability moves out (`mod2-ur2`). Omitted entirely where no module
                # declares anything, because a module with no state is ordinary, not a finding.
                ("added by modules — the core does not own these",
                 footprint.from_modules()))
    for heading, places in (s for s in sections if s[1]):
        print(f"\n{heading}\n")
        for wrote in places:
            # `ado4-ur3` — the list names what is irreplaceable, so somebody can point the backup
            # they already run at it. That is what the archive this tool used to offer was for, and
            # saying it costs a word where taking custody cost three policies core cannot own.
            marks = " ".join(filter(None, [
                "" if wrote.keep else "disposable",
                "IRREPLACEABLE" if wrote.irreplaceable else "",
                "shared" if wrote.shared else "",
                "SECRET" if wrote.secret else ""]))
            print(f"  {wrote.where}" + (f"   [{marks}]" if marks else ""))
            for line in textwrap.wrap(wrote.what, 72):
                print(f"      {line}")
    # Facts, and then nothing. What to do about a secret depends on a threat model, an
    # infrastructure and a set of obligations this tool cannot see, and `ado4-nfr3` is the whole
    # argument: naming what a thing is leaves the judgement where it belongs.
    print("\nIRREPLACEABLE means nothing else holds it: a run that was not recorded cannot be\n"
          "recovered from a later one, and a record that has not reached a holder exists only\n"
          "here. SECRET means the file carries a credential.\n\n"
          "Plumb takes no archive of any of it.\n\n"
          "A passphrase appears nowhere above because it is never written down — losing it loses\n"
          "the account.")
    return EXIT_OK


def _say_left(left) -> None:
    """What the archive refused, and which of it a restore will have to be given by hand."""
    needed = [entry for entry in left if entry.get("needed")]
    other = [entry for entry in left if not entry.get("needed")]
    if needed:
        print("\n  left out, and a restore is incomplete without it:")
        for entry in needed:
            print(f"    {entry['where']}")
            for line in textwrap.wrap(entry["why"], 70):
                print(f"        {line}")
    if other:
        print("\n  left out, and nothing is missing for it:")
        for entry in other:
            first, *rest = textwrap.wrap(f"{entry['where']} — {entry['why']}", 74) or [""]
            print(f"    {first}")
            for line in rest:
                print(f"        {line}")


def cmd_registry_moved(args) -> int:
    """Named where it is performed, rather than failing where it is used (`ado1-nfr2`)."""
    print("plumb: managing a registry is the service operator's, and this is the client.\n\n"
          "  It belongs to whoever runs a holder, where it can actually be performed.\n"
          "  If you are enrolling, you do not mint your own credential — the operator sends one.\n"
          "  If you want an identity nobody has to issue:  plumb account create",
          file=sys.stderr)
    return 1


def cmd_board(args) -> int:
    """Run a board and note what it was asked to do (`ch6-32`).

    A wrapper rather than a line at each `return`: this function has several exits and a note taken
    on only some of them is worse than none — a filing would carry the shape of whichever run
    happened to end the way somebody remembered to record.
    """
    import sys as _sys

    outcome = "unfinished"
    try:
        code = _board(args)
        outcome = f"exit {code}"
        return code
    except SystemExit as leaving:
        outcome = f"exit {leaving.code}"
        raise


def _board(args) -> int:
    """Run the adapter, derive, emit, and note what was asked (`ch6-32`).

    Every number printed is one the gate produced.

    ``--manifest`` skips the runner entirely and reads one that already exists. That is not a
    convenience: the core reads only the manifest (``dev07-3-3``), and a manifest this process did not
    produce is the only way to *demonstrate* that rather than assert it. It is also the seam every
    future adapter arrives through — a Java adapter emits this file and nothing else.
    """
    import contextlib

    from plumb.core.board import Board, natural_key
    from plumb.core.gate import label, NOTHING_OBSERVED, prose, run_conditions
    from plumb.core.manifest import InvalidManifest, Manifest

    namespaces, absent, blind = (), (), ()
    if args.manifest:
        # Repeatable, because several adapters produce several manifests and the board derives
        # from their union (`dev07-3-3`). One file is the same code path with one element.
        from plumb.core.manifest import merge

        try:
            manifest = merge(*[Manifest.read(Path(f)) for f in args.manifest])
        except (OSError, InvalidManifest, ValueError) as bad:
            print(f"--manifest: {bad}", file=sys.stderr)
            return EXIT_CANNOT_BOARD
    else:
        from plumb.config import Config, InvalidConfig
        from plumb.launch import LaunchFailed, produce

        try:
            config = Config.find(args.project)
        except InvalidConfig as bad:
            print(f"{bad}", file=sys.stderr)
            return EXIT_CANNOT_BOARD

        # The runner writes its own progress to stdout, which would corrupt the neutral format
        # on the way to a consumer (`dev07-5-3`). Its chatter goes to stderr; stdout carries only
        # the board.
        say = lambda line: print(line, file=sys.stderr, flush=True)
        try:
            with contextlib.redirect_stdout(sys.stderr):
                # No flag defers to what the project declared, which defaults to off (`dev07-2-2`).
                # The flag can only turn it *on*: a switch that silently overrode a project's own
                # declaration would make the board depend on how it was invoked. Progress goes to
                # stderr — a run measured in minutes that prints nothing looks like a hang.
                manifest, absent, blind = produce(config, pytest_args=args.pytest_args,
                                                  mutation=args.mutation, report=say,
                                                  tests=getattr(args, "tests", False))
                namespaces = config.specs
        except (LaunchFailed, InvalidConfig) as bad:
            print(f"{bad}", file=sys.stderr)
            return EXIT_CANNOT_BOARD
        if args.emit_manifest:
            Manifest.write(manifest, Path(args.emit_manifest))
            print(f"manifest → {args.emit_manifest}", file=sys.stderr)
        args._adapter = config.adapter

    # Scope changes the *view* and never a status (`dev07-5-1`), and it is applied where the verdicts
    # are derived rather than to the document — the run observed what it observed whatever you
    # asked to see, so run-level facts read the whole manifest.
    board = Board.render(manifest, namespaces, absent, blind, scope=args.scope,
                         rendered_by=__version__)
    # Derived once and used twice — printed for a person, returned for a machine — so the two can
    # never disagree about what this run was (`dev07-5-2`, `dev07-5-3`).
    nothing_observed = NOTHING_OBSERVED in run_conditions(manifest, namespaces, absent, blind)
    exit_code = EXIT_NOTHING_OBSERVED if nothing_observed else EXIT_OK

    if args.json:
        print(board.to_json())
        return exit_code

    if nothing_observed:
        # Printed *instead of* the nothing-cited guidance, not beside it: telling someone whose
        # runner discovered no tests to go and write a citation sends them to fix the one thing
        # that is not broken.
        print(_nothing_observed(), file=sys.stderr)
    elif not board.verdicts:
        print(_nothing_cited(getattr(args, "_adapter", "python")), file=sys.stderr)

    if getattr(args, "series", None):
        # Explicit, never a side effect: a board run that quietly grew a store would make `--json`
        # a mutating operation, and a series nobody chose to keep is one nobody knows the shape of.
        from plumb.core.series import append

        changed = append(Path(args.series), manifest)
        # Zero is the ordinary case on a healthy project and is said rather than left silent —
        # "nothing changed" and "the store was not written" are different facts (`dev07-3-3`).
        say(f"series: {len(changed)} transition(s) -> {args.series}")

        if getattr(args, "push", False):
            say(_push_series(Path(args.series), getattr(args, "enrolment", None),
                             getattr(args, "project", None)))

    print("\n══════ BOARD ══════")
    for sid, verdict in sorted(board.verdicts.items(), key=lambda kv: natural_key(kv[0])):
        depth = f"  [{' · '.join(verdict.achieved)}]" if verdict.achieved else ""
        fact = board.manifest.stories[sid].mutation
        # A score, never a word: "survived" reads as a failing grade, and a story whose tests
        # check most of what they run has not failed anything.
        # A score, and beside it the part of the shortfall that is not about the tests at all.
        # `82/185 checked · 61 never reached` and `82/185 checked` say very different things to
        # somebody deciding whether their tests are weak.
        score = f"  {fact.killed}/{fact.total} checked" if fact else ""
        if fact and fact.unreached:
            score += f" · {fact.unreached} never reached"
        if verdict.aspects:
            # One line per aspect and no line pretending to be the subject (`dev07-4-3-ur05`). A
            # decision's aspects close at different times, so a row summarising them would be the
            # one thing every other row on this board is not: a status nobody derived.
            print(f"  {'':28} {sid}{score}")
            words = board.manifest.stories[sid].lexicon
            for aspect, per in verdict.aspects.items():
                rung = f"  [{' · '.join(per.achieved)}]" if per.achieved else ""
                said = label(per, words)
                # The condition is dropped once the word already carries it — `breached` says
                # more than `unproven (evidence.failed)` and repeating the code beside it is
                # noise. Where the lexicon has no word, the code stays and the reader is not
                # left guessing why nothing was said.
                why = "" if said != per.status else (
                    f"  ({per.conditions[0]})" if per.conditions else "")
                print(f"  {said.upper():>28} · {aspect}{rung}{why}")
            continue
        said = label(verdict, board.manifest.stories[sid].lexicon)
        print(f"  {said.upper():28} {sid}{depth}{score}")
        # NOT HERE. A survivor sits in the scope of every story that reached its method, so
        # printing them under each story repeats one work item once per story — measured on a
        # measured at 205 distinct sites printed 2,378 times, in a board of 2,449 lines. That is
        # `dev07-3-2`'s defect one field over, and it was introduced by the same reasoning: *the
        # reader asked for mutation, so give them everything*. They are collected and printed
        # once, below.
    # ONCE EACH, and only when asked. The manifest carries every story's list because a consumer
    # wants them keyed by story; a person wants the work items, and the same site under nine
    # stories is one thing to go and fix.
    if getattr(args, "survivors", False):
        # ONE ROW PER SITE. Keying reach into the identity split a site that one story reached and
        # another did not into two rows — the same line printed twice, once excused and once not.
        # Reach belongs to the site across the stories that scoped it: unreachable only if NONE of
        # them evaluated it, because one story reaching it makes it a real work item.
        distinct: dict[tuple, set] = {}
        anywhere: dict[tuple, bool] = {}
        for sid, story in board.manifest.stories.items():
            for one in (story.mutation.survivors if story.mutation else ()):
                key = (one.file, one.line, one.where, one.operator)
                distinct.setdefault(key, set()).add(sid)
                anywhere[key] = anywhere.get(key, False) or one.reached is not False
        if distinct:
            unreached = sum(1 for key in distinct if not anywhere[key])
            said = f"\n  {len(distinct)} surviving mutant(s) — no citing test noticed these"
            if unreached:
                said += (f"\n  {unreached} of them were never reached: no citing test evaluates "
                         "that line, so no assertion could have caught them")
            print(said)
            for key, stories in sorted(distinct.items()):
                file, line, where, operator = key
                shared = f"  ({len(stories)} stories)" if len(stories) > 1 else ""
                # The distinction the reader acts on. Never reached means no citing test evaluates
                # this line, so no assertion could have caught it; the rest are tests that ran the
                # code and did not check it.
                why = "" if anywhere[key] else "  — never reached"
                print(f"    {file}:{line}  {operator} · {where}{shared}{why}")

    for code, count in sorted(_conditions(board).items()):
        # Nothing is silently skipped: say what could not run, what to do, and what that looks
        # like (`dev07-1-4`, `dev07-5-1`). Each part is labelled so the reader can tell the diagnosis
        # from the instruction rather than parsing one long sentence.
        condition = prose(code)
        print(f"\n  {count} stories  [{code}]")
        if condition:
            print(f"       what · {condition.what}")
            print(f"       next · {condition.next_step}")
            if condition.example:
                print(f"    example · {condition.example}")
    for code in run_conditions(manifest, namespaces, absent):
        # On the board itself, not only on stderr above: what a reader keeps, pastes into a
        # ticket or scrolls back to is the board, and a run-level fact that lives only in the
        # chatter is one the board still fails to state (`dev07-5-2`).
        condition = prose(code)
        print(f"\n  this run  [{code}]")
        print(f"       what · {condition.what}")
        print(f"       next · {condition.next_step}")
        print(f"    example · {condition.example}")
    for unlock in board.as_dict()["unlocks"]:
        # The board markets its own next step from its own output — no selling (`dev07-5-2`).
        print(f"\n  unlock  [{unlock['code']}]")
        print(f"       what · {unlock['what']}")
        print(f"       next · {unlock['next_step']}")
    print("\n  " + " · ".join(f"{k}: {v}" for k, v in sorted(board.summary().items())))
    if board.verdicts:
        # The board states its own scope, every run (`dev07-3-2`). Without it the counts above are the
        # whole message, and a reader takes them for their project rather than for the part of it
        # something happened to cite — the denominator that is not there reading as one that is.
        # Said beside the counts rather than once at adoption, because the misreading is available
        # on every run and the person at risk of it is whoever is looking now.
        print(f"  answering for the {len(board.verdicts)} subject(s) this run's tests cited, and "
              f"nothing else — a subject nothing cites is absent here rather than unproven, and "
              f"what is left to do lives with the project")
    print("═══════════════════\n")
    return exit_code


#: What to do when a board is empty, in the spelling of whichever adapter ran. The launcher may
#: name a language; the core may not (`dev07-3-3`), which is why this lives here and not in the gate.
_FIRST_CITATION = {
    "java": '    @Proves(value = "APP-1", depth = "unit")\n    void yourTest() { ... }',
    "python": '    @pytest.mark.proves("APP-1", depth="unit")\n    def test_your_thing(): ...',
}


def _nothing_cited(adapter: str) -> str:
    """An empty board is the most likely first run, and silence reads as a broken tool rather
    than as "you have not cited anything yet"."""
    return (
        "\nNo stories are cited yet, so there is nothing to derive a board from.\n\n"
        "Cite one from a test — the id is yours, and Plumb keeps no catalog of them:\n\n"
        f"{_FIRST_CITATION.get(adapter, _FIRST_CITATION['python'])}\n\n"
        "Then say where your production code lives, in plumb.toml beside your project:\n\n"
        '    production   = ["src/myapp"]\n'
        '    entry_points = ["myapp.cli:main"]\n\n'
        "Without entry_points a story can still pass; it just cannot be checked for reaching\n"
        "the wired system, and the board says so rather than pretending otherwise.\n"
    )


def _nothing_observed() -> str:
    """The run discovered no tests, which is a broken run and not a young project.

    Deliberately says nothing about citations. The two empty boards are told apart precisely so
    that each can be answered with the thing that is actually wrong, and the older message —
    *"you have not cited anything yet"* — is the wrong answer here in the most expensive way: it
    reads as reassurance, and it sends the reader to edit a test file when the fault is in how the
    suite is being invoked (`dev07-5-2`).
    """
    return (
        "\nNo tests were observed, so there was nothing to derive a board from.\n\n"
        "This is not the same as having no citations yet — the runner found no tests at all,\n"
        "which usually means it was pointed somewhere they are not:\n\n"
        "  · run your own test command first and check it reports a non-zero count\n"
        "  · check the test path or classpath this project declares in plumb.toml\n"
        "  · if you narrowed the run yourself, check the filter still matches something\n\n"
        "An empty board from a run that observed nothing looks exactly like a correct first\n"
        "run, which is why this says so rather than leaving you to notice.\n"
    )


def _conditions(board) -> dict[str, int]:
    counts: dict[str, int] = {}
    for verdict in board.verdicts.values():
        for code in verdict.conditions:
            counts[code] = counts.get(code, 0) + 1
    return counts


def _channel() -> str:
    """Which stream this install came from, if it was resolved through one (``ado1``).

    Read from a marker the installer wrote beside the binary rather than from the artifact, because
    the channel is a property of the install: one build can be named by both channels at once, so
    the version cannot tell an adopter — or a defect report — which stream they are following.
    Silent when there is no marker, which is what a pinned version or a checkout looks like.
    """
    try:
        marker = Path(sys.argv[0]).resolve().parent / ".plumb-install"
        channel = marker.read_text().split()[0]
    except (OSError, IndexError):
        return ""
    return "" if channel == "pinned" else f" ({channel})"


def build_parser() -> argparse.ArgumentParser:
    """``plumb <group> <command>`` — the board and friction capture. The nesting was added
    before it was needed, so that gaining a second group moved no existing command."""
    parser = argparse.ArgumentParser(prog="plumb", description="Plumb — proof that a story is done")
    # `ado1`. The first thing anyone does with an unfamiliar tool is ask what it is, and until
    # this existed the answer was an argument-parsing error. It is also the only way to get the
    # version out of an artifact installed from a rolling `latest` URL, where the user never typed
    # one — which is what makes a defect report actionable and a friction record unambiguous.
    parser.add_argument("--version", action="version", version=f"plumb {__version__}{_channel()}")
    groups = parser.add_subparsers(dest="group", required=True)

    board = groups.add_parser("board", help="derive and emit the board from a test run")
    board.add_argument("--json", action="store_true",
                       help="emit machine-readable JSON instead of the text board")
    board.add_argument("--manifest", metavar="FILE", action="append",
                       help="derive from a manifest file instead of running the tests — how a "
                            "run from another language gets a board")
    board.add_argument("--mutation", action="store_true",
                       help="also check that the tests citing a story would notice its code "
                            "being broken. Slow — minutes on a small project, longer on a real "
                            "one; it prints the cost before starting. Never fails a build")
    board.add_argument("--survivors", action="store_true",
                       help="list the mutants no test noticed, once each, after the board. Off by "
                            "default: a survivor sits in every story that scoped it, so printing "
                            "them under each one repeats the same work item many times — measured "
                            "measured at 205 distinct sites printed 2,378 times, burying the "
                            "verdicts under them")
    board.add_argument("--tests", action="store_true",
                       help="list every test the run observed and what it grounded, instead of "
                            "counting them. On a mature suite the citing tests are a small "
                            "minority, so this is off by default: the board's output should scale "
                            "with the spec, not with the suite")
    board.add_argument("--scope", metavar="NAMESPACE",
                       help="show only stories whose id begins with NAMESPACE, for a repository "
                            "carrying more than one spec. A view, never a gate: every story reads "
                            "exactly what it reads unscoped")
    board.add_argument("--emit-manifest", metavar="FILE",
                       help="write the manifest the runner produced, to inspect or replay")
    board.add_argument("--project", metavar="DIR", default=".",
                       help="the project to read plumb.toml from (default: this directory)")
    board.add_argument("pytest_args", nargs="*",
                       help="passed to the runner, e.g. a path to limit collection. Put `--` "
                            "first to pass the runner its own flags: plumb board -- -k orders")
    board.add_argument(
        "--series", metavar="FILE",
        help="also append what this run changed to a series (`dev07-6-1`); opt-in, never a side effect")
    board.add_argument(
        "--push", action="store_true",
        help="with --series, also send what the service has not been given. A failure to reach it "
             "reports and never fails the board")
    board.add_argument("--enrolment", help=ENROLMENT_HELP)
    board.set_defaults(func=cmd_board)

    init = groups.add_parser("init", help="set a project up to run a board")
    init.add_argument("--project", metavar="DIR", default=".",
                      help="the project to write plumb.toml into (default: this directory)")
    init.set_defaults(func=cmd_init)

    account = groups.add_parser(
        "account", help="an identity nobody has to issue you")
    account.add_argument("--account", help="account file (default: ~/.config/plumb/account.json)")
    acc = account.add_subparsers(dest="command", required=True)
    created = acc.add_parser("create", help="generate an identity; nothing is shown to copy")
    created.add_argument("--endpoint", help="the service this account is at, if you have one")
    opened = acc.add_parser("open", help="open the account at its holder; signed, never credentialled")
    opened.add_argument("--email", required=True,
                        help="the anchor address — what survives losing this machine")
    opened.add_argument("--endpoint", help="override the account file's holder")
    redeem = acc.add_parser("redeem", help="redeem a credential link; the answer comes once")
    redeem.add_argument("token", help="the token from the link")
    redeem.add_argument("--endpoint", help="override the account file's holder")
    acc.add_parser("export", help="print the root, for CI or a copy of your own")
    shown = acc.add_parser(
        "show", help="what this install holds, and whether it can still sign with it")
    for taking in (acc.choices["export"], shown):
        taking.add_argument("--root", dest="passphrase", metavar="HEX",
                            help="the root to use, if it is not this machine's "
                                 "(or set PLUMB_ROOT)")
    account.set_defaults(func=cmd_account)
    prints = groups.add_parser(
        "footprint", help="what Plumb has written, where, and what losing each place would cost")
    prints.add_argument("--project", metavar="DIR", default=".",
                        help="project directory (default: .)")
    prints.set_defaults(func=cmd_footprint)

    # Optional, and nothing else in the tool reads any of it (`dev03`). Offered because of what it
    # does when it is run: opens at the spec and closes by measuring against it.
    sess = groups.add_parser(
        "session", help="open from a cursor and close by measuring the session against the spec")
    sess.add_argument("--project", metavar="DIR", default=".",
                      help="project directory (default: .)")
    loop = sess.add_subparsers(dest="command", required=True)
    loop.add_parser("start", help="what is next, whether the ground is sound, and a reading")
    closing = loop.add_parser(
        "wrap-up", help="the delta since the open, and the gate: committed, and a cursor set")
    closing.add_argument("--next", dest="next_task", metavar="TEXT",
                         help="the single next thing")
    closing.add_argument("--ref", metavar="ID",
                         help="where it is specified — a story or an open unknown")
    closing.add_argument("--context", metavar="TEXT",
                         help="the one line the next session cannot reconstruct by reading")
    sess.set_defaults(func=cmd_session)

    # Kept as a parser rather than removed, so the command that moved says where it went instead of
    # answering with argparse's "invalid choice" (`ado1-nfr2`).
    moved = groups.add_parser("registry", help="moved: operator-side, on the series holder's command")
    moved.add_argument("rest", nargs="*")
    moved.set_defaults(func=cmd_registry_moved)

    manifest = groups.add_parser("manifest", help="work with a manifest a run produced")
    man_sub = manifest.add_subparsers(dest="manifest_command", required=True)
    man_migrate = man_sub.add_parser(
        "migrate", help="bring a manifest written by an older schema forward, in place")
    man_migrate.add_argument("file", help="the manifest to rewrite")
    man_migrate.set_defaults(func=cmd_manifest_migrate)

    modules = groups.add_parser("modules", help="what is mounted, what it adds, and what it reaches")
    modules.set_defaults(func=cmd_modules)

    # Last, and after every core verb exists, because what the core owns is the set a module may
    # not name (`mod2-ur1`) — and that set is only complete here. A mount placed earlier would let
    # whichever module happened to load first take a name the core was about to add.
    from plumb.modules import mount

    found = mount(groups, reserved=set(groups.choices),
                  say=lambda line: print(line, file=sys.stderr))
    # Carried to the command rather than recomputed by it (`mod2-sr3`). It asked `discover` again
    # with an empty reserved set, so the listing could refuse nothing for naming a core verb and
    # printed a module as mounted — verbs, surfaces and writes — while every invocation of the
    # tool refused that same module. The trust decision is made on this list.
    modules.set_defaults(mounted=found)
    return parser


def cmd_modules(args) -> int:
    """``mod4`` — the mounted modules, their verbs, their surfaces and their reach."""
    from plumb.modules import render

    print(render(args.mounted))
    return 0


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
