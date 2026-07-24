# Decision Intelligence Capability

A first-class SkynetClaw capability that sits **above reasoning** and turns it into
**verifiable, adaptive, resource-aware decision-making**.

- Design: [ADR-0012](../../../docs/adr/ADR-0012-decision-intelligence-capability.md)
- Docs: [Architecture](../../../docs/decision-intelligence-capability/ARCHITECTURE.md) ·
  [Capability Spec](../../../docs/decision-intelligence-capability/CAPABILITY_SPEC.md) ·
  [Service Contracts](../../../docs/decision-intelligence-capability/SERVICE_CONTRACTS.md) ·
  [Engine Interfaces](../../../docs/decision-intelligence-capability/ENGINE_INTERFACES.md) ·
  [Developer Guide](../../../docs/decision-intelligence-capability/DEVELOPER_GUIDE.md)

## Layout (Capability → Service → Engine → Tool → Validator)

```
capabilities/decision_intelligence/
  capability.py        facade: decide() / adapt() / learn()
  contracts.py         shared dataclasses (single source of truth)
  registry.py          pluggable planners / utilities / simulators / policies
  engines/             12 pure, single-responsibility engines (+ interfaces.py Protocols)
  services/            10 stateful orchestrators
  validators/          Decision Validation Gate (integrates CVL + DIF)
```

## Reuse (never duplicated)

- `logic/` (ADR-0008) — the CSP reasoning substrate (Constraint engine).
- `decision_intelligence/` DIF (ADR-0011) — counter-example / verification (Counter Example engine).
- `cognitive_validation.py` CVL (ADR-0002) — the consistency validator (Validation Gate).

## Quick start

```python
from capabilities.decision_intelligence import (
    DecisionIntelligenceCapability, DecisionRequest, Goal, GoalDirection,
    ResourceVector, ActionCandidate)

cap = DecisionIntelligenceCapability()
req = DecisionRequest(
    world={"revenue": 100.0, "cost": 50.0},
    goals=[Goal("grow", "revenue", GoalDirection.MAXIMIZE, weight=3.0),
           Goal("lean", "cost",    GoalDirection.MINIMIZE, weight=1.0)],
    available_resources=ResourceVector.of({"budget": 100, "effort": 10}),
    seed_actions=[ActionCandidate("seo", "Organic SEO", effects=(("revenue", 1.5),),
                                  required_resources=ResourceVector.of({"effort": 4}),
                                  estimated_confidence=0.8)],
    constraints_text="cost <= 200")
r = cap.decide(req)
print(r.accepted, r.decision.chosen.id, r.decision.explanation)
```

## Guarantees

Model-free · deterministic replay · multiple planners/utilities/simulators/policies ·
plugin decision policies (RL-ready) · reuses (never duplicates) the reasoning/verification/
validation stack · backward compatible.

## Tests

```
python -m pytest backend/tests/test_dic_*.py -q
```
