# OX-HOUSE-STABILIZATION-1 — Benchmark Results (stored)

Measured 2026-06-24. Inference runtime: **Ollama 0.30.10, CPU-only** (RTX 3060
rejected — see GPU root cause below). CPU: Intel i3-10100F (4 threads).

## Phase 3 — Benchmark Matrix

### qwen3.5:9b · think=false · tool-first prompt (live, CPU)
| num_ctx | first tool call | prompt_eval | gen |
|--------:|----------------:|------------:|----:|
| 2048 | 94.9s | 1430 tok / 69.7s = **20.5 t/s** | 43 tok / 8.7s = 4.9 t/s |
| 4096 | 83.6s | 1430 tok / 66.5s = **21.5 t/s** | 43 tok / 7.7s = 5.6 t/s |
| 8192 | 77.1s | 1430 tok / 62.1s = **23.0 t/s** | 43 tok / 7.6s = 5.7 t/s |

- **prompt_eval (~21 t/s) dominates** first-tool-call latency (~65s of ~80s).
- `num_ctx` is **not** a useful lever (no material effect; marginally faster larger).
- 1430 prompt tokens ≈ the 14 selected tool schemas; SYS+task is tiny.
- At ~21 t/s, a 15s budget allows only ~315 prompt tokens → the tool-schema set,
  not the base prompt, is the binding constraint on CPU.

### gemma4:26b / SkynetClaw (23 GB CPU loads — impractical on this i3)
Earlier-measured (default ctx, write_file tool task): gemma4:26b think=false
**54.8s**, think=true **93.7s**. Not the execution model; not re-swept (each call
~1–2 min on CPU).

## Phase 2 — GPU root cause (from Ollama server.log)
```
skipping CUDA device — compute capability not in compiled architectures
device="NVIDIA GeForce RTX 3060" cc=860 archs="[750 890 1000 1200]" libDirs="...cuda_v13"
```
RTX 3060 = sm_86. Installed `cuda_v13` runner compiled for [sm_75, sm_89, sm_100,
sm_120] only — no sm_86 (Ampere/30-series), and no `cuda_v12` fallback runner.
→ GPU rejected, inference falls to CPU. Driver 591.86 / CUDA 13.1 is fine.

## Verdict
Production gate (TTFT<15s, first-tool<15s, ≥90% over 10 runs, no timeout) is
**unreachable on CPU** at 21 t/s prompt-eval. Fix is operator-side GPU engagement
(Ollama runner with sm_86). On GPU, prompt-eval ~1000+ t/s → <1s → gate passes.
