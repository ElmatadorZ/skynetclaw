# Runtime Architecture & Orchestrator

> The hardware-abstraction layer of the AIOS: one interface over many model
> backends, with dynamic routing, fallback, health, cost, and latency awareness.
> Parent: [Architecture](Architecture.md) · Built on `runtime_kernel.py`,
> `runtime_plugins/`, `runtime_router.py`, `runtime_registry.py`, `runtime_boot.py`,
> `llm_adapter.py`.

## 1. Role
Councils, agents, skills, and tools must never know *which* model answers them. They
ask the **Runtime Orchestrator** for a completion against a *capability + policy*; the
orchestrator picks a runtime, calls its driver, and returns a uniform stream. This is
the existing kernel/driver split, formalized.

## 2. Driver model (plugin architecture — already exists)
Every backend is a **driver plugin** in `runtime_plugins/` implementing one contract
and emitting the canonical event stream (`__tool_calls__` / `text` / `done`):
```python
class RuntimeDriver(Protocol):
    id: str; api_type: str            # "ollama" | "openai" | "anthropic" | "gemini" | custom
    def health(self) -> Health        # online, latency_ms, loaded_model
    def models(self) -> list[str]
    def stream(self, payload, *, base_url, api_key) -> Iterator[Event]
    def cost(self, usage) -> float     # $/token table
```
Supported: **Local Ollama**, **llama.cpp/OpenAI-compatible** (the live ElmatadorZ
execution server), **OpenAI**, **Anthropic**, **Gemini**, **Custom**. Adding a
backend = drop a driver file; the registry discovers it. `llm_adapter.py` already
normalizes openai-vs-ollama event contracts.

## 3. Connection vs runtime vs model
- **Connection** (SQLite `connections`): a configured endpoint (`base_url`,
  `api_type`, `is_active`) — already the source of truth.
- **Runtime**: a driver bound to a connection.
- **Model**: a name served by a runtime (`exec_model`, e.g. `ElmatadorZ`).
Settings already pin `exec_connection`/`exec_model`; V2 keeps this and layers routing
policy on top.

## 4. Routing policy (dynamic)
A request carries requirements; the router scores candidate runtimes:
```jsonc
{ "capability":"reasoning|execution|embedding|vision|long-context",
  "policy":{ "prefer":"local", "max_cost_usd":0.0, "max_latency_ms":8000,
             "min_context":16384 } }
```
Scoring = `online ✓` → meets `min_context` → within `max_cost`/`max_latency` →
preference (local-first by default) → measured latency (health). The local
ElmatadorZ runtime wins for execution; cloud runtimes are fallbacks.

## 5. Fallback & health
- **Health checks**: each driver's `health()` is probed (cheap, cached TTL — the
  pattern already in `system_graph._online`). Unhealthy runtimes drop out of routing.
- **Automatic fallback**: on driver error / timeout / health-fail, the router retries
  the next candidate in policy order; the failover is logged and telemetried
  (existing `FAILOVER_REPORT` concept). A mission's `resources.runtimes` bounds the
  candidate set.
- **Circuit breaker**: repeated failures open the breaker for a cooldown so a dead
  backend isn't hammered.

## 6. Cost & latency awareness
Every call records `tokens_in/out`, `latency_ms`, and `cost_usd` (driver `cost()`).
These feed: routing decisions (avoid expensive/slow when policy forbids), mission
**resource budgets** (`max_cost_usd`/`max_tokens` enforced — mission BLOCKED on
exhaustion), and observability (token usage, tool/runtime latency, cost panels).

## 7. Interface (DI)
```python
class RuntimeOrchestrator:
    def __init__(self, registry: RuntimeRegistry, router: RuntimeRouter,
                 bus: EventBus, telemetry: Telemetry, governance: GovernanceGate): ...
    def complete(self, payload, *, requirements) -> Iterator[Event]
    def embed(self, text, *, requirements) -> list[float]
    def health_all(self) -> dict[str, Health]
```
Governance is injected: runtime calls are a privileged action (cost, external egress)
and pass the gate. Callers depend only on this facade — never a base URL.

## 8. Events & compatibility
Events: `runtime.selected`, `runtime.fallback`, `runtime.health`, `runtime.usage`.
Compatibility: the kernel/registry/router/boot modules already exist and are
flag-gated (`kernel_enabled`); V2 makes the orchestrator the single call path while
the legacy direct `_llm_stream(...)` remains as the fallback when the flag is off.
