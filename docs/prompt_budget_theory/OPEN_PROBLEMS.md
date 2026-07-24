# OPEN_PROBLEMS.md
### What remains genuinely unknown in prompt-budget theory

Pure theory. Each entry states the open question, why the tools in `UPPER_BOUND_THEOREM.md` do **not** already close it, and what a solution would require. Ordered from most foundational to most applied.

---

## OP-1 — A published, tight *lower* bound on chars-per-token per tokenizer
**Open.** Fact 2 gives the loose ceiling `|κ(x)| ≤ bytes(x)`. There is no known **non-trivial, provable** upper bound of the form `|κ(x)| ≤ α·bytes(x) + c` with `α < 1` that holds for *all* inputs of a given tokenizer — because adversarial rare-script/OOV input forces `α → 1`. 
**What's unknown:** whether, for a *specific realistic input distribution* `D`, one can certify `α_D < 1` with high probability *and* a hard worst-case fallback. A distribution-dependent-but-certified expansion constant would let a safe bound be tight on-distribution and merely safe off-distribution. No such certified constant exists in the literature.

## OP-2 — A bounded, model-agnostic characterization of template injection `E_tmpl`
**Open.** Theorem 2 shows template injection is unbounded over an *unrestricted* class `𝒯`. Real templates are not unrestricted — they are structured (finite role set, one wrapper per tool, one generation prompt). 
**What's unknown:** a formal *grammar* for chat templates such that `E_tmpl` is provably bounded by a function of `(k messages, |T| tools)` alone — i.e. a template-class `𝒯_bounded` with a proven `E_tmpl ≤ ϕ(k,|T|)`. This would convert "measure the constants per model" folklore into a theorem. It does not exist; templates are currently free-form Jinja with no bounding contract.

## OP-3 — Cross-implementation tokenizer equivalence certificates
**Open.** BPE is deterministic *given identical merges and identical pre-tokenization*, but SentencePiece-vs-HuggingFace merge-order semantics and pre-tokenizer regexes can diverge, and BOS-handling differs between template and loader (double-BOS). 
**What's unknown:** a decidable procedure that, given two tokenizer artifacts, *certifies* `κ_A ≡ κ_B` on all inputs (or exhibits a divergence witness). Without it, `E_ver` from a silent tokenizer swap is undetectable by the budget. This is an open verification problem, not merely an engineering one.

## OP-4 — Budgeting under multimodal expansion `E_mm`
**Open.** Image/audio/video token counts are set by patchifiers/encoders whose rules are (a) model-specific, (b) sometimes resolution/content-dependent, (c) occasionally undocumented. 
**What's unknown:** a general upper-bound function for media tokens computable from the *media metadata alone* (dimensions, duration, codec) across model families. Present practice is per-model tables. A cross-family theorem is open.

## OP-5 — Sound budgeting across an *untrusted or drifting* gateway
**Open.** Theorem 4 kills safety when a downstream gateway may inject content or swap the pipeline unnotified. 
**What's unknown:** a *protocol* (cryptographic or attestation-based) by which an inference endpoint commits to a specific `(τ, ε, κ, version)` at measurement time so the client's bound is transferable to inference time — a "tokenization attestation." No such standard exists; count-token endpoints return a number, not a *binding commitment* to the pipeline that will serve the next request.

## OP-6 — The provider's own residual `E_samp`
**Open.** Vendors that own the full pipeline still document their token counts as **estimates** that "may differ by a small amount." 
**What's unknown, publicly:** the *source and magnitude model* of that residual — batching effects, nondeterministic normalization, version skew between the count path and the inference path. Whether it is formally zero-able is unknown outside the providers. This is the gap between Corollary 1.2 ("co-location ⇒ tight") and reality ("co-location ⇒ tight up to an unspecified ε").

## OP-7 — Sub-additivity slack `Δ_merge` as a usable resource
**Open.** The only safety-positive term (`E_merge`, Fact 1) is discarded in every practical bound because quantifying it needs `κ`. 
**What's unknown:** whether cross-boundary merge savings admit a *lower* bound computable from template structure (e.g. "concatenating these two known markers saves ≥ m tokens"), which would let a bound be *tightened safely* using template knowledge alone. Untouched in the literature.

## OP-8 — Compression that is *token-count-verifiable*, not just quality-verifiable
**Open.** LLMLingua-family compressors optimize quality under a target ratio; the recent formal-framework work verifies *content commitments*. 
**What's unknown:** a compressor with a *post-compression certificate* `n(compressed O) ≤ C − n_gen` that is sound without re-invoking the server — i.e. compression and budgeting proven together. Current systems compress, then *hope* (or re-measure via co-location).

## OP-9 — Statistical vs. worst-case budgeting formalism
**Open.** All of the above is worst-case (`∀ O`). Production tolerates a small overflow probability. 
**What's unknown:** a clean PAC-style theory — "with probability ≥ 1−δ over input distribution `D`, `B(O) ≥ n(O)`" — with `B` computed from visible content plus a *learned* template/tokenizer surrogate, and *certified* generalization bounds on the undercount tail. This would formalize the honest middle ground between "loose byte ceiling" (safe, wasteful) and "content heuristic" (tight, unsafe). It is not established.

---

## The single open question beneath them all

> **Can the serialization+template contribution be made a *bounded, attested* function of the visible request — without co-locating with the inference server?**

OP-2 (bounded template grammar) and OP-5 (pipeline attestation) are two attacks on it — one mathematical, one protocol-level. Until one succeeds, `UPPER_BOUND_THEOREM.md` Theorem 2 stands: outside co-location or a bounded-template contract, a *visible-prompt-only* safe budget is impossible, and every deployed "budget" is either the **loose byte ceiling** (safe, `3–5×` wasteful) or an **empirical heuristic** (tight, unsafe in the tail). Closing that gap is the open frontier.
