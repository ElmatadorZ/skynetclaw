# Knowledge Lifecycle — the belief state machine (recovered)

> The states a belief passes through, each transition backed by an organ that is named in
> historical evidence (organ docstrings / commit messages). Tags per transition.
> **Key:** most transitions that *change what the organism does* are **human-gated**; only
> the reinforcement edge is automatic. Marked ⟨AUTO⟩ vs ⟨GATE⟩.

## States
`UNKNOWN → OBSERVED → HYPOTHESIS → TESTED → SUPPORTED → CHALLENGED → RETRACTED / SUPERSEDED`

## Transition table (organ = evidence)
| From → To | Organ / evidence | Condition | Auto/Gate | Tag |
|---|---|---|---|---|
| **UNKNOWN → OBSERVED** | mission ledger / tool memory; curiosity ("Gap Discovery") | experience recorded, or a gap named | ⟨AUTO⟩ | SUPPORTED |
| **OBSERVED → HYPOTHESIS** | causal ("correlation → testable causal hypothesis"); lesson-synthesis (repeated+consistent) | repeated evidence in similar context | ⟨AUTO⟩ | SUPPORTED |
| **HYPOTHESIS → TESTED** | experiment ("control ordering vs test ordering") | a controlled comparison is *proposed* (execution autonomy UNKNOWN) | ⟨GATE/UNKNOWN⟩ | LIKELY |
| **TESTED → SUPPORTED** | first-principles ("support ≥5 AND confidence ≥0.70 AND ≥2 independent systems"); theory (holds in ≥2 domains) | corroboration + sample-size + calibration thresholds met | ⟨GATE⟩ *"candidates; humans/later protocols decide"* | SUPPORTED |
| **SUPPORTED → (behaviour)** | reinforcement (capability_weights.json; lift→weight) | positive lift over baseline | **⟨AUTO⟩** (rate-limited) | SUPPORTED |
| **SUPPORTED → CHALLENGED** | belief-revision ("recent evidence contradicts a promoted belief"); calibration (predicted≠observed); paradigm (anomalies accumulate) | drift / miscalibration / anomaly | ⟨AUTO detect⟩ | SUPPORTED |
| **CHALLENGED → RETRACTED** | belief-revision — *detection only*; humans decide | contradiction sustained | **⟨GATE⟩** ("no promotion, no demotion, no autonomous correction") | SUPPORTED (that it is gated) |
| **CHALLENGED → (weight↓)** | reinforcement (negative lift → weight↓, "surfaces as a warning") | sustained negative lift | **⟨AUTO⟩** (rate-limited) | SUPPORTED |
| **SUPPORTED → SUPERSEDED** | paradigm ("PARADIGM SHIFT in progress" → new dominant framework) | a broader theory subsumes it | ⟨GATE/UNKNOWN⟩ | LIKELY |

## The state machine (with the human gate marked)
```
 UNKNOWN ──auto──▶ OBSERVED ──auto──▶ HYPOTHESIS ──propose──▶ TESTED
                                                                 │  (thresholds:
                                                                 │   ≥5 support, ≥0.70 conf,
                                                                 ▼   ≥2 independent systems)
                                                    ┌──── SUPPORTED ────┐
                                       auto(weights)│                   │gate
                                     reinforcement  ▼                   ▼   ("humans decide")
                                     capability_weights            CHALLENGED
                                      (rate-limited)          (belief-revision / calibration /
                                                                 paradigm anomalies — AUTO detect)
                                                                    │            │
                                                              gate  ▼            ▼ auto(weight↓)
                                                           RETRACTED        (warning surfaced)
                                                                    │
                                                                    ▼ (broader theory)
                                                               SUPERSEDED
   ═══ the belief may drive BEHAVIOUR automatically only via the reinforcement weight edge;
       every other promotion/retraction is ⟨GATE⟩ = deferred to human / later protocol ═══
```

## Two invariants of the lifecycle (SUPPORTED)
1. **No state is terminal-as-truth.** Even SUPPORTED and paradigm are provisional; a
   CHALLENGED edge always exists (belief-revision, calibration, paradigm). Fallibilism is
   structural.
2. **Detection is automatic; action is gated.** The organism will *notice* a belief has
   failed on its own, but (except capability-weights) it will not *act on that* without a
   human. The gate is the deliberate seam where V1's "humans adjudicate truth" gene lives on.

## UNKNOWNs
- Whether HYPOTHESIS→TESTED experiments ever *execute* autonomously (organs are read-only). **UNKNOWN.**
- Whether SUPERSEDED is ever actually reached in practice or only modelled. **UNKNOWN** (no
  run-time evidence recovered).
