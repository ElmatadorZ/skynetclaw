# 05 — Provenance & Honest Novelty Assessment

Where each result already lives. **Sourcing caveat:** no external literature was
accessed while writing this (no web/library); the correspondences are recalled
from standard knowledge and exact citations are **UNKNOWN / unverified** — check
before quoting. Tags describe how *established* the component is.

---

## Component-by-component provenance

| This work | Established field / result | Confidence in the correspondence |
|---|---|---|
| Ambiguity set `V(y)`, envelope `n⁺=⋁V` = minimal safe upper (Lemma 0, A2) | **Robust / distributionally-robust optimization**: worst-case over an uncertainty set; the least conservative safe bound is the *support function* of the set | **LIKELY genuine special case** (it *is* the support-function construction) |
| Exact ⟺ `n` is `σ(K)`-measurable (A1) | **Measure theory / sufficiency**; "a statistic determines a quantity iff the quantity is measurable w.r.t. it" | **SUPPORTED** (textbook) |
| Abstract estimator, Galois connection, best sound element (A4) | **Abstract interpretation** (Cousot–Cousot 1977): sound-by-construction static analysis, `α/γ`, best abstraction | **SUPPORTED** as the same construction |
| Tightness ⟂ Computability; soundness ⇒ over-approximation (Thm D, D1) | **Rice's theorem**; undecidability of nontrivial semantic properties ⇒ exact analysis impossible ⇒ conservative analysis | **SUPPORTED** (Thm D is a direct halting reduction) |
| Coverage–width / probabilistic price (Thm E, E1) | **Statistical decision theory**; Neyman confidence intervals (coverage vs width), quantile estimation, risk `α` | **SUPPORTED** (classical) |
| Information ⇒ tightness ceiling (Thm C, C1) | **Rate–distortion / information theory**; more information (finer σ-algebra) cannot increase distortion | **LIKELY** (monotonicity is elementary; the RD analogy is structural) |
| Interval type, dependency/over-conservatism | **Interval arithmetic** (Moore) | **SUPPORTED** as the interval-domain instance of A4 |
| "No estimator best on all axes / all instances" (Thm F) | **No-Free-Lunch** (Wolpert–Macready) in spirit; and Pareto/multi-objective optimality | **LIKELY** in spirit; **SUPPORTED** as a direct assembly of B+D+E |

## What is and isn't new here

- **Not new:** every *component* theorem is either textbook (A1, A3, E),
  foundational in another field (A4/Rice/robust-opt), or an elementary
  monotonicity (C). I claim **no** novelty for them.
- **The only contribution** is *organizational*: (i) placing the six estimator
  types on one ambiguity-set/`σ(K)` substrate; (ii) proving the five-axis
  no-dominator as a single corollary of the component walls; (iii) making the
  "which estimator when" a **theorem** (Corollary G) rather than folklore; and
  (iv) exhibiting a concrete engineering instance as a *corollary* (`06`).
- **Novelty rating: LOW.** This is a synthesis/repackaging. Stated plainly per
  the honesty clause — the result's worth is unification and demotion, not
  discovery.

## Open / unverified (per discipline)
- **U-cite:** all field attributions above are from memory; citations unverified
  (no sources accessed). **UNKNOWN** until checked.
- **U-gen:** the master theorem is proved for `P` a complete lattice / `ℝ≥0`.
  Extension to non-complete or non-total value orders is only sketched (F
  robustness note); **LIKELY** but not fully proved here.
- **U-nfl:** the correspondence to formal No-Free-Lunch is *in spirit*; a precise
  reduction (measure over problem instances) is **not** carried out. **SPECULATIVE**
  as a formal equivalence.
