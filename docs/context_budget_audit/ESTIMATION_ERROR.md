# ESTIMATION_ERROR.md
### Bounds on `error = actual_tokens − estimated_tokens`

Positive error = **undercount** = estimator reads low = **the dangerous direction** (it says "ok" while the real prompt overflows `num_ctx`).

Two estimator regimes exist (`context_budget.py:33–49`):
- **R1 (heuristic):** `tiktoken` absent → `(len(text)+3)//4`. **This is the production regime** — `tiktoken` is *not* in `requirements.txt` and `import tiktoken` fails on this machine (verified).
- **R2 (cl100k):** `tiktoken` present → `len(cl100k.encode(text))`. GPT tokenizer, still ≠ the model's tokenizer.

Neither regime uses the tokenizer that actually runs at Stage F (nemotron3 / qwen2.5 BPE).

---

## 1. Structural error (tokenizer-independent) — always ≥ 0, always omitted

These are contributions the estimator scores as **0** by construction, so they add to `actual` no matter which regime is active:

| Omitted source | Typical magnitude | Bounded? |
|---|---|---|
| `assistant.tool_calls` args (H1) | 0 → thousands of tokens (e.g. `write_file` content arg) | **No** |
| Message envelopes ×N (H2–H5) | ~4–7 tok × message count (30+ msgs → 120–210+) | Grows with history |
| Tools template wrapper delta (H6) | tens → hundreds | No |
| Tool `name`/scaffolding (H7–H8) | small, ×N tool turns | No |

**Structural floor on undercount:** even with a *perfect* tokenizer for `content`, `actual ≥ estimated + (envelopes) + (tool_calls args) + (template wrapper)`. This term is **strictly positive** and **unbounded** (dominated by H1 when the agent emits large tool arguments).

---

## 2. Tokenizer error (regime-dependent) — sign varies by content

Let `r_model` = true chars/token of the model tokenizer for a given text, `r_est` = the estimator's effective chars/token.

- **R1 heuristic** fixes `r_est = 4`.
- **R2 cl100k** gives `r_est ≈ 4` for English prose, higher for whitespace-heavy code.

Error sign flips with content type:

| Content type | Model BPE behavior | vs 4-char / cl100k | Direction |
|---|---|---|---|
| English prose | ~4 chars/tok | ≈ equal | ~neutral |
| **Thai / CJK / emoji** | byte-fallback → ~1–2 bytes/tok, ≪ 4 chars/tok | estimator **way low** | **UNDERCOUNT (severe)** |
| Dense JSON / code (schemas, args) | merges tokens → often >4 chars/tok | estimator counts *more* than real | OVERCOUNT |
| Repetitive / templated text | strong BPE merges | estimator high | OVERCOUNT |

The system's prompts are English-dominant (`backend/prompts/*`), but **user tasks and tool results are Thai** (`main.py` alone holds 3,933 Thai chars in operator-facing strings; news/web/obsidian tool outputs are Thai). Thai is the worst case and it lands in the `history`/`tool` buckets that grow during a run.

---

## 3. Concrete measurements (estimator's own formula)

| Input | chars | est tokens (R1) | UTF-8 bytes | Plausible real (model BPE) | Error |
|---|---|---|---|---|---|
| Thai sentence | 61 | **16** | 179 | ~40–90 | **−24 to −74 (undercount)** |
| `write_file` schema JSON | 250 | 63 | 250 | ~55–70 | ~0 to slight over |
| `write_file` tool_call w/ big arg | 4082 | **1021** est — but lives in `tool_calls` → **counted as 0** | — | ~1000–1400 | **−1000 to −1400 (undercount)** |

(The model tokenizer could not be loaded offline — `transformers`/`sentencepiece`/`tiktoken` all absent, verified. "Plausible real" ranges are byte-fallback estimates, tagged **LIKELY**, not measured.)

---

## 4. The four bounds requested

- **UPPER BOUND on `estimated` (i.e. the best case for safety):** none provable. There is no code path that guarantees `estimated ≥ actual`. → **the estimator is not an upper bound.**
- **LOWER BOUND on error (most conservative case):** for pure ASCII English `content` with no tool_calls and few messages, error ≈ +(envelope tokens) only, i.e. estimator is *slightly* low but close. Best realistic case.
- **WORST CASE:** a turn whose new material is a large `write_file`/`edit_file` tool call in Thai, over a long multi-message history. Undercount = (uncounted tool_calls args, unbounded) + (Thai byte-fallback factor 2.5–5×) + (30+ envelopes). Easily **thousands of tokens** low. This is the exact shape the module says overflowed in production (`n_prompt_tokens=17160/16384`, `main.py:5068`).
- **AVERAGE CASE:** dominated by two offsetting terms — JSON/code **overcount** vs. Thai + structural **undercount**. Net sign is **content-dependent and not sign-stable** → the estimator is *neither reliably conservative nor reliably tight*.

- **UNKNOWN:** the exact per-message envelope token cost and the tools-template wrapper cost for the specific nemotron3/qwen2.5 templates — never measured here (server-side, offline). Tagged UNKNOWN.

---

## 5. One-line conclusion

`error` has a **positive, unbounded structural component** (omitted `tool_calls` + envelopes) plus a **sign-unstable tokenizer component** (Thai undercounts, JSON overcounts). Therefore `estimated_tokens < actual_tokens` is not a rare edge — it is a **whole regime** (large tool-call turns, Thai text), and its magnitude is **not bounded above**.
