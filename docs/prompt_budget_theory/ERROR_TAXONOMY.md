# ERROR_TAXONOMY.md
### A formal taxonomy of every error source in prompt budgeting

Pure theory. Let `B(O)` be any estimator and `n(O) = |Φ(σ(O))|` the realized token count. Define the **signed error** `E(O) = n(O) − B(O)`. Positive `E` = **undercount** = unsafe (the window can overflow while the budget reads clear). We decompose `E` into independent, individually-attributable sources.

Two grading axes per source:
- **Sign** — `≥0` (always undercount), `≤0` (always overcount), or `±` (indefinite).
- **Boundedness** — is the source provably bounded by something the estimator can compute?

---

## Master decomposition

From `MATHEMATICAL_MODEL.md §5`, telescoping the pipeline:

```
E(O) =  E_ser  +  E_tmpl  +  E_spec  +  E_struct  +  E_tok  +  E_mm  −  E_merge  +  E_ver  +  E_samp
```

Each term is defined and graded below. The sum is exact (it is a telescoping identity over the stage functions, not a heuristic list).

---

## T1 — Serialization error `E_ser`
**Definition.** Tokens attributable to `σ⁻¹∘σ` altering byte content vs. the author's intended content: JSON escaping of embedded strings (`\"`, `\n`, `\uXXXX`), unicode normalization mismatch, whitespace the encoder inserts.
**Sign:** `±` (escaping usually adds; normalization can add or remove).
**Bounded?** Yes, by a constant factor of the escaped content length — *if* the encoder is known.
**Notes.** Small per field, but multiplies across many structured fields (e.g. arguments carrying code with many quotes/newlines).

## T2 — Template injection error `E_tmpl`
**Definition.** Tokens of role markers, turn separators, tool-schema wrapper `ρ(T)`, tool-call/result delimiters, and the generation prompt (`g_0, a_i, b_i, g_1, ρ` in the model). 
**Sign:** **`≥0`** — the template only *adds* relative to bare content.
**Bounded?** **Only if `τ` is known.** From the client's view it is **unbounded**: `τ` may inject arbitrary fixed text (a large system wrapper, duplicated schema, verbose tool prose).
**Notes.** Grows with **message count**, so it drifts upward over a multi-turn run even when content is flat. This is the structurally dominant undercount for long conversations.

## T3 — Special-token error `E_spec`
**Definition.** BOS/EOS/control atoms (type 12). Each is `+1` token of zero byte-width.
**Sign:** **`≥0`.**
**Bounded?** Yes if the *count* of structural events in `τ,ε` is known (≈ 1–3 per message + a few global). Not derivable from content bytes.
**Notes.** Includes pathologies like double-BOS when a template and the loader both prepend BOS — a real, observed defect, so `E_spec` is not even guaranteed to equal the "intended" count.

## T4 — Structural-omission error `E_struct`
**Definition.** Tokens of authored payload the estimator *fails to read* because it lives in non-`content` fields: tool-call arguments, function names, tool ids, message names.
**Sign:** **`≥0`** (omitted mass can only be missing).
**Bounded?** Bounded by the byte content of `extras`, which **is** visible to the author — so this is the one nonnegative source that is *always closable in principle* by reading all fields. Its presence is an estimator defect, not a theoretical necessity.
**Notes.** Distinct from T2: T4 is *authored* content wrongly excluded; T2 is *injected* content that was never in `O`.

## T5 — Tokenizer-mismatch error `E_tok`
**Definition.** `⟨semantic⟩_κ − f(‖O‖_b)` — the gap between the true segmentation under `κ` and the estimator's surrogate (`bytes/ρ`, or a different tokenizer `κ̃`).
**Sign:** **`±`.** Overcount on dense JSON/code/repetitive text (strong BPE merges → few real tokens); undercount on rare scripts / byte-fallback languages (near 1 token/byte). Language-dependent (see T6).
**Bounded?** Below by `0` and above by `bytes` (Fact 2), but the *tight* value needs `κ`. The sign is not fixable without `κ`.
**Notes.** This is the term that makes the estimator **not sign-stable**: the same run mixes overcounting and undercounting spans.

## T6 — Language / script effect `E_lang` (a structured sub-case of `E_tok`)
**Definition.** The dependence of `E_tok` on the writing system: Latin prose ≈ 4 chars/token; CJK, Thai, Indic, emoji, and out-of-vocabulary tokens trend toward byte-fallback (1–2 bytes/token). A `bytes/4` or Latin-calibrated surrogate under-predicts these by 2–5×.
**Sign:** `≥0` (undercount) for low-resource scripts; `≤0` for scripts the surrogate over-weights.
**Bounded?** Bounded by `bytes` above; tight value tokenizer-specific.
**Notes.** Separated out because it is the most *operationally common* driver of undercount in non-English deployments and is invisible to Latin-calibrated intuition.

## T7 — Multimodal-expansion error `E_mm`
**Definition.** Images/audio/video expand to a token count set by the model's patchifier/vision encoder (fixed grid, or content/resolution-dependent). A placeholder in `O` occupies ~1 unit of visible content but tens–thousands of tokens.
**Sign:** **`≥0`** (massively).
**Bounded?** Only if the model's media-tokenization rule is known; otherwise unbounded.

## T8 — Merge-saving `E_merge` (the single negative-signed term)
**Definition.** `Δ_merge ≥ 0` from Fact 1 — cross-boundary merges that make the whole shorter than the sum of parts. Enters `E` with a **minus** sign, i.e. it makes the estimator *safer* (more conservative).
**Sign:** contributes `≤0` to `E`.
**Bounded?** `0 ≤ E_merge ≤ Σ(boundary effects)`; needs `κ` to quantify. It is the estimator's only structural *ally*.

## T9 — Version / deployment drift `E_ver`
**Definition.** The realized `Φ` changes without notice: a template update, tokenizer revision, server-side prompt injection (safety preambles, system-of-record headers added by a gateway), or a different `num_ctx` than assumed.
**Sign:** `±`, often `≥0` (gateways add).
**Bounded?** **No** — by definition the estimator does not know the change occurred. This is *epistemic*, not numerical, error.

## T10 — Sampling / runtime uncertainty `E_samp`
**Definition.** Residual nondeterminism the *provider itself* warns about even when it owns the tokenizer (e.g. token-count endpoints documented as estimates that "may differ by a small amount"), plus reserved-generation miscalibration (`n_gen` actual vs. assumed).
**Sign:** `±`, small.
**Bounded?** Empirically small; not formally zero.

---

## Grading summary

| Term | Source | Sign | Bounded by client-computable quantity? |
|---|---|---|---|
| T1 `E_ser` | serialization/escaping | ± | yes, if encoder known |
| T2 `E_tmpl` | template injection | **≥0** | **no** (unless τ known) |
| T3 `E_spec` | special tokens | **≥0** | yes, if τ/ε structure known |
| T4 `E_struct` | omitted authored fields | **≥0** | **yes** (author sees the bytes) |
| T5 `E_tok` | tokenizer surrogate gap | ± | ceiling `bytes`; tight needs κ |
| T6 `E_lang` | script/byte-fallback | ≥0 (low-resource) | ceiling `bytes`; tight needs κ |
| T7 `E_mm` | multimodal expansion | **≥0** | no (unless media rule known) |
| T8 `E_merge` | cross-boundary merges | ≤0 (safe) | needs κ |
| T9 `E_ver` | deployment drift | ± | **no** (epistemic) |
| T10 `E_samp` | runtime residual | ± small | ~empirical |

---

## Two structural conclusions

1. **The nonnegative terms outnumber and out-scale the single negative one.** `E_tmpl, E_spec, E_struct, E_mm, E_lang` all push toward undercount; only `E_merge` pushes toward safety, and it is bounded by boundary effects. So the *natural drift* of a content-only estimator is toward **unsafe**, not safe.
2. **The unbounded terms are exactly the ones requiring downstream knowledge.** `E_tmpl` (needs τ), `E_mm` (needs media rule), `E_ver` (needs deployment identity) have **no client-computable bound**. Everything the client *can* bound (T1, T3, T4, and the `bytes`-ceiling of T5/T6) is bounded; everything it *cannot* see is unbounded. The taxonomy therefore localizes the entire safety question to: *does the estimator possess `τ`, `ε`, and the deployment identity?* — which is the theorem of the next file.
