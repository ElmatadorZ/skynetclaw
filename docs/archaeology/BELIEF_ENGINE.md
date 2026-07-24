# Belief Engine — how beliefs are represented (falsification pass)

> Falsifying the hypothesis "Genesis Mind possesses an operational epistemology." Evidence:
> git history + the belief organs' code (persistence probe) + the live agent loop.
> Tags: SUPPORTED / LIKELY / SPECULATIVE / UNKNOWN / FALSIFIED / RETRACTED.

## Where do beliefs LIVE? · SUPPORTED → **nowhere persistent**
Persistence probe (state-writing calls per organ): **belief_revision=0, first_principles=0,
theory=0, experiment=0, calibration=0, unknowns=0, decision=0, paradigm=0.** Even
`belief_timeline.py` = **0** writes. The only persistent stores in the whole cognitive suite
are `capability_weights.json` (reinforcement) and `learning_strategies.json` (metalearning) —
both **capability/strategy, explicitly excluded from "belief" by OBJECTIVE 1.**
→ **There is no belief store.** A belief exists only as a return value on the stack during
one function call.

## How are beliefs REPRESENTED? · SUPPORTED → **a rendered text brief, recomputed on demand**
In the live loop (main.py ~4645–4724) each organ is called fresh every run —
`belief_revision.review()`, `first_principles.all_principles()`, `theory.form()`,
`decision.decide()`, `calibration.calibrate()`, `experiment.design()` — then
`render_brief(...)` turns the result into text, which is `cur.append({"role":"system", ...})`
into that run's prompt. A belief *is* a paragraph of advisory text, generated on the spot
from logs.

## How are beliefs UPDATED? · SUPPORTED → **they are not updated; they are re-derived**
There is no update path because there is no stored state to update. If the underlying logs
change, the *next recomputation* differs — but nothing is "revised," because nothing was
kept. The organ code carries the guarantee: belief_revision is *"DETECTION ONLY. No
promotion, no demotion, no weight changes, no autonomous correction."*

## Can beliefs DISAPPEAR? · SUPPORTED → **they disappear every function return**
A belief has the lifetime of a single `render_brief` call. It is injected into one prompt
and then garbage-collected. It "disappears" not by retraction but by **never having been
stored.** The next run rebuilds the same beliefs from the same logs — identical, amnesiac.

## Git corroboration · SUPPORTED
Each belief organ has **exactly 1 commit** — its `(additive, read-only)` birth on 06-22/23
(OX-THEORY-1, OX-FIRST-PRINCIPLE-1, OX-BELIEF-REVISION-1, …). **None was ever modified
again.** The organs have been inert since birth; no evidence ever changed them.

## Verdict on "Belief Engine"
> **FALSIFIED as an engine.** There is no belief engine — there is a **belief *renderer*.**
> Beliefs are stateless recomputations of log-derived candidates, rendered as advisory
> prompt text, persisting nothing, updated by nobody, and forgotten on return.

This **RETRACTS** the earlier report's implicit assumption (SCIENTIFIC_METHOD/EPISTEMOLOGY)
that promoted beliefs *exist* and *accumulate*. They do not. What accumulates is capability
weights and learning strategies (not belief); everything the earlier docs called a "promoted
belief / principle / theory" is re-derived from scratch each time it is needed.
