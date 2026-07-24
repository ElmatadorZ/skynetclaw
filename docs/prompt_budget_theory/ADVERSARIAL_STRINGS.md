# ADVERSARIAL_STRINGS.md
### Empirical assault on the byte ceiling (OBJECTIVE 3)

Measurement, in service of the proof. Instrument: qwen3.5:9b real tokenizer via
Ollama `/api/generate` (`raw:true`, `prompt_eval_count`), calibrated with no
fixed template overhead (`"hello"`→1, `"a"×100`→13). `raw:true` ⇒ pure
tokenization of the given bytes. This is a **proxy** for the production
qwen2.5-14b tokenizer (llama.cpp `:8080` was down this session); cross-model
identity is LIKELY (same Qwen 151k-vocab BPE class), not SUPPORTED — tag **U1**.

Target: find any `x` with `n_κ(x) > bytes(raw x)` — which would break Fact 2 and,
with it, the safety half of optimality. The only mechanism that *could* do this
is **normalization expansion**: if `κ` normalizes `x → ν(x)` with `bytes(ν(x)) >
bytes(x)` before tokenizing, then `n_κ` is bounded by `bytes(ν(x))`, not
`bytes(x)`. Every other adversary (ZWJ, RTL, combining, surrogates, PUA) only
*adds bytes* and stays under the ceiling.

---

## Results (raw bytes vs NFKC bytes vs real tokens)

| case (× reps)             | code pts | raw B | NFKC B | tokens | tok ≤ rawB |
|---|---|---|---|---|---|
| U+FDFD BISMILLAH ligature | 1  | 3  | 3   | 3  | YES |
| U+FDFA SALLALLAHOU ×5     | 5  | 15 | **165** | 15 | YES |
| fullwidth digits ×5       | 15 | 45 | 15  | 15 | YES |
| ligature ﬃ ×10            | 10 | 30 | 30  | 30 | YES (at ceiling) |
| combining zalgo (e+20 ◌́)  | 21 | 41 | 40  | 21 | YES |
| ZWJ family emoji ×3       | 15 | 54 | 54  | 39 | YES |
| RTL override + Arabic ×2  | 14 | 32 | 32  | 14 | YES |
| private-use area ×10      | 10 | 30 | 30  | 30 | **YES (= ceiling)** |
| control chars ×10         | 40 | 40 | 40  | 40 | **YES (= ceiling)** |
| lone-surrogate-ish (WTF8) | 10 | 30 | 30  | 3  | YES |
| mixed pathological        | 6  | 18 | **45** | 11 | YES |

**Byte-ceiling violations: 0 / 11.**

## Interpretation

1. **The normalization attack does not fire.** U+FDFA expands 3→165 bytes under
   NFKC, yet tokenizes to **15 tokens ≤ 15 raw bytes**; "mixed pathological"
   expands 18→45 NFKC yet is 11 tokens. ⇒ the Qwen byte-BPE **does not apply
   expanding compatibility normalization at tokenization time** — it tokenizes
   the *raw* UTF-8 bytes. So `bytes(raw x)` is safe for this family without a
   normalization correction. **SUPPORTED** for this tokenizer; the general-`ν`
   caveat is retained abstractly (a *different* family with NFKC-in-pipeline
   would need `bytes(ν(x))`, obtainable from the known serialization `ε`).

2. **The ceiling is attained by a real tokenizer.** PUA (30=30) and control
   chars (40=40) reach exactly one token per byte via byte-fallback — empirical
   witness for Lemma L1 (route C). Optimality is not an artifact of the
   degenerate family member; production tokenizers realize the worst case on
   OOV input.

3. **No adversary exceeded bytes.** ZWJ, RTL override, combining stacks,
   surrogate-ish WTF-8, PUA, controls — all `≤ bytes`. Consistent with Fact 2's
   partition argument (a byte cannot split into >1 token).

## Honest limits of this evidence
- **U1**: qwen3.5 ≠ qwen2.5-14b (production); Qwen-family identity assumed.
- **U2**: a tokenizer *with* an NFKC/NFKD normalizer in-pipeline (some
  SentencePiece configs) is **not** tested here and *could* need `bytes(ν(x))`;
  the byte-ceiling then holds on `ν(x)`, not raw `x`. UNKNOWN for such families;
  the fix is assumption-covered (estimator knows `ε ⊇ ν`).
- Sample is adversarially *chosen*, not random — appropriate for a
  counterexample hunt (one violation would suffice to break safety; none found),
  but it establishes *existence of no counterexample in this set*, not a
  probabilistic bound.
