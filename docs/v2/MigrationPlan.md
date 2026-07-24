# Migration Plan

> How to get from V1 to V2 with **no breaking changes**: every engine ships behind a
> feature flag, defaults off, and the V1 path stays live until the V2 path is proven.
> Parent: [Architecture](Architecture.md) · [ImplementationRoadmap](ImplementationRoadmap.md)

## 1. Rules of migration
1. **Additive first.** New code wraps old code; old code keeps running.
2. **Flagged.** Each engine has a flag in `config/flags.yaml` (`mission_engine`,
   `council_engine`, `execution_engine`, `runtime_orchestrator`, `governance_v2`,
   `knowledge_graph`, `reflection_engine`, `dashboard_v2`). Default: **off**.
3. **Reversible.** Turning a flag off restores V1 behavior exactly.
4. **Governed.** Data migrations are additive (new columns/tables); no destructive
   schema change without a backup + operator approval. Honors "no destructive action
   without operator approval."
5. **Observable.** Each phase ships its telemetry before it ships its behavior.

## 2. Strangler-fig sequence
The V2 engines wrap V1 at the call site. The flow is replaced one seam at a time:
```
Phase 0  Scaffolding      core/di.py, core/flags.py, engine package shells + interfaces
Phase 1  Observability    Telemetry facade over telemetry/observability; spans everywhere
Phase 2  Runtime          RuntimeOrchestrator wraps kernel/router; flag routes _llm_stream
Phase 3  Governance v2    GovernanceGate unifies GPS-2 + shadow_gate + os_permissions
Phase 4  Execution        ExecutionEngine wraps workflow/; agent loop → state machine
Phase 5  Mission          MissionEngine wraps house_state; /api/agent/run → quick-mission
Phase 6  Council          CouncilEngine adds hierarchy/authority/voting over roster
Phase 7  Knowledge+Memory KnowledgeGraph + MemoryService; import existing stores
Phase 8  Reflection       ReflectionEngine on mission.completed; learning-on, evolve-gated
Phase 9  Dashboard v2     mission-first UI; node map → secondary
Phase 10 Relocation       physically move modules into engines/* with re-export shims
```
Each phase is independently shippable and independently revertible.

## 3. Per-phase exit criteria (proof before promotion)
A flag flips to **on by default** only when, for that engine:
- V2 path passes the same scenarios as V1 (parity tests), **and**
- telemetry shows no regression in latency/cost/failure rate, **and**
- a rollback (flag off) is verified to restore V1.

## 4. Data migration (additive, backed up)
- **Mission**: add columns to `house_state` (`objective`, `constraints`,
  `success_criteria`, `graph`, `completion_pct`, `reflection`); old rows default.
- **Knowledge graph**: new `knowledge_graph.db`; a one-time idempotent importer
  ingests lessons/council-memory/Obsidian notes as deduped KG nodes. Re-runnable.
- **Telemetry**: consolidate into `runtime_metrics.db`; old metric writes mirrored
  during transition.
- Every migration: **backup first**, dry-run report, then apply on approval.

## 5. Compatibility guarantees
- `/api/agent/run` and the V1 chat UI keep working through all phases.
- Existing `SKILL.md`, `runtime_plugins/`, `plugins/apps/` load unchanged.
- The local **ElmatadorZ** execution runtime remains the default execution model;
  routing policy is local-first, so behavior matches V1 until cloud fallback is
  explicitly enabled.
- Legacy import paths survive Phase 10 via re-export shims for one release, then
  deprecate with a warning.

## 6. Risk register
| Risk | Mitigation |
|---|---|
| Engine wrapping changes timing/output | parity tests + flag rollback |
| KG import duplicates memory | dedupe (content hash + semantic) is idempotent |
| Self-evolution changes system silently | proposals gated; auto-apply opt-in per target |
| Runtime routing picks wrong/expensive model | local-first policy + cost/latency caps + budgets |
| Mid-flight import breakage in Phase 10 | re-export shims, one engine at a time |
