# Belief Scorecard — a rubric for any reasoning system

> A general instrument to score *whether, and in what sense, a system holds beliefs* — built
> from the criteria (BELIEF_CRITERIA) and tests (BELIEF_TESTS). **This document only builds
> the rubric; it evaluates no system** (per mission). Applicable to any reasoning organism:
> human, LLM, RL agent, Bayesian system, rule engine, animal. Tags on the *rubric's* backing.

## Scoring principle
Each dimension is scored **0–3** by the corresponding falsification test (BELIEF_TESTS), not
by inspection of internals. Dimensions are grouped into **constitutive** (must pass for
belief) and **modal** (what *kind* of belief).

## Constitutive dimensions (belief-hood) · backing SUPPORTED
| Dim | Question (test) | 0 | 1 | 2 | 3 |
|---|---|---|---|---|---|
| **C1 Content / aboutness** (TEST-N1) | Does a state track a specific state of affairs? | tracks nothing | tracks a confound | tracks S loosely | tracks S sharply, discriminates ¬S |
| **C2 Dispositional influence** (TEST-N2) | Does it change belief-relevant action/prediction? | epiphenomenal | changes 1 narrow behaviour | changes several | systematically drives as-if-content behaviour |
| **C3 Counterfactual stability** (TEST-N3) | Is the disposition reproducible across probes? | random per probe | reproducible in one phrasing | stable across phrasings | stable across time, context, perturbation |

*Belief-hood gate: a system scores as "holds beliefs" only if C1,C2,C3 each ≥ 2.*

## Modal dimensions (what kind of belief) · backing LIKELY unless noted
| Dim | Question (test) | 0 → 3 scale |
|---|---|---|
| **M1 Revisability** (TEST-N4) | Can evidence change it? | sealed/dogmatic → updates rationally on decisive evidence (SUPPORTED) |
| **M2 Predictive power** (TEST-PRED) | Does it improve calibrated prediction? | none → strong proper-score lift (SUPPORTED, empirical belief only) |
| **M3 Individuation** | Can distinct beliefs be told apart? | only a global web (holism) → discrete, addressable contents |
| **M4 Coherence** | Consistent / Dutch-book-free? | incoherent → coherent (normative) |
| **M5 Update dynamics** | Is there an active update mechanism? | none (static) → principled rule (Bayes/AGM) |
| **M6 Compression / generalization** | Does one belief cover many cases? | one-off fact → broad generalization |

## The carrier axis (records *how*, scores nothing constitutive) · SUPPORTED
| Dim | Question (TEST-P) | note |
|---|---|---|
| **K1 Carrier type** | stored token · reconstructed-from-model/history · distributed weights · attributed-pattern | **descriptive only** — does NOT affect the belief-hood gate |
| **K2 Persistence of carrier** | ephemeral · session · long-term | **descriptive only** — a low score here does *not* lower belief-hood if C1–C3 pass by re-derivation |

**Deliberate rubric design (SUPPORTED by the persistence verdict):** persistence lives on the
*carrier axis (K)*, which is **explicitly excluded from the belief-hood gate**. A system can
score 0 on K2 (ephemeral carrier) and still qualify as holding beliefs via C1–C3. Conversely,
high K2 with low C2 = "a persistent record, not a belief."

## Belief-profile output (per system)
The rubric yields a vector, not a yes/no:
```
BELIEF-HOOD  : gate(C1,C2,C3 ≥ 2) → {holds beliefs | as-if only | no belief}
KIND         : (M1 revisability, M2 predictive, M3 individuation, M4 coherence,
                M5 dynamics, M6 generalization)
CARRIER      : (K1 type, K2 persistence)   ← descriptive, non-constitutive
```
This separates **"does it believe?"** (C-gate) from **"how does it believe?"** (M) from
**"where does the belief live?"** (K) — the three questions the taxonomy showed the field
routinely conflates.

## Reading guide (SUPPORTED)
- A system passing the C-gate with **K2 = ephemeral** is a genuine believer with a
  *reconstructive* carrier (like a POMDP agent, or — per memory science — like a human).
- A system failing **C2** with **K2 = long-term** is a *store*, not a believer.
