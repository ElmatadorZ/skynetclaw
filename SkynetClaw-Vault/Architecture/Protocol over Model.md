---
tags: [architecture, invariant]
type: principle
source: backend/context_budget.py (resolve_window)
---

# Protocol over Model

> **"Models are temporary. Protocols endure."** (ElmatadorZ)

The system is designed so the **brain is swappable** without touching the governance,
the agent loop, the theory, or the bridges. Evidence this is real: `governance.py`
references the model **zero times**; the theory is agent-general; the bridges are
model-agnostic.

## The one place a model-specific constant had leaked (now fixed)
The context window was hardcoded to `16384` (the llama.cpp VRAM ceiling) throughout the
protocol layer. Lifted into `context_budget.resolve_window(conn, api_type, model, base)`:

**precedence:** explicit connection declaration (`context_window`/`n_ctx`) > local-host
safe default (16384) > model-name hint (claude 200k, gpt-4o 128k…) > cloud default.

Handles the real trap: **local llama.cpp speaks `api_type="openai"` yet is 16k-capped** —
distinguished by the *loopback host*, not the api_type. Zero-regression: an undeclared
local connection stays 16384; a cloud model gains its real window; the operator can pin
any window per connection.

## The consequence (ties to [[Governance — GPS-2]])
Making the protocol model-agnostic makes the **requisite-variety** warning sharper: a
stronger brain is now one connection-swap away, spiking the *governed's* variety while
the *governor* (the gate) stays fixed. So the [[Genesis Paradigm]] law — *no capability
without its governing invariant* — must hold for **model upgrades**, not only tool
additions. A stronger model is not uniformly better: forward-arc reliability rises, but
governance gets harder and unfixed security P1s become more exploitable.

## What is invariant vs what changes when you swap the model
- **Invariant:** plumbing, agent loop, governance, theory, bridges, [[Proprioception — Learning|proprioception]] (frozen weights → learning always lives in the scaffolding).
- **Changes:** context ceiling, execution failure-mode, tool-calling reliability, and **sovereignty** (a cloud API breaks commitment #1 of the [[Genesis Paradigm]]).

## See also
[[System Map]] · [[Genesis Paradigm]] · [[Execution Runtime & Constraints]] · [[🏠 HOME]]
