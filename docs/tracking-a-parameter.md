---
kind: how-to
role: [engineer, programmer]
summary: Give a tuned value a model and a measurement, so whether the number still earns its place is derived rather than assumed.
---

# Tracking a parameter

**For anyone carrying constants nobody has validated.**

A parameter **is a decision with a model and a measurement**. Everything about recording one — the
condition, `informs`, aspects, what the board will not do — is on
[Recording a decision](recording-a-decision.md), and none of it is repeated here. Set it up there
first. This page is only what differs.

A threshold, a window, a limit — `retry_after: 100`, a 20-day lookback. Where you can state a model
connecting the value to something measurable, and you have the measurement, it derives exactly as
a decision does and reads differently:

    [lexicon]
    retry_after = "parameter"

    [reduce]
    retry_after = "worst"

    [aspects]
    retry_after = ["measured", "beats-baseline", "holds-under-load"]

| word | what happened |
|---|---|
| **supported** | the measurement backs the value |
| **unvalidated** | nothing cites this aspect — the ordinary case for most constants |
| **refuted** | it was tested and lost |
| **unmeasured** | cited, and no measurement ran — every citing test was skipped |

As with a decision, a parameter nothing cites at all is absent from the board; **unvalidated**
appears on a declared aspect that nothing cites yet. Aspect names are yours. The core never reads them, so name them after what your evidence actually
distinguishes.

## Is it a parameter, or just a number?

**One question decides it: is there a model — something that would validate this number?**

Not whether you have measured it yet. The model is the half you can write down today, and writing
it down is what forces you to say what would confirm the value. The measurement is the half that
arrives later, and it only says how far along the parameter is: **unvalidated** before anything
tests it, **unmeasured** once something cites it and no measurement has run, **supported** or
**refuted** after. Gating on the measurement would send a value you fully intend to tune off to be
recorded as a decision, where the vocabulary does not fit a number and the intent is lost.

![Is it a parameter, or just a number?](parameter-or-number.svg)
