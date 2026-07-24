# runtime_graph.md — OX-KERNEL-ACTIVATION-1 Phase 8

## Legacy path (`runtime_kernel_enabled = false`)
```
UI
 ↓
Workflow
 ↓
Agent (agent_run)
 ↓
_llm_stream(payload, base, key, api_type)        ← agent knows model+endpoint+api
 ↓
 ├─ api_type cloud → _ad_stream_openai (OpenAI adapter)
 └─ else           → stream_ollama_chat (Ollama)
 ↓
Runtime (exec_connection: llama.cpp GPU  |  Ollama)
 ↓
Model
```

## Kernel path (`runtime_kernel_enabled = true`)
```
UI
 ↓
Workflow
 ↓
Agent (agent_run)            ← passes only messages + tools
 ↓
_kernel_exec_stream()         (compat bridge: same event contract)
 ↓
Runtime Kernel  ── get_kernel() singleton, discovery TTL-cached
 ↓
Capability Negotiation        required={"role":"Execution","tool_calling":true}
 ↓
Runtime Selection + Pool      rank by capability + measured metrics (NO names)
 ↓                            ├─ load-balance equal-top  ├─ FAILOVER on error
Driver (plugin)               ollama_driver | openai_driver
 ↓
Runtime                       llama.cpp GPU (#1) → Ollama (failover)
 ↓
Model                         chosen by capability, never named by the agent
```

## What the Agent knows
| | Legacy | Kernel |
|---|---|---|
| model name | yes (`exec_model`) | **no** |
| runtime/endpoint | yes (`base`,`api_type`) | **no** |
| provider/api | yes | **no** |
| interface | `_llm_stream(...)` | `_kernel_exec_stream(messages, tools)` |

The flag flips between them with zero change to agent/workflow/prompt code.
