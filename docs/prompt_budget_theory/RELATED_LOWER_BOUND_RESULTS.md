# RELATED_LOWER_BOUND_RESULTS.md
### Where this optimality result sits in known mathematics (OBJECTIVE 5)

Pure mathematics — placement, not new theory. **Sourcing caveat:** no external
literature was accessed this session (no web/library). The results below are
recalled from standard knowledge of these fields; exact citations are **UNKNOWN /
unverified** and must be checked before quotation. Each analogy is tagged by how
*formal* the correspondence is, not by how famous the result is.

---

## 1. Robust optimization — the exact frame (LIKELY formal equivalence)
The problem "least `B` with `B ≥ n_κ` for all `κ` in ambiguity set `𝒦`" is a
textbook **robust feasibility / minimax** problem. Its solution is always the
**support/upper-envelope function** `N(x)=sup_{κ∈𝒦} n_κ(x)`. Our result is the
instantiation `N = bytes`. The *optimality* half (Lemma O1) is not special to
tokenizers — it is the general fact that the pointwise sup of the uncertainty set
is the unique minimal robust-feasible bound. **This is the cleanest and most
defensible correspondence.** LIKELY a genuine special case, not just an analogy.

## 2. Kolmogorov / incompressibility (LIKELY as analogy, SPECULATIVE as theorem)
"For every `x` some family member spends one token per byte" mirrors the
**incompressibility theorem**: for any (prefix-free) description method, most
strings are incompressible, so no method shortens all strings. Here the family
plays the role of the description method and byte-fallback guarantees a member
for which `x` is "incompressible" (pure bytes). The *structure* — a per-object
adversary defeating any uniform improvement — is the same. A precise reduction
(coding cost ↔ token count) is plausible but **not carried out here**;
SPECULATIVE as a formal theorem, LIKELY as an explanatory analogy.

## 3. Universal source coding / Kraft (LIKELY analogy)
The byte-identity tokenizer `κ₀` is the "no-model" code: it assigns each symbol
its raw cost. Beating it uniformly would beat the worst-case source, which
universal-coding lower bounds forbid without distributional assumptions —
matching our "improvement needs a guaranteed-merge (distributional) assumption."
Correspondence is at the level of *worst-case-vs-average-case*, LIKELY.

## 4. Competitive analysis (LIKELY, quantitative)
Read `bytes` as an online/robust strategy against the adversary "which `κ`":
- **Competitive ratio vs the family envelope:** `bytes / N = 1` — byte-count is
  **1-competitive** (optimal) against the family. SUPPORTED (it *equals* `N`).
- **Price of universality vs a single known `κ`:** `bytes / n_κ ≈ 3–5` for
  natural Latin text (Cor 1.1 of `UPPER_BOUND_THEOREM.md`); ≈ 17 for Thai
  (measured 544 B / 32 tok). This is the cost of not knowing the member — the
  gap between minimax-safe and oracle-tight. SUPPORTED (measured), and it is the
  quantitative meaning of "loose but optimal."

## 5. Communication complexity (SPECULATIVE)
Each attained pair `(κ*, x)` with `n_{κ*}(x)=bytes(x)` behaves like a **fooling
pair**: no single sub-byte bound can be correct for all of them simultaneously.
The flavor matches fooling-set lower bounds, but no protocol/partition-matrix
formalization is attempted. SPECULATIVE.

## 6. Approximation algorithms (context, not equivalence)
`bytes` is a worst-case-optimal *upper* estimator; the interesting approximation
question (a `(1+ε)` estimate of the *actual* `n_κ`) requires member knowledge and
leaves the universal regime entirely. Out of scope; noted to prevent conflation
of "optimal safe upper bound" with "optimal approximation of the true count."

---

## Net placement
The result is, most rigorously, a **support-function / minimax identity** (§1):
byte-count is the upper envelope of the tokenizer-family uncertainty set, hence
the unique minimal robust-safe bound *by construction*, with the only mathematical
content being `envelope = bytes` (proved via byte-fallback, `LOWER_BOUND.md`). The
incompressibility and universal-coding readings (§2–3) explain *why* uniform
improvement is impossible but are LIKELY/SPECULATIVE as formal equivalences and
were **not** reduced. Citations UNKNOWN — verify before external use.
