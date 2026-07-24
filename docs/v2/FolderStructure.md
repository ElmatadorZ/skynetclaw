# Folder Structure

> Target V2 layout. **Additive** — existing files stay where they are; V2 introduces
> `engines/` and `core/` packages that *wrap* current modules. Nothing is moved in a
> breaking way until [MigrationPlan](MigrationPlan.md) phases say so.
> Parent: [Architecture](Architecture.md)

## 1. Principle
Group by **OS layer**, not by feature. Each engine is a package with a public
interface (`__init__.py` exporting the Protocol + impl) and is independently testable.
Current flat `backend/*.py` modules become the *implementations* injected into engines.

## 2. Target tree
```
backend/
├─ core/                       # L0 OS core + cross-cutting (mostly EXISTS)
│  ├─ os/                      #   genesis_os.py, os_ipc.py, os_permissions.py,
│  │                          #   os_services.py, os_packages.py, os_workspace.py, os_apps.py
│  ├─ ipc.py                  #   EventBus facade (wraps os_ipc)
│  ├─ di.py                   #   container: builds + injects engines (NEW, thin)
│  ├─ flags.py                #   feature flags (NEW, thin)
│  └─ telemetry.py            #   Telemetry facade (wraps telemetry.py/observability.py)
│
├─ engines/                    # the V2 engines (wrappers over existing logic)
│  ├─ mission/                #   MissionEngine  ← house_state.py, workflow_runs.py
│  ├─ council/                #   CouncilEngine  ← agent_council.py, commander.py
│  ├─ execution/              #   ExecutionEngine ← workflow/ (ir,compiler,engine,nodes,context)
│  ├─ governance/             #   GovernanceGate  ← governance.py, governance_engine.py,
│  │                          #                     skynetclaw_meta.shadow_gate
│  ├─ reflection/             #   ReflectionEngine ← agentic_workflow.reflect, lesson_synthesis
│  ├─ knowledge/              #   KnowledgeGraph + MemoryService ← system_graph.py, stores
│  └─ runtime/                #   RuntimeOrchestrator ← runtime_kernel, runtime_plugins/,
│                             #                          runtime_router, runtime_registry, llm_adapter
│
├─ skills/                     # EXISTS — skill plugins (SKILL.md folders)
├─ runtime_plugins/            # EXISTS — runtime driver plugins
├─ plugins/apps/               # EXISTS — app plugins
│
├─ data/                       # stores (SQLite/JSON)
│  ├─ skynerclaw.db            #   connections, etc. (EXISTS)
│  ├─ house_state.*            #   mission ledger (EXISTS)
│  ├─ knowledge_graph.db       #   kg_nodes/kg_edges/kg_embeddings (NEW)
│  └─ runtime_metrics.db       #   telemetry (EXISTS/consolidated)
│
├─ config/
│  ├─ council.yaml             #   tiers, authority, veto (NEW)
│  ├─ reflection.yaml          #   auto-apply policy (NEW)
│  └─ flags.yaml               #   engine feature flags (NEW)
│
├─ main.py                     # EXISTS — slims to: build DI container, mount routers
└─ api/                        # routers split by surface (NEW, optional)
   ├─ mission.py  council.py  runtime.py  kg.py  observability.py  system.py

docs/v2/                       # this architecture set
index.html                     # EXISTS — SPA, gains Missions view (DashboardArchitecture)
```

## 3. Mapping rule
For every existing module there is exactly one engine that owns it. Engines depend on
**interfaces**, not on each other's modules. The `core/di.py` container is the only
place that knows concrete classes — it constructs them and injects dependencies
(constructor injection), matching the `GenesisOS` facade already in use.

## 4. What is NEW vs EXISTS
- **NEW (thin)**: `core/di.py`, `core/flags.py`, `engines/*/` package shells +
  interfaces, `knowledge/` (KG + memory), `config/*.yaml`, optional `api/` split.
- **EXISTS (wrapped, unchanged)**: everything under `os/`, `runtime_*`, `workflow/`,
  `governance*`, `house_state`, `skills/`, `runtime_plugins/`, `system_graph`,
  `telemetry`/`observability`, `main.py` logic.

## 5. Migration of files
Files are **not physically moved** in early phases — engines import them in place.
Physical relocation into `engines/*/` is the *last* phase, done one engine at a time
with the old path re-exporting for a release (deprecation shim), so imports never
break mid-flight. See [MigrationPlan](MigrationPlan.md).
