# Model Gateway Kernel

> The Runtime Orchestrator grows up. A runtime is no longer a **router** that picks a
> connection — it is an **inference cluster** that knows queue, GPU, batch, cost, and
> lease. Serves hundreds of agents over finite hardware.
> Parent: [V3-Architecture](../V3-Architecture.md) · Evolves
> [RuntimeArchitecture (V2)](../../v2/RuntimeArchitecture.md)

## 1. Why it changes shape
V2's orchestrator selects a healthy connection and streams. That works for one user.
For hundreds of agents on one GPU, the hard problems are **queueing, batching, and
admission against capacity** — serving, not routing. The Gateway owns model serving;
it does not own resource policy (that is the [Scheduler](Scheduler.md)) — it *serves
against leases the Scheduler grants*.

## 2. Responsibilities
- **Queue** inference requests per model/worker with priority (from the Scheduler).
- **Batch** compatible requests to maximize GPU throughput (continuous batching).
- **Workers** — a pool of model workers (local llama.cpp/Ollama + remote OpenAI/
  Anthropic/Gemini/custom), each a [driver plugin](../../v2/RuntimeArchitecture.md#2-driver-model-plugin-architecture--already-exists).
- **Lease enforcement** — serve only against a valid Scheduler lease; no lease → reject
  or queue.
- **Cost & latency accounting** — per request; feeds Scheduler quotas and Observability.
- **Health & fallback** — unhealthy workers drop out; requests fail over (V2 behavior),
  now with a circuit breaker supervised by the [Supervisor](Supervisor.md).

## 3. Request lifecycle
```
agent → request(capability, requirements)
      → Scheduler.lease(gpu/token)         (admission)
      → Gateway.enqueue(request, lease)    (priority queue)
      → batch + dispatch to best worker    (routing policy: capability, cost, latency, local-first)
      → stream events back (text/tool_calls/done)   (canonical contract, llm_adapter)
      → account(tokens, cost, latency) → release lease
```

## 4. Interface
```python
class ModelGateway:
    def complete(self, request, *, capability, lease) -> Iterator[Event]
    def embed(self, text, *, capability, lease) -> list[float]
    def workers(self) -> list[WorkerHealth]
    def capacity(self) -> Capacity                 # inflight slots, queue depth → Scheduler
    def register_worker(self, driver: RuntimeDriver) -> None   # plugin
```
Callers depend only on this facade and a capability + lease — never a base URL.

## 5. Events
`gateway.enqueued`, `gateway.batched`, `gateway.dispatched`, `gateway.worker_health`,
`gateway.fallback`, `runtime.usage` (tokens/cost/latency). Journaled.

## 6. Single → distributed
Workstation: one in-proc queue, one or two local workers (ElmatadorZ on the 3060),
batch size small. Organization: a Gateway service fronting a **fleet** of GPU workers
across nodes; the same queue/batch/lease abstraction; autoscaling workers is a capacity
signal to the Scheduler. Agents are unchanged.

## 6b. Sibling of the Reality Boundary Kernel (survived demotion)
A red-team asked whether MGW is merely the [Reality Boundary](RealityBoundary.md) kernel
specialized to inference — i.e. removable. **No.** Its defining invariant is **request
coalescing** (batch many requests into one GPU pass; re-execution is safe). RBK's is
**per-effect individuation** (never coalesce; re-execution forbidden). These *contradict*,
so MGW cannot be a Liskov subtype of RBK — it would have to *invert* the parent's
invariant. They are **siblings at the egress boundary**, sharing only generic plumbing
(driver registry, health, fallback, accounting) factored into a non-kernel library
**`egress-io`**. Nor is batching the Scheduler's job: Scheduler owns *allocation*
(resource-agnostic), MGW owns *packing* (inference-specific). See
[DecisionLog §3b](../DecisionLog.md#3b-post-freeze-precedents-from-the-red-team).

## 7. Compatibility
Built on the existing `runtime_kernel`/`runtime_router`/`runtime_registry`/
`runtime_plugins/`/`llm_adapter` — they become the Gateway's routing + driver layer.
Local-first ElmatadorZ remains the default worker; cloud workers are added as drivers.
With `model_gateway` off, the V2 direct-stream path runs unchanged.
