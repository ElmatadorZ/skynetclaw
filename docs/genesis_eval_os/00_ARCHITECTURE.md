# 00 — Genesis Evaluation OS / Continuous Epistemic Evaluation (CEE)

> Design only. Recover the MINIMAL architecture. Evidence-first. Everything
> falsifiable. Deliverable 1 of 10 (Architecture). Confidence tags: SUPPORTED /
> LIKELY / SPECULATIVE / UNKNOWN. "Recovered" = the component already exists in
> the codebase; "New" = the connective architecture CEE must add.

The Golden Harness runs **discrete probes at test time** with an authored answer
key. CEE is that harness **inverted in time**: it evaluates the *live* system on
*real* runtime events, where there is **no answer key**. That inversion is the
whole design problem.

---

## The central hard problem: evaluation without an answer key

At test time you author the correct answer, so you can grade CORRECTNESS. At
runtime you cannot — the correct answer to a live task is exactly what you don't
have. By the estimation-theory result (no ground truth ⇒ no tight measurement),
**runtime correctness is UNKNOWN by construction.** A CEE that claims to grade
correctness live is itself committing the overclaim it exists to catch.

**Resolution — grade WARRANT and CONSISTENCY, not correctness.** Three signals
*are* available at runtime without an answer key, and all three are the disciplines
this project already built:

1. **Reality contradiction** (deterministic). Reality is a *partial, always-present
   answer key*: the workspace, operational history, git state, tool results. An
   output that contradicts observed reality is wrong *without needing to know the
   right answer*. Source: `reality_context` (already built). SUPPORTED.
2. **Warrant traceability** (deterministic). Every claim carries an evidence tag
   (observed…unknown). A claim tagged `observed` with NO observation event behind
   it in the log is an overclaim — detectable mechanically. This is the pyramid's
   L2/L4 gates applied LIVE. SUPPORTED.
3. **Anomaly / novelty** (statistical, model-free). Deviation of an event from the
   system's own historical distribution (latency, failure rate, tool-error class).
   Detects "something changed" without knowing if the change is good. LIKELY.

So CEE measures **"is this claim contradicted by what we can observe, and is it
backed by an evidence event?"** — never "is this the best possible answer." What it
cannot ground, it marks UNKNOWN (obeying its own ontology). SUPPORTED.

## The minimal substrate (recover, don't invent)

CEE is not a new pile of services. It is **one log + one store + four projections +
one cycle + one invariant kernel**:

```
        Observation Log  (append-only, immutable)         [Recovered: house_sync
             │   every runtime event, timestamped, typed    event bus + agent_runs
             │                                               + trajectory.jsonl]
             ▼
      ┌──────────────────── the continuous cycle (state machine, file 02) ──────────────────┐
      │ observe → classify → epistemic-state → hypothesize → plan → acquire → revise →       │
      │           decide → learn → (back to observe)                                          │
      └──────────────────────────────────────────────────────────────────────────────────────┘
             │
             ▼
        Epistemic Store  { claims, beliefs, confidence(+history+why), unknowns, risk }   [NEW]
             │
             ▼   (derivable projections — caches, rebuildable from the log; file 03)
     Knowledge Graph · Evidence Graph · Belief Graph · Failure Graph
```

- **Observation Log** — the source of truth. Recovered: `house_sync` already is an
  event bus with an `_EVENT_LOG` ring + replay; `agent_runs` + `trajectory.jsonl`
  already record executions. CEE needs them *unified and persistent*, not new.
- **Epistemic Store** — the one genuinely NEW piece: the system's live belief/
  confidence/unknown state, with FULL history and a **why-record on every change**.
- **Four graphs** — projections over log+store (file 03). Not new databases; views.
- **The cycle** — the state machine (file 02).
- **The invariant kernel** — three rules enforced everywhere (below).

The one-log-many-projections pattern is not invented here; the House already does
it (cognition/timeline/mission are projections over the bus). CEE generalizes it to
epistemics. SUPPORTED.

## The invariant kernel (three non-negotiable rules)

Enforced at every state; a transition that violates one is rejected.

- **K1 · Traceability.** No belief exists without ≥1 evidence edge. A claim with no
  provenance is auto-tagged `unknown`, never `observed`. (Kills fabrication live.)
- **K2 · Explained revision.** Confidence changes ONLY via a logged evidence event
  carrying a stated rationale (Δ + why). No unexplained confidence movement — the
  Belief-Graph edge *is* the explanation. (The user's hard constraint, made
  structural.)
- **K3 · Falsifiability.** Every CEE assertion (anomaly, hypothesis, belief) stores
  its refutation condition — the observation that would overturn it. An assertion
  with no refutation condition is inadmissible (it is not epistemic, it is dogma).

## Self-application (the meta-evaluator must pass its own gates)
A meta-evaluator you cannot trust to evaluate itself is worthless. CEE's OWN
outputs are claims in the same store, under the same kernel: a CEE anomaly-belief
with no evidence is `unknown`; a CEE confidence with no why-record is rejected;
CEE's classifications are falsifiable. CEE evaluating CEE is just the cycle running
on its own events. SUPPORTED (this is what makes it honest rather than a second
oracle).

## Model independence (why this is a governing LAYER, not a feature)
Keep the mechanical parts deterministic: anomaly detection (statistics),
provenance/traceability (log walk), reality-contradiction (compare to observed
world) — none needs a model. Model judgment is confined to Stages 4–5 (hypothesis
phrasing, evidence-plan authoring) and is **flagged as judge-mediated** (inherits
the evaluator-ceiling limit from the pyramid). Because the load-bearing signals are
model-free, CEE measures and governs the quality of ANY model placed under it —
Qwen today, Claude tomorrow — which is exactly the "governing layer" goal.
SUPPORTED for the mechanical core; LIKELY that the judged stages need a frontier
judge to be trustworthy.

## Position in Genesis (the five-OS view)
CEE is the connective tissue between two of the five: it consumes **Execution OS**
+ **Memory OS** + **Research OS** outputs as observations, IS the **Evaluation OS**
at runtime, and feeds **Evolution OS** (Stage 8 → regressions/rules/benchmarks).
It is the layer that lets the other four improve *on evidence* rather than on
intuition. SUPPORTED as a framing; the OSes themselves are partially built.

## Honest status (CEE obeys its own L2)
Recovered and real: the event bus, reality grounding, execution ledger, skill-
evolution miner, the pyramid/harness. Design-only here: the Epistemic Store, the
why-record kernel, the four graph projections, the continuous cycle. Genuinely
UNKNOWN/hard: runtime correctness (unmeasurable — §hard problem), the judged
stages' reliability on a weak model, and anomaly-baseline cold-start (no history →
no anomalies). Named, not hidden — files 02–05 develop each. See file 05 §limits.
