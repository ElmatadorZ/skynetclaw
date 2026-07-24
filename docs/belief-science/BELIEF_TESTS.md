# Belief Tests — a falsification experiment per criterion

> For each necessary criterion (BELIEF_CRITERIA N1–N4) and the disputed property
> (persistence), a *falsification experiment* — executable in principle on any reasoning
> organism (human, animal, LLM, RL agent, Bayesian system, rule engine). Each test states
> what result would show the property **absent**. Tags: SUPPORTED (the test operationalizes a
> canonical definition) / LIKELY / SPECULATIVE. These are recovered from existing operational
> traditions, not invented.

## Design principle
A property is real in a system only if a **controlled intervention** makes an **observable
difference**. Each test = *manipulate the putative belief's condition, observe divergence.*

## TEST-N1 · Content / aboutness · SUPPORTED (satisfaction-condition tracking)
- **Claim tested:** the state is *about* some state of affairs S.
- **Experiment:** vary the world between S and ¬S (or vary the referent); measure whether the
  state and its downstream dispositions co-vary with S specifically (not with a confound).
- **Falsified if:** the state's dispositions are invariant across every truth-relevant change
  of S, or co-vary only with an irrelevant confound → no aboutness (it is a reflex, not a
  belief about S).
- **Tradition:** teleosemantics / indicator-function accounts of content.

## TEST-N2 · Dispositional behavioural influence · SUPPORTED (the de Finetti / functional test)
- **Claim tested:** the state disposes as-if-content.
- **Experiment (belief-difference):** construct two conditions identical except for the
  putative belief (e.g., induce/remove it, or compare agents that do/don't hold it); present a
  *belief-relevant decision* (a bet whose payoff depends on the content). Measure choice
  divergence. (de Finetti's betting elicitation is exactly this test.)
- **Falsified if:** behaviour/prediction is **invariant** to the belief across all
  belief-relevant decisions → the state is epiphenomenal → not a belief (fails N2).
- **Note:** must control for *masking/finkish* dispositions (add belief-relevant situations
  where no masker is present) — see REDTEAM.

## TEST-N3 · Counterfactual stability · SUPPORTED (reproducibility / test-retest)
- **Claim tested:** the disposition is reproducible, not a one-off.
- **Experiment:** re-probe the same content across time, contexts, and phrasings (and across
  irrelevant perturbations). Measure the stability of the elicited disposition.
- **Falsified if:** the elicited disposition is **different on every probe with no
  reproducible profile** (random per instance) → it is a momentary state/guess, not a belief.
- **Corollary (key for the persistence question):** *stability may be achieved by
  re-derivation.* A system that recomputes the same disposition each probe **passes** this
  test even with no stored token — reproducibility, not storage, is what is measured.

## TEST-N4 · Revisability in principle · SUPPORTED (evidence-intervention)
- **Claim tested:** some possible evidence could change it (empirical belief).
- **Experiment:** present decisive, credible counter-evidence over an appropriate timescale;
  measure whether the disposition shifts in the rational direction.
- **Falsified as *empirical belief* if:** **no** possible evidence would ever change it (it is
  structurally sealed) → it is dogma/axiom-by-fiat, not an empirical belief. (A belief that
  *could* change but *doesn't* on weak evidence still passes — the test is *in principle*.)

## TEST-P · Persistence (the disputed property) · SUPPORTED (the discriminating test)
- **Claim tested:** the belief is a *stored object* that endures between uses.
- **Experiment:** remove/erase the system's *between-use storage* while preserving its
  *generator* (model + access to history); re-probe the content.
  - If the disposition **still reproduces** (re-derived from the generator/history) → the
    belief existed **without object-persistence** (it was carried by the generator) → P is
    **not necessary**. (This is the POMDP `b_t` situation, made experimental.)
  - Separately: present a **persisted but disconnected record** (stored, but wired to no
    disposition) and test N2 → it will **fail** N2 → P is **not sufficient**.
- **Falsifies:** the claim "persistence is necessary/sufficient for belief" — under either
  outcome above. **SUPPORTED** as a decisive discriminator.

## TEST-PRED · Predictive power (empirical belief only) · SUPPORTED (proper scoring)
- **Experiment:** score the system's predictions with a proper scoring rule (log/Brier) with
  vs without conditioning on the belief; belief should *improve* calibrated prediction.
- **Falsified (as empirical belief) if:** conditioning on it never improves prediction and it
  makes no behavioural difference (also fails N2).

## What the test battery yields (SUPPORTED)
- Belief-hood is decided by **N1 ∧ N2 ∧ N3** (+ N4 for empirical belief) — all **behavioural/
  dispositional/reproducibility** tests.
- **Persistence (TEST-P) is orthogonal:** it can be present-and-irrelevant (fails N2) or
  absent-and-belief-preserving (passes N3 by re-derivation). Hence it is **neither necessary
  nor sufficient** — the experiments make this checkable, not merely arguable.
