# SERIALIZATION_PIPELINE.md
### The exact transformation chain: `cur` → llama.cpp prompt

**Mode:** Reliability verification. No code changed. Evidence only.
**Question this file answers:** What is the real object that reaches the model, and where in that chain does `context_budget.assess()` take its measurement?

---

## 0. The two runtime paths (both server-side templated)

The EXECUTION loop (`backend/main.py`) sends the request through `_llm_stream()` → `stream_ollama_chat()` (`main.py:2504`) OR a kernel path (`_kernel_exec_stream`, `main.py:5127`). The destination is one of:

| Path | Endpoint | Templating + tokenization happens in | Evidence |
|---|---|---|---|
| Local Ollama | `POST {base}/api/chat` | Ollama → llama.cpp (server-side) | `main.py:2513` |
| Dedicated GPU runtime | `POST {base}/v1/chat/completions` (`api_type=openai`) | llama.cpp server (server-side) | `main.py:4197–4212` |

**Decisive fact:** In *both* paths the client sends **structured JSON** (`messages`, `tools`), never a rendered string. The chat template, special tokens, and tokenizer all execute **inside the server, after the HTTP boundary**. The Python process — and therefore `assess()` — never sees the bytes that are actually tokenized.

Model on the local path: `nemotron3:33b` (`Modelfile_Skynet-Claw:1`). On the exec path: `qwen2.5-7b` (`main.py:4198`). Both use byte-level BPE / SentencePiece tokenizers — **not** `cl100k_base`.

---

## 1. The exact wire payload

Built at `main.py:5086`:

```python
payload = {
    "model": model,
    "messages": cur,          # list[dict]  role/content (+ tool_calls / name)
    "stream": True,
    "tools": _MISSION_TOOLS,   # OpenAI-style function schemas
    "keep_alive": "30m",
    "options": {"num_ctx": 16384, "temperature": 0.1},
}
if not _exec_is_cloud:
    payload["think"] = False
```

`assess()` is called immediately BEFORE this, at `main.py:5051`:
```python
_bdg = _cb.assess(cur, tools=_MISSION_TOOLS, limit=16384)
```
So the estimator's two inputs (`cur`, `_MISSION_TOOLS`) are the *same Python objects* that go on the wire. Good — the **inputs** match. The divergence is entirely in **what the server does to them afterward**.

---

## 2. The complete transformation chain

```
STAGE A   messages list `cur`  (role, content, [tool_calls], [name])
              │
              │  ── assess() MEASURES HERE ──  (sums estimate_tokens(content) per msg
              │                                  + estimate_tokens(json.dumps(tools)))
              ▼
STAGE B   json.dumps(payload)          → HTTP body (client side)
              │  httpx POST  (main.py:2513 / openai /v1)
──────────────┼──────────── HTTP BOUNDARY — Python's visibility ends here ───────────
              ▼
STAGE C   server parses JSON → messages[] + tools[]
              ▼
STAGE D   CHAT TEMPLATE render (Go template in Ollama / Jinja in llama.cpp)
              • role markers:      <|im_start|>system … <|im_end|>   (Qwen) / <|start_header_id|> (Llama)
              • tools block:       template-specific "# Tools" preamble + per-tool JSON injection
              • tool_calls render: assistant function calls serialized back into the prompt
              • tool results:      wrapped as <|im_start|>tool … or <tool_response> … </tool_response>
              • generation prompt: trailing <|im_start|>assistant  (the "add_generation_prompt")
              ▼
STAGE E   SPECIAL / CONTROL TOKENS added
              • BOS (e.g. <|begin_of_text|> / model-specific)
              • EOS / turn separators per message
              ▼
STAGE F   TOKENIZER  (model's own byte-level BPE / SentencePiece — NOT cl100k_base)
              • byte-fallback splitting for Thai / emoji / rare code points
              ▼
STAGE G   token id array  ── this is the REAL prompt length compared to num_ctx=16384
              │
              ▼
STAGE H   llama.cpp context check:
              if n_tokens > num_ctx → SILENT truncation (context shift / drop),
              NOT an error. Model degrades → "operative went silent" (the documented
              production symptom, main.py:5067, context_budget.py:5–7).
```

`assess()` measures at **Stage A**. The number that matters for safety is produced at **Stage G**. Everything in **Stages D–F is added after `assess()` has already returned** and is invisible to it.

---

## 3. What is present at Stage A but re-encoded differently downstream

- `cur` is assembled almost entirely from `cur.append({...})` calls (≈40 sites, `main.py:3832–5851`). The system preamble is not one message but **many** separate `role:"system"` briefs (`main.py:4367–4960`: constitution, datetime banner, live rule, memory block, intent, reputation, tool-intel, control, capability, calibration, etc.), plus a per-step ledger (`main.py:5042`), plus interleaved `assistant`/`tool`/`user` turns.
- Each of those messages becomes one template envelope (role markers + separators) at Stage D. `assess()` counts only the inner `content` text.
- `tools` is measured as `json.dumps(tools)` (compact-ish Python JSON). The template at Stage D does **not** emit that exact string — it emits a template-specific rendering (headers, whitespace, sometimes pretty-printed JSON, sometimes a signature-style schema). Same information, **different token count**.

---

## 4. Summary of the pipeline

`assess()` measures the **semantic payload** (the content authors put into messages + the raw JSON of the tool schemas). The model consumes the **rendered, special-token-wrapped, model-tokenized prompt**. These are related but are **not the same object**. The gap is the subject of `TOKEN_SOURCES.md` and `ESTIMATION_ERROR.md`.
