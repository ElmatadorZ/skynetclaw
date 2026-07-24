# 03 — The Trade-off Theorems

Pure mathematics. Notation from `00`–`01`. Each theorem pins four of the five
dimensions and shows a forced loss on the fifth. Together they are the load
for the master impossibility (`04`). Confidence tags per statement.

---

## Theorem B (Safety ⟂ Tightness — the diameter law)
Fix `y` with `diam(y) = n⁺(y) − n⁻(y) > 0` (nontrivial ambiguity; work in
`P=ℝ≥0`). Then:
1. No **exact** estimator exists at `y` (Thm A1).
2. Every **hard-safe upper** `U` has worst-case error `sup_{ω∈Ω_y}(U(y)−n(ω)) =
   U(y) − n⁻(y) ≥ n⁺(y) − n⁻(y) = diam(y)`, with equality iff `U(y)=n⁺(y)`.
3. Every **zero-slack point** estimator (error `0` on some `ω`) is **unsafe** for
   another `ω'∈Ω_y` (over- or under-shoots), so cannot be hard-safe on both
   sides.
**Proof.** (2) `U(y) ≥ n⁺(y)` by safety; subtract the smallest true value
`n⁻(y)`. (3) a single point `p` cannot equal two distinct values `n(ω)≠n(ω')`;
if `p=n(ω)` then `p<n⁺` so `p<n(ω')` for the maximizing `ω'`, violating upper
safety at `ω'`. ∎ **SUPPORTED.**

> **Diameter law:** hard safety costs at least `diam(y)` of tightness. Safety and
> tightness are jointly maximal **iff** `diam(y)=0` **iff** `|V(y)|=1`. The
> trade-off is not a modelling artifact; it equals the ambiguity of the
> information.

## Theorem C (Tightness is bought only with Information)
Let `K₁ ⪯ K₂` (K₂ finer). For every `y₂∈range(K₂)` with `y₁=` its image under the
coarsening, `Ω_{y₂} ⊆ Ω_{y₁}`, hence `V₂(y₂) ⊆ V₁(y₁)`, hence
```
n⁻₁ ≤ n⁻₂ ≤ n⁺₂ ≤ n⁺₁    and    diam₂ ≤ diam₁.
```
Thus refining information **weakly tightens both envelopes and can only shrink the
diameter**. Moreover `diam≡0` (exactness attainable) **iff** `σ(K)` is fine enough
that `n` is measurable (Thm A1).
**Proof.** Refinement means each `K₂`-cell is contained in a `K₁`-cell; image of a
subset under `n` is a subset; sup/inf are monotone under `⊆`. ∎ **SUPPORTED.**

> **Corollary C1 (no free tightness).** The tightness ceiling `−diam(y)` is a
> functional of the *information map alone*. To raise it you must supply a finer
> `K` (physically: measure more). No estimator, however clever, beats the ceiling
> its information sets. This is the `J → T` coupling.

## Theorem D (Tightness ⟂ Computability — undecidable envelopes)
There is a problem `⟨Ω,n,K⟩` with every `V(y) ⊆ {0,1}` (so `diam ≤ 1`, envelope
*finite*) for which `n⁺` is **not computable**, yet a computable hard-safe upper
estimator exists (the constant `1`).
**Construction.** Let `y` encode a machine `M_y`. Worlds `Ω_y = ℕ ∪ {∞}`;
`n(k)=1` iff `M_y` halts exactly at step `k`, `n(∞)=0`. Then
`n⁺(y)=1 ⇔ M_y halts` = the halting predicate — uncomputable. But `U≡1` is
computable and hard-safe (`1 ≥ n(ω) ∀ω`). Any estimator within `<½` of `n⁺`
decides halting, so **no computable estimator is even approximately tight**.
∎ **SUPPORTED** (reduction from halting; the "nontrivial semantic property ⇒
undecidable" phenomenon, provenance Rice, `05`).

> **Corollary D1 (soundness forces approximation).** When `n⁺` is uncomputable,
> the only computable hard-safe options are **loose over-approximations**
> (abstract estimators, Thm A4). Hence: *computable ∧ hard-safe ⇒ not tight*, on
> such problems. This is the `T ⟂ C` wall and the raison d'être of the abstract
> type.

## Theorem E (Probabilistic tightness has a strict price)
Suppose `μ_y` is available. For `α∈(0,1)`, `q_{1−α}(y) ≤ n⁺(y)`, and the gap
`n⁺(y) − q_{1−α}(y)` can be made arbitrarily large by placing the top of `V(y)`
on an `α`-thin tail. But:
1. `q_{1−α}` is **hard-safe iff** `α=0`, in which case `q_1 = ess sup_{μ} n =
   n⁺` (assuming `μ` has support meeting `n⁺`): the tightness gain vanishes.
2. Achieving `α>0` tightness **requires** the measure `μ_y ∉ σ(K)` (extra
   information, `01` D4) and yields only **probabilistic** safety: `μ_y(n>q)=α>0`.
**Proof.** Quantile monotonicity for the gap; (1) coverage `1` forces the
quantile to the essential supremum; (2) is the definition of `μ`-quantile and the
positivity of the residual tail mass. ∎ **SUPPORTED** (classical decision theory,
`05`).

> **Corollary E1 (the coverage–width law).** Tightness beyond the hard-safe
> envelope is purchased with (a) a prior and (b) exactly `α` units of surrendered
> safety. There is no probabilistic estimator that is both hard-safe and strictly
> tighter than `n⁺`. This is the `S(hard) ⟂ T` trade re-mediated by information.

## Theorem X (Complexity ⟂ Tightness, and a Complexity ⟂ Safety cliff)
Model a resource-bounded estimator as reading at most `b` bits of `y`.
1. **Loosening (safe regime).** Reading a prefix induces a coarser effective
   information map `K_b ⪯ K`; by Thm C, `diam_b ≥ diam`, so less compute ⇒ (weakly)
   more slack. Tightness is monotone nondecreasing in `b`, with ceiling at
   full-read `= −diam`. **SUPPORTED** (Thm C applied to `K_b`).
2. **Safety cliff.** If, instead of coarsening soundly, the estimator *assumes*
   the unread `|y|−b` bits contribute the minimum (to save work), it computes a
   value `< n⁺` on inputs whose unread part mattered → **hard safety fails**
   (undercount). So sub-linear compute is compatible with hard safety *only* via
   sound coarsening (part 1), never via optimistic omission.
   **Proof.** Exhibit two observations agreeing on the read prefix but differing
   on the tail with distinct `n⁺`; the omission-estimator returns one value,
   unsafe for the larger. ∎ **SUPPORTED.**

> **Corollary X1.** A hard-safe estimator must, at minimum, *read enough of the
> information to bound `V`*; there is a complexity floor below which safety and
> non-triviality are incompatible. Cheapness is traded against tightness above
> that floor, and against safety below it.

---

## Summary of the walls

| Pinned high | Forced loss | Condition | Theorem |
|---|---|---|---|
| Safety(hard) + no info gain | Tightness ≥ diam | `diam>0` | B |
| Tightness | needs finer `K` | always | C |
| Tightness + Computable | impossible (loose only) | `n⁺` undecidable | D |
| Tightness beyond `n⁺` | loses hard safety + needs `μ` | `α>0` | E |
| Cheapness (low `X`) | more slack, or (if omitting) unsafe | bounded read | X |

No wall is removable without paying on another axis. `04` assembles these into
the non-existence of a dominator.
