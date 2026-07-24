# OPTIMALITY.md
### Formalizing "smallest universally-safe upper bound"

Pure mathematics. Continues (does not extend) `UPPER_BOUND_THEOREM.md`. Question:
is `bytes(x)` the *smallest* universally-safe token-count upper bound for an
estimator that knows only {rendered prompt, serialization, tokenizer family}?

Confidence tags: SUPPORTED / LIKELY / SPECULATIVE / UNKNOWN / FALSIFIED.

---

## Notation (fixed for all six files)

- `Σ = {0,…,255}`, `Σ*` finite byte strings. `bytes(x) = |x|` (length in bytes).
- A **tokenizer** `κ : Σ* → 𝕋*` maps a byte string to a token list; `n_κ(x) = |κ(x)|`.
- `𝒦` = the **tokenizer family** the estimator is told the true `κ` lies in
  (byte-level BPE, or SentencePiece with byte fallback). The exact member is
  **unknown**.
- **Content scope.** Optimality is stated for the *text* term. Special tokens
  (BOS/EOS/control atoms) are additive, `+q`, handled once in `FINAL_THEOREM.md`;
  they do not interact with the byte argument.

## Definitions (OBJECTIVE 1)

**D1 (κ-safe).** `B : Σ*→ℝ≥0` is *safe for κ* iff `B(x) ≥ n_κ(x)` for all `x`.

**D2 (universally safe).** `B` is *universally safe over 𝒦* iff it is safe for
every `κ∈𝒦`: `∀κ∈𝒦 ∀x : B(x) ≥ n_κ(x)`. Equivalently `B ≥ N` pointwise, where

> **N(x) := sup_{κ∈𝒦} n_κ(x)**   (the *family envelope*).

**D3 (strict domination).** `B₁ ≺ B₂` iff `B₁(x) ≤ B₂(x) ∀x` **and**
`B₁(x₀) < B₂(x₀)` for some `x₀`.

**D4 (minimal safe estimator).** A universally-safe `B` is *minimal* iff no
universally-safe `B'` satisfies `B' ≺ B`.

**D5 (tightness).** `B` is *tight at x* iff `B(x) = N(x)`; *tight* iff tight ∀x.

**D6 (Pareto optimality).** The objective is pointwise value (minimize) under the
feasibility constraint D2. Because the constraint set is a pointwise lower-bound
half-space `{B : B ≥ N}`, the problem is **pointwise-separable**: minimizing each
`B(x)` independently subject to `B(x) ≥ N(x)` yields the unique minimizer
`B(x)=N(x)`. Hence the Pareto frontier is the **single point `N`**.

## The one nontrivial lemma the whole question reduces to

**Lemma O1 (envelope is the unique minimal safe estimator).**
The set of universally-safe estimators is exactly `{B : B ≥ N}`; its pointwise
infimum `N` is itself a member; therefore `N` is the **unique** minimal safe
estimator, and `N` is tight by definition. *Proof:* D2 ⟺ `B ≥ N`. `N ≥ N`, so
`N` is safe. If `B ≺ N` then `B(x₀) < N(x₀)` for some `x₀`, so `B` is not safe.
∎ **SUPPORTED** (immediate).

**Consequence.** "Is `bytes` optimal?" is *exactly* the question **"is `N = bytes`?"**
- If `N(x) = bytes(x) ∀x` → `bytes` **is** the unique minimal safe estimator →
  optimal, tight, non-improvable.
- If `N(x₀) < bytes(x₀)` for some `x₀` → `bytes` is *loose* at `x₀`; a strictly
  tighter universally-safe estimator (namely `N`) exists → `bytes` **not** optimal.

Everything else (`LOWER_BOUND`, `IMPOSSIBILITY`, `ADVERSARIAL_STRINGS`) is the
determination of `N` versus `bytes`.

## Two regimes, stated up front (resolved in the later files)

- **R-universal** (`𝒦` = full byte-fallback BPE class, unrestricted merges):
  `N = bytes` — proven in `LOWER_BOUND.md`/`IMPOSSIBILITY_OF_TIGHTER_BOUND.md`.
  `bytes` optimal. SUPPORTED.
- **R-restricted** (`𝒦` known to share a *universal* merge, e.g. "always merges
  the ASCII space-run"): `N < bytes` on inputs hitting that merge → `bytes`
  loose. `bytes` **not** optimal there. This is the honest boundary of the claim
  and is where the theorem could be FALSIFIED — see `FINAL_THEOREM.md §Scope`.
