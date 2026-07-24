# 06 — Prompt Budgeting as a Corollary

The general theory (`00`–`04`) was built with no reference to any application.
This file instantiates it once. The claim of the mission — *"if the abstract
impossibility holds, prompt budgeting is a Corollary, not a Main Theorem"* — is
discharged here: every prior prompt-budget result is a substitution instance.

---

## The instantiation map

| Abstract object (`00`) | Instance |
|---|---|
| worlds `Ω` | possible tokenizers/templates consistent with what the client knows |
| observation `y = K(ω)` | the rendered string + serialization + tokenizer *family* |
| target `n(ω)` | realized token count of the request under world `ω` |
| ambiguity set `V(y)` | `{ |κ(x)| : κ ∈ family, template consistent }` |
| envelope `n⁺(y)` | worst-case token count over the family |

## Prior results recovered as substitution instances

- **`bytes(x)` is the minimal safe upper bound** (prior `UPPER_BOUND_THEOREM.md`,
  `LOWER_BOUND.md`) = **Lemma 0 + A2**: `n⁺ = ⋁V`. The specific computation
  `⋁V = bytes` is the domain fact (byte-fallback ceiling); the *optimality* of
  using `n⁺` is the abstract Lemma 0. **SUPPORTED.**
- **"Exact tokenizer ⇒ exact count; family only ⇒ safe upper"** (prior Cor 1.2 vs
  the universal theorem) = **Theorem A1 vs A2**: knowing `κ` collapses `V` to a
  singleton (exact feasible); knowing only the family leaves `diam>0` (only safe
  upper). **SUPPORTED.**
- **"Byte-count is loose against a single tokenizer (3–5×, 17× Thai)"** = **Thm B
  diameter law**: the slack equals the ambiguity `diam(V)`; measured slack = the
  family's spread. **SUPPORTED.**
- **"Tighten only by learning the tokenizer / calling the server's counter"** =
  **Thm C**: tightness is bought with information (refine `K` until `|V|=1`).
  **SUPPORTED.**
- **"Chars/4 is not safe (8 est vs 78 real on emoji)"** = a violation of the
  **safe-upper** guarantee, i.e. the heuristic is a *point/optimistic* estimator
  (Thm X.2 optimistic-omission cliff), not a member of `{U ≥ n⁺}`. **SUPPORTED.**
- **"A cheaper byte estimate trades exactness for O(1) and stays safe"** = **Thm
  X.1**: a coarse but sound read; slack up, safety preserved. **SUPPORTED.**

## The demotion, precisely
The prompt-budget "main theorem" (byte-count optimal safe bound) is exactly:
> **Corollary (of Lemma 0 + A2 + the domain lemma `⋁V=bytes`).** In the estimation
> problem where information = {string, serialization, tokenizer family}, the
> minimal hard-safe upper estimator is the envelope `n⁺`, which here equals
> `bytes`. Choosing it is the `diam>0, need-upper, envelope-cheap` row of the
> Selection Theorem (Cor G).

No new mathematics is needed for prompt budgeting beyond substituting the domain
computation `⋁V=bytes` into the abstract results. **This is the corollary status
the mission asked to establish.** SUPPORTED.

## Which estimator prompt-budgeting *should* use — read off Cor G
- If the runtime exposes its own token counter (or the exact `κ` is known):
  `|V|=1` → **Exact**. Best when available (dominates).
- If only the family is known and the envelope is cheap (`⋁V=bytes`):
  **Safe upper** `= bytes`. The universal-optimal choice; loose by `diam`.
- If per-request tightness matters and a distribution over inputs is known:
  **Probabilistic** quantile — tighter, `α`-risk, needs the prior. (Trade per
  Thm E.)
- If the true pipeline/template is unknown-and-unbounded (server may inject):
  the envelope is *unbounded* (A2 fails) → only the **vacuous** bound is
  hard-safe → must either obtain template knowledge or accept probabilistic
  safety. (This is the earlier `Thm 2` impossibility, now a case of A2.)

## Closing note (scope honesty, inherited)
The corollary's *optimality* is universal-only (Pareto, not dominance): against a
known tokenizer, byte-count is the loosest safe choice (Thm B). The engineering
decision — hard-safe-loose `bytes` vs tight-soft probabilistic vs exact-if-
counter-available — is precisely the Pareto selection of Cor G, with the binding
scarcity being *whether the exact tokenizer/counter is reachable*. Nothing in the
application escapes the abstract trade-off; it only chooses a cell in it.
