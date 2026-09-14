---
kind: explanation
role: [programmer, devops]
summary: What a story takes to add, and what Plumb adds to every run of your suite.
---

# Time per story

**For programmers and DevOps** who will run this suite many times a day, and want to know what
that turns into.

**One line proves it.**

    @pytest.mark.proves("ORD-1", depth="wiring")
    def test_an_order_gets_a_queue():
        assert run("A-1")["queue"] == "standard"

That test is one you were writing anyway. The line above it says which requirement it is about —
Plumb does not ask for a test you did not need. It runs the suite, watches what actually executed,
and derives whether `ORD-1` is proven; there is no status for anyone to type.

That is the whole recurring effort per story. Setting the project up happens once, and
[Getting started](getting-started.md) covers it.

So there is no meaningful sum over your backlog. The number that adds up is the next one — there
are two, and only one of them multiplies.

---

## What every run adds

**Overhead is proportional to how much production code executes under the tracer.** Not to how many
tests you have, not to how many stories cite them. That single rule predicts everything below.

Same 200 tests, three different shapes of work:

| what the tests do | `pytest` | `plumb board` | added |
|---|---|---|---|
| almost nothing | 0.45s | 1.12s | 0.67s |
| wait on I/O (5ms each) | 1.55s | 2.29s | 0.74s |
| run compute inside traced code | 0.47s | 12.74s | **12.27s** |

The middle row is the reassuring one and the bottom row is the warning. **Waiting is free** — the
I/O suite does three times the wall-clock work and pays the same 0.7s, because time spent blocked
is not time spent executing traced lines. **Executing traced production code is not free** — the
third suite runs the same 200 tests and pays eighteen times more, purely because each test drives
several hundred lines of watched code.

Growth with suite size, on trivial tests:

| tests | `pytest` | `plumb board` | added |
|---|---|---|---|
| 10 | 0.31s | 0.39s | 0.08s |
| 50 | 0.34s | 0.57s | 0.23s |
| 200 | 0.47s | 1.10s | 0.64s |
| 800 | 1.03s | 3.17s | 2.13s |

It is **not** a fixed startup cost you amortise away. It grows with the work traced. Assume tracing
is the dominant term and size from the shape of your own suite, not from these totals.

---

## Three levers, in the order worth trying

**Narrow `production`.** This is the setting that decides what gets watched, and it is the biggest
lever you have. On the compute-heavy suite above, narrowing the pattern from a whole package to the
one module that mattered took **12.74s to 4.79s** without changing a test. A pattern wider than the
truth costs you on every run, forever.

**Do not re-run the suite to re-read the board.** Save the run once, render it as often as you
like:

    plumb board --emit-manifest run.json     # the slow part, once
    plumb board --manifest run.json          # 0.13s, and repeatable

Rendering a saved manifest does not run anything — no tests, no `plumb.toml`, no project directory
needed. On that same compute-heavy suite it is **0.13s** against 12.74s. If you are looking at a
board repeatedly, in CI or in review, this is the path.

**Leave mutation off.** It is off by default. It is a far deeper and far slower check and none of
the numbers here include it; [What to expect](what-to-expect.md#what-mutation-costs) covers it
separately.

---

## Where the time actually goes

Not into citations. Two things take real thought, both once:

**Naming your entry points.** The few places a real request enters your system. Getting them wrong
is the usual reason a first board is confusing.

**Deciding what a `depth` honestly is.** Claiming `wiring` for a test that calls a function directly
does not quietly downgrade — it fails the story. The time that costs you is the time you spend
finding out a test proves less than someone assumed, which is the check earning its keep.
[Testing depth](testing-depth.md) explains the rungs.

If a story is expensive, it is nearly always because the *test* is expensive to write, and that is
true with or without Plumb.

---

*Measured with the Python adapter on one machine, best of three runs each, mutation off. Treat the
ratios as the finding and the absolute numbers as illustration — your suite's shape decides the
result.*

---

## See also

- [Getting started](getting-started.md) — configuration to first proven story
- [The command line](command-line.md) — `--manifest`, `--emit-manifest` and how they interact
- [What to expect the first time](what-to-expect.md) — the surprises, with reasons
