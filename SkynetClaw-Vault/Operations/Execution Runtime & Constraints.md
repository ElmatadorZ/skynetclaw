---
tags: [operations, constraint]
type: reference
source: launch_execution_runtime.ps1, execution_watchdog.py; commit 8fa6619
---

# Execution Runtime & Constraints

> **The real bottleneck.** However good everything above is, it is limited by a model that
> dies mid-task. Stabilizing `:8080` unblocked the whole system (it is what let the
> [[Planner — Vol IV Runtime|planner]] finally build a complete dashboard).

## The runtime
`llama-server.exe` (llama.cpp CUDA), Qwen2.5-14B GGUF, alias `ElmatadorZ`, OpenAI-compat on
`:8080`, `-c 16384`, flash-attn, `-ngl 99` (all layers on the RTX 3060 12GB).

## The "dies repeatedly" root cause (found by measurement)
1. **The watchdog wasn't running** — only the backend process was up, so once `:8080` died
   *nothing brought it back*.
2. **Default 4 slots** each reserved a full 16k context → a single request effectively got
   ~1/4 of the window; and the 14B+16k sat at **95% of the 12GB card (11.6GB)** — the OOM edge.

## The fixes (commit 8fa6619)
- **`--parallel 1`** (launch script + watchdog): one slot, the **full 16384 per request**
  (single-user House). Round-1 dashboard output went 655 → 3257 chars with the fuller context.
- **Backend auto-starts the watchdog** on startup (`main.py __main__`), so `:8080` is
  supervised for the backend's lifetime and a crash auto-recovers in **seconds**
  (`SKYNET_NO_WATCHDOG=1` to opt out).
- **Singleton lock** (`.watchdog.lock`, PID-checked) — a second watchdog exits immediately;
  no two fighting over the port.

## Honest residual (a [[Roadmap & Open Problems|known trade-off]])
VRAM is still ~95% (`--parallel` didn't free it; the weights dominate). Under GPU
contention (e.g. the stealth Chrome) an OOM crash is still possible — but the always-running
watchdog recovers it fast: *"dies and stays dead" → "dies and is back in seconds."* A
durable VRAM fix (lower `-ngl`, or the 7B) is a quality/stability trade-off for the operator.

## The other constraint
Ollama (`:11434`) falls back to CPU on this GPU (sm_86) → slow; the execution path uses
llama.cpp on `:8080`, not Ollama. Context is 16k on the local model but adapts per
connection — [[Protocol over Model]].

## See also
[[System Map]] · [[Planner — Vol IV Runtime]] · [[Eval Scoreboard]] · [[🏠 HOME]]
