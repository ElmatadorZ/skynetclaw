# 00 — Ontology of Estimation Under an Information Constraint

Pure mathematics. No reference to any application domain. This file fixes the
objects; all theorems in `02–04` are stated over them. Confidence tags:
SUPPORTED / LIKELY / SPECULATIVE / UNKNOWN / FALSIFIED. Most results here are
definitional (SUPPORTED by construction); provenance to established fields is in
`05_RELATED_WORK.md`.

---

## 0. Standing assumptions (stated, per discipline)

- **(P)** The **value codomain** `(P, ≤)` is a complete lattice (so every subset
  has a supremum `⋁` and infimum `⋀`). The canonical instance is
  `P = ℝ≥0 ∪ {∞}` with the usual order. Nothing uses more than: a partial order
  with existing sup/inf of the relevant sets.
- **(Ω)** A set of **worlds** `Ω` (the ground truth lives here).
- **(n)** A **target functional** `n : Ω → P` — the quantity we wish to know.
- **(K)** An **information map** `K : Ω → 𝒴` — everything the estimator may
  observe. It induces the equivalence `ω ∼ ω' ⇔ K(ω)=K(ω')` and the σ-algebra /
  partition `σ(K)`.

The estimator never sees `ω`; it sees only `y = K(ω)` and must act as a function
of `y`.

## 1. The ambiguity set — the single central object

For an observation `y ∈ range(K)`:
```
Ω_y := K⁻¹(y)                     (worlds consistent with what was seen)
V(y) := { n(ω) : ω ∈ Ω_y } ⊆ P    (values the truth could take, given y)
n⁻(y) := ⋀ V(y),   n⁺(y) := ⋁ V(y)   (tightest sound floor / ceiling)
diam(y) := "gap between n⁻(y) and n⁺(y)"  (in ℝ: n⁺−n⁻)
```
Everything downstream is a statement about `V(y)`. **Key reading:** information
limits estimation *only* through `V(y)`; two problems with the same family of
ambiguity sets are estimation-equivalent. (SUPPORTED, definitional.)

## 2. The six estimator types, defined over `V`

An **estimator** is a (measurable/computable) map from observations to an output.
Types differ by output shape and the guarantee demanded.

| Type | Output | Defining guarantee | Canonical optimum |
|---|---|---|---|
| **Exact** `E` | a point in `P` | `E(y) = n(ω)` for *all* `ω∈Ω_y` | exists ⟺ `|V(y)|=1`; then `E=` that point |
| **Safe upper** `U` | a point in `P` | `U(y) ≥ v` for all `v∈V(y)` | minimal `U = n⁺` |
| **(Safe) lower** `L` | a point in `P` | `L(y) ≤ v` for all `v∈V(y)` | maximal `L = n⁻` |
| **Interval** `I` | `[l,u]⊆P` | `V(y) ⊆ [l,u]` (soundness) | tightest `= [n⁻,n⁺]` |
| **Probabilistic** `Q` | a point/quantile, w.r.t. measure `μ` on `Ω_y` | `μ({ω : n(ω) ≤ Q(y)}) ≥ 1−α` | `Q = q_{1−α}` (μ-quantile) |
| **Abstract** `Â` | an element of a lattice `A`, `γ:A→2^P` | `V(y) ⊆ γ(Â(y))` (soundness) | best in `A` via Galois connection |

Notes:
- **Exact ⊂ Safe-upper ∩ Safe-lower**: when `|V|=1`, `n⁻=n⁺=E`.
- **Interval = (Safe lower, Safe upper) paired.** `[n⁻,n⁺]` is the join of the two
  one-sided optima.
- **Abstract generalizes Interval**: the interval lattice is one choice of `A`
  with `γ([l,u])=[l,u]`. Coarser `A` (signs, congruences, polyhedra…) trade
  precision for computability (`03`, Thm D).
- **Probabilistic is the only type requiring extra structure** (a measure `μ`)
  not present in `K` alone. This asymmetry drives Thm E.

## 3. What "optimal" means here (recalled from the prior optimality note)

For a fixed guarantee, the *set* of estimators satisfying it is an up-set (upper
set) in the pointwise order, and the guarantee-optimal estimator is its pointwise
extremum:
> **Lemma 0 (envelope optimality).** The safe-upper estimators are exactly
> `{U : U ≥ n⁺ pointwise}`; `n⁺` is their unique minimum. Dually `n⁻` is the
> unique maximum of safe-lower estimators. *(Proof: `U` safe ⟺ `U(y) ≥ ⋁V(y) =
> n⁺(y)`; `n⁺` satisfies it and is below every other.)* ∎ **SUPPORTED.**

This is the abstract core; `02_FEASIBILITY.md` develops existence, `03` the
trade-offs, `04` the impossibility of a type that wins on all axes.
