# COUNTEREXAMPLES.md
### Concrete cases where `estimated < actual` (budget says "ok", real prompt overflows)

Each case cites the code that makes it possible. All are reachable on the live EXECUTION path (`main.py:5044–5093`).

---

## CE-1 — The uncounted tool-call argument (structural, unbounded)

**Setup.** The model calls `write_file` (or `edit_file`, `run_python`, `http_request` with a body) with a large `arguments` payload. The assistant message is appended as:
```python
cur.append({"role":"assistant","content":full_text,"tool_calls":tool_calls_this})   # main.py:5376
```
On the **next** step, `assess()` runs over `cur`. For this message it computes `estimate_tokens(_content(m))` = `estimate_tokens(full_text)` only. `full_text` is often near-empty (thinking is off, `think=False`, `main.py:5099`). The entire `tool_calls` JSON — the function name + the full file content as an argument — is scored **0**.

**Result.** A `write_file` carrying a 4 KB argument contributes ~1021 estimator-tokens of real prompt but **0** to the budget (measured with the estimator's own formula). The chat template re-serializes that tool call into the prompt at Stage D, so the model *does* pay for it.

**Undercount:** unbounded — scales with argument size. **Severity: critical.**

---

## CE-2 — Thai task / Thai tool output (tokenizer, factor 2.5–5×)

**Setup.** Operator submits a Thai task (`cur.append({"role":"user","content":req.task})`, `main.py:4436`) or a tool returns Thai text (news/web/obsidian). Bucket = `history`/`tool`.

**Result.** 61 Thai chars → estimator **16 tokens**; the same text is **179 UTF-8 bytes** and a byte-fallback BPE tokenizer (nemotron3 / qwen2.5) emits ~40–90 tokens. A 2 KB Thai tool result estimated at ~500 tokens can be **1200–2500** real tokens.

**Undercount:** multiplicative on all Thai content. **Severity: high** (this system is Thai-facing).

---

## CE-3 — Death by a thousand envelopes (structural, grows with history)

**Setup.** The preamble is assembled as **many separate messages** — constitution, datetime banner, live-rule, memory, intent, reputation, tool-intel, control, capability, calibration briefs, per-step ledger… (`main.py:4367–5042`, 30+ `cur.append`). Each is one template envelope at Stage D.

**Result.** `assess()` counts only inner content. 30 messages × ~5 envelope tokens ≈ **150 tokens** uncounted, before any BOS/EOS/generation-prompt. Grows as tool/assistant/user turns accumulate.

**Undercount:** +100–250 baseline, monotonically increasing. **Severity: medium** (dangerous near the threshold).

---

## CE-4 — Tools-template wrapper ≠ `json.dumps` (structural)

**Setup.** `schema = estimate_tokens(json.dumps(tools))` (`context_budget.py:80`). But the server renders the schema through the model's tool template ("# Tools", per-tool signatures, pretty whitespace, sometimes duplicated names in prose).

**Result.** For nemotron3/qwen2.5 the template rendering of N tools is generally *longer* than the compact `json.dumps`. The schema bucket can be under-measured by tens–hundreds of tokens depending on template verbosity.

**Undercount:** template-dependent (UNKNOWN magnitude, but sign is plausibly positive). **Severity: medium.**

---

## CE-5 — The exact production shape, one step early

**Setup.** `context_budget.py:64–66` and `main.py:5067–5068` record the real incident: static preamble + 49-tool schema alone = `n_prompt_tokens=17160/16384`. The fix routes on `assess()`'s own number. But `assess()`'s number is the **estimate**, not 17160.

**Result.** If the estimate for that same static shape comes back **below** the CRITICAL ratio (0.88 × 14336 ≈ 12615) — entirely possible once you *add back* the uncounted envelopes/tool_calls that pushed the real count to 17160 — the loop sends the request believing it is "ok"/"warning", and llama.cpp silently truncates. The very failure the module exists to prevent recurs, now *masked* by a green budget reading.

**Severity: critical** (it defeats the module's stated purpose).

---

## CE-6 — cl100k regime does not save it (regime R2)

Even if `tiktoken` were installed, `cl100k_base` ≠ nemotron3/qwen2.5 vocab. Thai and code tokenize differently; envelopes/tool_calls are *still* uncounted (those are structural, not tokenizer bugs). CE-1, CE-3, CE-4 survive R2 unchanged; CE-2 is reduced but not eliminated.

---

## Aggregate

CE-1 and CE-3 are **always present** and **grow without bound**. CE-2 is **always present** for Thai content. Any single one can drive `estimated < actual`; in a long Thai run that writes files they **stack**. The existence of even one reachable counterexample is sufficient to refute "always an upper bound."
