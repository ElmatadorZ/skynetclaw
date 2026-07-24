# TOKEN_SOURCES.md
### Every contributor to the real prompt — measured vs. hidden

Tags per stage (Objective 2):
- **SUPPORTED** — `assess()` measures the *same object* the server tokenizes.
- **LIKELY** — measures an *approximation* of that object (same information, different token count).
- **UNKNOWN** — measures a *different object*, or nothing at all, for this contributor.

Reference: `context_budget.py:40–92`. Counting rule per message is `estimate_tokens(_content(m))`, where `_content(m)` returns **only `m["content"]`** as a string (`context_budget.py:52–54`).

---

## A. Token sources that ARE counted

| # | Source | How assess counts it | Tag | Note |
|---|---|---|---|---|
| 1 | `system` message text | `prompt += estimate_tokens(content)` | **LIKELY** | Text is real; token *count* uses cl100k/4-char, not model BPE. |
| 2 | `user` message text (task, nudges, ledger) | `history += …` | **LIKELY** | Same tokenizer caveat. Thai tasks → large undercount (see ESTIMATION_ERROR). |
| 3 | `tool` result text | `tool += …` | **LIKELY** | Capped at ~4000 chars by `_truncate_tool_result` (`main.py:19`) — bounds size, not token accuracy. |
| 4 | `assistant` free text (`content`) | `reasoning += …` | **LIKELY** | Only the `content` field. See hidden source #H1. |
| 5 | Tool **schema** list | `schema = estimate_tokens(json.dumps(tools))` | **LIKELY** | Counts a JSON dump; server renders schemas via template, a *different* string. |

No source in group A is **SUPPORTED** (exact), because the tokenizer at Stage F is never the one `estimate_tokens` uses (`cl100k_base` or 4-char). Every "counted" source is at best an approximation of its own token count.

---

## B. Hidden token sources — added AFTER `assess()` returns

| # | Hidden source | Where it enters the prompt | Counted by assess? | Tag |
|---|---|---|---|---|
| H1 | **`assistant.tool_calls`** (function name + full arguments JSON) | Stage D re-serializes prior tool calls into the prompt | **NO** — `_content()` reads only `content`, never `tool_calls` (`context_budget.py:52`). The assistant msg is appended with a `tool_calls` field at `main.py:5376–5381`. | **UNKNOWN** |
| H2 | **Per-message template envelope** — role markers / turn separators (`<|im_start|>role … <|im_end|>`, `<|start_header_id|>` …) | Stage D, once per message | **NO** | **UNKNOWN** |
| H3 | **BOS token(s)** at prompt start | Stage E | **NO** | **UNKNOWN** |
| H4 | **EOS / turn-end tokens** per message | Stage E | **NO** | **UNKNOWN** |
| H5 | **`add_generation_prompt`** — trailing `<|im_start|>assistant` marker requesting the reply | Stage D tail | **NO** | **UNKNOWN** |
| H6 | **Tools template wrapper** — the "# Tools / You are provided with function signatures…" preamble + per-tool formatting/whitespace that differs from `json.dumps` | Stage D | **Partially** — raw schema JSON counted (#5), wrapper text + whitespace delta NOT | **UNKNOWN** (the delta) |
| H7 | **`tool` message `name` field** | Stage D renders the tool name into the response envelope | **NO** — only `content` counted; `name` present at `main.py:5599` | **UNKNOWN** (small) |
| H8 | **Tool-call ID / role scaffolding** for tool results (`<tool_response>…</tool_response>` or JSON envelope) | Stage D | **NO** | **UNKNOWN** |
| H9 | **JSON escaping / re-encoding** inside the template (arguments embedded as JSON strings with escaped quotes/newlines) | Stage D–F | **NO** (assistant args uncounted at all; escaping adds tokens) | **UNKNOWN** |
| H10 | **Byte-fallback expansion** of Thai / emoji / rare glyphs by the model tokenizer | Stage F | **NO** — heuristic assumes ~4 chars/token regardless of script | **UNKNOWN → undercount** |

---

## C. Magnitude anchors (from code + measurement)

- **#5 schema:** the module's own docstring records a real production case — a 49-tool fallback schema ≈ **4.4k tokens** (`context_budget.py:64–66`). This is now counted (good), but as `json.dumps`, not as the template renders it.
- **H1 tool_calls:** a single `write_file` call carrying file content as its argument was measured at **~1021 estimated tokens** of `tool_calls` that `assess()` scores as **0** (demonstrated with the estimator's own formula). For a real model tokenizer the true count is higher still.
- **H2–H5 envelopes:** `cur` routinely holds **30+ separate messages** (many `system` briefs, `main.py:4367–4960`). At a typical 4–7 template tokens per message envelope that is **~120–210 tokens** of pure scaffolding, entirely uncounted.
- **H10 Thai:** 61 Thai characters → estimator says **16 tokens**; the string is **179 UTF-8 bytes**, and byte-fallback BPE tokenizes rare scripts closer to the byte count → true tokens plausibly **40–90+**.

---

## D. Verdict of this file

Every source that `assess()` counts is **LIKELY** (approximate), never **SUPPORTED** (exact).
Ten distinct token sources (H1–H10) are **UNKNOWN** and are added strictly **after** the measurement point. Several of them (H1, H6, H10) are **not bounded** by the truncation guards, so their contribution can be large and is systematically **omitted**, biasing the estimate **downward** exactly when it must not be.
