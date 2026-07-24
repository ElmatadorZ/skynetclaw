# FAILOVER_REPORT.md — OX-KERNEL-ACTIVATION-1 Phase 7

**Claim:** kill the primary runtime → the Kernel automatically selects the next
ranked runtime and continues execution, with **no agent modification**.

## Evidence 1 — live (during this mission)
The llama.cpp GPU server (primary Execution runtime, rank #1) went down between
test runs. With the flag on, `kernel.infer(required={"role":"Execution"})`:
1. Negotiated Execution candidates → ranked the (now-offline) GPU model #1.
2. `openai_driver.infer` to `http://127.0.0.1:8080/v1` raised (connection refused).
3. Kernel caught it, called `_mark_unhealthy`, and **failed over to the next
   ranked Execution runtime (Ollama)** — the call still completed (slower, CPU).
4. The agent code was untouched; it just consumed the same event stream.

After restarting the GPU server, the kernel re-selected it as #1 automatically
(discovery TTL refresh) — no manual intervention.

## Evidence 2 — deterministic unit tests (`tests/test_runtime_kernel.py`)
- `test_failover_to_next_runtime`: a driver that raises on the first runtime's
  URL; the kernel iterates ranked candidates and recovers on the second,
  emitting `__tool_calls__`. **PASS.**
- `test_all_runtimes_down_yields_error`: every candidate fails → kernel yields a
  single `{"type":"error"}` (honest failure, no crash). **PASS.**

## Mechanism (runtime_kernel.infer)
```
candidates = negotiate(required)          # ranked by capability + metrics
for sel in candidates:                    # ← FAILOVER loop
    try:    yield from driver.infer(sel…)  # success → return
    except: mark_unhealthy(sel.url); continue
yield {"type":"error", "all runtimes failed"}
```
Selection is by capability, never by name, so failover targets are discovered,
not hardcoded. Health monitor (`kernel.health()`) also flips `instance.healthy`,
excluding dead runtimes from the next negotiation.

## Verdict: PASS — automatic next-runtime failover, agent unmodified.
