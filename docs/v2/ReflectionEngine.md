# Reflection Engine

> Closes the loop: every completed (or failed) mission triggers structured learning
> that updates memory and can evolve skills, agents, and workflows.
> Parent: [Architecture](Architecture.md) · Built on `agentic_workflow.reflect`,
> `lesson_synthesis.py`, `reinforcement.py`, `calibration.py`.

## 1. Principle
An OS that doesn't learn is just a runtime. The Reflection Engine runs on the
`mission.completed` / `mission.failed` event and turns raw mission history into
durable, retrievable knowledge — and, when warranted, into **changes to the system
itself** (skills, agent config, workflow).

## 2. Reflection questions (the protocol)
For each finished mission the engine answers, with evidence from the mission log,
timeline, and KG subgraph:
1. **What worked?** → successful strategies (long-term memory)
2. **What failed?** → failure cases + root cause
3. **What should be remembered?** → promote working-memory items to long-term
4. **What should be forgotten?** → tombstone stale/contradicted nodes
5. **Should any Skill evolve?** → propose SKILL.md edits / new skill
6. **Should any Agent evolve?** → propose authority/role/prompt tuning
7. **Should the Workflow change?** → propose DAG/template changes

## 3. Output object
```jsonc
{
  "mission_id":"OX-..",
  "summary":"string",
  "worked":["..."], "failed":["..."],
  "remember":[{"node":"kg:..","reason":".."}],
  "forget":[{"node":"kg:..","reason":".."}],
  "proposals":[                          // evolution proposals — GOVERNED, not auto-applied
    {"target":"skill:web-dashboard-builder","change":"add trigger ...","risk":"low"},
    {"target":"agent:scout","change":"raise authority 0.5→0.6","risk":"medium"},
    {"target":"workflow:news_report","change":"add verify step","risk":"low"}
  ],
  "calibration":{"agent":"analyst","predicted":0.8,"actual":1.0}, // feeds calibration.py
  "ts":..
}
```

## 4. Memory updates (automatic, safe)
- **Remember/forget** apply automatically to memory (promote / tombstone) — these are
  reversible and low-risk.
- **Calibration** updates each council member's confidence model (`calibration.py`)
  from predicted-vs-actual outcomes.
- Lessons + patterns are written as **versioned KG nodes** (`lesson_synthesis.py`),
  linked `learned_from` → the mission.

## 5. Evolution proposals (governed, never silent)
Changes to skills/agents/workflows are **proposals**, routed through the
[Governance Engine](Architecture.md#5-cross-cutting-kernels):
```
reflection.proposal → risk score → (auto-apply if low + reversible)
                                  → human approval gate if medium/high/irreversible
                                  → audit log → applied → next mission benefits
```
This satisfies "agents evolve" while honoring **"no destructive action without
operator approval."** Self-modification is opt-in per target via `reflection.yaml`
(`auto_apply: [skill.triggers]`, everything else gated).

## 6. Interface (DI)
```python
class ReflectionEngine:
    def __init__(self, memory: MemoryService, governance: GovernanceGate,
                 runtime: RuntimeOrchestrator, registry: PluginRegistry,
                 bus: EventBus, telemetry: Telemetry): ...
    def run(self, mission: Mission) -> Reflection: ...
    def apply(self, proposal: Proposal) -> ApplyResult: ...   # via governance
```
Subscribes to `mission.completed`/`mission.failed`; emits `mission.reflected`,
`reflection.proposal`, `skill.evolved`, `agent.evolved`, `workflow.evolved`.

## 7. Compatibility
- Wraps the existing `agentic_workflow.reflect` and OX cognitive modules; when the
  `reflection_engine` flag is off, V1 reflection (if any) runs unchanged.
- Proposals default to **gated** — V2 ships learning-on, self-modification-off until
  the operator opts in per target.
