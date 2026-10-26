"""The receiving end of the series API — where an adopter's own run history lands.

Deliberately stdlib-only. It runs on a box already serving production sites, so the smallest
possible thing that can be correct is the right thing: no framework, no dependency tree to keep
patched, no build step. It binds to localhost and expects a reverse proxy in front for TLS.

It is the **second** API (``dev07-6-2-2-1-nfr1``): it touches no manifest, fills no slot, and moves no story's
status. Nothing it accepts can become evidence.

**It authenticates nobody, and that is the design rather than an omission.** This holder is one
an adopter runs for themselves, so there is no second party to be told apart from — no credential,
no account, no grant, no quota per holder. What it protects is a disk, and the only bound it
enforces is the one that keeps the disk from filling (`dev07-6-2`).
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
import re
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from plumb.holder import FileHolder

MAX_BODY_BYTES = 256 * 1024
SAFE_ID = re.compile(r"\A[0-9a-z][0-9a-z-]{0,120}\Z")


from plumb.holder import FileHolder


def specification() -> dict:
    """What this series holder serves, from the holder itself (``dev07-6-2-2-1-ur1``).

    Served rather than documented: a document describes the holder somebody built, and this
    describes the one that is running — which is the one answering requests.
    """
    return {
        "service": "plumb-series",
        "endpoints": {
            "POST /series/{subject}": "append this run's transitions",
            "GET /series/{subject}": "everything held for a subject, discarded ranges included",
            "GET /spec": "this document",
            "GET /health": "liveness",
        },
        # The producer batches against this, so it is published rather than agreed by coincidence
        # (`dev07-6-2-2-1-ur1`, `dev07-6-2`): a client that guesses the cap is one that discovers it by being
        # refused halfway through a backlog.
        "series": {"max_body_bytes": MAX_BODY_BYTES},
        "refusals": {
            "413": "body too large — split the batch",
            "422": "unreadable series; see `error` — terminal",
            "507": "no room to accept more; the backlog is still yours — retryable",
        },
    }


#: What this holder holds **in total** — one bound over the pool rather than a quota per
#: anything, because there is nobody here to meter separately and what is being protected is a
#: disk. A stated bound survives a bad month where a promise kept by breaking it does not.
POOL_BYTES = 2 * 1024 * 1024 * 1024

#: What is left for whatever else lives on this host, below which this holder stops accepting
#: (``dev07-6-2-2-2-ur1``). A service that fills a shared disk has not exceeded a quota, it has taken out
#: everything beside it — and the number that prevents that is the **operator's**, because only they
#: know what else is on the volume. A default that is generous enough to be safe everywhere would
#: refuse on any small host, and one small enough to always work would protect nobody; so this is a
#: floor to be raised with ``--reserve`` on a host that is sharing, and it is read from the disk on
#: every write rather than believed once from configuration.
DISK_HEADROOM_BYTES = 256 * 1024 * 1024

#: A log is compacted once it carries this many records more than the state it replays to. The
#: number is a ratio rather than a size because the base is proportional to a project's test count
#: and the churn is not — so a small project compacts rarely and a large one no more often, which
#: is the property the shared bound wanted and a fixed byte bound would not give.
COMPACT_ABOVE = 2

#: A tombstone is a single short line, so a log bigger than this cannot be one and is answered
#: by its size rather than by reading it. Generous on purpose: the cost of being wrong upward is
#: one wasted read, and of being wrong downward is treating a live log as an empty one.
_TOMBSTONE_CEILING = 4096

#: One lock per subject, because the server is threaded and two runs of one project arriving
#: together would interleave a read-then-append. Held across the append and the compaction that
#: may follow it: compaction rewrites the file, so a concurrent append would land in a log that no
#: longer exists.
_subject_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(subject: str) -> threading.Lock:
    with _locks_guard:
        return _subject_locks.setdefault(subject, threading.Lock())


class SupportHandler(BaseHTTPRequestHandler):
    server_version = "plumb-series"
    sys_version = ""  # do not advertise the Python version to the internet

    store_root: Path

    def do_GET(self):
        if self.path == "/health":
            self._respond(200, {"status": "ok"})
        elif self.path.rstrip("/") == "/spec":
            self._respond(200, specification())
        elif self.path.rstrip("/").startswith("/series/"):
            self._series_get(self.path.rstrip("/").rsplit("/", 1)[-1])
        else:
            self._respond(404, {"error": "no such endpoint"})

    def _retrieved(self, subject: str) -> None:
        """Note that somebody came for this, which is what keeps it (`D38`).

        Retrieval and not transmission, deliberately: it rewards the users for whom the data is
        doing something, which is a better proxy for value than volume sent — and a subject kept
        recent by writing alone would let anything that writes a lot keep itself alive.
        """
        self.holder.mark_retrieved(subject)

    def _series_get(self, subject: str) -> None:
        """Return everything held for a subject — **including what we dropped** (`dev07-6-2`).

        This endpoint is what makes *custodial* true rather than asserted: a store that
        cannot hand it back is holding nothing for anyone. And it is what *kept recent by
        use* measures, so retrieval is not a read-only convenience here, it is the signal.
        """
        if not SAFE_ID.match(subject):
            return self._respond(422, {"error": "subject must be lowercase alphanumeric and "
                                                "hyphens", "refused": "content"})
        store = self._series_store(subject)
        if not store.is_file():
            # Never held and emptied are different answers, and this one says which (`dev07-3-3`).
            return self._respond(404, {"error": "nothing held for this subject",
                                       "subject": subject})
        records = [json.loads(line) for line in store.read_text().splitlines() if line.strip()]
        self._retrieved(subject)
        # Extent travels with the answer (`dev07-6-3`). A holder keeps a history under a bound and
        # discards ranges it once held (`dev07-6-2`), so what it hands back can be *shorter* than what
        # the asker has — and the rule is the same in both directions: no store answers a question
        # about a range it does not hold as though it held it.
        from plumb.core.series import extent, read as read_series

        held = extent(read_series(store))
        self._respond(200, {"subject": subject, "records": records,
                            "discarded": [r for r in records if "discarded_from" in r],
                            "extent": {"role": "authority", "first": held.first,
                                       "last": held.last, "whole": held.whole,
                                       "gaps": [list(g) for g in held.gaps]}})

    def do_POST(self):
        route = self.path.rstrip("/")
        if self.path.rstrip("/").startswith("/series/"):
            return self._series_post(self.path.rstrip("/").rsplit("/", 1)[-1])
        return self._respond(404, {"error": "no such endpoint"})

    def _series_store(self, subject: str) -> Path:
        """The one place a series' path is spelled."""
        return self.store_root / "series" / f"{subject}.jsonl"

    def _series_post(self, subject: str) -> None:
        """Append a run's transitions for a subject.

        Appended verbatim rather than re-derived: the adopter's run did the measuring and this
        holds what it said (`dev07-3-1` — a holder never decides). Sequences are renumbered onto this
        store's own, because a sequence says *where in this store* and two stores counting
        independently would collide the moment anything was compacted.
        """
        if not SAFE_ID.match(subject):
            return self._respond(422, {"error": "subject must be lowercase alphanumeric and "
                                                "hyphens", "refused": "content"})
        body = self._read_body()
        if body is None:
            return self._respond(413, {"error": f"body exceeds {MAX_BODY_BYTES} bytes"})
        if self._room_to_accept() <= 0:
            # Retryable, never terminal: the producer keeps its backlog for the next attempt and the
            # run that made it does not fail (`dev07-6-2`, `dev07-6-2-2-1-sr3`). Refusing to take more is what a
            # shortage costs; discarding what is already held is what it must never cost.
            return self._respond(507, {
                "error": "this holder has no room to accept more; the backlog is still yours",
                "retryable": True})
        try:
            incoming = json.loads(body.decode("utf-8"))
            records = incoming["records"]
            if not isinstance(records, list):
                raise ValueError("records must be a list")
        except (ValueError, KeyError, TypeError, UnicodeDecodeError) as rejected:
            return self._respond(422, {"error": f"unreadable series: {rejected}",
                                       "refused": "content"})

        from plumb.core.series import last_seq

        store = self._series_store(subject)
        store.parent.mkdir(parents=True, exist_ok=True)

        with _lock_for(subject):
            # The tail, not the whole file: appending is the hot path and reading a history to
            # find out where it ends makes every write cost what the history costs.
            seq = last_seq(store)
            with store.open("a", encoding="utf-8") as out:
                for record in records:
                    seq += 1
                    out.write(json.dumps({**record, "seq": seq}, separators=(",", ":")) + "\n")

        self._respond(201, {"status": "held", "subject": subject, "records": len(records),
                            "through": seq})
        # **After the response, not before it.** Compaction is triggered by a write because this
        # service has no scheduler and adding one would be a second operational obligation — the
        # cost we refused when we declined to self-host a tracker. But measured at 2.7 seconds
        # for a large project's log, so an adopter must not wait for our housekeeping: the reply is
        # already flushed, and this thread is theirs to finish in (`dev07-6-2-2-1-nfr4` — the caller
        # is never held for our convenience).
        self._compact(subject)
        self._evict_if_over_pool()

    def _free_bytes(self) -> int:
        import shutil

        try:
            return shutil.disk_usage(self.store_root).free
        except OSError:
            return -1  # unreadable: never refuse on a reading we do not have

    def _room_to_accept(self) -> int:
        """Free bytes beyond the headroom this host owes whatever else runs on it (``dev07-6-2-2-2-ur1``).

        Negative or zero means no room. The response to that is to stop **accepting**, never to
        start discarding: an account past its allowance has spent its own budget and pays in its own
        extent, where a host low on disk is our shortage, and paying for it by destroying histories
        we promised to keep would spend custody itself to keep taking on more of it.

        Written the other way round first — the ceiling eviction ranks against was made disk-aware,
        and on a volume already under the headroom it drove to zero and discarded everything held.
        That is the exact failure this exists to prevent, arriving through the mechanism meant to
        prevent it.
        """
        import shutil

        try:
            return shutil.disk_usage(self.store_root).free - self.server.reserve_bytes
        except OSError:
            return 1  # unreadable disk: do not refuse on a reading we do not have

    def _pool_bytes(self) -> int:
        return self.holder.bytes_held()

    def _evict_if_over_pool(self) -> None:
        """Bring the pool under its bound, dropping whole subjects least-recently-retrieved first.

        **Any write may evict any subject**, which is the whole of why this works. Compaction is
        per-subject and a growing log belongs to somebody who is writing; eviction is pool-level,
        and the subjects that should go are precisely the ones nobody is writing to. So a busy
        adopter's writes pay for evicting quiet ones, and nothing is left waiting on a scheduler
        that does not exist.

        The pool only grows on a write, so a write is the only moment the bound can be crossed —
        which makes this trigger sufficient rather than merely convenient.

        **Whole subjects, because compaction cannot reclaim a base.** It produces a new one of the
        same size, so the only way to free a large adopter's footprint is to drop it entire
        (`D38`).
        """
        held = self.holder
        ceiling = self.server.pool_bytes if self.server.pool_bytes is not None else POOL_BYTES
        total = held.bytes_held()
        if total <= ceiling:
            return

        # The pool is the pool: the bound is over everything held here.
        everything = held.subjects()
        # A subject already reduced to its tombstone is not a candidate: evicting it rewrites one
        # short line with another and frees nothing, and because it frees nothing the loop walks
        # straight on into a subject that still holds data. Observed — a busy adopter's live series
        # dropped in the pass after a quiet one had already been tombstoned. The tombstone's own
        # bytes stay counted, which is honest: `dev07-6-2` requires the record be kept, so it is
        # footprint we have chosen to carry and not space we can pretend to reclaim.
        alive = [s for s in everything if not held.is_tombstone(s)]
        for subject in sorted(alive, key=held.last_retrieved):
            if total <= ceiling:
                return
            total -= held.discard(subject, "evicted — the pool is at its bound")

    def _compact(self, subject: str, always: bool = False) -> None:
        """Compact when the log carries more than it needs to say what is true.

        Conditional, because the work is O(history) and the check is not. Ratio rather than size:
        the base is proportional to a project's test count and the churn is not, so this fires at
        roughly the same *frequency* whatever the project's size — once every seventy-odd runs at
        the 1.3% churn measured — and amortises to nothing.

        **The ratio is the policy and stays here; the two numbers it needs are the holder's**
        (`dev07-6-2`). A backend that answered *should I compact* would be a backend carrying its own
        copy of the threshold, and two copies are how two implementations come to enforce different
        bounds while both believing they enforce this one.
        """
        try:
            records, facts = self.holder.churn(subject)
            above = (self.server.compact_above if self.server.compact_above is not None
                     else COMPACT_ABOVE)
            if not always and records <= above * max(facts, 1):
                return
            self.holder.compact(subject, reason="compacted")
        except Exception as failed:  # noqa: BLE001 — housekeeping never fails a held record
            # The record is already stored and already acknowledged. A store that lost an
            # adopter's run because its own tidying broke would be the worst trade available, so
            # this is reported and never raised (`dev07-5-1`).
            self.log_message("series compaction for %s failed: %s", subject, failed)

    def _read_body(self) -> bytes | None:
        length = int(self.headers.get("Content-Length") or 0)
        return None if length > MAX_BODY_BYTES else self.rfile.read(length)

    def _respond(self, status: int, payload: dict) -> None:
        body = (json.dumps(payload) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        """One line per request, to stderr, for journald. Never the body: a record is a
        contributor's words and its anchors, and a log is not a store. Written directly rather
        than via log_error, which routes back here."""
        import sys as _sys
        print(f"{self.address_string()} {fmt % args}", file=_sys.stderr, flush=True)


def build(store_root: Path | str, host="127.0.0.1", port=8081,
          reserve_bytes: int = DISK_HEADROOM_BYTES,
          pool_bytes: int | None = None,
          compact_above: int | None = None):
    root = Path(store_root)
    handler = type("BoundSeriesHandler", (SupportHandler,), {
        "store_root": root,
        # What holds the histories, asked in questions rather than reached through paths
        # (`dev07-6-2`). The lock table is shared rather than owned, so a discard and an append on
        # one subject exclude each other — two tables keyed the same way would not.
        "holder": FileHolder(root, lock=_lock_for),
    })
    server = ThreadingHTTPServer((host, port), handler)
    server.reserve_bytes = reserve_bytes
    # Left as `None` when it was not given, and read from the module at use. A number captured here
    # would be the same number forever, which is fine for a process and wrong for a test that sets
    # the bound and then exercises it — and a bound a test cannot vary is one nothing exercises.
    server.pool_bytes = pool_bytes
    server.compact_above = compact_above
    # Said at startup rather than discovered on a write: a host that is already under its reserve is
    # one that will refuse the first transmission it is offered, and an operator should learn that
    # from the log line they read when they start it.
    import shutil

    # A custodial store on storage the OS clears is `dev07-6-1`'s *we lost it* arriving by
    # configuration — and it would be silent, because an emptied directory reads exactly like one
    # nothing was ever written to. Named at startup rather than discovered a fortnight later.
    resolved = Path(store_root).resolve()
    if any(str(resolved).startswith(where) for where in ("/tmp", "/var/tmp", "/dev/shm")):
        print(f"plumb: {resolved} is under a directory the system clears without warning. A series "
              f"is custodial and a cleared store reads exactly like one nothing was written to — "
              f"point --store somewhere durable.", flush=True)
    try:
        free = shutil.disk_usage(Path(store_root)).free
        mib = lambda n: f"{n // (1024 * 1024)} MiB"
        pool = pool_bytes if pool_bytes is not None else POOL_BYTES
        print(f"plumb: {mib(free)} free · writes refused under {mib(reserve_bytes)} · "
              f"holding at most {mib(pool)}", flush=True)
        total = shutil.disk_usage(Path(store_root)).total
        if pool >= total:
            print(f"plumb: the pool ({mib(pool)}) is at or above this whole filesystem "
                  f"({mib(total)}) — that is not a bound. Set --pool below what the volume can "
                  f"spare.", flush=True)
        if free <= reserve_bytes:
            print("plumb: at or under the hard reserve — transmissions are refused as retryable "
                  "until there is room. Nothing held is discarded.", flush=True)
    except OSError:
        pass
    return server


def build_parser():
    """The holder's own command surface, built where a check can read it (``dev00-1-1``).

    Serving is the whole of it, and the bare form deployments already invoke. What used to be here
    besides — minting credentials, opening and closing a door — belonged to a holder that
    admitted strangers, and this one admits nobody because it is one an adopter runs for themselves.
    """
    import argparse

    parser = argparse.ArgumentParser(prog="plumb-series-holder", description=__doc__)
    parser.add_argument("--store", help="directory series are written to")
    parser.add_argument("--reserve", type=int, default=DISK_HEADROOM_BYTES // (1024 * 1024),
                        metavar="MIB",
                        help="MiB to leave free for whatever else is on this volume; below it, "
                             "transmissions are refused as retryable and nothing held is discarded")
    parser.add_argument("--pool", type=int, metavar="MIB",
                        help=f"MiB this holder may hold in total "
                             f"(default: {POOL_BYTES // (1024 * 1024)})")
    parser.add_argument("--compact-above", type=int, metavar="RATIO",
                        help="compact a series once it stores this many records per fact it says")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8081)
    return parser


def main(argv=None) -> int:
    global _serving
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.store:
        parser.error("--store is required to serve")
    mib = 1024 * 1024
    server = build(args.store, args.host, args.port,
                   reserve_bytes=args.reserve * mib,
                   pool_bytes=args.pool * mib if args.pool else None,
                   compact_above=args.compact_above)
    _serving = server
    print(f"listening on {args.host}:{args.port}, storing to {args.store}", flush=True)
    try:
        server.serve_forever()
    finally:
        _serving = None
        server.server_close()
    return 0




