# False Positives — imitations of belief that contain none

> Situations that reproduce *some* belief signature (BELIEF_SIGNATURES) without instantiating
> belief. For each: what it mimics, which signature exposes it, and its status. This is the
> catalogue any belief-detector must survive. Tags: SUPPORTED / LIKELY / SPECULATIVE / UNKNOWN.

## The imitators

### FP-1 · Giant lookup table / rote memory ("Blockhead", Ned Block) · SUPPORTED
- **Mimics:** SIG-1, SIG-2, SIG-5 on any **pre-enumerated** item — perfect behaviour over a
  finite tested set.
- **Exposed by:** SIG-3 (off-distribution) + SIG-4 (novel inference). A table has no
  generalization or productivity; a genuinely novel, content-entailed probe it was never given
  → it fails (or must be infinite). *The canonical proof that finite behavioural identity ≠
  belief.*

### FP-2 · Behaviour cloning / imitation learning · SUPPORTED
- **Mimics:** SIG-2 (acts as-if) by copying a believer's outputs.
- **Exposed by:** SIG-5 (won't update to *new* evidence the demonstrator never saw) + SIG-6
  (no direction of fit — it reproduces action, not a world-tracking state).

### FP-3 · Heuristics / shortcuts · SUPPORTED
- **Mimics:** SIG-1/SIG-2 **in-distribution**.
- **Exposed by:** SIG-3 — heuristics break precisely off-distribution (that is what makes them
  heuristics).

### FP-4 · Retrieval / cached lookup (incl. RAG-style fetch) · SUPPORTED
- **Mimics:** SIG-1 content-covariation and verbal endorsement (M9).
- **Exposed by:** SIG-4 (no integration — re-fetches, doesn't infer) + SIG-6 (no revision of a
  *held* state; it re-queries a store — that is memory, per DIFFERENTIAL_DIAGNOSIS, not belief).

### FP-5 · Statistical coincidence / overfitting · SUPPORTED
- **Mimics:** SIG-1 on a particular sample by chance/overfit.
- **Exposed by:** SIG-3 + replication under SIG-5; coincidence does not survive a fresh sample
  or an intervention.

### FP-6 · Teaching-to-the-test / prompt leakage · SUPPORTED
- **Mimics:** whatever signature is *probed*, if the answers leaked into training/context.
- **Exposed by:** strict **held-out, pre-registered, leakage-controlled** probes (protocol
  hygiene, not a new signature).

### FP-7 · Clever Hans / experimenter-cue reading · SUPPORTED (comparative psych)
- **Mimics:** SIG-1/SIG-2 by covarying with *the experimenter's* unconscious cue, not the
  content.
- **Exposed by:** cue-control (blind the experimenter; remove the cue) → behaviour collapses.
  A confound of *content* covariation, so it specifically attacks SIG-1's validity.

### FP-8 · Chinese Room (Searle) · SPECULATIVE (a *limit* false-positive) 
- **Mimics:** potentially **all** signatures — correct symbol manipulation without
  "understanding".
- **Status:** targets *semantic understanding/consciousness*, not *functional belief*. Under
  the surviving dispositional definition, a system passing all signatures **has** functional
  belief by definition; the Room's "no understanding" is a claim about *phenomenal/original
  intentionality*, which the prior mission ruled **not necessary** for belief. → As a
  false-positive *for belief*, it is **UNKNOWN/contested**, not established.

### FP-9 · Frozen true belief that never needed updating · LIKELY (a *near-miss*, not a fake)
- **Mimics:** looks like habit (never changes) though it is a real belief that no evidence has
  challenged.
- **Note:** this is the *inverse* risk — a **false negative** for SIG-5. Handled by testing
  *revisability-in-principle* (present hypothetical decisive evidence), not actual change.

## The structural lesson (SUPPORTED)
Every single-signature test has a false positive:
| Signature alone | Defeated by |
|---|---|
| SIG-1 content covariation | FP-7 Clever Hans, FP-5 coincidence |
| SIG-2 behavioural influence | FP-1 lookup, FP-2 cloning |
| SIG-3 generalization | FP-6 leakage (if the "novel" set leaked) |
| SIG-5 updating | FP-2 (updates copied), FP-9 (real belief looks frozen) |
→ **No single signature is safe.** Belief is inferable only from the **conjunction** of
signatures under **hygiene controls** (held-out, cue-blind, intervention-based). This is why
BLACK_BOX_PROTOCOL must stack them — the false-positives are individually lethal and only
jointly excludable. The one imitator that no *finite* battery fully excludes is **FP-1
(Blockhead)** — carried into REDTEAM_OF_OBSERVABILITY.
