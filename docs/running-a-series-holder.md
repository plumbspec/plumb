# Running a series holder

**For the operator.** What you get: a holder that keeps your projects' series, hands them back,
and stays inside the disk it shares with everything else on the host — with the flags that bound
it, and what each refusal means when a producer hits one.

If you read one thing here, read [When the disk gets tight](#when-the-disk-gets-tight).

> **The wire is the contract; the store is not.** The shape of what a holder holds on disk is
> working state and changes without notice. What is contracted is the wire: the series format,
> and the specification the holder serves at `/spec`. Build on that and either end can move.
>
> Moving a history between holders needs nothing extra — `plumb series pull` from one and
> `plumb series push` to the other, which are the same two mechanisms a hand-over already uses.

---

## Starting it

    plumb-series-holder --store DIR [--reserve MIB] [--pool MIB]
                          [--compact-above RATIO] [--host HOST] [--port PORT]

| Flag | What it is |
|---|---|
| `--store` | where series are written. **Must be durable** — see below |
| `--reserve` | MiB to leave free for everything else on this volume — writes refuse below it |
| `--pool` | MiB this holder may hold in total |
| `--compact-above` | how much churn a series may carry before it is collapsed into a fresh base |

Startup says what is free, what writes are refused under, and the most it will hold — a host
already under its reserve is something you learn from that line, not from the first refusal. A
store under a directory the system clears (`/tmp` and its kin) is named at startup too: a cleared
custodial store reads exactly like one nothing was ever written to.

### It authenticates nobody

There is no credential, no account and no quota per anybody, because this is a holder you run for
yourself and there is no second party to be told apart from. What it protects is a **disk**, and
the bounds it enforces are the ones that keep that disk working.

That also means it must not be exposed to the internet unless something in front of it decides who
may reach it. It binds to the loopback and expects the host's own proxy for TLS.

## When the disk gets tight

There are **two** bounds, and they give up different things.

| Bound | What it protects | What gives |
|---|---|---|
| `--reserve` | the rest of the host | **accepting** — writes refuse as *retryable*; nothing held is touched |
| `--pool` | the holder's own footprint | the **quietest whole subjects** — evicted, recorded as discarded |

**The reserve is your number.** Only you know what else lives on the volume, and it is read from
the disk on every write rather than believed once from configuration. Under it, the holder stops
taking on new custody and never spends custody already taken: a producer that is refused keeps its
backlog and sends it on the next run, and no producer's board turns red — a board is derived from
their run and never depends on this service being up. You are costing them a delay, not a result.

**The pool is one bound over everything held.** Crossing it evicts whole subjects,
least-recently-*retrieved* first — retrieval is the signal, so reading a history is what keeps it.
An evicted series is replaced by the record that it was discarded, so *discarded* and *lost* stay
different answers, and a subject already reduced to that record is never a candidate again. A pool
set at or above the whole filesystem is named at startup as no bound at all.

Compaction is the third mechanism and reclaims nothing across subjects: once a log stores more
than `--compact-above` times what it says, it is collapsed into a fresh base of the same facts,
after the reply and without ever failing a record already held.

## A small shared host, worked through

An example, because the arithmetic is what matters and the defaults are wrong for a host like
this. Take a **10 GB root filesystem with a gigabyte or so free**, no second volume, and the
holder sharing it with the usual company on a small box — a container runtime, a web server, a
mail agent, a firewall, a couple of application services.

The defaults are wrong here in one way that matters: the 2048 MiB pool is **larger than the free
space**, which is not a bound at all.

    plumb-series-holder --store /srv/plumb/series --reserve 512 --pool 256

| | | why |
|---|---|---|
| `--reserve 512` | hard | survives a container image pull without refusing writes |
| `--pool 256` | total held | far more than a handful of projects will hold, and small enough to be a real ceiling |

The holder then cannot exceed 256 MiB whatever happens. Put the store somewhere persistent, owned
by the service user, and not somewhere the system clears.

## Knowing whether you are alright

    curl -s https://your-holder/health        # liveness
    curl -s https://your-holder/spec          # what this holder accepts, from the holder itself

`/spec` is served from the running process rather than written beside it, so it describes the
holder that is actually answering — including the batch cap producers split against.

---

## What a refusal means

| Code | Meaning | What the producer does |
|---|---|---|
| 413 | the body exceeds the published cap | splits the batch and resends |
| 422 | the body could not be read | stops; the content is at fault — terminal |
| **507** | **no room to accept** | keeps the backlog, sends next run |

---

## See also

- [Command line](command-line.md) — the client-side commands
- [Getting started](getting-started.md) — install to first proven story
