# IMPOSSIBILITY_OF_TIGHTER_BOUND.md
### Proof by contradiction: no universally-safe B' is strictly below bytes

Pure mathematics. Notation from `OPTIMALITY.md`; uses `N(x)=bytes(x)` from
`LOWER_BOUND.md`. Addresses OBJECTIVES 2 and 6.

---

## Theorem I1 (pointwise non-improvability)
Under the unrestricted byte-fallback family `𝒦` (`κ₀∈𝒦`), no universally-safe
estimator is strictly smaller than `bytes` at *any* point:

> `∀ B universally safe, ∀ x : B(x) ≥ bytes(x).`

**Proof.** By Lemma L1 there is `κ*∈𝒦` with `n_{κ*}(x)=bytes(x)`. Universal
safety (D2) requires `B(x) ≥ n_{κ*}(x) = bytes(x)`. ∎ **SUPPORTED.**

**Corollary I1.1 (OBJECTIVE 2 target is impossible).** There is **no**
universally-safe `B'` with `B'(x) < bytes(x)` for even one `x`, let alone "for
every `x`." The constructive request of OBJECTIVE 2 has no solution. ∎

**Corollary I1.2 (uniqueness).** The only tight universally-safe estimator is
`bytes` itself: `B` universally safe and `B(x₀)<bytes(x₀)` ⇒ unsafe (I1); so any
universally-safe `B ≤ bytes` must equal `bytes`. ∎

## The adversary, made explicit (OBJECTIVE 6)
Assume for contradiction a computable universally-safe `B'` and a point `x₀` with
`B'(x₀) < bytes(x₀)`. The adversary need not search: it **names** the witness.
- **Adversary A (degenerate):** return `κ₀` (empty merges). Then
  `n_{κ₀}(x₀) = bytes(x₀) > B'(x₀)` — `B'` undercounts, unsafe. Contradiction.
- **Adversary B (real):** for `x₀` = out-of-vocabulary bytes (PUA / control /
  unseen script), a *production* tokenizer already gives `n_κ(x₀)=bytes(x₀)`
  (measured). The contradiction holds even if `𝒦` is narrowed to "tokenizers
  that occur in practice," provided it contains one that byte-falls-back on `x₀`.

Both adversaries are `O(1)` to exhibit; the impossibility is not merely
non-constructive. **SUPPORTED.**

## Why "strictly tighter everywhere while safe" is self-contradictory
A universally-safe `B'` must dominate the envelope `N` (Lemma O1). `N = bytes`
(`LOWER_BOUND.md`). `B' < bytes` somewhere ⇒ `B' < N` somewhere ⇒ `B'` is **not**
above the envelope ⇒ not universally safe. "Strictly tighter than the envelope"
and "safe against the whole family" are contradictory by the definition of the
envelope. This is the same shape as: *no function is strictly below a pointwise
supremum and still ≥ every member.* **SUPPORTED** (definitional).

## The escape hatch — and why it changes the assumptions, not the math
`B' < bytes` **can** be safe **iff** the family is restricted so that
`N(x₀) < bytes(x₀)`, i.e. some merge is guaranteed present in *every* member and
applies to `x₀`. Then the improved bound is `N` itself (subtract the guaranteed
merge savings), and it is *again* the unique minimal safe estimator for that
smaller family. So:
- Tighter-than-`bytes` safe estimators exist **only** by importing extra
  knowledge (a guaranteed-merge assumption) — which is *no longer* "knows only
  the family" in the adversarial sense.
- Given genuinely only "byte-fallback BPE, exact merges unknown," the worst case
  includes a member that merges nothing on `x₀`, and `bytes` is unbeatable.

**Result:** under the stated knowledge (rendered prompt + serialization +
tokenizer *family* only), `bytes` is not improvable. Improvement requires
converting family-knowledge into member-knowledge. **SUPPORTED**, with the
restriction-assumption boundary stated honestly (FALSIFIED-if-restricted).
