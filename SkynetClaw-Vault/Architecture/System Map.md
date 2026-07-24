---
tags: [architecture]
type: reference
---

# System Map

The runtime shape of THE HOUSE. Full code: `backend/main.py` (~8600 lines), `index.html`.

## Processes & ports
| Service | Port | What | Notes |
|---|---|---|---|
| Backend (FastAPI) | `8766` | agent loop, tools, governance, bridges, SSE | `python backend/main.py` |
| Execution model (llama.cpp) | `8080` | Qwen2.5-14B, alias `ElmatadorZ`, OpenAI-compat | see [[Execution Runtime & Constraints]] |
| Ollama | `11434` | alt local models | GPU sm_86 → CPU fallback (slow) |
| Stealth browser bridge | `8781` | isolated Chrome automation (separate 3.13 venv) | localhost + token |

## Data (SQLite)
`skynerclaw.db` (agent_runs, connections, integrations, skills, custom_tools,
telegram_sessions, workflow_runs, embeddings) · `warrant_log.jsonl` (CEE) ·
`eval_log.jsonl` (scoreboard). Config: `settings.json`, `governance_config.json`.

## The request path (agent)
```
user / Telegram
  → /api/agent/run  (or /api/agent/plan_execute for builds — see [[Planner — Vol IV Runtime]])
    → reality_context grounding  (workspace files + operational history)
    → proprioception  (lessons from own outcomes — [[Proprioception — Learning]])
    → GPS-2 gate  (allow / escalate→human / deny — [[Governance — GPS-2]])
    → exec_tool(name, args)  → the tool
    → warrant_check on completion  ([[CEE — Warrant Runtime]])
```

## LLM routing
`_llm_stream(payload, base, key, api_type)` dispatches **cloud** (OpenAI/Anthropic
compat, Bearer) vs **local** (Ollama / llama.cpp). `is_cloud()` = api_type not in
{"", ollama, local}. Context window is resolved per-connection — see [[Protocol over Model]].

## Supervision (self-healing)
The backend **auto-starts** `execution_watchdog.py` on startup (singleton-locked); it
keeps `:8080` alive and auto-recovers a crash in seconds. See
[[Execution Runtime & Constraints]].

## Event bus
`house_sync.publish(type, payload, source)` + `/api/house/events` (SSE with replay) —
warrant_violation, eval_run, plan_complete, budget_critical, mission_recovered, …

## See also
[[Runtime Bridges]] · [[Protocol over Model]] · [[Governance — GPS-2]] · [[🏠 HOME]]
