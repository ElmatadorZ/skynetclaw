# BOOT_GRAPH.md — OX-HOUSE-BOOT-1

## Autonomous startup (the operator only installs the app)
```
GenesisHouse.exe  (or `python main.py`)
        │
        ▼
Bootstrap Loader  (runtime_boot.BootLoader)   ── publishes Boot Event Bus ──┐
        │                                                                    │
        ▼                                                                    │
[CONFIG]      config/paths.py → mode (source/portable/installed/exe)   CONFIG_LOADED
        ▼                                                                    │
[PLUGINS]     runtime_plugins.load_drivers()                           PLUGIN_DISCOVERED
        ▼                                                                    │
[RUNTIMES]    manifests (runtime/*.json) → kernel discover (drivers)   RUNTIME_DISCOVERED
        ▼                                                                    │
[DRIVERS]     driver.describe() / connect()                            DRIVER_READY
        ▼                                                                    │
[CAPABILITIES] classify models by declared caps (no names)             CAPABILITY_READY
        ▼                                                                    │
[HEALTH]      runtime_router.health_report()                           HEALTH_OK
        ▼                                                                    │
[BENCHMARK]   wizard: first-launch → measure exec models;              BENCHMARK_COMPLETE
              warm → reuse, re-benchmark only changed → runtime_metrics.db
        ▼                                                                    │
[REGISTRY]    runtime_registry.build_registry → runtime_registry.db    REGISTRY_READY
        ▼                                                                    │
[POOLS]       kernel.pools() (Execution/Reasoning/Council/Vision/…)    POOL_READY
        ▼                                                                    │
[SESSIONS]    warm top Execution runtime (keep_alive residency)        SESSION_READY
        ▼                                                                    │
[WORKFLOW]    workflow engine ready                                    WORKFLOW_READY
        ▼                                                                    │
     HOUSE READY ◄──────────────────────────────────────────────────  HOUSE_READY
        │                                                                    │
        ├─ Health Monitor thread (every 30s): unhealthy → rebuild pools → failover
        └─ Runtime Kernel is the single execution entry point ───────────────┘
                 │
   Agent → kernel.infer(role) → Capability Router → Driver → Runtime → Model
```

## Observability
`/api/boot/start` (trigger) · `/api/boot/events` (event bus) · `/api/boot/status`
(stage timeline + pools). The operator never selects a runtime/endpoint/provider/
model/driver — discovery + capability negotiation choose everything by measurement.
```
