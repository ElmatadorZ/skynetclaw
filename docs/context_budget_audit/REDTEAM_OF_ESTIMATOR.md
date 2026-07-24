# REDTEAM_OF_ESTIMATOR.md
### Adversarial destruction of the estimator. Assume a production outage rides on proving it wrong.

Objective: break `estimated ≥ actual` and/or `level` correctness. Each attack is a reachable state on `main.py`'s EXECUTION loop. No code changed; these describe inputs, not patches.

---

## ATTACK 1 — Hide tokens in `tool_calls` (the kill shot)

**Vector.** Get the model to emit one large-argument tool call (`write_file`, `edit_file`, `run_python`, `http_request` with body). The assistant turn is stored with `tool_calls` (`main.py:5380`); `assess()` reads only `content` (`context_budget.py:52`).
**Effect.** Arbitrary tokens enter the *next* prompt at Stage D while scoring **0** in the budget. A 6 KB file argument ≈ 1500+ real tokens, invisible.
**Why fatal.** Unbounded and structural — no tokenizer choice, no reserve margin fixes it. Stack two such turns and you clear the entire 1720-token reserve while `level` still reads `ok`.
**Status: BROKEN.**

---

## ATTACK 2 — Thai / byte-fallback payload

**Vector.** Submit a Thai task, or force a Thai tool result (news/web/obsidian). `content` counted at 4 chars/token; model uses byte-fallback BPE.
**Effect.** 2.5–5× undercount on that text (61 chars → 16 est vs ~40–90 real). Fill `history`/`tool` with Thai and the real prompt is multiples of the estimate.
**Why fatal.** The reserve margin is 12%; this attack produces 150–400% error on the affected span.
**Status: BROKEN** (and it is the *native language of this deployment*).

---

## ATTACK 3 — Envelope inflation

**Vector.** Anything that increases message *count* without increasing counted `content` much — many short tool calls, many system briefs (already 30+ at `main.py:4367–4960`), rapid nudge/ledger churn.
**Effect.** Each message adds BOS-less envelope tokens (role markers, separators, generation prompt) that `assess()` never counts (TOKEN_SOURCES H2–H5).
**Why fatal.** Monotonic drift: the longer the run, the more the estimate lags — worst exactly when you approach the limit.
**Status: BROKEN (slow bleed).**

---

## ATTACK 4 — Schema template blow-up

**Vector.** Rely on the counted `json.dumps(tools)` (`context_budget.py:80`) being the schema size. Trigger the 49-tool fallback set (`context_budget.py:64`).
**Effect.** Server renders tools via the model template (headers + per-tool signatures + whitespace), generally larger than compact JSON. The schema bucket under-reads by the template delta.
**Status: DENTED** (sign plausibly positive; magnitude UNKNOWN, template-specific).

---

## ATTACK 5 — Stale `limit` constant

**Vector.** `assess(limit=16384)` is hard-passed at all call sites (`main.py:5051` etc.) and `DEFAULT_LIMIT=16384` (`context_budget.py:28`). If a connection, Modelfile, or exec runtime serves a **smaller** effective `num_ctx` (e.g. a quantized 8K build, or Ollama capping to the model's trained context), the budget computes against 16384 while the server truncates at the smaller number.
**Effect.** `usable` is overstated → `ratio` understated → false `ok`.
**Status: BROKEN if any runtime's real ctx < 16384** (not verified per-runtime — UNKNOWN, but unguarded).

---

## ATTACK 6 — Reserve is not enforced downstream

**Vector.** `reserve=2048` assumes the *response* fits in 2048. Nothing caps generation (`num_predict` unset in payload `options`, `main.py:5092`). A verbose reply consumes more; the *next* turn's prompt then carries a longer assistant `content`.
**Effect.** The headroom the whole safety argument leans on is an assumption about model behavior, not an enforced limit.
**Status: DENTED** (indirect; affects the margin that A2/A3 undercounts eat into).

---

## ATTACK 7 — Regime downgrade is silent

**Vector.** `tiktoken` is absent in production (verified: not in `requirements.txt`, import fails). The code silently falls to the 4-char heuristic (`context_budget.py:36–37, 43–49`) with no signal in the assessment output.
**Effect.** Operators reading `total`/`ratio` cannot tell whether they got cl100k or the cruder heuristic. The weaker regime (worse on Thai) is the one actually running.
**Status: BROKEN (observability)** — the number carries no confidence tag.

---

## Damage report

| Attack | Breaks `estimated ≥ actual`? | Bounded? | Reachable now? |
|---|---|---|---|
| 1 tool_calls | **Yes** | No | Yes (any file write) |
| 2 Thai | **Yes** | No | Yes (default language) |
| 3 envelopes | Yes (drift) | Grows | Yes (every long run) |
| 4 schema template | Likely | UNKNOWN | Yes (fallback toolset) |
| 5 stale limit | Yes | — | Conditional (UNKNOWN) |
| 6 reserve | Weakens margin | — | Yes |
| 7 regime | Observability | — | Yes (prod) |

**Conclusion of the red team:** the estimator is destroyed as a *proof* by Attack 1 alone (single reachable counterexample, unbounded). Attacks 2 and 3 make failure the *expected* behavior of this specific Thai-language, file-writing deployment rather than a corner case. The 12% reserve margin is the only thing standing between the heuristic and the outage it was built to prevent, and Attacks 1–2 each individually exceed that margin.
