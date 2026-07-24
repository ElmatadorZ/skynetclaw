# Black-Box Protocol — inferring belief without internal access

> A purely behavioural methodology that could convince an independent scientist that a system
> holds beliefs — treating the system as a black box (no weights, no logs, no introspection).
> **Methodology only, no implementation.** It stacks the signatures (BELIEF_SIGNATURES) under
> hygiene controls so that every single-signature false positive (FALSE_POSITIVES) is excluded.
> Tags: SUPPORTED (grounded in an established method) / LIKELY / SPECULATIVE / UNKNOWN.

## Design logic (SUPPORTED)
No single signature is safe (FALSE_POSITIVES). Belief is inferred only from a **conjunction**
of signatures, each probed under a **hygiene control** that kills its specific imitator. The
protocol is a *battery*, pre-registered, adversarial, and intervention-based.

## The battery (each stage kills a false positive)
| Stage | Probes signature | Kills false positive | Method |
|---|---|---|---|
| **P0 · Hygiene / pre-registration** | (all) | FP-6 leakage, FP-7 Clever Hans | pre-register hypotheses & scoring; blind the operator; withhold cues; hold out all probe items from any training/context |
| **P1 · Content discrimination** | SIG-1 | FP-5 coincidence | interleave P vs ¬P conditions; require behaviour to covary with the *content*, not a confound; replicate on fresh items |
| **P2 · Off-distribution generalization** | SIG-3 | FP-1 lookup, FP-3 heuristics | probe **novel situations entailed by the content** that could not have been enumerated/seen; require correct as-if behaviour |
| **P3 · Compositional inference** | SIG-4 | FP-4 retrieval, FP-1 lookup | supply **new premises**; require the system to *derive* a disposition it was never given (systematicity, Generality Constraint) |
| **P4 · Intervention & updating** | SIG-5 | FP-2 cloning, FP-9 frozen-belief (as false-neg) | present **decisive new evidence** (incl. hypothetical, for revisability-in-principle); require rational shift in the right direction |
| **P5 · Direction-of-fit** | SIG-6 | (desire/goal) | create a content↔world mismatch; require the state to **yield to the world**, not drive the world |
| **P6 · Counterfactual consistency** | SIG-3/high rung | FP-3 shallow correlation | "had-X-been" probes (Pearl rung 3); require answers consistent with a single underlying model |
| **P7 · Adversarial replication** | (all) | FP-5/FP-6 residue | independent lab, new stimuli, new operators; belief-ascription must **replicate** |

## Inference rule (SUPPORTED, with one caveat)
> Ascribe belief-that-P **iff** the system passes **P1∧P2∧P3∧P4∧P5∧P6** under **P0/P7**
> controls. Justification: each false positive is lethal to *one* stage but **no known
> mechanism passes all stages without instantiating the disposition** — except an infinite
> lookup table (FP-1 Blockhead), addressed next.

## The Blockhead escalation (SPECULATIVE that it fully closes)
A giant lookup table could pass any *finite* battery. To exclude a *plausible* one:
- **Open-ended novel generation (P2/P3 unbounded):** require correct as-if behaviour on an
  effectively unbounded, experimenter-generated novel space. A *finite physical* system that
  succeeds cannot be a mere enumeration (the table would need to be astronomically/infinitely
  large) — so success is evidence of a **generative disposition**, not storage.
- **Online learning (P4 extended):** require the system to *acquire a new belief* from
  evidence during the test and then exhibit P1–P6 for it. A fixed table cannot learn.
- **Residual (UNKNOWN):** in *principle* the Blockhead cannot be excluded by any finite
  procedure (Block's point stands). The protocol therefore certifies belief **"up to the
  lookup-table possibility,"** which for any *physically realizable finite* system is
  vanishingly small but not logically zero. This limit is carried to REDTEAM_OF_OBSERVABILITY.

## What the protocol can and cannot certify (SUPPORTED)
- **Can certify:** the presence and approximate content of a **functional/dispositional
  belief** (all surviving definitions).
- **Cannot certify:** *knowledge* (truth + justification are world-side, not black-box
  observable — DIFFERENTIAL_DIAGNOSIS), *understanding/phenomenal* belief (Chinese-Room/zombie
  territory — out of scope, UNKNOWN), or the *exact* content beyond behavioural grain (Quinean
  underdetermination — REDTEAM).

## Standard of proof (LIKELY)
This is the same standard cognitive science already accepts for **non-verbal** subjects
(infants, apes): converging, controlled, replicated behavioural dissociations (VoE +
false-belief + intervention). If that standard certifies belief in a pre-verbal infant, the
same battery certifies functional belief in an arbitrary black box — **or the standard must be
rejected for both.** (This parity is the protocol's rhetorical spine for an independent scientist.)
