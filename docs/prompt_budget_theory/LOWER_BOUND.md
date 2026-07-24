# LOWER_BOUND.md
### The family envelope equals bytes: N(x) = bytes(x)

Pure mathematics. Notation from `OPTIMALITY.md`. Goal: compute `N(x) =
sup_{κ∈𝒦} n_κ(x)` and show it equals `bytes(x)`, which by Lemma O1 makes
`bytes` the unique minimal universally-safe estimator.

---

## Upper half — safety (N ≤ bytes)

**Fact 2 (byte ceiling).** For every byte-fallback tokenizer `κ∈𝒦` and every
`x` on its **rendered/normalized** input, `n_κ(x) ≤ bytes(x)`.
*Proof.* The atom of a byte-level tokenizer is a byte; the base vocabulary
contains all 256 bytes, so tokenization is a *partition* of the byte string into
contiguous non-empty groups (each group = one token). A partition of `bytes(x)`
elements has at most `bytes(x)` parts. Merges only *coarsen* the partition
(fewer parts). ∎ **SUPPORTED** (structural), and empirically confirmed 0/11 on
adversarial input (`ADVERSARIAL_STRINGS.md`).

Therefore `N(x) = sup_κ n_κ(x) ≤ bytes(x)`.

## Lower half — achievability (N ≥ bytes)

**Lemma L1 (the ceiling is achieved).** For every `x` there exists `κ*∈𝒦` with
`n_{κ*}(x) = bytes(x)`.

**Proof route A — the degenerate member (clean, load-bearing).**
The empty-merge tokenizer `κ₀` (merge table `M=∅`) is a well-formed member of the
byte-level BPE family: with no merges, every byte is emitted as its own token, so
`n_{κ₀}(x) = bytes(x)` for **all** `x`. Since the estimator knows only that
`κ∈𝒦` and `κ₀∈𝒦`, safety must hold against `κ₀`. ∎

*Load-bearing assumption made explicit:* `κ₀∈𝒦`, i.e. the family is **not**
restricted to exclude near-degenerate merge tables. This is the single
assumption on which universal optimality rests; `FINAL_THEOREM.md §Scope`
isolates it and shows the claim is FALSIFIED without it.

**Proof route B — a non-degenerate witness (robustness, removes reliance on κ₀).**
Fix `x`. A rank-ordered BPE fires a merge only on an adjacent pair present in the
current sequence. Choose `κ` whose merge list `M` contains no rule whose pair ever
occurs as an adjacent pair during the greedy reduction of `x` (e.g. `κ` trained on
a corpus over byte-patterns disjoint from those in `x`). No merge fires ⇒
`n_κ(x)=bytes(x)`. Such `κ` exists in the unrestricted family for every finite `x`.
∎ **LIKELY** (the "disjoint corpus ⇒ no applicable merge" step is intuitive but
its fully-general form depends on merge-interaction details; the degenerate route
A is the rigorous one, B is corroboration).

**Proof route C — empirical existence (a *single real* tokenizer suffices).**
Measured on qwen3.5 (one fixed, richly-trained κ): private-use-area bytes give
`30 tokens = 30 bytes`, control chars `40 = 40` — the ceiling is **attained** by a
real deployed tokenizer via byte-fallback on out-of-vocabulary input. So Lemma L1
does not depend on an artificial family member; the worst case is realized by
production-grade tokenizers on adversarial content. **SUPPORTED** (direct
measurement, `ADVERSARIAL_STRINGS.md`; instrument = qwen3.5 proxy for the
qwen2.5 production tokenizer — cross-model identity LIKELY, U1).

## Conclusion

`N(x) ≤ bytes(x)` (Fact 2) and `N(x) ≥ n_{κ*}(x) = bytes(x)` (Lemma L1) give

> **N(x) = bytes(x) for all x.**   (SUPPORTED, under `κ₀∈𝒦` / unrestricted family)

By Lemma O1, `bytes` is therefore the **unique minimal universally-safe upper
bound**. It is not merely safe — it is the envelope itself. Any claim of a
strictly tighter universal bound is refuted in
`IMPOSSIBILITY_OF_TIGHTER_BOUND.md`.

## What would falsify this file
A single `x` for which **no** family member attains `bytes(x)` — i.e. every
`κ∈𝒦` merges *some* pair of `x`. This occurs **iff** the family is restricted so
that a common merge is universal across all members (regime R-restricted). Under
the unrestricted family it cannot occur (route A). So the falsifier is precisely
"the family is restricted," which is a change of assumption, not a defeat of the
math. UNKNOWN in general deployments *which* regime holds; for a client that
truly knows "only the family," R-universal is the correct, safe reading.
