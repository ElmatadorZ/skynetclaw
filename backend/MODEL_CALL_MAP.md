# MODEL_CALL_MAP.md — OX-KERNEL-ACTIVATION-1 Phase 1

Every place the backend invokes a model, found by scanning for `_llm_stream`,
`stream_ollama_chat`, OpenAI/Ollama adapters, and direct runtime HTTP.

| Caller | Site | Current Runtime | Purpose | Path | Activated? |
|---|---|---|---|---|---|
| **agent_run loop** | `main.py:4796` | `_llm_stream` → exec_connection (llama.cpp GPU) / Ollama | autonomous tool execution | **EXECUTION** | ✅ flag-gated → `kernel.infer()` |
| `_llm_stream` (dispatch) | `main.py:415/418` | adapter (OpenAI) or `stream_ollama_chat` (Ollama) | single legacy dispatch point | both | legacy (compat layer) |
| `chat()` | `main.py:3551` | `_llm_stream` (active conn) | chat tool loop | Execution-ish (chat) | legacy (not agent) |
| `obs_search()` | `main.py:7176` | `_llm_stream` | Obsidian RAG answer | Reasoning/RAG | legacy |
| `comprehend/plan/reflect` | `agentic_workflow.py:198` | direct httpx POST `/api/chat` | workflow reasoning | **REASONING** | legacy (constraint: do not redesign workflow) |
| council specialists | council module | Ollama `/api/chat` | multi-agent debate | **COUNCIL** | legacy |

## Decision
- **The EXECUTION path = the agent loop (`main.py:4796`)** — this is what OX-KERNEL-ACTIVATION-1 routes through the Runtime Kernel behind `runtime_kernel_enabled`.
- REASONING (`agentic_workflow`) and COUNCIL paths are deliberately left on the legacy path — the mission's hard constraints forbid redesigning workflow/reasoning, and those are not the execution layer. They can be activated later by the same flag pattern with role=Reasoning/Council.
- `chat()` and `obs_search()` are secondary, non-agent callers left on legacy (no behaviour change).

## Result
When `runtime_kernel_enabled=true`, the agent's execution dispatch no longer
names a runtime/model/endpoint/api/provider — it calls `_kernel_exec_stream` →
`kernel.infer(required={"role":"Execution"})`. When `false`, byte-for-byte legacy.
