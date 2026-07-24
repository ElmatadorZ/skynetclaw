# SkynetClaw Capability Model

**Version:** 0.1 (DRAFT — design only) · **Date:** 2026-07-13 · **Owner:** ElmatadorZ
**Governs:** ADR-0007 (Capability-first Architecture). **Status:** the master registry
of SkynetClaw's cognitive capabilities. Nothing is built until it is a node here.

This is the "cognitive periodic table" of SkynetClaw — a **projection** of the deeper
foundation, not the foundation itself. It is a **realization map** (the five-layer
Capability → Service → Engine → Tool → Validator per capability), a **maturity
dashboard**, and the **benchmark index**. It grows from ~40 nodes today to 100+ without
re-architecture.

> **v0.2 reconciliation (2026-07-13).** Three root specs now underlie this document and
> take precedence where they overlap:
> - **[COGNITIVE_PRIMITIVES.md](COGNITIVE_PRIMITIVES.md)** — the base layer. Capabilities
>   *compose from* primitives; the sub-capability leaves below are shorthand for their
>   primitive composition.
> - **[CAPABILITY_DEPENDENCY_GRAPH.md](CAPABILITY_DEPENDENCY_GRAPH.md)** — the true
>   structure is a **graph, not the tree** drawn in §2. This model is a per-family
>   *view* of the CDG; the CDG is the single source of truth for dependencies.
> - **[MATURITY_MODEL.md](MATURITY_MODEL.md)** — the `present/partial/missing` labels in
>   §3 are **hand-estimates pending computation**. Real maturity is
>   `computed(Benchmark, Validator, Coverage, Reliability)` with a dependency ceiling,
>   in five bands (Missing/Emerging/Partial/Present/Trusted). Treat §3's labels as a
>   provisional snapshot to be replaced by the computed score.

---

## 1. Reading this model

Each capability row carries:

| Field | Meaning |
|---|---|
| **Capability** | the stable cognitive noun |
| **Maturity** | `present` (built + assured) · `partial` (exists, unassured/scattered) · `missing` |
| **Realization** | its five-layer collapse: S=Service · E=Engine · T=Tool · V=Validator (`—` = layer collapsed/absent) |
| **Hook** | the kernel hook where its Validator runs (SPEC §5) |
| **Benchmark** | the SCB category that measures it (`—` = no coverage yet — a blind spot) |

**Layer-collapse rule (ADR-0007):** simple capabilities omit the Service layer; only
capabilities with routing / lifecycle / multiple engines earn a Service.

---

## 2. The Capability Tree

```
SkynetClaw Cognition
├── Reasoning
│   ├── Arithmetic
│   ├── Expression (multi-term)
│   ├── Algebraic / Symbolic
│   ├── Logic (propositional / contradiction)
│   ├── Causal
│   └── Quantitative (multi-step)
├── Analysis                     ◀── realized by the CAF (ADR-0006)
│   ├── Decision (weighted-criteria / expected-value)
│   ├── Cost–Benefit
│   ├── Sensitivity
│   ├── Scenario
│   ├── Risk (severity × likelihood)
│   ├── Financial / Unit-Economics (NPV / IRR / payback)
│   └── Resource Allocation
├── Optimization
│   ├── Constraint Solve
│   ├── Linear / Assignment
│   └── Trade-off (Pareto)
├── Planning
│   ├── Decomposition
│   ├── Dependency-DAG
│   ├── Scheduling
│   └── Precondition / Goal-coverage
├── Forecasting
│   ├── Trend / Projection
│   ├── Scenario-Forecast
│   └── Monte-Carlo / Distributional
├── Verification (Assurance)     ◀── realized by CVL → CAE (ADR-0002/04/05)
│   ├── Arithmetic-check · Expression-check
│   ├── Method-completeness
│   ├── Citation / Warrant
│   ├── Consistency
│   └── Plan-wellformedness
├── Memory
│   ├── Recall · Persist
│   └── Provenance
├── Knowledge
│   ├── Retrieval
│   ├── Grounding
│   └── Fact-check
├── Metacognition
│   ├── Confidence-Calibration
│   ├── Reflection-quality
│   └── Self-consistency
├── Safety
│   ├── Secret-leak · PII
│   └── Unsafe-act
├── Communication
│   ├── Relevance · Language-match · Format
├── Governance
│   ├── Policy · Permission · Escalation
└── Orchestration
    ├── Task-shape routing
    └── Council deliberation
```

---

## 3. Realization & maturity (the gap map)

### Reasoning
| Capability | Maturity | Realization (S·E·T·V) | Hook | Benchmark |
|---|---|---|---|---|
| Arithmetic | **present** | E `safe_math` · T `calculator` · V `arithmetic` | PRE_VALIDATE | SCB-002 |
| Expression (multi-term) | **present** | E `safe_math` · T `calculator` · V `expression` | PRE_VALIDATE | SCB-002 |
| Algebraic / Symbolic | missing | — | — | — |
| Logic | missing | V `logic` (planned) | PRE_COMMIT | SCB-001 (partial) |
| Causal | missing | — | — | — |
| Quantitative (multi-step) | **partial** | (prose today; CAF target) | PRE_COMMIT | SCB-002 |

### Analysis  — realized by the **Cognitive Analysis Framework (CAF)**
| Capability | Maturity | Realization | Hook | Benchmark |
|---|---|---|---|---|
| Decision | missing | S `DecisionService` · E `DecisionEngine` · T `decision_matrix` · V `decision_wellformed` | PRE_ACT/COMMIT | *new: Decision* |
| Cost–Benefit | missing | E `CBAEngine` · T `cost_benefit` · V `cba_complete` | PRE_COMMIT | *new: Financial* |
| Sensitivity | missing | E `SensitivityEngine` · T `sensitivity` · V `sensitivity_absent` | PRE_COMMIT | *new: Robustness* |
| Scenario | missing | E `ScenarioEngine` · T `scenario` | PRE_COMMIT | *new: Scenario* |
| Risk | missing | E `RiskEngine` · T `risk_register` · V `risk_ranked` | PRE_COMMIT | *new: Risk* |
| Financial / Unit-Economics | missing | E `FinanceEngine` (NPV/IRR/payback) · T `unit_economics` · V `finance_sane` | PRE_COMMIT | *new: Financial* |
| Resource Allocation | missing | S `AllocationService` · E `AllocEngine` · T `allocate` | PRE_ACT | *new: Allocation* |

### Optimization
| Capability | Maturity | Realization | Hook | Benchmark |
|---|---|---|---|---|
| Constraint Solve | missing | S `OptService` · E `ConstraintEngine` · T `solve_constraints` · V `solution_feasible` | PRE_ACT | *new: Constraints* |
| Linear / Assignment | missing | E `LPEngine` · T `optimize` | PRE_ACT | *new: Optimization* |
| Trade-off (Pareto) | missing | E `ParetoEngine` | PRE_COMMIT | *new: Optimization* |

### Planning  — realized by **Planning Engine v2** (dependent ADR)
| Capability | Maturity | Realization | Hook | Benchmark |
|---|---|---|---|---|
| Decomposition | **partial** | E planner `_pcall` (linear) | PRE_PLAN | SCB-005 |
| Dependency-DAG | missing | E `PlanDAGEngine` · V `plan_wellformed` | PRE_PLAN | SCB-005 |
| Scheduling | missing | E `SchedulerEngine` | PRE_PLAN | *new: Long-horizon* |
| Precondition / Goal-coverage | missing | V `goal_coverage` | PRE_PLAN | SCB-005 |

### Forecasting
| Capability | Maturity | Realization | Hook | Benchmark |
|---|---|---|---|---|
| Trend / Projection | missing | E `TrendEngine` · T `forecast` | PRE_COMMIT | *new: Forecast* |
| Scenario-Forecast | **partial** | Forecaster council role (prose) | — | *new: Forecast* |
| Monte-Carlo / Distributional | missing | E `MonteCarloEngine` | PRE_COMMIT | *new: Forecast* |

### Verification (Assurance) — realized by **CVL → CAE**
| Capability | Maturity | Realization | Hook | Benchmark |
|---|---|---|---|---|
| Arithmetic/Expression-check | **present** | V `arithmetic`,`expression` | PRE_VALIDATE | SCB-002 |
| Method-completeness | missing | V `method_completeness` | PRE_COMMIT | SCB-002 |
| Citation / Warrant | **partial** | V `warrant_check` (unmigrated) | PRE_COMMIT | *new: Grounding* |
| Consistency | missing | V `consistency_value_vs_tools` | PRE_COMMIT | SCB-004 |
| Plan-wellformedness | missing | V `plan_wellformed` | PRE_PLAN | SCB-005 |

### Memory · Knowledge · Metacognition · Safety · Communication · Governance · Orchestration
| Capability | Maturity | Realization | Hook | Benchmark |
|---|---|---|---|---|
| Memory: Recall/Persist | **present** | S `kernel_memory` · V `recall_consistency`(planned) | PRE_COMMIT | *new: Memory* |
| Memory: Provenance | missing | V `provenance` | PRE_COMMIT | — |
| Knowledge: Retrieval | **partial** | T `web_search`,`search_obsidian` | PRE_ACT | *new: Grounding* |
| Knowledge: Grounding/Fact-check | missing | V `knowledge_grounded` (warnings-only) | PRE_COMMIT | *new: Factuality* |
| Metacog: Confidence-Calibration | **missing (designed)** | S `CalibrationService` (CVL v3 P2) | PRE_COMMIT | *new: Calibration* |
| Metacog: Reflection-quality | **partial** | reflect phase (unscored) | — | *new: Reflection* |
| Metacog: Self-consistency | missing | E `EnsembleEngine` | — | SCB-001/003 |
| Safety: Secret-leak/PII | **present** (secret) | V `secret_leak` | PRE_RESPONSE | *new: Safety* |
| Safety: Unsafe-act | **partial** | S GPS-2 / shadow gate | PRE_ACT | *new: Safety* |
| Communication | missing | V `relevance`,`language_match`,`format` | PRE_RESPONSE | *new: Communication* |
| Governance: Policy/Permission | **present** | S `kernel_policy` · GPS-2 · operator role | PRE_ACT | governance evals |
| Orchestration: Task-routing | **partial** | S `continental_relay`/`discovery` | — | *new: Routing* |

---

## 4. What the gap map shows (summary)

- **present:** ~9 capabilities — almost all in the **control plane** (governance,
  safety-secret, memory, arithmetic verification). Confirms the review's thesis.
- **partial:** ~9 — real but unassured/scattered (quantitative, planning-decomposition,
  citation, retrieval, reflection, routing).
- **missing:** ~22 — overwhelmingly the **Analysis / Optimization / Forecasting /
  Metacognition** families — i.e. the **cognitive data plane**. This is the growth
  frontier, and the CAF (ADR-0006) is its first tranche.
- **benchmark blind spots:** every `—`/`*new*` in the Benchmark column is a category
  the Benchmark OS must add (§ Benchmark OS spec). Today's SCB covers ~5 of ~15 needed.

---

## 5. Invariants of the model

1. A capability is **not** its tool. The row is stable; its Engine/Tool may change.
2. A capability MUST declare a Validator (its assurance) and a Benchmark (its
   measurement) before it graduates to `present`. **No capability is "done" until it is
   assured and measured** — this is the anti-blind-growth rule, inherited from CVL v2/v3.
3. Maturity only advances `missing → partial → present` when the Validator is green
   **and** the Benchmark category exists and passes its bar.
4. The model is rendered live in Intel (future): the gap map becomes a dashboard.
