# CORRECTNESS_PROOF.md
### Can `context_budget.py` be trusted as a safety *proof*, or only as a heuristic?

A "safety upper-bound" claim is: **for all reachable states, `estimated_tokens ≥ actual_tokens`** (so that `estimated ≤ usable` ⇒ `actual ≤ usable` ⇒ no `num_ctx` overflow). We test that universal claim.

---

## 1. Assumption ledger (Objective 6)

For each assumption the estimator relies on, its status:
`CODE` = guaranteed by this repo's code · `LLAMA` = guaranteed by llama.cpp/Ollama · `EMPIRICAL` = only observed, not guaranteed.

| # | Assumption | Status | Evidence / why it can fail |
|---|---|---|---|
| A1 | The tokens that matter = `content` of each message | **FALSE by CODE** | `_content()` ignores `tool_calls` (`context_budget.py:52`), which is appended and rendered (`main.py:5376`). |
| A2 | `estimate_tokens` approximates the model's tokenizer | **EMPIRICAL, and weak** | Uses `cl100k_base` or `4 chars/tok` (`context_budget.py:33–49`); model is nemotron3/qwen2.5 BPE. Diverges on Thai/code. |
| A3 | 4 chars/token is "conservative" (docstring claim, line 13/48) | **FALSE in general** | Conservative only for ASCII-ish prose; anti-conservative for Thai/CJK/byte-fallback (ESTIMATION_ERROR §2). |
| A4 | `json.dumps(tools)` ≈ the schema the model sees | **EMPIRICAL** | Template rendering ≠ compact JSON (CE-4). |
| A5 | The chat template adds negligible tokens | **FALSE by LLAMA** | Templates add role markers, BOS/EOS, generation prompt, tool wrappers (TOKEN_SOURCES H2–H9). Not negligible at 30+ msgs. |
| A6 | `limit = num_ctx = 16384` and `reserve = 2048` | **CODE (mostly)** | Matches payload `options.num_ctx` (`main.py:5092`) and Modelfile (`Modelfile_Skynet-Claw:21`). But `limit`/`reserve` are constants (`context_budget.py:28–29`); if a connection/Modelfile sets a different `num_ctx`, the constant is stale — not guaranteed equal. |
| A7 | Overflow is prevented if `estimated ≤ usable` | **UNSOUND** — depends on A1–A5 all holding | They don't. So the implication breaks. |
| A8 | Overflowing `num_ctx` is the failure to avoid | **LLAMA-true** | llama.cpp silently truncates/shifts context; no error (matches "operative went silent", `context_budget.py:5–7`). Correct threat model. |

Only A6 (partially) and A8 hold. The load-bearing ones (A1, A2, A3, A5, A7) do **not**.

---

## 2. Is it conservative or inconsistent? (Objective 5)

**Inconsistent.** The error is not single-signed:

- **Overcount side (estimated > actual):** dense JSON tool schemas and repetitive text under the 4-char heuristic — BPE merges make real tokens fewer than `chars/4`. So on a schema-heavy, English, no-large-tool-call turn the estimator can read **high** (falsely pessimistic — safe but wasteful, may trigger unneeded compression).
- **Undercount side (estimated < actual):** uncounted `tool_calls`, Thai text, template envelopes (COUNTEREXAMPLES CE-1/2/3).

Because the same run mixes both, the sign of the net error flips between steps. A safety bound must be **one-signed** (always ≥). This one is **two-signed** ⇒ it is a heuristic, not a bound.

---

## 3. The proof attempt and its collapse

Claim to prove: `∀ states: estimated ≥ actual`.

Disproof: exhibit one reachable state with `estimated < actual`. COUNTEREXAMPLES CE-1 supplies it — a `write_file` turn contributes ≥ ~1000 real tokens and 0 estimated tokens, with every other term non-negative. Therefore `actual > estimated`. One counterexample refutes a universal claim. ∎

The claim is **false**. No amount of averaging rescues a universal safety property; safety is a `∀`, not an expectation.

---

## 4. What it *is* (the honest positive statement)

- It is a **correlated live signal**: `estimated` rises and falls with `actual`, so as a *trend/trigger* for compression it is genuinely useful, and it fixed the original omission (it now counts the tool schema, the term that caused the first outage — `context_budget.py:64`).
- It is **directionally correct most of the time** for English-prose-dominated turns without large tool arguments.
- It has **real conservative margin** built in (`reserve=2048` headroom, CRITICAL at 0.88 not 1.0), which absorbs *small* structural undercounts. This margin is why it "usually" works — but the margin is a fixed ~1720 tokens of slack (0.12 × 14336), and CE-1/CE-2 can exceed it.

---

## 5. Answer

`context_budget.py` **cannot be trusted as a mathematically safe upper bound.** It can be trusted as a **useful, correlated heuristic with a fixed safety margin** that holds for the common case and fails, silently and unboundedly, on the large-tool-call and Thai-heavy cases — which are reachable on the production EXECUTION path. The safety guarantee is **empirical (holds because of the 12% reserve margin), not proven.**
