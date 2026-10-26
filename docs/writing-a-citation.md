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

`ORD-1`, `JIRA-4417`, `REQ-3.2`, a spreadsheet row — Plumb mints no identifiers and keeps no catalogue
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

**It is grounded like any other citation.** The test has to reach the code the way a request would:

| the `informs` test… | grounding | the aspect reads |
|---|---|---|
| goes in through a declared entry point and passes | `grounded` | **holding** (a parameter: **supported**) |
| calls the code directly and passes | `ungrounded` | `UNPROVEN` with `grounding.not-wired` |
| asserts only on a constant or on values it built itself | `untouched` | `UNPROVEN` with `grounding.untouched` |
| ran and failed | — | **breached** (a parameter: **refuted**) |

The decision words cover only *evaluated and holding*, *fired*, *nobody is watching* and *nothing
ran*, so the two middle rows show the plain status and the code beside it. A falsifier "checked" by a
test that never touched the system is not holding — it is unexamined, and the board says so.

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

A decision's aspect that nothing cites reads **silent**, not *unproven*; a parameter's reads
**unvalidated**. (A subject nothing cites at all is absent from the board, like any other.) Name the subject's vocabulary in `plumb.toml` and the board says the word:

    [lexicon]
    "D41" = "decision"

The underlying status and condition code are unchanged, so anything reading the board mechanically
is unaffected. The full
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

That list is the story's **achieved vector**: the depths claimed by its citations that **passed**
and that the run **did not refute**. A `wiring` claim whose test never reached an entry point is
refuted (`depth.unsupported`) and left out; a failing citation is left out. The status is a separate
question — a behavioral story is PROVEN only when a passing citation went in through a declared entry
point, so a story whose tests all call the code directly reads `UNPROVEN [unit]`: unit-only, and
visibly so. "Done" is a shape, not a bit.

---

## Mistakes that pass silently

None of these is named as a mistake. Most leave a board that looks fine; the rest are judged
correctly and only the mistake itself goes unmentioned. If a story you expected is missing, has a
blank or odd bracket, or reads better than you believe, check this list first.

- **A marker with no story id cites nothing.** `@pytest.mark.proves` on its own runs the test and
  puts nothing on the board.
- **A missing depth is accepted in Python.** `@pytest.mark.proves("ORD-1")` cites the story and
  claims no rung, so a test that goes through an entry point makes it `PROVEN` with **no bracket at
  all**. Java will not compile this, because `depth()` has no default.
- **A misspelled depth is not named.** Nothing validates the string. The story is still judged —
  a `depth="wirring"` test that never came in through an entry point still leaves its story
  `UNPROVEN` with `grounding.not-wired`. What goes unsaid is the claim: `wirring` is not one of the
  wired rungs, so it never raises `depth.unsupported`, and it appears in the bracket exactly as
  written — `[wirring]` — whatever the test reached.
- **A typo inside your namespace is invisible.** `specs` in `plumb.toml` catches an id outside every
  namespace (`spec.orphan`), but `ORD-1O5` for `ORD-105` starts with `ORD` and is read as a real,
  different story.
- **A commented-out test cites nothing**, so its story leaves the board — absent, not unproven. A
  **skipped** one stays, as `UNPROVEN` with `evidence.not-observed`.
- **A test with no assertion still proves.** `main("A-1")` with nothing after it goes through the
  entry point and passes, so the story reads `PROVEN [wiring]`. Grounding proves the code ran;
  only mutation asks whether the test checked anything.
- **Fixtures are not watched the way the test body is.** Setup is observed only for what it reads.
  Production code a fixture *runs* — a collaborator it builds, a service it starts — is not seen as
  executed. Build that collaborator in the test body without going through an entry point and the
  story carries `grounding.reached-outside`; build the same one in a fixture and nothing is said,
  even when the test asserts on what it produced.

  **Both are legitimate when the story is about what the entry point does.** Building the
  collaborator is arranging the world the call happens in; the claim is the call through the entry
  point and what it returns, and that is what grounding checks. So `grounding.reached-outside` from
  setup in the test body is a prompt to confirm the assertion is about the entry point's result, not
  a fault — and moving the setup into a fixture is fine for the same reason, not a way around the
  check. What is not fine, in either place, is asserting on something only the setup produced: then
  the claim rests on code no entry point ran, and the story says more than the run showed.

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

**Already cite requirements under another marker name?** Tell Plumb rather than renaming every
citation:

    [python]
    marker = "requirement"

`informs` is read whatever this says. A run that finds no citations under the configured name, and
does find other markers carrying a string, names them and suggests this setting.

---

## See also

- [Getting started](getting-started.md) — configuration to your first proven story
- [Testing depth](testing-depth.md) — what each `depth` value claims
- [What to expect the first time](what-to-expect.md) — the surprises, with reasons
