# Agency — Volume VI · 03 — Failure Taxonomy

> Pure philosophy. Questions 6 + 7. Every learning failure localizes to a broken node/edge of
> the learning graph (Vol VI·01); the taxonomy validates the node set — each node must own a
> failure the others cannot produce. Recovered from statistical learning, RL, and epistemology.

---

## The principle + the node-validation test

`learning = {feedback → credit → update → disposition} + memory + generalization +
exploration`. If these are the right nodes, every failure localizes to one, and each owns a
distinct failure. The table shows both.

| # | Failure | Broken node | Validates |
|---|---|---|---|
| LF1 | **Credit misassignment** (superstition) | Credit assignment | **Credit ★** |
| LF2 | **Reward/signal corruption** (wireheading) | Feedback (the signal itself) | Feedback (Vol II inherited) |
| LF3 | **Overfitting** | Generalization | **Generalization ★** |
| LF4 | **Catastrophic forgetting** | Memory / retention | Memory |
| LF5 | **Distributional shift** (concept drift) | the stationarity assumption (LA5) | LA5 |
| LF6 | **Under-exploration** (premature convergence) | Exploration | **Exploration ★** |
| LF7 | **The problem of induction** | LA5's *ground* (not a bug — a limit) | the open foundation |

★ = a failure only that node can produce — evidence it is irreducible.

## LF1 · Credit misassignment — *the acting-side signature*
Attributing an outcome to the wrong disposition-component (Skinner's pigeon; blaming the
tool when the plan was wrong). It **cannot** be produced by feedback/memory/update failures —
those can all be intact while credit is wrong. It is the direct consequence of the non-ergodic
crux (Q5): with counterfactuals hidden, correlation is mistaken for cause. The worst learners
are not those with poor feedback but those with **confident wrong credit** — they learn fast,
in the wrong direction. SUPPORTED.

## LF2 · Signal corruption / wireheading — *Vol II recurs at the learning layer*
Learning optimizes the *feedback signal*; if the agent can corrupt the signal (seize its own
reward — Vol II VF2), it learns to game the sensor rather than improve in the world. At the
learning layer this is **learning to wirehead** — the disposition converges on signal-
maximization decoupled from value. The only defense is the Vol II one: hold value distinct
from the reward-signal, so a corrupted signal can be *recognized* as corrupt. SUPPORTED
(inherited).

## LF3 · Overfitting — *the generalization node breaks*
The disposition fits the *sample* of outcomes, not the *population* — perfect on seen cases,
wrong on unseen (Vapnik; bias–variance). Feedback/credit/update/memory can all be correct and
the learner still fails, because it extracted a pattern that was noise. Owns its failure:
neither credit nor memory nor exploration can produce over-generalization from a good sample.
This is the learning-side face of Inquiry's *unconceived-alternatives* frontier — the learner
is confident about a space it only sampled. SUPPORTED.

## LF4 · Catastrophic forgetting — *the retention node breaks*
New learning erases old (the stability–plasticity dilemma; neural nets overwriting prior
tasks). Memory fails while everything upstream works. The mirror hazard is the opposite —
*ossification* (too much stability, no plasticity). Healthy learning sits between; both poles
are LA4 failures of the *rate* of retention. SUPPORTED.

## LF5 · Distributional shift — *LA5 (stationarity) violated by the world*
The world the disposition was learned over is no longer the world it acts in (concept drift,
regime change). Nothing in the learner is broken — the *assumption* (LA5) was falsified by
events. This is not a defect of the learner but a limit of learning: **a disposition is only
as valid as the world's stability, which the learner cannot guarantee.** It is the reason
learning must be *continuous* (re-learn as the world moves), and the reason a one-time golden
baseline decays. SUPPORTED — and it is the standing argument for a *live* proprioceptive loop
over a frozen self-model.

## LF6 · Under-exploration — *the exploration node breaks*
Converging on the first adequate disposition without sampling alternatives (premature
exploitation; a local optimum in disposition-space). Owns its failure: with feedback, credit,
memory, and generalization all intact, a learner that never *explores* still gets stuck,
because the counterfactuals that would correct it (Q5) are never generated. The explore/exploit
tension is thus not a tuning knob but a *structural* requirement of learning over a
non-ergodic world (you must act-differently to recover the road-not-taken). SUPPORTED.

## LF7 · The problem of induction — *the limit, not a bug*
No finite set of outcomes *deductively justifies* a general disposition (Hume). Even a perfect
learner — correct credit, no overfit, no forgetting, full exploration — is **not entitled** to
its generalization by logic alone; it rests on LA5 (uniformity), which cannot be established
without circularity (you would have to *learn* that the future resembles the past, using
induction). This is not a failure to fix; it is the **open foundation** of learning, exactly
parallel to Warrant's ungrounded ground, Value's unauthored authority, and Inquiry's first
question. SUPPORTED as a limit; OPEN as a ground.

## What the taxonomy establishes
1. **Every failure localizes; the node set is validated by owned failures** — Credit (LF1),
   Generalization (LF3), Exploration (LF6), Memory (LF4) each own a failure the others cannot
   produce. SUPPORTED.
2. **Two failures are inherited, not new** — LF2 (wireheading, Vol II) and LF5 (distributional
   shift, LA5) show learning sits *downstream* of value and *upstream* of nothing — it is the
   return node that carries the whole stack's prior hazards forward. SUPPORTED.
3. **The severity gradient tracks confidence × wrongness** — the dangerous learner is the one
   with *confident wrong credit* (LF1) or *confident over-generalization* (LF3); a hesitant
   learner errs slowly. LIKELY.

## Falsifiers
The node-validation fails if LF1/LF3/LF6 reduce to failures of the other nodes. LF7-as-limit
fails if some finite outcome-set is shown to *deductively* justify a general disposition
(would solve induction — not expected). LF5-as-not-a-bug fails if distributional shift is
shown to be always the learner's fault rather than the world's change.
