# OS_GRAPH.md — OX-HOUSE-OS-1

Genesis House as an AI Operating System. The Runtime Kernel is now **one
subsystem**; everything above it is modular, installable, and independently
manageable.

```
                         GenesisHouse.exe
                               │
                    ┌──────────▼───────────┐
                    │     GENESIS OS       │  genesis_os.GenesisOS (facade)
                    │   boot() / status()  │
                    └──────────┬───────────┘
        ┌───────────┬──────────┼───────────┬─────────────┬──────────────┐
        ▼           ▼          ▼           ▼             ▼              ▼
   Permission    IPC Bus   Service Mgr  Workspace    Application     Package
   + Audit       (pub/sub) (start/stop/  Manager     Manager        Manager
   (Phase 3)     (Phase 4)  health)      (Phase 7)   (Phase 1)      (.gpkg, P5)
        │           │      (Phase 2)         │            │              │
        │           │          │             │            ▼              │
        │           │          │             │      ┌───────────┐        │
        └───────────┴──────────┴─────────────┴──────│ AppContext│◄───────┘
                  every privileged call brokered →   └─────┬─────┘
                                                           │ (capability-checked)
        ┌──────────────────────────────────────────────────┘
        ▼            ▼            ▼            ▼            ▼
   runtime svc   workflow svc  memory svc  monitoring   scheduler svc
        │
        ▼
  ┌──────────────┐  ← the Runtime Kernel is just the "runtime" service
  │ Runtime      │     Boot → Kernel → Capability Router → Driver → Runtime → Model
  │ Kernel       │     (built in OX-RUNTIME-KERNEL-1 / activated in OX-KERNEL-ACTIVATION-1
  │ (subsystem)  │      / self-booted in OX-HOUSE-BOOT-1)
  └──────────────┘

Apps  ──publish/subscribe──►  IPC Bus  ──►  other apps/services   (no direct refs)
Apps  ──require(cap)──►  Permission Mgr  ──►  Audit Log            (no direct privilege)
Apps  ──ctx.infer()──►  (cap: runtime.infer)  ──►  Kernel.infer()  (no model names)
```

## Boot order
`GenesisOS.boot()` → start services (runtime/workflow/memory/monitoring/
scheduler) → discover apps → `os.ready`. The runtime service lazily binds the
already-built Runtime Kernel (OX-HOUSE-BOOT-1) — the OS does not re-implement it.

## Layering vs the goal
```
OS ─ Boot ─ Kernel ─ Workflow ─ Applications ─ Agents
```
Applications can be installed / removed / updated / executed independently
(`.gpkg` + Application Manager), mediated by permissions and IPC. Everything is
relocatable (config.paths) for portable / installed / frozen-exe modes.

## APIs
`POST /api/os/boot` · `GET /api/os` · `GET /api/os/services` ·
`POST /api/os/services/{name}/{action}` · `GET /api/os/apps` ·
`POST /api/os/apps/{id}/{action}` · `GET /api/os/ipc` · `GET /api/os/permissions`
· `GET /desktop`.
