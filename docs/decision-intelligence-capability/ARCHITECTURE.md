# Decision Intelligence Capability — Architecture

> Companion to [ADR-0012](../adr/ADR-0012-decision-intelligence-capability.md).
> A first-class capability that sits **above** reasoning and turns it into verifiable,
> adaptive, resource-aware decision-making. Reuses `logic/` (ADR-0008),
> `decision_intelligence/` DIF (ADR-0011), and CVL (ADR-0002) — no duplication.

## Layered architecture (Capability → Service → Engine → Tool → Validator)

```mermaid
flowchart TD
    C[DecisionIntelligenceCapability<br/>facade · decide / adapt / learn]
    subgraph Services [Services — stateful orchestrators]
      GS[GoalManagement] --- WS[WorldState] --- CS[Constraint]
      PS[Planning] --- SS[Simulation] --- US[Utility]
      DS[Decision] --- RB[ReviewBoard] --- AS[Adaptation] --- LS[Learning]
    end
    subgraph Engines [Engines — pure · single-responsibility · never call each other]
      GE[Goal] & WE[WorldState] & CE[ConstraintGraph] & AGE[ActionGenerator]
      PE[Planner] & OSE[OutcomeSimulation] & UEE[UtilityEvaluation]
      DSE[DecisionSelection] & DRE[DecisionReview] & CEE[CounterExample]
      APE[AdaptivePlanning] & LE[Learning]
    end
    V[Decision Validation Gate<br/>5 validations]
    subgraph Reused [Reused substrate — NOT re-implemented]
      LOGIC[logic/ · CSP engine] --- DIF[decision_intelligence/ · DIF] --- CVL[cognitive_validation · CVL]
    end
    C --> Services --> Engines
    C --> V
    CEE -. reuses .-> DIF
    CE  -. reuses .-> LOGIC
    V   -. reuses .-> CVL
    V   -. reuses .-> DIF
    DIF -. reuses .-> LOGIC
```

ASCII fallback:

```
Capability (facade)                DecisionIntelligenceCapability.decide/adapt/learn
  └─ Services (10, stateful)       Goal · WorldState · Constraint · Planning · Simulation
       │                           Utility · Decision · ReviewBoard · Adaptation · Learning
       └─ Engines (12, pure)       Goal · WorldState · ConstraintGraph · ActionGenerator ·
            │  (no engine→engine)   Planner · OutcomeSimulation · UtilityEvaluation ·
            │                       DecisionSelection · DecisionReview · CounterExample ·
            │                       AdaptivePlanning · Learning
            └─ Validator            Decision Validation Gate  → integrates CVL + DIF
  reuses ▶ logic/ (ADR-0008) · decision_intelligence/ DIF (ADR-0011) · CVL (ADR-0002)
```

**Rules (enforced structurally):** engines import only `contracts`, `interfaces`, and the
reused substrate — never another engine. Services own engine instances and pass data
between them; services may call services (e.g. Adaptation → Planning). Everything
pluggable (planner/utility/simulator/policy) resolves through `registry.py`.

## Decision sequence

```mermaid
sequenceDiagram
    participant Caller
    participant Cap as Capability
    participant Plan as PlanningService
    participant Sim as SimulationService
    participant Con as ConstraintService
    participant Ut as UtilityService
    participant Dec as DecisionService
    participant RB as ReviewBoardService
    participant Gate as ValidationGate
    Caller->>Cap: decide(DecisionRequest)
    Cap->>Plan: candidates(world, goals, resources)  %% MULTIPLE, never one
    Plan-->>Cap: [ActionCandidate...]
    loop each candidate
      Cap->>Sim: simulate(world, action, horizons)   %% 5/10/20/30 + uncertainty
      Cap->>Con: penalty(projected_world, constraints)
    end
    Cap->>Ut: evaluate_all(+ pareto_front)
    Cap->>Dec: decide(scores, pareto)                 %% rank · reject invalid · choose · explain
    Cap->>RB: review(decision)                        %% counter-example + challenges
    RB-->>Cap: ReviewVerdict (may REJECT)
    Cap->>Gate: validate (constraint·consistency·counterexample·confidence·decision)
    Gate-->>Cap: GateResult
    Cap-->>Caller: DecisionResult (accepted = verdict.ok AND gate.ok)
```

## Adaptive re-planning (minimal patch)

```
world change ─▶ AdaptationService ─▶ AdaptivePlanningEngine.patch
   diff(old,new) → for each plan step: does it touch a changed var?
     yes → regenerate ONLY that step (via PlanningService)   → changed_steps
     no  → keep as-is                                        → kept_steps
   result: PlanPatch (never a full re-plan)
```

## Determinism & LLM-independence

No LLM, no `eval`, no RNG or wall-clock in the decision path. A `DecisionRequest` + a fixed
set of registered plugins ⇒ byte-identical `DecisionResult` (deterministic replay). The
simulator's uncertainty is a closed-form function of horizon × (1 − confidence), not
sampling. Verified by `test_dic_integration` / `test_dic_stress` / `test_dic_simulation`.

## Tests

| File | Type |
|---|---|
| `backend/tests/test_dic_unit.py` | unit (per engine) |
| `backend/tests/test_dic_integration.py` | integration + acceptance criteria |
| `backend/tests/test_dic_scenario.py` | scenario (end-to-end) |
| `backend/tests/test_dic_simulation.py` | simulation properties |
| `backend/tests/test_dic_stress.py` | stress + benchmark |

Reused-subsystem suites (`test_logic`, `test_di_*`, `test_decision`) stay green —
backward compatibility.
