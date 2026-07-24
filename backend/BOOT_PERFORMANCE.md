# BOOT_PERFORMANCE.md — OX-HOUSE-BOOT-1 Phase 14

Measured on this machine (RTX 3060 GPU runtime + Ollama; 2 drivers, 9 models).
Boot is deterministic: fixed stage order, fixed discovery order.

## Cold vs Warm
| Boot | READY time | Benchmark | Notes |
|---|---:|---:|---|
| **Cold** (first launch, no registry) | **28.2 s** | 21.2 s | full capability scan + benchmark of execution models |
| **Warm** (registry reuse, wizard) | **6.9 s** | 0.001 s | reuses runtime_registry.db + runtime_metrics.db; re-benchmarks only changed models |

## Stage breakdown
| Stage | Cold (ms) | Warm (ms) | What |
|---|--:|--:|---|
| CONFIG | 1 | 2 | path mode (source/portable/exe) |
| PLUGINS | 9 | 14 | driver discovery (load_drivers) |
| **RUNTIMES** | **6840** | **6823** | runtime discovery via kernel drivers (Ollama /api/show ×8 + offline probes, trimmed) |
| DRIVERS | 0 | 0 | driver.describe/connect |
| CAPABILITIES | 0 | 0 | classify by declared caps |
| HEALTH | 32 | 18 | health_report |
| **BENCHMARK** | **21222** | **1** | wizard: cold = measure exec models; warm = reuse |
| REGISTRY | 1 | 0 | build_registry + runtime_registry.db |
| POOLS | 0 | 0 | kernel.pools() (already discovered) |
| SESSIONS | 67 | 0 | warm top Execution runtime |
| WORKFLOW | 0 | 0 | engine ready |

## Sub-metrics (Phase 14)
- **Driver Load:** ~9 ms
- **Runtime Discovery:** ~6.8 s (dominated by Ollama `/api/show` per-model + 3 offline-port probes at trimmed 1.2 s timeout)
- **Benchmark Duration:** 21.2 s cold (execution models incl. slow Ollama-CPU) / ~0 warm
- **Pool Build:** ~0 ms (reads the already-discovered kernel — no second scan)
- **Registry Reuse:** benchmark 21.2 s → **1 ms** when registry+metrics present
- **READY Time:** **28.2 s cold / 6.9 s warm**

## Notes
- The earlier pre-optimization boot was 87.9 s; eliminating the duplicate scan
  (RUNTIMES + POOLS both scanned) and trimming offline-probe timeouts cut cold to
  28.2 s and warm to 6.9 s.
- Discovery (the warm floor) is networked; it is TTL-cached (60 s) in a running
  process, so subsequent boots/agent calls within the window are near-instant.
- Benchmarking Ollama-CPU models is the slow part of cold boot; it is a one-time
  first-launch cost (wizard), not paid on warm boots.
