# 01 — The Five Dimensions as Formal Orders

Pure mathematics. Notation from `00_ONTOLOGY.md`. To prove "no estimator wins on
all dimensions" (`04`) we must first make each dimension a partial order in which
"better" is well-defined. Confidence: SUPPORTED (definitional) unless noted.

---

## The desideratum vector

To each estimator `B` for a problem `⟨Ω,n,K⟩` we assign a vector
```
D(B) = ( Safety(B), Tightness(B), Computability(B), Info(B), Complexity(B) )
```
in a product of five posets. "Dominant" = maximal in the product order. `04`
shows the top element is unattained for nontrivial problems.

## D1 — Safety `S` (a chain)

The *kind* of guarantee that the estimate lies on the required side of the truth:
```
none  <  probabilistic(1−α)  <  hard(∀)
```
- **hard**: `∀ω∈Ω_y` the one-sided relation holds (e.g. `U(y) ≥ n(ω)`).
- **probabilistic(1−α)**: holds with `μ`-measure `≥ 1−α`; increasing in `1−α`.
- **none**: point/expected estimate, no side guarantee.
Higher = safer. Hard safety is the top. (SUPPORTED.)

## D2 — Tightness `T` (reverse of error; a chain per observation, aggregated)

For a one-sided safe estimator, the **slack** at `y` is the order-distance from
the estimate to the optimal envelope; for an interval it is the width; for a
point estimator vs truth it is `|B(y) − n(ω)|` (worst-case over `ω`). Define
```
Tightness(B) := − sup_y  slack(B,y)      (larger = tighter; 0 slack = tight)
```
Tight (top) means `U=n⁺` / `L=n⁻` / width `=diam` / point error `=0`. (SUPPORTED.)

## D3 — Computability `C` (a chain)

```
uncomputable  <  computable  <  primitive-recursive / total-decidable
```
graded by the class in which `B` (as a function of `y`) lies. Top of practical
interest: computable-total. (SUPPORTED; classes from computability theory.)

## D4 — Information availability `J` (a lattice — the σ-algebra order)

`J(B)` = the coarseness of information `B` actually consumes, ordered by
refinement of `σ(K)`:
```
K₁ ⪯ K₂  ⇔  σ(K₁) ⊆ σ(K₂)   (K₂ is finer / more informative)
```
Two readings used below:
- **Available info** — a property of the *problem* (`K`): how fine `σ(K)` is.
- **Required info** — a property of the *estimator*: the coarsest sub-σ-algebra
  it needs to meet its guarantee. *Lower required info is better* (more portable).
So on this axis "better" = "achieves the guarantee while depending on **less**."
Note the tension flagged here and proved in `03` Thm C: **available** info upper-
bounds achievable tightness, while **required** info is a cost. (SUPPORTED.)

## D5 — Complexity `X` (a chain, reverse of resource cost)

`X(B) := −cost(B)` where `cost` is time/space to compute `B(y)` as a function of
`|y|` (or of problem size). Cheaper = better. Top = `O(1)`. Distinct from D3:
`C` is the qualitative decidability class; `X` is the quantitative rate within
the decidable class. (SUPPORTED.)

## The product order and the "ideal corner"

Order estimators by
```
B ⊑ B'  ⇔  D(B) ≤ D(B') componentwise (S,T,C,J*,X),  with J counted as −required-info.
```
The **ideal corner** `⊤` is: hard-safe, tight (zero slack), computable-cheap,
requiring minimal information. `04`'s master theorem: `⊤` is **attained iff the
problem is trivial** (`|V(y)|=1 ∀y` and the envelope is decidable), and otherwise
the Pareto set is an antichain of ≥2 incomparable estimators — no dominator.

## Why the axes are genuinely independent (not collapsible)

Each pair is separated by an instance where one moves while the other is pinned:
- `S` vs `T`: fixed `V` with `diam>0` — hard safety forces slack (`03` Thm B).
- `T` vs `C`: `V` finite but `n⁺` encodes the halting set — tight ⇒ uncomputable
  (`03` Thm D).
- `T` vs `J`: refining `K` shrinks `V`, raising the tightness ceiling (`03` Thm C).
- `T` vs `X`: bounded reading budget → coarser effective info → more slack
  (`03` Thm X).
- `S` vs `X`: too small a budget to read all of `y`, if the estimator *guesses*
  the unread part, breaks hard safety (`03` Thm X, part 2).
Independence ⇒ the product order does not collapse to a chain ⇒ a real
Pareto frontier can exist. (SUPPORTED via the cited constructions.)
