# The Scientific Method of Genesis Mind (recovered, not invented)

> Research-scientist reconstruction of the organism's *knowledge-production* process, from
> historical/artifact evidence: the epistemic organs' **own docstrings**, commit messages
> (06-22/23 burst), the Trust documents, quality gate, chaos/regression reports, and the
> prior archaeology (as immutable evidence, minus the claims falsified in ARCHAEOLOGY_REDTEAM).
> Tags: SUPPORTED / LIKELY / SPECULATIVE / UNKNOWN / OVERCLAIM / FALSIFIED / RETRACTED.
>
> **Central caveat (SUPPORTED, decisive):** the cognitive apparatus is an **observatory**,
> not an actuator. Nearly every organ self-declares *"read-only / DETECTION ONLY / humans
> decide."* Exactly one organ (reinforcement) closes evidence→behaviour automatically, and
> only within tight rate-limits. Read every stage below through that lens.

## 1. Observation · SUPPORTED
The organism records raw experience (mission ledger, tool memory, agent runs, artifact
registry). But — quote — *"experience is not learning. A log is not a lesson"*
(lesson_synthesis). Observation is explicitly held **insufficient** on its own.

## 2. Hypothesis · SUPPORTED
Correlations are turned into **testable causal hypotheses**: causal-discovery *"contrasts
successful vs failed episodes ... turning correlation into testable causal hypotheses with
supporting/contradicting evidence."* Hypotheses are named as candidates, not truths.

## 3. Prediction · SUPPORTED
Beliefs carry a **predicted confidence** that is later checked (calibration: *"measure
whether PREDICTED confidence matches OBSERVED outcomes"*). A belief that predicts nothing
checkable cannot be calibrated → cannot graduate.

## 4. Experiment · SUPPORTED (design) / LIKELY (execution) / UNKNOWN (autonomy)
Experiment-design *"move[s] from CORRELATION to CONTROLLED VALIDATION — is X actually the
CAUSE? proposes controlled experiments — a control ordering vs a test ordering."* It
**proposes** control-vs-test experiments. Whether these experiments are ever *run
autonomously* (vs proposed for humans) = **UNKNOWN** from evidence (the organ is read-only).

## 5. Measurement · SUPPORTED
Calibration is the measurement organ: predicted-vs-observed across decisions, promoted
beliefs, and principles, *"so the House knows where its self-assessment can be trusted."*
Reinforcement measures **lift over baseline** per capability.

## 6. Failure · SUPPORTED
Two failure detectors: (a) belief-revision *"detect[s] when accumulated RECENT evidence
contradicts a previously PROMOTED belief"* (over-confidence/drift); (b) at the engineering
level, chaos/regression tests surface failures (e.g. CHAOS-001). Failure is a first-class
observed event, not an exception to hide.

## 7. Retraction · LIKELY (cognitive) / SUPPORTED (engineering)
Cognitive: belief-revision flags a belief as contradicted **but does not retract it** —
*"DETECTION ONLY. No promotion, no demotion... humans / later protocols decide."* So
**cognitive retraction is human-gated** (detection, not action) — LIKELY, and deliberately
incomplete. Engineering: a failing quality gate blocks a merge = an enforced retraction of
a change — SUPPORTED.

## 8. Revision · SUPPORTED (narrow) / OVERCLAIM if called general
The **only** automatic evidence→behaviour revision is reinforcement: *positive lift →
weight↑, negative lift → weight↓*, persisted to `capability_weights.json`, then *"reorders
recalled capabilities by weight."* Guarded: *"no single mission can jump a weight more than
MAX_STEP"*, clamp [0.5, 1.5]. All other revision is human-gated. Claiming the organism
"autonomously revises its beliefs" in general = **OVERCLAIM** (only capability-weights do).

## 9. Regression · SUPPORTED
The engineering organ of permanence: Epic Trust — *"every failure becomes a permanent
regression test."* Confirmed by real artifacts: security-regression (10/10), chaos-test
(CHAOS-001 → fixed → EXP-2 guard), a11y-regression (22/22). A defeated failure cannot
recur without a red test.

## 10. Institutional Memory · SUPPORTED
Two memories: (a) **cognitive** — lesson-synthesis (*repeated+consistent → reusable
conclusion*), promoted first-principles (*cross-validated by ≥2 systems*), reinforcement
weights; (b) **engineering** — DecisionLog, KNOWN_RISKS, TRUST_SCOREBOARD, and the
regression suites themselves as frozen memory of past failures.

## The recovered loop (SUPPORTED)
```
 experience ─▶ [is-it-a-lesson? repeated+consistent] ─▶ hypothesis (causal)
    ▲                                                        │
    │                                                        ▼
 institutional        prediction (confidence) ─▶ experiment (control vs test, proposed)
 memory  ◀── regression ◀── measurement (calibration: predicted vs observed)
    ▲                                    │
    │                       failure/drift (belief-revision: contradicted?)
    │                                    │
    └───── revision ◀────────────────────┘
           └─ AUTOMATIC only for capability-weights (reinforcement, rate-limited)
           └─ HUMAN-GATED for everything else ("humans / later protocols decide")
```

## Verdict of this reconstruction (LIKELY)
Every *organ* of a scientific method is present and evidence-backed. But the **actuating
edge** (evidence → revised belief → changed behaviour) is **closed automatically in only
one narrow place** and **human-gated everywhere else**. This is a **scientific
*observatory* + a human-supervised method**, not a fully autonomous self-revising science.
See REDTEAM_OF_THE_METHOD for the attack on this claim, and the FINAL ANSWER there.
