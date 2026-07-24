# 04 — Master Impossibility & the Selection Corollary

Pure mathematics. Assembles `02`–`03`. Two results: (I) no estimator is optimal
on all five dimensions for a nontrivial problem; (II) therefore the *choice* of
estimator type is a proven function of the problem's scarcities.

---

## Triviality, defined
A problem `⟨Ω,n,K⟩` is **trivial** iff (a) `|V(y)|=1` for all `y` (no ambiguity,
Thm A1) and (b) the resulting `E` is computable in the ambient cost class. Else
**nontrivial** (it has *ambiguity* at some `y`, and/or an *undecidable/ costly*
envelope).

## Theorem F (No universal dominator)
For the product order `⊑` of `01`:

1. **Trivial ⇒ a dominator exists.** If the problem is trivial, the exact
   estimator `E` attains the ideal corner `⊤`: hard-safe (both sides, error `0`),
   tight (slack `0`), computable, requires exactly `σ(K)`, cheap as `E`. It
   dominates every other estimator.
2. **Nontrivial ⇒ no dominator.** If the problem is nontrivial, the set of
   feasible estimators has **at least two incomparable Pareto-maximal elements**,
   so no `⊑`-greatest element (dominator) exists.

**Proof of (2).** Take any `y*` witnessing nontriviality.

*Case ambiguity* (`diam(y*)>0`, envelope computable). Exhibit two feasible
estimators and show incomparability:
- `U* = n⁺` : hard-safe, computable; slack `= diam(y*)>0` (Thm B.2).
- `Q = q_{1−α}` for an available/added `μ`, `α∈(0,1)` chosen so `q_{1−α}(y*) <
  n⁺(y*)` : strictly tighter than `U*` at `y*`, but only probabilistic safety and
  requires `μ` (Thm E).
Then `T(Q) > T(U*)` while `S(U*) = hard > prob = S(Q)` and `J`-required(`Q`) >
`J`-required(`U*`). Neither `⊑`-dominates the other (each beats the other on some
axis). If instead no `μ` is admitted, replace `Q` by a **point** estimator
`p=n⁻(y*)` (tight *for the low world*, error `0` there) which is not hard-upper-
safe (Thm B.3): again `T(p)>T(U*)` on that world but `S(p)<S(U*)`. Incomparable.
∎ for this case.

*Case undecidable/costly envelope* (`n⁺` uncomputable or super-budget). Exhibit:
- `Â` : a computable sound abstract over-approximation (Thm A4): hard-safe,
  computable, but slack `> diam` (strictly looser than the — unavailable —
  envelope, Thm D.1).
- `U* = n⁺` : tight-to-envelope and hard-safe, but **uncomputable** (Thm D) /
  or costs above budget.
Then `C(Â) = computable > uncomputable = C(U*)` while `T(U*) > T(Â)`. Neither
dominates. ∎

In both cases two feasible estimators are `⊑`-incomparable, so the feasible set
has no greatest element. Since a dominator would be a greatest element, **none
exists.** ∎ **SUPPORTED** (assembles B, D, E, A4).

> **Statement.** *A single estimator is optimal in Safety, Tightness,
> Computability, Information-economy and Complexity simultaneously **iff** the
> problem is trivial. Every problem with genuine ambiguity or an intractable
> envelope forces a Pareto trade-off among estimator types.* This is the
> requested master impossibility.

### Robustness of F (red-team)
- *Could a cleverer 6th type dodge it?* No: any estimator's `D`-vector is
  constrained by Thms B/C/D/E/X, which quantify over **all** maps of the given
  output shape. A new type is still a map from `y`; its guarantee places it in
  one of the up-sets of `00`§3, inheriting the same walls. (SUPPORTED.)
- *Does completeness of `P` matter?* Only to guarantee `n⁻,n⁺` exist. For merely
  partially-ordered `P` without some sups, the safe-upper type can be *infeasible*
  (no least upper bound), which only *strengthens* "no dominator". (LIKELY.)
- *Is `α` cheating (adding `μ`)?* The trade is charged on the `J` axis precisely
  so it is not free; that is why `Q` and `U*` are incomparable rather than `Q`
  dominating. (SUPPORTED.)

---

## Corollary G (Selection theorem — "when to use which", proven)
For a problem with ambiguity set family `V`, information map `K`, envelope
decidability `dec(n⁺)`, budget `X₀`, available measure `μ?`, and required side:

| Problem condition | Pareto-optimal type | Why (theorem) |
|---|---|---|
| `|V(y)|≡1` (sufficient info, decidable) | **Exact** `E` | A1; dominates (F.1) |
| `diam>0`, need upper guarantee, `n⁺` decidable & ≤`X₀` | **Safe upper** `n⁺` | Lemma 0 + B: unique minimal hard-safe upper |
| `diam>0`, need lower guarantee | **Safe lower** `n⁻` | dual |
| `diam>0`, need two-sided quantified uncertainty, no `μ` | **Interval** `[n⁻,n⁺]` | A2: tightest sound two-sided |
| `n⁺` undecidable or cost `>X₀` | **Abstract** `Â` in a tractable `A` | A4 + D1: best sound computable |
| `μ` available, can accept `α`-risk, want sub-envelope tightness | **Probabilistic** `q_{1−α}` | A3 + E: minimal `α`-safe, strictly tighter |

Each row is **optimal for its regime and dominated in another** (that is the
content of F). Hence the "right estimator" is not a universal object but a
**function of (information, decidability, budget, prior-availability, required
side)**. **SUPPORTED.**

> The decision procedure: *measure your scarcities first (which of ambiguity /
> undecidability / budget / prior binds), then read the type off Corollary G.*
> Choosing an estimator without locating the binding scarcity is choosing a point
> in a Pareto set at random.
