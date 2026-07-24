# Belief Taxonomy — operational models of belief across the sciences

> Recovering *operational* definitions of belief from philosophy, cognitive science,
> decision theory, predictive processing, RL, and knowledge representation. This is a
> literature-recovery pass; the assumption "belief = persisted object" is treated as one
> model among many, not a premise. Tags: SUPPORTED (canonical in the field) / LIKELY
> (mainstream but contested) / SPECULATIVE (synthesis) / UNKNOWN / FALSIFIED / RETRACTED.
>
> **Methodology (per mission): science before AI.** Historical → modern-operational → compare.

## Axis of disagreement (the taxonomy's spine)
Every model below answers three questions differently:
1. **Carrier** — is a belief a *stored token* or a *reconstructed/dispositional state*?
2. **Individuation** — is a belief a *discrete item* or a *pattern in a whole system*?
3. **Existence test** — does a belief exist because it is *represented*, or because it is
   *acted/predicted on*?

## The models

### T1 · Representationalism / Language of Thought (Fodor) · SUPPORTED (position exists)
- **Definition:** a belief is a stored mental representation (a token in a "language of
  thought") with propositional content and a functional role.
- **Required properties:** persisted symbolic token · content · causal role.
- **Failure cases:** implicit/tacit beliefs never explicitly stored (below, T7) are not
  tokens yet are called beliefs → representationalism under-counts them.
- **Carrier:** stored token. **→ persistence NECESSARY** *on this model only.*

### T2 · Dispositionalism (Ryle; behaviourist lineage) · SUPPORTED
- **Definition:** to believe P is to be *disposed* to act, assent, and infer as-if-P.
- **Required properties:** a stable behavioural disposition (counterfactual profile). No
  stored object required.
- **Failure cases:** *finkish/masked dispositions* — one may believe P yet not act on it
  (masking) → the behavioural signature under-determines belief.
- **Carrier:** disposition (a persisting *profile*, not a token).

### T3 · Functionalism (Lewis; Armstrong) · SUPPORTED
- **Definition:** a belief is any internal state occupying the *causal role* "belief" —
  caused by perception, combining with desires, causing action.
- **Required properties:** the functional role, realizable in any substrate.
- **Failure cases:** functional under-determination (many roles, coarse individuation).
- **Carrier:** role-occupant (storage optional).

### T4 · Interpretationism / Intentional Stance (Dennett) · SUPPORTED
- **Definition:** beliefs are *real patterns* an interpreter must attribute to predict a
  system's behaviour; they exist iff the intentional-stance prediction succeeds.
- **Required properties:** predictive indispensability of the attribution.
- **Failure cases:** stance-relativity (belief is observer-indexed); coarse content.
- **Carrier:** a pattern in behaviour — **no stored token required.**

### T5 · Credence / Operational Bayesianism (Ramsey; de Finetti) · SUPPORTED
- **Definition:** degree of belief = the *betting quotient* — the price at which the agent
  would bet on P (revealed by choice), constrained by coherence (no Dutch book).
- **Required properties:** a coherent disposition-to-bet; probabilistic structure.
- **Failure cases:** preference reversals / incoherence; unmeasurable for one-off events.
- **Carrier:** a behavioural disposition (the number is *revealed*, not necessarily *stored*).

### T6 · Bayesian representation / AGM belief base · SUPPORTED
- **Definition (probabilistic):** belief = a probability distribution (prior/posterior)
  updated by conditionalization. **(logical, AGM — Alchourrón–Gärdenfors–Makinson):**
  belief = a sentence in a belief set, changed by expansion/revision/contraction per
  rationality postulates.
- **Required properties:** an update rule (Bayes / AGM postulates); a maintained set/dist.
- **Failure cases:** logical omniscience (idealization); the whole set persists (costly).
- **Carrier:** a maintained representation. **→ persistence assumed** *by these models.*

### T7 · Tacit / Implicit belief (Dennett's "zebras don't wear overcoats") · SUPPORTED
- **Definition:** a belief entailed by, but never explicitly stored in, the system.
- **Required properties:** derivability / dispositional readiness to assent.
- **Failure cases:** infinite entailments (which of the infinitely-many implied beliefs are
  "really" held?).
- **Carrier:** none — **belief without any stored token.** (Direct counterexample to T1.)

### T8 · Predictive processing / active inference (Friston; Clark; Hohwy) · SUPPORTED (framework) / LIKELY (that it *is* "belief")
- **Definition:** "beliefs" are the parameters/posteriors of a generative model that
  minimize prediction error (free energy); perception and action both update/serve them.
- **Required properties:** predictive power; error-driven update; a generative model.
- **Failure cases:** whether sub-personal parameters deserve the word "belief" is contested.
- **Carrier:** model parameters (persist in synaptic weights) — but the *criterion* is
  prediction, not storage.

### T9 · RL "belief state" (POMDP; control theory) · SUPPORTED
- **Definition:** the belief state `b_t` = a probability distribution over hidden states =
  a *sufficient statistic of the observation history*, updated each step.
- **Required properties:** it summarizes history for optimal action; recomputable from
  history + model.
- **Failure cases:** approximation error; intractability in large spaces.
- **Carrier:** **a computed function of history — not a stored belief token.** `b_t` can be
  *re-derived* from history; it need not be an independently persisted object. **Direct
  formal example of belief-by-reconstruction.**

### T10 · Procedural / behavioural belief (policies, value functions, weights) · LIKELY
- **Definition:** "beliefs" implicit in a learned policy/value function — the agent behaves
  *as-if* it believes, with no declarative representation.
- **Required properties:** systematic as-if behaviour.
- **Failure cases:** hard to ascribe determinate content (interpretation-dependent, cf. T4).
- **Carrier:** distributed weights (persist), but content is implicit.

### T11 · Occurrent vs Standing belief (standard cog-sci distinction) · SUPPORTED
- **Definition:** *occurrent/working* belief = actively entertained *now* (in working
  memory); *standing/dispositional* belief = would be assented to if queried.
- **Point:** the field *already* names a belief that is **momentary and not long-term-stored**
  (occurrent). Persistence separates *standing* from *occurrent*; it does not define belief.

## Eliminativist caveat · SUPPORTED (as a live position)
### T0 · Eliminative materialism (Churchland)
- **Claim:** "belief" is a posit of folk psychology — a possibly-false theory — and may name
  no natural kind; a mature science might *eliminate* it.
- **Consequence for this taxonomy:** the *folk* concept may not be a scientific natural kind
  (see REDTEAM_OF_BELIEF); but the *operational* constructs (T5, T8, T9) are precise and
  survive independently of folk belief.

## What the taxonomy already shows (SUPPORTED)
- Models split cleanly on **carrier**: T1/T6 require a maintained representation; T2/T4/T5/
  T7/T9/T11-occurrent do **not**. → "belief = persisted object" is **one model (T1/T6), not
  the definition.** The prior assumption is thereby **not universal** (formally FALSIFIED as
  *the* definition; it survives as *a* model).
- The one property present in **every** surviving model is **behavioural/predictive
  disposition** (act/bet/predict as-if-content) — see BELIEF_CRITERIA.
