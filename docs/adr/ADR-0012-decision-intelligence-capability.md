# ADR-0012 — Decision Intelligence Capability (verifiable, adaptive, resource-aware decisions)

**Status:** Accepted (implementing) · **Date:** 2026-07-18 · **Blast radius:** Large (new first-class capability)
**Constitution:** Articles II (root-cause/DRY), IV (capability-first), VIII (deterministic, no `eval`, model-free), IX (SOLID/stable interfaces), XI (verify)
**Under:** ADR-0007 (Capability-first: Capability→Service→Engine→Tool→Validator)
**Reuses:** ADR-0008 (Cognitive Logic Engine, `backend/logic/`), ADR-0011 (Decision Intelligence Framework, `backend/decision_intelligence/`), ADR-0002 (CVL, `backend/cognitive_validation.py`)
**Relates:** ADR-0003 (Cognitive Kernel), Epic Trust (evidence-first)

## Context

The platform can *reason* (logic engine) and can make a *verifiable single decision over a
constraint model* (DIF). It cannot yet do **decision-making as a capability**: hold goals,
model world state, generate *multiple* resource-aware plans, simulate their outcomes over
time, weigh them by configurable objectives, choose and explain, have the choice
challenged by a review board, adapt a plan when the world changes without re-planning from
scratch, and learn from outcomes. That is a distinct capability that **sits above
reasoning**.

The mission's own rule governs the design: *reuse before rebuild; never duplicate
reasoning components; preserve backward compatibility; architecture quality over speed.*

## Decision

Introduce a **first-class capability** at `backend/capabilities/decision_intelligence/`
following the canonical stack **Capability → Service → Engine → Tool → Validator**.

### Reuse map (no duplication)

| Requirement | Reused subsystem | New wrapper in this capability |
|---|---|---|
| Reasoning / constraint substrate | `logic/` (ADR-0008) | Constraint Graph Engine |
| Constraint analysis, verification, confidence | `decision_intelligence/` DIF (ADR-0011) | Constraint Service, Decision Review Engine |
| Counter-example search | DIF `counter_example` | Counter Example Engine (thin adapter) |
| Final validation gate | CVL `cognitive_validation.validate()` | Decision Validation Gate (validator layer) |

DIF stays at `backend/decision_intelligence/` unchanged (its ADR-0011 tests stay green —
**backward compatibility**). The capability imports it (`import decision_intelligence`); the
name echo is intentional — DIF is the *verification engine inside* the broader capability.

### Genuinely new layers (built here)

Goals · World State · Planning (multi-candidate, resource-aware) · Simulation
(deterministic multi-horizon) · Utility (weighted / Pareto / penalties) · Decision
selection · Review Board · Adaptive Planning (minimal patch) · Learning.

### Layering rules (Article IX)

```
Capability (facade)                    DecisionIntelligenceCapability.decide()
   └─ Services (stateful orchestrators) Goal, WorldState, Constraint, Planning,
        │                               Simulation, Utility, Decision, ReviewBoard,
        │                               Adaptation, Learning
        └─ Engines (pure, single-resp.) 12 engines, each a stable Protocol
             └─ Validators               Decision Validation Gate (CVL + DIF)
```

- **Engines are pure and single-responsibility.** An engine imports only `contracts`,
  `interfaces`, and reused *substrate* (logic/DIF/CVL) — **never another engine**.
- **Engines communicate only through Services.** A service owns engine instances and
  passes data between them; services may call services; the capability wires services.
- **Everything is a stable interface** (`engines/interfaces.py` Protocols) so planners,
  utilities, simulators, and decision policies are **pluggable** (`registry.py`).

### Planner contract (hard requirement)

A planner **never returns one action**. It returns ≥1 `ActionCandidate`, each carrying
`expected_benefits`, `expected_costs`, `required_resources`, `risks`, `dependencies`,
`estimated_confidence`. Enforced by the Engine interface and tested.

### Determinism & LLM-independence (Article VIII)

The entire capability is **model-free** and **deterministic**: no LLM, no `eval`, no
wall-clock or RNG in the decision path (learning may attach timestamps as metadata only).
A `DecisionRequest` + a fixed set of registered plugins yields a byte-identical
`DecisionResult` — **deterministic replay**. Simulator uncertainty is a deterministic
function of horizon, not sampling.

### Validation (integrate CVL, don't fork it)

The Decision Validation Gate composes five checks before a decision is accepted —
**Constraint** (DIF verifier), **Consistency** (CVL `validate()` over the rendered
decision + world state), **Counterexample** (DIF counter-example / Review Board),
**Confidence** (threshold on the computed confidence), **Decision** (structural: a valid,
selected, explained candidate exists). No new CVL validator *plugins* are written
(honors ADR-0003's validator-development pause); we call CVL's stable API.

## Consequences

**Positive** — a real decision capability with clean seams; multiple planners / utilities /
simulators / policies via registry; deterministic replay; RL-ready (policies + learning
ledger are pluggable); reuses the proven reasoning/verification/validation stack with zero
duplication; DIF/logic/CVL untouched (backward compatible).

**Costs / limits (honest)**
- Large surface (10 services, 12 engines) — mitigated by strict single-responsibility and
  stable interfaces; each piece is independently testable.
- The deterministic simulator is a **transparent model** (effect application + per-variable
  trend/decay + horizon-widening uncertainty), not a learned world model. It is pluggable;
  a learned simulator can replace it without touching callers.
- Not wired into the RC-1 agent runtime (Epic Trust freeze). The capability exposes a
  `decide()` API + a ready tool schema; runtime registration is a deliberate follow-up.

## Verification (Article XI)

`backend/tests/test_dic_*.py`: unit (per engine), integration (service wiring), scenario
(end-to-end decisions incl. reject-invalid + explanation), simulation (multi-horizon
determinism, uncertainty widens monotonically), stress (many candidates / large state),
benchmark. Asserts every acceptance criterion: LLM-independent, deterministic replay,
multiple planners/utilities/simulators, plugin policies, backward compatibility (DIF/logic/
CVL suites still green), no duplication.

## Follow-ups

1. Register a `decide` capability tool in `BUILTIN_TOOLS` (post-freeze).
2. Ship an RL decision policy plugin using the Learning ledger.
3. Replace the transparent simulator with a learned one behind the same interface.
