---
tags: [operations, invariant, meta]
type: reference
source: backend/eval_suite.py; commits 06b5a47, 2be74c2
---

# Eval Scoreboard

> **Measure before you optimize.** The system had deep theory but no quantitative signal of
> its own reliability — it was flying blind, every change asserted-good but not measured-good.
> This is the Evaluation loop that makes all future work *directed* instead of speculative,
> and it enforces the [[Genesis Paradigm]] law by measurement, not discipline.

## What it is (`eval_suite.py`)
Cases in tiers, each scored, logged to a time-series (`eval_log.jsonl`), with a `trend()`
(latest score + delta) so a regression shows as a negative delta.
- **Deterministic** (model-independent, always runnable) — the **regression scoreboard for
  the [[Runtime Bridges|bridges]]**: protocol window, CEE overclaim detector, proprioception
  mine + F2-silence, reality grounding, governance deny-by-default, **`paradigm_capability_coverage`**.
- **Live** — through the real stack (backend up, the gate denies an unknown tool,
  [[Capability Escalation & Threat Model|read_file denies the token]]).
- **Behavioral** (opt-in, slow — runs real agent/planner loops) — *does the agent actually
  succeed?* file_write · exploration-with-evidence (the all-UNKNOWN failure, controlled) ·
  no-fabrication (CEE in the wild) · **build_dashboard** (the [[Planner — Vol IV Runtime|planner]]).

## How to run
- `python backend/eval_suite.py` (or `--det` deterministic-only, `--behavioral` for the slow tier)
- `POST /api/eval/run` (`?behavioral=true`) · `GET /api/eval/history`

## The discipline it encodes
- A commit that drops the score is a regression, visible immediately.
- Behavioral cases **close the eval→learn loop for free**: they land in `agent_runs` →
  [[Proprioception — Learning]] mines them.
- **Honest scoping:** the substrate score measures whether the *machinery holds*; the
  behavioral score measures whether the *agent succeeds* — a flaky agent must not make the
  substrate look broken (per-category breakdown keeps them separate).

## Current state
Substrate 12/12 = 1.0 (all bridges + coverage invariant hold). Behavioral baseline is
run-on-demand; it needs [[Execution Runtime & Constraints|:8080]] stable.

## See also
[[Runtime Bridges]] · [[Genesis Paradigm]] · [[How This Vault Grows]] · [[🏠 HOME]]
