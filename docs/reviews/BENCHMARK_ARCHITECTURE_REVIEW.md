# SkynetClaw — Benchmark Architecture Review

**Reviewer role:** Staff Engineer, architecture review · **Date:** 2026-07-13
**Scope:** why the benchmark does not reach production quality; architectural (not
prompt) causes and fixes. **Non-goal:** code.

> **Data caveat (read first).** The task template arrived with the benchmark body
> unfilled (`<PASTE THE ENTIRE BENCHMARK HERE>`). Rather than fabricate a result, this
> review is anchored on SkynetClaw's *real* benchmarks: (a) the **eval_suite** —
> 48/48 green, but a behavioural/regression harness, and (b) the **SCB** cognitive
> report last provided this session — SCB-001 First-Principles **84**, SCB-002
> Quantitative **62**, SCB-003 Incomplete-Info **86**, SCB-004 Consistency **97**,
> SCB-005 Autonomous-Planning **78** (avg **81.4**). SCB numbers are the last-known
> measurement, not re-run (SCB is not yet an automated suite — itself finding §6).
> If you paste a specific run, the review re-points at it; the architecture findings
> hold regardless.

---

# 1 Executive Summary

**Two scores, because two different things are being measured — and conflating them is
the first architectural error.**

- **Cognitive output quality (SCB): 81.4 / 100 → FAIL** the production bar (≥ 90 per
  category). Two categories are sub-bar: SCB-002 Quantitative (62), SCB-005 Planning
  (78).
- **Substrate / harness maturity: high.** Kernel hooks, fail-closed governance,
  durable audit spine, CVL, continuous-eval — 48/48 behavioural. Production-grade *as
  a cognitive OS substrate*.

**Verdict: FAIL for production cognitive quality.** The substrate is ready; the
*reasoning output* is not, and — critically — the residual weaknesses are now mostly
**capability gaps and model limits**, not harness bugs. Early-session wins already
fixed the harness-fixable defects (context overflow, governance, verification).

**Top 3 strengths**
1. **Governance & traceability substrate** — PRE_ACT/PRE_COMMIT hooks, fail-closed
   GPS-2, authority-owned durable audit spine, authenticated operator role. This is
   the hardest part of a production cognitive OS and it is done well.
2. **Deterministic verification layer (CVL) + the `calculator`/`safe_math` pattern** —
   offloading a fragile model capability to a deterministic tool is textbook
   reliability engineering, and it is generalizable (see §4).
3. **Measurement scaffolding exists** — continuous nightly eval + Outcome Clock (7-day
   prediction judging). The *rails* for closed-loop improvement are laid.

**Top 5 weaknesses** (elaborated in §2)
1. **Quantitative multi-step reasoning (SCB-002 = 62)** — only *arithmetic* is
   toolified; multi-step *analysis* (unit economics, cost-benefit, sensitivity) is
   attempted in free-form prose.
2. **Autonomous planning (SCB-005 = 78)** — the planner is linear; no dependency DAG,
   no precondition/goal-coverage checking.
3. **No confidence calibration** — the system states conclusions without a calibrated
   confidence. For a cognitive OS this is a production blocker (you cannot trust, or
   triage, an uncalibrated agent).
4. **Missing structured-analysis capabilities** — no decision-matrix, sensitivity,
   constraint-optimization, cost-benefit, or unit-economics *engines*; these are
   emergent-prose, not deterministic primitives.
5. **Benchmark insufficiency (meta-weakness)** — the cognitive benchmark is
   manual/LLM-judged, 5 narrow categories, not automated or repeatable. You cannot
   drive to production quality with a non-repeatable, coverage-limited benchmark; this
   blocks every other fix from being *verified*.

---

# 2 Root Cause Analysis

For each weakness: **why** it happens and the **owning subsystem**.

**W1 — Quantitative multi-step reasoning (62).**
- *Why:* the 14B model is weak at chained numeric reasoning, and only single
  operations are offloaded to a tool. A DCA/unit-economics/cost-benefit question needs
  a *structured multi-step computation*, which the model performs in its head and gets
  wrong; CVL then only catches the arithmetic slips, not a wrong *method*.
- *Owning subsystem:* **Reasoning Engine** (model-bound) + **Tool Layer** (missing
  analysis primitives) + **Orchestration** (no "this is a quantitative task → route to
  a structured solver" step).

**W2 — Autonomous planning (78).**
- *Why:* `planner _pcall` produces a linear step list with no dependency graph, no
  preconditions, no goal-coverage check. Long-horizon tasks with interdependencies
  degrade; failures aren't attributable to a plan defect.
- *Owning subsystem:* **Planning Engine** (structural gap — the DAG, "P5", is still
  open) + **CVL** (no Planning-domain validator to reject a defective plan).

**W3 — No confidence calibration.**
- *Why:* nothing measures whether a claim asserted "confidently" is actually right at
  that rate. Confidence is rhetorical, not computed. CVL v3 *designs* calibration
  (ECE, likelihood ratios, Outcome-Clock training) but it is unbuilt.
- *Owning subsystem:* **CVL** (missing calibration) + **Memory/Learning Engine**
  (Outcome Clock exists but doesn't feed a calibration model).

**W4 — Missing structured-analysis capabilities.**
- *Why:* the system treats decision-analysis as prose generation. There is no
  deterministic decision-matrix / sensitivity / optimization engine to offload to —
  the exact gap `calculator` filled for arithmetic, unfilled for analysis.
- *Owning subsystem:* **Tool Layer** + **Knowledge Layer** (no analytic
  frameworks-as-tools) + **Orchestration** (no task-type → solver routing).

**W5 — Benchmark insufficiency.**
- *Why:* two benchmarks exist but measure different things and neither is a
  production cognitive benchmark. eval_suite is deterministic *behaviour* (the harness
  works); SCB is *quality* but manual, LLM-judged, 5 categories, not in CI. There is no
  automated, repeatable, coverage-complete cognitive benchmark.
- *Owning subsystem:* **Orchestration / Eval infrastructure** (the de-facto benchmark
  is a regression suite, not a cognitive one).

**Cross-cutting root cause (the Staff-Engineer synthesis):** SkynetClaw invested
heavily and correctly in the **control plane** (governance, audit, verification) and
under-invested in the **cognitive data plane** (structured reasoning, planning,
calibration). The substrate can now *govern and audit* a reasoning process it cannot
yet *perform to production standard*. That imbalance — not any single bug — is why the
benchmark stalls at ~81.

---

# 3 Missing Cognitive Capabilities

Assessed against the system as actually built:

| Capability | Status | Owning gap |
|---|---|---|
| Verification | **Partial** — CVL arithmetic/expression/secret-leak (deterministic) | reasoning-method & citation verification missing |
| Traceability | **Present** — kernel audit spine, per-decision events | strong; reuse it for reasoning traces |
| Quantitative reasoning | **Weak** — single-op only (`calculator`) | no multi-step analysis engine |
| Financial reasoning / Unit economics | **Missing** | no unit-economics/NPV/IRR primitives |
| Cost-benefit analysis | **Missing** | no CBA engine |
| Decision matrix | **Missing** | no weighted-criteria engine |
| Risk prioritization | **Missing** | no risk register / severity×likelihood engine |
| Sensitivity analysis | **Missing** | no "vary the assumption" engine |
| Constraint optimization | **Missing** | no LP/constraint solver primitive |
| Scenario planning | **Weak** — Forecaster council role exists, prose-only | no structured scenario tree |
| Confidence calibration | **Missing (designed)** | CVL v3 P2 unbuilt |
| Reflection quality | **Weak** — reflect phase exists, not scored | no reflection-quality metric |

**Pattern:** every *Missing* row is a **deterministic analytic framework** that could be
a tool the model invokes — the `calculator` pattern, generalized. These are not
"reasoning skills to prompt for"; they are **engines to build**.

---

# 4 Architectural Improvements (systems, not prompts)

### A1 — Structured Reasoning Toolkit (deterministic analysis primitives)
- **Purpose:** offload structured analysis to deterministic engines the model invokes
  as tools — decision-matrix, cost-benefit, unit-economics (NPV/IRR/payback), risk
  register (severity×likelihood), sensitivity (vary ±%), and a small constraint
  solver. Each returns a computed, auditable result the model narrates.
- **Benefits:** converts SCB-002 from "model reasons in prose" to "model fills a
  structured input, engine computes" — the same leap `calculator` gave arithmetic.
  Deterministic, testable, reusable across council roles.
- **Complexity:** Medium (each engine is small + pure; the work is the *catalog* and
  the routing).
- **Priority:** **P0.**
- **Dependencies:** Tool Layer, kernel PRE_ACT (already governs tools), an
  Orchestration router (A4).
- **Expected gain:** SCB-002 62 → 80-85; lifts any decision/financial task.

### A2 — Planning Engine v2 (dependency DAG + plan validators)
- **Purpose:** replace the linear `_pcall` list with a typed plan: steps + dependency
  DAG + preconditions + goal-coverage; expose a Planning CVL domain that rejects a
  cyclic/dangling/uncovered plan at PRE_PLAN.
- **Benefits:** long-horizon reliability; plan failures become *attributable*; closes
  "P5".
- **Complexity:** Large (planner rework touches the agent loop).
- **Priority:** **P1.**
- **Dependencies:** Planning Engine, CVL Planning domain (CVL v2 §5.6), kernel PRE_PLAN
  hook (defined, unwired).
- **Expected gain:** SCB-005 78 → 88.

### A3 — Confidence Calibration subsystem (CVL v3 P2)
- **Purpose:** attach a *calibrated* confidence to every claim; measure ECE against
  Outcome-Clock-judged outcomes; feed calibration back so confidence means something.
- **Benefits:** production triage (act on high-confidence, escalate low); unlocks the
  CVL-v3 confidence×severity decision matrix; is the honest substrate for autonomy.
- **Complexity:** Medium.
- **Priority:** **P1.**
- **Dependencies:** Outcome Clock (exists), CVL, assurance-memory ledger.
- **Expected gain:** cross-cutting; primarily reflection/traceability + safe autonomy,
  +3-5 on judged categories via better self-triage.

### A4 — Cognitive Orchestration Router (task-type → solver)
- **Purpose:** a classifier that recognizes task *shape* (quantitative /
  decision-under-constraints / planning / factual) and routes to the right engine
  (A1/A2) or council mode *before* free-form generation.
- **Benefits:** ensures the toolkit is actually used; removes reliance on the model
  choosing to invoke a tool (it often won't).
- **Complexity:** Medium.
- **Priority:** **P0** (A1 underdelivers without it).
- **Dependencies:** A1, existing discovery/continental_relay routing.
- **Expected gain:** multiplier on A1/A2 (they are inert if not routed to).

### A5 — Automated Cognitive Benchmark harness (SCB-as-code)
- **Purpose:** turn SCB into a repeatable, versioned, CI-runnable suite with rubric
  scoring + a calibration metric; add the missing categories (§6).
- **Benefits:** you cannot reach production quality against a non-repeatable benchmark;
  this makes every other improvement *measurable* and regression-proof.
- **Complexity:** Medium.
- **Priority:** **P0** (gates the credibility of all other gains).
- **Dependencies:** eval infra (exists), a judge (rubric + optional LLM-judge as a
  warnings-only signal).
- **Expected gain:** enables verified progress; no direct score gain but *de-risks* all.

### A6 — Self-consistency / ensemble reasoning (model-limit mitigation)
- **Purpose:** for hard reasoning (SCB-001/003, model-bound), sample N reasoning paths
  and reconcile (majority / consistency-scored) instead of a single greedy pass.
- **Benefits:** the one architectural lever on *fuzzy* reasoning the toolkit can't
  toolify; +variance reduction.
- **Complexity:** Medium (cost: N× inference on a CPU-bound host — gate by task value).
- **Priority:** **P2** (respect the 16k/CPU budget).
- **Dependencies:** runtime kernel (pools), Consistency CVL domain.
- **Expected gain:** SCB-001/003 +3-6, at a latency cost.

---

# 5 CVL Review

**Which validator rejects "this answer"?** No answer was pasted, so this is assessed
against the *failure mode* SCB-002 exhibits.

- If the failure is a **wrong arithmetic step** → `arithmetic` / `expression`
  (deterministic) already reject it. **Covered.**
- If the failure is **right arithmetic, wrong method** (e.g., ignored a cost, wrong
  NPV formula, no sensitivity) → **no validator catches it.** CVL verifies *operations*,
  not *analytic completeness*. **Gap.**
- If the failure is an **overconfident unsupported claim** → **no validator.** **Gap.**

**Proposed new validators (as CVL v2 domain drivers):**
1. **`method_completeness`** (Reasoning domain) — for a task tagged quantitative/
   decision, assert the answer used the expected structured engine (A1) and reported
   its inputs; a bare prose number for a CBA task → REPAIR. *Deterministic via the
   toolkit's audit trail, not judgment.*
2. **`confidence_calibration`** (new Reasoning/Meta driver) — flag unhedged absolutes
   ("definitely", "guaranteed", "100%") on claims with no supporting evidence source;
   warnings-only until calibrated (A3).
3. **`sensitivity_absent`** (Reasoning) — a quantitative recommendation that depends on
   assumptions but reports no range/sensitivity → FLAG.
4. **`plan_wellformed`** (Planning domain) — reject cyclic/dangling/uncovered plans
   (pairs with A2).
5. **`consistency_value_vs_tools`** (Consistency domain) — a number in the answer that
   appears in *no* tool result this session → FLAG (catches fabricated computation).

**Architectural note:** CVL currently verifies *correctness of stated operations*. The
missing class is *sufficiency of method* — which is exactly the CVL-v2 domain model's
purpose and the CVL-v3 "claim needs an assurance case" thesis. These validators are the
bridge.

---

# 6 Benchmark Coverage

**Is the benchmark sufficient? No.** Three structural blind spots:

1. **Two benchmarks measure different things and neither is the target.** eval_suite =
   behavioural regression (does the harness fire) — 48/48 but *cannot* detect a
   confidently-wrong answer. SCB = cognitive quality but **manual, LLM-judged, not in
   CI, not repeatable**. There is no automated cognitive benchmark. **You are flying on
   a regression suite while claiming a quality bar.**
2. **Category coverage is thin (5).** No dedicated **financial reasoning**,
   **decision-under-constraints**, **risk prioritization**, **sensitivity/robustness**,
   **long-horizon planning**, **calibration**, or **adversarial / prompt-injection**
   categories — several of which are exactly the missing capabilities in §3.
3. **No calibration or trace-quality metric.** Accuracy is scored; *calibration* (is
   confidence honest?) and *reasoning-trace quality* (is the method sound, not just the
   answer?) are not — the two metrics that most distinguish a production cognitive OS.

**Recommended new categories:** Financial/Unit-Economics · Decision-Under-Constraints ·
Risk Prioritization · Sensitivity & Robustness · Long-Horizon Planning ·
Confidence-Calibration (ECE/Brier) · Adversarial & Incomplete-Info · Reflection-Quality.
Plus: score every category on **{accuracy, calibration, trace-soundness}**, not just
accuracy.

---

# 7 Roadmap

- **Small (≈1-3 dev-days each):** `calculator`-style single engines from A1 (decision-
  matrix, cost-benefit, unit-economics) as tools; the §5 validators
  `method_completeness`, `consistency_value_vs_tools`; add 2-3 SCB categories to
  eval-as-code (A5 seed).
- **Medium (≈1-2 dev-weeks each):** A4 Orchestration Router; A3 Confidence Calibration
  (wire Outcome Clock → ECE); A5 full automated SCB harness with rubric + calibration
  metric; A6 self-consistency (value-gated).
- **Large (≈3-6 dev-weeks):** A2 Planning Engine v2 (dependency DAG + plan validators +
  agent-loop integration); the full Structured Reasoning Toolkit catalog + constraint
  solver; CVL-v3 assurance-case core if ratified.

**Sequencing:** A5 + A1 + A4 first (measure, build the primitives, route to them) →
A3 (calibrate) → A2 (planning) → A6 (ensemble) → CVL-v3. Rationale: A5 makes gains
*provable*; A1/A4 deliver the largest measurable SCB-002 lift for least risk.

---

# 8 ADR Recommendation

Yes — the shift from control-plane to cognitive-data-plane investment is
architecture-defining. Draft:

> **ADR-0006 — Structured Reasoning Toolkit + Automated Cognitive Benchmark**
> **Status:** Proposed · **Blast radius:** Large
> **Context:** SCB stalls at 81.4 (SCB-002=62, SCB-005=78). Root cause is not the
> harness (48/48 behavioural, governance/audit production-grade) but a missing
> cognitive data plane: structured analysis is done in prose, planning is linear,
> confidence is uncalibrated, and the cognitive benchmark is manual/non-repeatable.
> **Decision:** (1) build a Structured Reasoning Toolkit — deterministic analysis
> engines (decision-matrix, cost-benefit, unit-economics, risk, sensitivity,
> constraint-solve) invoked as governed tools, generalizing the `calculator` pattern;
> (2) add a Cognitive Orchestration Router that routes task-shape → engine before
> free-form generation; (3) make SCB an automated, versioned, CI benchmark scored on
> {accuracy, calibration, trace-soundness} with the missing categories. Planning v2 and
> Confidence Calibration follow as dependent ADRs.
> **Alternatives rejected:** prompt-engineering the model into better analysis
> (non-deterministic, unverifiable); a bigger model (orthogonal, and doesn't fix
> measurement or planning structure).
> **Consequences:** reuses the kernel (tools already governed at PRE_ACT; benchmark
> reuses eval infra); shifts investment to the data plane; makes progress measurable.
> **Verification:** each engine ships `conforms_to()` + eval cases; SCB-as-code shows
> the lift; no engine ships without a benchmark category exercising it.

---

## Challenge to my own conclusions (Article III)

- **"Deterministic tools fix reasoning" is over-claimed.** They fix *structured/
  quantitative* reasoning (SCB-002, financial, decision-matrix). They do **not** lift
  *first-principles* (SCB-001=84) or *incomplete-info* (SCB-003=86) — those are
  model-bound; the only architectural lever there is ensembling (A6) or a stronger
  model. I am NOT claiming the toolkit reaches 90 everywhere.
- **Is the real bottleneck just the 14B model?** Partly — and I say so plainly. But
  three of the five weaknesses (structured analysis, planning structure, calibration,
  benchmark) are **architectural and model-independent**; they would limit even a
  frontier model dropped into this harness. Architecture is the right lever for those.
- **Am I trusting stale SCB numbers?** Yes, with a flag — they are last-known, not
  re-run, because SCB isn't automated (which is finding §6, and A5 fixes the
  meta-problem so this review never has to hedge again).
- **Risk of the toolkit:** a catalog of engines can sprawl (the feature-freeze exists
  for a reason). Mitigation: each engine must be justified by a benchmark category that
  exercises it (A5 gates A1) — no engine without a measured need.
