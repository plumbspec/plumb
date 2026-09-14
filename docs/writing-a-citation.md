---
kind: tutorial
role: [programmer, qa]
summary: The one thing you write by hand — what goes in it, where it goes, and what it lets you say.
---

# Writing a citation

**For programmers and QA** writing their first few citations.

The pytest marker and the Java annotation are the same thing, and Plumb calls it a **citation**. It
is the only thing a human writes. Everything else on the board is derived from a run.

    @pytest.mark.proves("ORD-1", depth="wiring")
    def test_an_order_gets_a_queue():
        assert run("A-1")["queue"] == "standard"

    @Test
    @Proves(value = "ORD-1", depth = "wiring")
    void anOrderGetsAQueue() {
        assertEquals("standard", api.handle("A-1").queue());
    }

Three parts, one of them optional. This page is what each is for, and what you can say by combining
them.

---

## It goes on the test, never on the code

This is the rule the whole design rests on, so it is worth stating plainly: **the thing being judged
does not get to claim it passed.**

A citation on a production class would let the code assert its own doneness — which is precisely the
fake Plumb exists to catch. The test is a different artifact, written to a different purpose, and
its execution is the evidence. So the citation lives there.

If you find yourself wanting to annotate the implementation, what you actually want is a test that
drives it.

---

## The story id is yours

    @pytest.mark.proves("JIRA-4417", depth="wiring")

`ORD-1`, `JIRA-4417`, `dev07-1-3`, a spreadsheet row — Plumb mints no identifiers and keeps no catalogue
of them. The id is opaque to the tool and stays whatever your organisation already calls that
requirement.

This is deliberate: the moment Plumb owned the ids, you would have two lists to reconcile.

---

## The depth is a claim, not a label

    @pytest.mark.proves("ORD-1", depth="wiring")

`depth` says how far this test reached, and the run either supports it or refutes it. Claiming
`wiring` for a test that called a function directly does not quietly downgrade — it fails the story.

[Testing depth](testing-depth.md) is the full treatment of what each value means and which to pick.
For a first citation, claim what you honestly think the test does and let the board correct you.

---

## `ref` carries your tracker's key

    @pytest.mark.proves("ORD-1", depth="wiring", ref="JIRA-4417")

Optional. It is passed through to the manifest untouched — Plumb never parses it and never assigns
meaning to it. It exists so a system reading the manifest keeps its own identifiers instead of
adopting Plumb's.

Use it when the story id and your tracker's key are different things. Skip it when they are the
same.

---

## `informs`, for a subject that is never done

Some of what a project commits to is not a requirement that can be finished. A **decision** is a
claim about the future — *we will keep the pool under one bound* — and a **parameter** is a
decision with a number and a way to measure it. Neither can be *proven*. Evidence about them keeps
arriving, and the honest thing a test can do is **inform** them:

    @pytest.mark.informs("D41", about="falsifier")
    def test_the_queue_still_drains_within_the_window():
        assert drain_time() <= WINDOW

    @Test
    @Informs(value = "D41", about = "falsifier")
    void noThirdContributorWhileStoresAreKeyedBySubject() { ... }

A separate tag rather than an argument to `proves`, so a reader scanning a test file learns the
thing they act on from the tag alone: *that is not my code's test.* Reusing `proves` would carry the
doneness reading into the one place it must not go.

**It takes no depth.** Depth is a claim the run can refute — the gate checks a claimed rung against
what actually executed — and there is no analogue for a decision, so a depth here would be a number
nothing could contradict. The board shows an `informs` citation no rung, rather than inventing one.

### `about` names which part you tested

A decision has parts that fail independently:

| Aspect | What a test of it asserts |
|---|---|
| `levers` | the things the decision was made on were measured, and still read the way they did |
| `outcome` | the thing the decision was supposed to achieve actually happened |
| `falsifier` | the condition that would make the decision wrong has **not** fired |

Those are separate questions, and one can close while another has never been looked at. Without
`about`, every citation lands in one undifferentiated list and the board can print only one word for
all three — so a decision whose *outcome* passes reads fully settled while its *falsifier* has never
been evaluated. Declare the parts in `plumb.toml` under `[aspects]`; name
one in each citation.

Omit `about` and the citation is about the only aspect there is, which is what a plain story has.

### The words change, the codes do not

A decision that has nothing citing it reads **silent**, not *unproven*; a parameter reads
**unvalidated**. Set `lexicon` in your feed and the board says the word; the underlying status and
condition code are unchanged, so anything reading the board mechanically is unaffected. The full
table is under [the codes it can emit](command-line.md#the-codes-it-can-emit).

**A breach informs and never fails a build.** A decision whose falsifier has fired is news, not a
broken test — it means a choice needs revisiting, which is a conversation and not a red pipeline.

---

## One test can prove several stories

Because a citation is per **(test, story)** pair, not per test. Two ways to write it, and they mean
different things:

    @pytest.mark.proves("ORD-1", "ORD-2", depth="wiring")     # both, at the same depth

    @pytest.mark.proves("ORD-1", depth="wiring")              # each at its own depth
    @pytest.mark.proves("ORD-2", depth="unit")

In Java the annotation is repeatable, which gives you the second form:

    @Test
    @Proves(value = "ORD-1", depth = "wiring")
    @Proves(value = "ORD-2", depth = "unit")
    void oneTestTwoStories() { ... }

Do not stretch one test to cover more stories than it honestly exercises. Citing is cheap; a
citation that overstates is the thing the gate is built to find.

---

## Several tests can prove one story, at different depths

This is the one worth understanding, because it is where the model stops being a checkbox.

    @pytest.mark.proves("SHARED", depth="wiring")
    def test_the_wired_path(): ...

    @pytest.mark.proves("SHARED", depth="unit")
    def test_the_logic(): ...

The board shows both rungs:

    PROVEN   SHARED  [unit · wiring]

That list is the story's **achieved vector** — the rungs it is actually proven at, derived from what
ran. A story proven only at `unit` reads as *only* that deep, and stays visibly shallower than one
that also reached the wired system. "Done" is a shape, not a bit.

---

## Two ways a citation quietly does nothing

Both are worth knowing because neither announces itself.

**A marker with no story id is skipped.** In Python this is silent — the test runs, nothing is
cited, and no story appears on the board:

    @pytest.mark.proves                  # cites nothing at all
    def test_something(): ...

**A missing depth is accepted in Python.** The story is cited and rendered with no depth against it.
Java will not compile this, because `depth()` has no default — so the two languages disagree today,
and Python is the lenient one:

    @pytest.mark.proves("ORD-1")         # cited, but claims nothing about how deep

Neither is an error you will be told about. If a story you expected is missing from the board, or
appears with a blank depth, look at the citation first.

---

## Register the marker to silence pytest

If you also run `pytest` directly — and you will — every citation raises a warning, because `proves`
is not a marker pytest knows:

    PytestUnknownMarkWarning: Unknown pytest.mark.proves - is this a typo?

One entry in `pytest.ini` (or the equivalent in `pyproject.toml`) ends it, and changes nothing about
how Plumb reads your suite:

    [pytest]
    markers =
        proves(story_id, depth, ref): the stories this test proves
        informs(id, about, ref): the decisions or parameters this test reports on

Java needs no equivalent — the annotation is a real type, so your compiler already checks it.

Plumb registers both markers itself while it is driving the run, so this matters only for the
`pytest` you run directly — and it matters more than a warning suggests, because a project with
`--strict-markers` on turns that warning into a failure.

---

## See also

- [Getting started](getting-started.md) — configuration to your first proven story
- [Testing depth](testing-depth.md) — what each `depth` value claims
- [What to expect the first time](what-to-expect.md) — the surprises, with reasons
