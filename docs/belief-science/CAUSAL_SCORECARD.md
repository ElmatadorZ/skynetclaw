# Causal Scorecard — does a theory grant belief real causal status?

> A rubric for judging *any theory of belief* on whether it accords belief genuine causal power
> (vs mere predictive/descriptive status). **Scores theories, not systems** (per mission — it
> does not evaluate any implementation). Built from the causal signatures (BELIEF_CAUSAL_SIGNATURES)
> and the interventionist criterion. Tags on the rubric's backing.

## Scoring principle
A theory is scored on **what causal commitments it makes and how it discharges the exclusion
argument** — and, where the theory is empirical, whether its commitments match the interventional
evidence. Each dimension 0–3.

## Dimensions
| Dim | Question | 0 | 1 | 2 | 3 | Backing |
|---|---|---|---|---|---|---|
| **D1 · Interventional commitment** | does the theory predict do(belief) changes behaviour? | denies any | ambiguous | yes, hedged | yes, sharp & invariant | SUPPORTED (Woodward) |
| **D2 · Mediation commitment** | does belief lie *on the path* stimulus→behaviour (screens off)? | no | partial | yes | yes + specifies the mediation structure | SUPPORTED (Pearl) |
| **D3 · Grain / proportionality** | is belief the *difference-maker at its own grain* (not just micro-physics)? | only micro causes | agnostic | belief relevant | belief is the proportional cause | SUPPORTED (Yablo; List & Menzies) |
| **D4 · Exclusion escape** | how does it avoid Kim's exclusion? | doesn't (inert) | token-identity only (worry remains) | realization/identity | difference-making + special-science parity | SUPPORTED (Kim) |
| **D5 · Content efficacy** | does *content* (not just vehicle) do work? | content inert | silent | content as structuring cause | content efficacious + testable | LIKELY (Dretske) |
| **D6 · Empirical adequacy** | does it match belief-manipulation & lesion evidence? | contradicted | strained | consistent | predicts the evidence | SUPPORTED |
| **D7 · Parsimony cost** | does it posit belief-causes beyond need? | large surplus | some | lean | earns every posit by difference-making | SUPPORTED (Occam / van Fraassen) |
| **D8 · Falsifiability** | are its causal claims testable (BELIEF_CAUSAL_TESTS)? | untestable | barely | testable | sharply testable | SUPPORTED |

## The causal-status gate
- **"Grants belief REAL causal status"** requires **D1 ≥ 2 ∧ D2 ≥ 2 ∧ D4 ≥ 2** (interventional
  difference-maker, on the path, with a non-trivial exclusion escape).
- **"Grants belief only PREDICTIVE status"** = high D6/D7 but **D1 ≤ 1** (useful, not causal).
- **"Denies belief"** = D1 = 0 and D4 = 0 (eliminative / epiphenomenal-of-state).

## Output profile (per theory)
```
CAUSAL STATUS : gate(D1,D2,D4 ≥ 2) → {real cause | predictive-only | inert/denied}
STRENGTH      : (D1 intervention, D2 mediation, D3 grain)
METAPHYSICS   : (D4 exclusion escape, D5 content efficacy)
SCIENCE FIT   : (D6 empirical, D7 parsimony, D8 falsifiability)
```

## How to read a low D5 with high D1 (SUPPORTED)
A theory can score high on D1–D4 (belief-**state** is a real cause) yet low/agnostic on D5
(content efficacy). That profile = **"belief causes, but whether its *content* causes is open"** —
the honest current frontier (BELIEF_CAUSAL_SIGNATURES marks D5's clean signature UNKNOWN).

## Rubric self-limit (SUPPORTED)
D4 (exclusion escape) and D5 (content efficacy) are **partly metaphysical** — a theory can be
internally excellent on them while the underlying question stays empirically open. The scorecard
therefore separates **empirically-decidable** dimensions (D1,D2,D3,D6,D8) from **interpretive**
ones (D4,D5), so a theory's causal grade is not inflated by untestable commitments.
