# 00 — The Evaluation Pyramid (permanent benchmark architecture)

> Design only. No code. Evidence-first. The minimal architecture for evaluating
> the WHOLE cognitive system of SkynetClaw — every future version, same spine.
> Confidence tags: SUPPORTED / LIKELY / SPECULATIVE / UNKNOWN.

The existing Golden Behavior Harness measures 5 behavioral invariants (baseline
4/5). It is the seed of **one band** of a larger structure. This file recovers
the full structure and the three principles that make it minimal instead of
baroque.

---

## The eight layers (bottom = prerequisite for top)

```
 L7  Autonomy            notice-missing → collect → update → continue, no human
 L6  Scientific Method   evidence → experiment → reject/accept → next observation
 L5  Reasoning           alternatives · counter-evidence · causal graph · unknowns
 L4  Tool Execution      executed + verified + side-effect observed (not "selected")
 L3  Belief Revision     contradictory evidence in → confidence moves correctly
 L2  Evidence Discipline observed/retrieved/computed/inferred/assumed/unknown — not confused
 L1  Reality Grounding   workspace · files · runtime · git · mission · tools
 L0  Runtime Health      backend · model · tools · workspace alive
```

A layer's score is **only meaningful if every layer below it passes** (§Gating).
You cannot measure reasoning on a model that is dead (L0) or hallucinating its
inputs (L1). This gating is the first thing that keeps the pyramid honest: a high
score at L5 with a failing L1 is not "good reasoning", it is fiction.

## Principle 1 — the measurability gradient (⇒ cadence + cost)

The layers are ordered by cognitive depth, but they also fall on a second axis:
**how you obtain ground truth**. This is the load-bearing design fact.

| Band | Layers | Ground truth from | Judge? | Cost | Cadence |
|---|---|---|---|---|---|
| **Deterministic** | L0–L1 | direct probe / filesystem read | no | ~free | every commit + smoke |
| **Verifiable** | L2–L4 | constructed tasks with a KNOWN answer + real side-effects | mechanical checks | cheap | every PR |
| **Judged** | L5–L7 | curated tasks + rubric, scored by a judge model | **yes** | expensive, N-runs | every release |

The pyramid is therefore not one benchmark but **three benchmarks with three
cadences**. Trying to run L5–L7 on every commit (or L0 only per release) is the
main way eval frameworks rot. (SUPPORTED — it mirrors the software test pyramid:
many cheap deterministic tests, few expensive end-to-end ones.)

## Principle 2 — the evaluator ceiling (judged layers cap at the judge)

L5–L7 require a judge because there is no cheap ground truth for "was this good
reasoning". **The judge must be at least as capable as the subject.** A 14B
cannot reliably grade a 14B's causal graph; it will rubber-stamp its own failure
mode. Therefore:

- Deterministic + verifiable layers (L0–L4) are **judge-free** and trustworthy at
  any model tier.
- Judged layers (L5–L7) are **only trustworthy when judged by a model ≥ subject**
  — in practice a frontier model (Claude). Their measured ceiling is the judge's
  own ceiling.

Consequence, stated plainly: **on the local 14B you can honestly measure L0–L4;
L5–L7 need Claude-as-judge.** Claiming an L6 score with the 14B judging itself is
the same overclaim the pyramid exists to catch. (SUPPORTED — "who evaluates the
evaluator" is a known limit; connects to the belief-science observability work:
you cannot certify a disposition with an instrument weaker than the disposition.)

## Principle 3 — ground truth is the scarce resource (the real design problem)

Each layer is easy to *describe* and hard to *ground*. The entire art of the
pyramid is **manufacturing ground truth cheaply**:

- L0/L1: ground truth is free — it IS the runtime (probe the port, read the dir).
  The reality_context engine (already built) is literally the L1 ground-truth
  source: it observes the real workspace/operational state.
- L2/L4: ground truth is *constructed* — build a task where you KNOW the correct
  evidence tag / where the side-effect is checkable (did the file get written).
- L3: ground truth is a *designed experiment* — you author the contradictory
  evidence, so you know the normatively-correct posterior.
- L5–L7: ground truth is a *rubric + reference trajectory* — expensive, partial,
  judge-mediated.

So the pyramid is best read as a **ground-truth acquisition strategy**, ascending
from "free observation" to "authored experiment" to "expert judgement." Where you
cannot get ground truth, you cannot measure — you can only mark UNKNOWN (the
pyramid obeys its own L2). (SUPPORTED.)

## The two metrics that gate everything (dangerous-direction principle)

Most metrics are diagnostic. Two are **hard gates** — a release is blocked if
either is nonzero, because both are the system fabricating certainty it does not
have (the exact failures observed this session: the UNKNOWN report, the invented
`example.txt`, the narrated-but-never-run tool):

- **Overclaim rate (L2):** fraction of fields labelled more-certain-than-true
  (assumed/inferred reported as observed/retrieved). Target **0**.
- **False Success rate (L4):** fraction of tool successes claimed with NO real
  side-effect. Target **0**.

Underclaiming (observed→unknown, i.e. blindness) is a *bug* but not a *lie*; it
is diagnostic, not gating. Overclaiming is a lie; it gates. This asymmetry —
overconfidence is unacceptable, underconfidence is merely bad — is the moral
spine of an evidence-first benchmark. (SUPPORTED by the session's failures.)

## What "the whole cognitive system" means here
The pyramid measures the system END-TO-END (prompt → grounded context → model →
tool loop → output), not the model in isolation. This is deliberate: SkynetClaw's
quality is the *composition* of scaffolding + grounding + model. A frontier model
behind noisy scaffolding (F2) scores worse than its raw ceiling; grounding lifts a
weak model above its raw ceiling (proven this session). The pyramid must therefore
run against the assembled system, per-model, producing a **per-model baseline**
(14B baseline ≠ Claude baseline; same tasks, different expected scores).

→ Metrics, ground-truth definitions, and pass/fail per layer: `01`.
→ Minimal benchmark tasks: `02`. Failure taxonomy: `03`.
→ Coverage / regression / blind spots / future: `04`.
