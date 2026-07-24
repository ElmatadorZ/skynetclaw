# 02 — Feasibility: which estimators can exist at all

Pure mathematics. Notation from `00`. These theorems say *when* each estimator
type is even available, before any trade-off. Confidence tags per statement.

---

## Theorem A1 (Exactness ⟺ sufficiency)
An exact estimator exists **iff** `n` is `σ(K)`-measurable, equivalently
`|V(y)| = 1` for every observable `y`.
**Proof.** (⇐) If every `V(y)` is a singleton `{v_y}`, set `E(y)=v_y`; then for
all `ω∈Ω_y`, `n(ω)=v_y=E(K(ω))`. (⇒) If `E` is exact and `ω,ω'∈Ω_y`, then
`n(ω)=E(y)=n(ω')`, so `V(y)` is a singleton. ∎ **SUPPORTED.**

**Reading.** Exactness is not an estimator virtue — it is an **information**
property of the problem. No cleverness manufactures it when `|V(y)|>1`.

## Theorem A2 (Envelope existence = boundedness of the ambiguity set)
- A finite-valued **safe-upper** estimator exists iff `n⁺(y)=⋁V(y) < ⊤_P` for all
  `y` (the ambiguity set is bounded above). Its minimum is `n⁺` (Lemma 0).
- Dually a nontrivial **safe-lower** estimator: `n⁻` always exists in a complete
  lattice; it is informative iff `n⁻(y) > ⊥_P` for some `y`.
- An **interval** estimator exists iff both hold; tightest is `[n⁻,n⁺]`.
**Proof.** Immediate from completeness of `P` and Lemma 0. Finiteness is the only
extra condition (an unbounded `V(y)` admits only `U(y)=⊤`, i.e. the vacuous
bound). ∎ **SUPPORTED.**

## Theorem A3 (Probabilistic feasibility needs, and only needs, a measure)
A probabilistic estimator at level `1−α` exists iff `Ω_y` carries a probability
measure `μ_y` making `n(·)` measurable. Then `q_{1−α}(y):=⋀{t: μ_y(n≤t)≥1−α}`
satisfies the guarantee.
**Proof.** Standard quantile construction; the CDF `t↦μ_y(n≤t)` is nondecreasing
and right-continuous, so the infimum is attained/approached with coverage
`≥1−α`. ∎ **SUPPORTED** (classical). **Cost flagged:** `μ_y` is information *not*
contained in `K`; see `03` Thm E and `01` D4.

## Theorem A4 (Abstract feasibility via Galois connection)
Given a complete lattice `A` and a **Galois connection** `(α: 2^P ⇄ A :γ)`
(`α` monotone, `γ` monotone, `α(V)≤a ⇔ V⊆γ(a)`), the map `Â(y):=α(V(y))` is the
**best sound** abstract estimator in `A`: `V(y)⊆γ(Â(y))`, and no `a<Â(y)` is
sound.
**Proof.** Soundness: `α(V)≤α(V)` ⇒ `V⊆γ(α(V))`. Optimality: if `V⊆γ(a)` then
`α(V)≤a` by the connection. ∎ **SUPPORTED** (this is the defining property of
abstract interpretation; provenance `05`).

**Reading.** `A4` is why "abstract" is a genuine, principled fallback: whenever
the exact envelope `n⁺` is unavailable (uncomputable or too costly — `03`), one
retreats to a computable lattice `A` and gets the *tightest sound* element of it,
automatically. Interval is the case `A =` intervals.

## Corollary A5 (the availability lattice of types)
For a fixed problem `⟨Ω,n,K⟩`:
```
             exact                 (needs |V|≡1)
               │  (refine info to collapse V)
   interval [n⁻,n⁺]                (needs V bounded)
            ╱        ╲
   safe-upper n⁺   safe-lower n⁻
            │            │  (envelope uncomputable/costly)
        abstract Â (sound, computable, looser)
               ┊  (a measure μ becomes available)
        probabilistic q_{1−α}  (tighter, soft safety)
```
Each downward move relaxes a requirement (exactness→one-sidedness→computability→
hard-safety) in exchange for feasibility. `03` proves each move is *forced* by a
corresponding scarcity, and `04` that no single node dominates the diagram.
**SUPPORTED** (assembles A1–A4).
