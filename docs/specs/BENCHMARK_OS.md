# Benchmark OS — Specification

**Version:** 0.1 (DRAFT — design only) · **Date:** 2026-07-13 · **Owner:** ElmatadorZ
**Was:** "A5 — SCB as Code". Expanded per the Chief Architect: this is a **system**,
not a script. **Under:** ADR-0007 (Capability-first). It is the **measurement plane**
of the Cognitive OS — the counterpart to the CAF (production plane). No capability
graduates to `present` in the Capability Model until the Benchmark OS measures it.

---

## 1. Why a Benchmark OS (not a script)

Today SkynetClaw flies on two disconnected signals: `eval_suite` (deterministic
behavioural regression — 48/48, but blind to a confidently-wrong answer) and SCB
(cognitive quality, but manual / LLM-judged / 5 categories / not in CI). You cannot
drive a system to production cognitive quality with a non-repeatable, coverage-limited,
accuracy-only benchmark. The Benchmark OS makes cognitive quality a **measured,
versioned, trended, regression-guarded property** — the precondition for *provable*
progress and for the capability-graduation rule.

---

## 2. Components

```
Benchmark OS
├── Runner        — executes a suite: task → agent → captured answer + trace
├── Dataset       — versioned benchmark cases (inputs, tags: capability, difficulty)
├── Golden Answer — expected result and/or scoring rubric per case
├── Metrics       — {accuracy, calibration, trace-soundness} per case/category
├── Calibration   — ECE / Brier: is stated confidence honest? (headline metric)
├── Regression    — compare a run to a baseline; block on a drop (CI gate)
├── Trend         — score over time per capability/model (the improvement curve)
├── Dashboard     — Intel-integrated live view (reuses the architecture pane)
└── Leaderboard   — per-capability × per-model ranking (which model for which capability)
```

### Component contracts (ABI)
```
BenchmarkCase   : { id, capability, difficulty, input, golden|rubric, tags }
RunResult       : { case_id, answer, trace, scores{accuracy,calibration,trace}, model, ts }
Runner.run(suite, model) -> [RunResult]
Scorer.score(case, RunResult) -> scores      # rubric or golden-diff; LLM-judge = warnings-only
Calibration.ece(results) -> float            # trained against Outcome-Clock-judged reality
Regression.gate(run, baseline) -> pass|fail  # CI: any category drop > ε fails
Trend.series(capability) -> [ (ts, score) ]
Leaderboard.rank(capability) -> [ (model, score) ]
```

---

## 3. Scoring model (the departure from accuracy-only)

Every case is scored on **three axes**, not one:
1. **Accuracy** — is the answer right (golden diff, or rubric).
2. **Calibration** — did stated confidence match empirical correctness (ECE/Brier)?
   *An assured system must be calibrated, not merely accurate.*
3. **Trace-soundness** — was the *method* sound (did a quantitative answer carry a CAF
   trace; did a plan carry a DAG)? Consumes the CAF/kernel audit trace — deterministic,
   not a judgment call.

A capability's benchmark **bar** is a threshold on all three, not just accuracy.

---

## 4. Coverage — categories to add (the blind-spot fix)

Current SCB: First-Principles, Quantitative, Incomplete-Info, Consistency,
Autonomous-Planning (5). The Capability Model implies these **missing** categories:

Financial / Unit-Economics · Decision-Under-Constraints · Risk-Prioritization ·
Sensitivity & Robustness · Optimization / Constraint · Long-Horizon Planning ·
Confidence-Calibration · Adversarial & Prompt-Injection · Factuality / Grounding ·
Communication-Quality · Reflection-Quality.

**Rule:** every capability in the Capability Model maps to exactly one benchmark
category; a capability with no category is a coverage blind spot and cannot graduate.

---

## 5. Relationship to the rest of the system

- **Reuses** the existing continuous-eval scheduler (nightly) as the Runner's cron; the
  Outcome Clock as calibration ground-truth; `eval_suite` becomes the *behavioural*
  regression subset inside the Runner.
- **Feeds** the Capability Model's maturity column and the CAF/CVL metrics.
- **Gates** capability graduation and CI (Regression component).
- **Renders** into Intel (Dashboard/Leaderboard) — the measurement plane made visible.

---

## 6. Non-goals

- Not a replacement for `eval_suite` — it *contains* it as the behavioural subset.
- LLM-judge is a **warnings-only** scorer signal, never the graduation gate (must be a
  rubric/golden for a hard gate — determinism where a decision depends on it).
- Not a one-off report: if a benchmark isn't versioned, trended, and regression-gated,
  it is a script, not the Benchmark OS.

---

## 7. Priority

**P0** alongside the CAF: the CAF's gains are unprovable without it, and the
capability-graduation rule (no capability `present` without measurement) is
unenforceable without it. Build the Runner + Dataset + Golden + Metrics(3-axis) +
Regression first; Trend/Dashboard/Leaderboard follow.
