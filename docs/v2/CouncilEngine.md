# Council Engine

> Converts the flat 14-agent roster into a **hierarchical decision body** that plans,
> deliberates, votes, and reviews — per mission.
> Parent: [Architecture](Architecture.md) · Built on `agent_council.py`, `commander.py`,
> the existing roster in `system_graph.AGENT_ROSTER`.

## 1. From flat agents to hierarchy
V1 agents are peers selected ad-hoc. V2 organizes them into a chain of authority so
decisions have an owner, dissent is recorded, and escalation is explicit:
```
Commander            supreme intent · verify · override          (elite_commander)
   ↓
Governor             presides · arbitrates · enforces governance  (governor)
   ↓
Council (advisors)   Architect · Strategist · Analyst · Scout ·
                     Skeptic · Forecaster · Auditor · Storyteller
   ↓
Workers              executor + tool-wielding sub-agents
   ↓
Execution → Review → Memory Update
```
The roster already exists (`AGENT_ROSTER`); V2 assigns each a **tier + authority**
rather than inventing new agents.

## 2. Council member object
```jsonc
{
  "id": "analyst",
  "role": "evidence · analysis · facts",
  "tier": "advisor",                 // commander|governor|advisor|worker
  "authority": 0.6,                  // weight in voting / veto power
  "can_veto": false,                 // Skeptic & Governor: true
  "confidence": 0.0,                 // self-rated on current opinion (calibration.py)
  "opinion": "string",               // position on the current question
  "reasoning": "string",             // why (audited)
  "dependencies": ["scout","analyst"],// whose output it needs first
  "vote": null                       // approve|reject|abstain + weight
}
```
Confidence is fed by the existing `calibration.py`; reasoning/opinions are stored in
council memory and indexed into the [Knowledge Graph](KnowledgeGraph.md).

## 3. Deliberation protocol
1. **Convene** — Governor selects relevant members for the mission objective
   (reuses skill/agent selection logic; Scout/Analyst for research, Architect for
   design, Forecaster for risk, Skeptic always).
2. **Gather** — members with no dependencies produce opinions first; dependency
   order is a small DAG (same engine as the mission graph).
3. **Debate** — opinions cross-referenced; Skeptic runs the `shadow_gate`
   (anti-hallucination / anti-loop) against each claim.
4. **Vote** — weighted by `authority`; `can_veto` members can block. Ties escalate
   to Governor, then Commander.
5. **Decide** — produces a **Plan** (the mission graph) + a recorded rationale.
6. **Review** (post-execution) — Auditor + Skeptic score the result against
   success criteria; feeds the [Reflection Engine](ReflectionEngine.md).

## 4. Interfaces (DI)
```python
class CouncilMember(Protocol):
    id: str; tier: str; authority: float; can_veto: bool
    def opine(self, ctx: MissionContext) -> Opinion: ...
    def vote(self, proposal: Plan) -> Vote: ...

class CouncilEngine:
    def __init__(self, members: list[CouncilMember], bus: EventBus,
                 governance: GovernanceGate, runtime: RuntimeOrchestrator,
                 memory: MemoryService, telemetry: Telemetry): ...
    def convene(self, mission: Mission) -> Council: ...
    def deliberate(self, mission: Mission) -> Plan: ...
    def review(self, mission: Mission, result) -> ReviewReport: ...
```
Members are **plugins**: a member is any object implementing `CouncilMember`,
discovered from a registry — adding "Negotiator" = drop a class, no engine change.
Each member calls models **only through the Runtime Orchestrator** (injected), never
a hardcoded base URL.

## 5. Events
`council.convened`, `council.opinion`, `council.debate`, `council.vote`,
`council.decided`, `council.vetoed`, `council.review`. The dashboard renders these as
the live "Thinking Process" panel.

## 6. Compatibility
- Wraps `agent_council.py` / `commander.py`; the existing council run becomes the
  `advisor`-tier path. Tiers/authority are config (`council.yaml`), so the hierarchy
  is tunable without code edits.
- Behind the `council_engine` flag; when off, V1 flat selection runs unchanged.
- Governance is **not** a council member — it wraps the council (every vote and the
  final plan pass `GPS2Gate`).
