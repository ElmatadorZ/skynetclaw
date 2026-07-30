# Choosing a model

SkynetClaw is **model-independent**. The council, the memory, the governance gate and the grading
loop do not care which engine answers — swapping the model changes cost and quality, not the
architecture.

This page covers the three ways to point it at one.

---

## 1 · Local — Ollama (the default)

Nothing leaves your machine. No key, no account.

```bash
# install from https://ollama.com, then:
ollama pull llama3.1:8b          # reasoning
ollama pull qwen2.5-coder:7b     # execution (tool calls, file edits)
ollama serve                     # if it is not already running
```

Then in `backend/settings.json`:

```jsonc
{
  "model":           "llama3.1:8b",
  "active_model":    "llama3.1:8b",
  "default_model":   "llama3.1:8b",
  "exec_model":      "qwen2.5-coder:7b",
  "exec_connection": "ollama"
}
```

**No GPU required.** A 7–8B model runs on CPU; it is slower, not broken. If you have an NVIDIA GPU,
Ollama will use it automatically.

**If Ollama is not on this machine**, point the backend at it — the default is
`http://localhost:11434`:

```bash
# .env
OLLAMA_BASE_URL=http://192.168.1.20:11434
```

`docker compose` sets this to `http://ollama:11434` for you, because inside a container
"localhost" is the container itself and not the host.

Runtime discovery probes that address **in addition to** localhost, so a local and a remote
Ollama can coexist. Probes run concurrently: a runtime you have not installed costs the
connect timeout once for the whole scan, not once each.

### Why two models

```jsonc
"model":      "llama3.1:8b",       // reasoning — the council deliberates with this
"exec_model": "qwen2.5-coder:7b",  // execution — tool calls and file edits
```

The model that *reasons* does not have to be the model that *executes*. Tool loops are frequent and
short; deliberation is rare and long. A small fast model on the execution path keeps the loop cheap
without dulling the thinking. Set both to the same tag if you prefer — it works, it just costs more
time per tool call.

---

## 2 · Local — any OpenAI-compatible server

`llama.cpp`'s `llama-server`, LM Studio, vLLM, text-generation-webui, and similar all expose an
OpenAI-compatible `/v1` API. Register one as a connection:

```bash
curl -X POST http://127.0.0.1:8766/api/connections \
  -H 'Content-Type: application/json' \
  -d '{"api_type":"custom","label":"llama.cpp","base_url":"http://127.0.0.1:8080/v1","api_key":""}'
```

Then list and activate it:

```bash
curl http://127.0.0.1:8766/api/connections
curl -X POST http://127.0.0.1:8766/api/connections/<id>/activate
curl http://127.0.0.1:8766/api/connections/<id>/ping     # confirm it answers
```

> **Context ceiling matters.** A server started with a small `--ctx-size` will reject long prompts,
> and the failure surfaces several steps later as a confusing model error rather than as "prompt too
> long". If long tasks fail oddly, check the ceiling first.

---

## 3 · Cloud providers

Ten providers are supported through one universal adapter. Add the key to `.env`, then register a
connection the same way as above with the matching `api_type`.

| `api_type` | Provider | Base URL (default) |
|---|---|---|
| `openai` | OpenAI | `https://api.openai.com/v1` |
| `anthropic` | Anthropic Claude | `https://api.anthropic.com/v1` |
| `gemini` | Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` |
| `groq` | Groq | `https://api.groq.com/openai/v1` |
| `openrouter` | OpenRouter | `https://openrouter.ai/api/v1` |
| `deepseek` | DeepSeek | `https://api.deepseek.com/v1` |
| `xai` | xAI Grok | `https://api.x.ai/v1` |
| `mistral` | Mistral | `https://api.mistral.ai/v1` |
| `together` | Together AI | `https://api.together.xyz/v1` |
| `custom` | anything OpenAI-compatible | you supply it |

```bash
# .env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
OPENROUTER_API_KEY=sk-or-...
```

```bash
curl -X POST http://127.0.0.1:8766/api/connections \
  -H 'Content-Type: application/json' \
  -d '{"api_type":"anthropic","label":"Claude","api_key":"sk-ant-..."}'
```

`.env` is git-ignored. Keys never enter the repository.

---

## Mixing local and cloud

Connections coexist. A common arrangement:

| Path | Model | Why |
|---|---|---|
| Deliberation | a strong cloud model | the council is where quality pays |
| Execution | a small local model | tool loops are frequent; keep them free and fast |
| Sensitive work | local only | nothing leaves the machine |

Inspect and change routing:

```bash
curl http://127.0.0.1:8766/api/router/config
curl http://127.0.0.1:8766/api/router/audit      # what actually routed where
```

---

## Which local model should I start with?

| You have | Try | Expect |
|---|---|---|
| CPU only, 8 GB RAM | `llama3.2:3b` | usable for chat; weak on long tool chains |
| CPU only, 16 GB RAM | `llama3.1:8b` | the sensible default |
| GPU, 8–12 GB VRAM | `llama3.1:8b` or `qwen2.5:14b` | comfortable |
| GPU, 24 GB+ VRAM | a 30B-class model | strong deliberation |

**An honest note on small models.** Below roughly 7B, models struggle with long multi-step tool
chains and with returning strict JSON. That is not a bug in SkynetClaw — the governance gate will
correctly reject malformed output, and the run will fail loudly rather than silently accept
nonsense. If a small model keeps failing at execution, that is the system working. Use a larger
model, or route only execution to a code-tuned one.

---

## Verifying your setup

```bash
curl http://127.0.0.1:8766/api/models          # what the active connection offers
curl http://127.0.0.1:8766/api/providers       # supported provider types
curl http://127.0.0.1:8766/api/system/health   # everything at once
```

Health reports `GREEN` only when every subsystem loaded. If a model check fails, that check names
what is missing.

---

## Embeddings — both worlds, one setting

Semantic search over your vault needs an embedding model. `backend/settings.json`:

```jsonc
"embed_model": "nomic-embed-text"          // local, via Ollama
"embed_model": "text-embedding-3-small"    // OpenAI-compatible / cloud
```

The House dispatches on the **active connection's** `api_type`, because the two
worlds disagree on every detail of this call:

| | route | field | response |
|---|---|---|---|
| Ollama | `POST /api/embeddings` | `prompt` | `{"embedding": [...]}` |
| OpenAI-compatible | `POST /embeddings` | `input` | `{"data":[{"embedding":[...]}]}` |

You do not choose between them — set `embed_model` to something the active
connection serves and the right dialect is used.

**If no embedding model is reachable, search falls back to keyword matching and
says so.** It does not return a zero vector: that would make every similarity
score identical and look like a working semantic search.
