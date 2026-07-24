# Cognitive Analysis Framework (CAF) — Architecture & Interface Specification

**Version:** 0.1 (DRAFT — design only, no code) · **Date:** 2026-07-13 · **Owner:** ElmatadorZ
**Realizes:** the **Analysis** capability family (Capability Model §2). **Governs:**
ADR-0006. **Under:** ADR-0007 (Capability-first). **Was:** "A1 Structured Reasoning
Toolkit" — renamed because it is a *framework of thinking*, not a bag of utilities.

---

## 1. Purpose & position

The benchmark review found the system performs structured analysis (cost-benefit,
decision, sensitivity, financial) in **free-form prose** — non-deterministic and
unverifiable — which is the primary cause of SCB-002 = 62. CAF is the **Service +
Engine layer** for the Analysis family: a plugin framework of **deterministic analysis
engines** the agent invokes as governed tools, each returning a computed, auditable
result with its full computation trace.

CAF is to *analysis* what `safe_math`/`calculator` is to *arithmetic* — the same
proven pattern (offload a fragile model capability to a deterministic engine),
generalized to a family, under the five-layer hierarchy.

```
Analysis (Capability family)
        ↓
  AnalysisService        ← CAF: routing, plugin registry, case lifecycle, method selection
        ↓
  AnalysisEngine (plugin) ← Decision · CostBenefit · Sensitivity · Scenario · Risk ·
                            Finance · Optimization · Forecast · Constraint · Allocation
        ↓
  Analysis Tool           ← the schema'd, PRE_ACT-governed surface the model calls
        ↓
  Analysis Validator      ← CVL/CAE driver: method-completeness, sensitivity-absent, …
```

Every analysis type is a **plugin** (Open-Closed): a new analysis = a new engine +
tool schema + validator, registered — never a framework change.

---

## 2. Design principles

1. **Deterministic core.** An engine computes; it never calls the model. Reproducible,
   testable, cheap.
2. **Structured in, structured out, trace attached.** The engine consumes a typed
   request and returns a typed result **plus its computation trace** — the trace is
   what the Validator (`method_completeness`) and the audit spine consume. Analysis
   becomes auditable, not narrated.
3. **The model's job shrinks to framing.** The model extracts the *inputs* (options,
   criteria, cash-flows, constraints) from the task and narrates the *result*. The
   *computation* leaves the model entirely — where its errors live.
4. **Governed like any tool.** Analysis tools pass the kernel PRE_ACT hook; results
   pass PRE_COMMIT validators. CAF adds no kernel primitives.
5. **Routed, not hoped-for.** The Cognitive Orchestration Router (dependent, ADR-0006
   §Roadmap) recognizes task-shape and *routes* to CAF before free-form generation —
   because a 14B model will often not choose the tool itself.
6. **Layer-collapse.** A simple engine (cost-benefit) needs no dedicated Service; it
   registers directly under the shared `AnalysisService`. Only families with real
   routing/lifecycle (Optimization with solver back-ends) earn a sub-Service.

---

## 3. Plugin catalog (each an AnalysisEngine)

| Plugin | Computes | Key inputs | Validator |
|---|---|---|---|
| **Decision** | weighted-criteria / expected-value ranking (AHP-lite) | options, criteria, weights, scores | `decision_wellformed` (weights sum≈1, all scored, no dominated pick) |
| **CostBenefit** | NPV of benefits − costs, ratio, break-even | cost/benefit streams, horizon, rate | `cba_complete` (all named costs included) |
| **Finance / Unit-Economics** | NPV, IRR, payback, margin, LTV/CAC | cash-flows, rate, unit inputs | `finance_sane` (rate>−1, sign checks) |
| **Sensitivity** | vary each assumption ±Δ → output range, tornado | base model + assumptions + Δ | `sensitivity_absent` (recommendation reports a range) |
| **Scenario** | best/base/worst (+ custom) outcomes | scenario definitions | — |
| **Risk** | severity × likelihood ranking, exposure | risk register | `risk_ranked` (ordered, no unranked risk) |
| **Optimization / Constraint** | feasible/optimal allocation under constraints | variables, objective, constraints | `solution_feasible` (constraints satisfied) |
| **Forecast** | trend/projection, distribution | series, method, horizon | — |
| **Resource Allocation** | assignment / budget split | resources, demands, limits | `allocation_valid` |

Ship order follows the Capability Model maturity + a Benchmark category existing for
each (ADR-0006).

---

## 4. Interface Specification (contracts — ABI, not code)

```
# The unit of work
AnalysisRequest:
  { type,                # "decision" | "cost_benefit" | "sensitivity" | ...
    inputs,             # engine-specific typed payload (schema per plugin)
    context }           # task id, correlation id (kernel D2), workspace

AnalysisResult:
  { type, value,        # the headline output (ranking / NPV / range …)
    detail,             # structured breakdown (per-option scores, per-year NPV …)
    trace,              # the ordered computation steps — the auditable record
    assumptions,        # what the engine took as given (feeds Sensitivity + calibration)
    confidence }        # deterministic engines = 1.0; report input-uncertainty if modelled

# The plugin contract (Open-Closed)
AnalysisEngine (Protocol):
  type          : str
  input_schema  : JSONSchema                 # drives the Tool surface + validation
  applicable(request) -> bool
  compute(request) -> AnalysisResult         # deterministic, never calls the model
  conforms_to() -> {ok, checks}              # A6: an engine is 'done' only when green

# The Service
AnalysisService:
  register(engine)                           # plugin registration
  select(task_shape) -> engine | None        # method selection (used by the Router)
  run(AnalysisRequest) -> AnalysisResult     # lifecycle + audit emission
  # emits an audit-spine event per run (reuses kernel_events); result → PRE_COMMIT validators
```

**Boundary contracts (what CAF reuses, unchanged):**
- **Tool layer / kernel:** each engine is exposed as one governed tool (schema =
  `input_schema`); the tool call passes PRE_ACT like any other.
- **CVL/CAE:** the plugin's Validator is a domain driver at PRE_COMMIT; a quantitative
  answer with *no* CAF trace for a task that demanded analysis → `method_completeness`
  REPAIR.
- **Audit spine:** `AnalysisService.run` emits a `cognitive.analysis` event carrying
  the trace id — analysis is on the black-box recorder.
- **Calibration (future):** `AnalysisResult.assumptions` + Outcome Clock feed the
  Confidence-Calibration capability.

---

## 5. Runtime lifecycle of one analysis

```
Task → Router detects shape (e.g. "which option?") 
     → AnalysisService.select → engine
     → model extracts inputs → AnalysisRequest
     → engine.compute (deterministic) → AnalysisResult (+trace)
     → PRE_COMMIT: method_completeness / sensitivity_absent validate the result
     → model narrates the RESULT (not the computation)
     → audit spine records {request, result.trace, decision}
```

The model touches **framing and narration**; the **computation and its assurance** are
deterministic. That division is the whole point.

---

## 6. Metrics (per engine, feeding the Benchmark OS)

- **Correctness:** engine output vs golden answer on its benchmark category (should be
  ~100% — it is deterministic).
- **Adoption:** fraction of applicable tasks where the engine was actually invoked (the
  Router's KPI — a great engine never called is worthless).
- **Method-completeness rate:** fraction of quantitative answers that carried a CAF
  trace (the anti-prose metric).
- **Downstream lift:** SCB-002 / Financial / Decision category score before vs after.

---

## 7. Non-goals

- No engine calls the model (determinism is the value).
- No new kernel primitives (reuse hooks/tools/validators/audit).
- Not every analysis ships at once — gated by a benchmark category existing (ADR-0006).
- CAF does not *decide*; it *computes and assures*. The agent/council still owns the
  judgment call, now on a correct computed basis.

---

## 8. Open questions

1. **Input extraction reliability.** The model must map a messy task → a clean
   `AnalysisRequest`. If it mis-frames, the engine computes the wrong thing correctly.
   Mitigation: the Validator checks input *completeness*; the Router may confirm the
   frame. This is the residual model-dependency and must be measured.
2. **Engine granularity.** Decision vs Cost-Benefit vs Finance overlap — one
   configurable engine or several? Lean several (clear schemas), share primitives
   (safe_math, NPV) underneath.
3. **Service vs sub-Service.** Does Optimization need its own Service (solver
   back-ends) or a plugin under AnalysisService? Decide at that plugin's ADR.
