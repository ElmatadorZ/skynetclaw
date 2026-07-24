# benchmark_kernel_activation.md — OX-KERNEL-ACTIVATION-1 Phase 6

Legacy execution path vs Runtime-Kernel execution path, warm, same GPU runtime
(qwen2.5-7B on llama.cpp, RTX 3060). First-tool-call latency, 5 reps/task/path.
Both paths exercised through the real backend functions (`_llm_stream` vs
`_kernel_exec_stream`) with the House's own tool schemas.

| Path | Task | n | ok | first-tool mean / med / p95 (s) |
|---|---|--:|--:|---|
| **KERNEL** | create | 5 | 5 | 0.50 / 0.50 / 0.51 |
| **KERNEL** | read   | 5 | 5 | 0.41 / 0.41 / 0.41 |
| **KERNEL** | edit   | 5 | 5 | 0.72 / 0.71 / 0.74 |
| **KERNEL** | search | 5 | 5 | 0.62 / 0.54 / 1.01 |
| LEGACY | create | 5 | 5 | 0.78 / 0.74 / 0.95 |
| LEGACY | read   | 5 | 5 | 0.66 / 0.66 / 0.68 |
| LEGACY | edit   | 5 | 5 | 0.96 / 0.96 / 0.97 |
| LEGACY | search | 5 | 5 | 0.83 / 0.73 / 1.24 |

## Metrics summary
| Metric | Legacy | Kernel |
|---|---|---|
| Tool success | 20/20 (100%) | 20/20 (100%) |
| Failure rate | 0% | 0% |
| Timeout rate | 0% | 0% |
| First-tool latency (median) | 0.66–0.96s | **0.41–0.72s** |
| TTFT < 15s | ✅ | ✅ |
| GPU usage | RTX 3060 (5.8 GB) | RTX 3060 (5.8 GB) |
| Session reuse | n/a | ✅ (kernel session per runtime+model) |

## Finding
**No regression.** The kernel path matches the legacy path and is marginally
faster (kernel drivers use urllib; the legacy OpenAI adapter carries an httpx
keepalive watchdog). Activation adds in-process capability negotiation
(microseconds; discovery is TTL-cached at 60s) and routes to the same GPU
runtime — so latency is unchanged-to-better while the agent loses all knowledge
of runtime/model/endpoint/api/provider.

## Scope note (honest)
This is 40 paired first-tool measurements (4 task types × 5 reps × 2 paths),
warm. It targets the **execution dispatch** (the model-call core). The full
multi-step `/api/agent/run` loop requires a House-server restart to load the
flag; the dispatch is where activation lives and where regression would appear.
Cold-start (fresh process) adds ~7s discovery + ~20s model load on the first
call only — both amortized by the kernel singleton + keep_alive in a running
server.
