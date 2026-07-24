# UPPER_BOUND_THEOREM.md
### When a mathematically safe prompt-budget upper-bound exists — proof and impossibility

Pure theory. Notation from `MATHEMATICAL_MODEL.md`. Reachable requests `O ∈ 𝒪`; realized count `n(O) = |Φ(σ(O))|` with `Φ = κ∘ε∘τ∘σ⁻¹`. A **safe upper bound** is a computable `B : 𝒪 → ℝ_{≥0}` with

> **(SAFE)** `∀ O ∈ 𝒪 : B(O) ≥ n(O)`.

Given (SAFE), enforcing `B(O) ≤ C − n_gen` guarantees `n(O) ≤ C − n_gen` — no overflow. The question is exactly *when* a `B` satisfying (SAFE) exists, and *what knowledge* it presupposes.

---

## Part I — Positive result: a safe bound EXISTS under explicit conditions

### Assumptions

- **(A-FAM) Tokenizer family with byte ceiling.** `κ` belongs to a family (byte-level BPE, or SentencePiece with byte fallback) for which `|κ(x)| ≤ bytes(x)` for all `x ∈ Σ*_•`, and each special token contributes exactly `1` (Facts 2 & 4). The estimator need only know the *family*, not the merge table.
- **(A-TMPL) Template byte-length oracle.** The estimator can compute an upper bound `β(O) ≥ bytes(text-part of ε(τ(σ⁻¹(σ(O)))))` on the rendered byte length, and a count `q(O) ≥ n_spec(O)` on injected special tokens. Equivalently: it knows `τ` and `ε` up to an over-estimate of their byte output and their special-token count.

### Theorem 1 (Constructive safe bound)
Under (A-FAM)+(A-TMPL), define
```
B*(O) := β(O) + q(O).
```
Then `B*` satisfies (SAFE).

**Proof.** Let `x = ε(τ(σ⁻¹(σ(O))))` decompose into its text part `x_t` and its `n_spec` special-token atoms. By Fact 4 the atoms contribute exactly `n_spec ≤ q(O)` tokens. By Fact 2, `|κ(x_t)| ≤ bytes(x_t) ≤ β(O)`. Token count is additive over the atom/text partition (special atoms are not merged with text), so
`n(O) = |κ(x_t)| + n_spec ≤ β(O) + q(O) = B*(O).` ∎

**Reading.** A safe upper bound *does* exist — and, crucially, **`B*` never invokes `κ`'s exact segmentation.** The exact tokenizer is *not* required; only (i) the family-level byte ceiling and (ii) an over-estimate of the rendered string's byte length and special-token count. Condition (A-TMPL) is the binding one: it demands knowledge of the *serialization + template*, not the tokenizer.

### Corollary 1.1 (Looseness price)
`B*` can be arbitrarily loose. Realized ratios are typically `bytes/token ≈ 3–5` for natural text, so `B* = bytes` over-estimates by `3–5×`. A byte-ceiling budget is *safe* but wastes most of the window. **Tightness and required knowledge trade off:** to shrink `B*` toward `n` you must replace the family ceiling (Fact 2) with the exact `κ` — i.e. buy tightness with tokenizer knowledge.

### Corollary 1.2 (Co-located exactness)
If the estimator additionally has the exact `κ, ε, τ` (e.g. it *is* the inference server, or calls the server's own tokenize/count endpoint), then `B(O) := n(O)` is computable and is the *tight* safe bound (`E ≡ 0`, modulo T10 runtime residual). This is the only route to a bound that is both safe and tight.

---

## Part II — Impossibility: a safe bound CANNOT exist without serialization knowledge

### Theorem 2 (Template-unawareness ⇒ no safe bound)
Suppose the estimator sees only the visible object `O` and the true template is **unknown**, drawn from a class `𝒯` that is **additively unbounded**: for every `t ∈ ℝ_{≥0}` there is a `τ' ∈ 𝒯` whose global preamble `g_0` contains at least `t` tokens of fixed text. Then **no** computable `B : 𝒪 → ℝ_{≥0}` satisfies (SAFE) simultaneously for all `τ' ∈ 𝒯`.

**Proof (adversary).** Fix any candidate `B`. Choose any `O`. Compute the finite value `B(O)`. By additive-unboundedness pick `τ' ∈ 𝒯` with `|κ(ε(g_0'))| ≥ B(O) + 1`. For this deployment,
`n(O) ≥ |κ(ε(g_0'))| ≥ B(O) + 1 > B(O)`,
violating (SAFE). Since `B` was arbitrary, no safe bound exists over `𝒯`. ∎

**Reading.** From the client's vantage the server can prepend arbitrary content (safety preambles, RAG-of-policy, gateway headers) *after* the budget is computed. Against an unknown, unbounded template, budgeting the visible prompt is **provably impossible**. This is the formal core of `E_tmpl` and `E_ver` being "unbounded" in the taxonomy.

### Theorem 3 (What tokenizer-unawareness alone costs)
Suppose `τ, ε` are known (so (A-TMPL) holds) but `κ` is unknown *within family (A-FAM)*. Then:
1. The **safe** bound `B*` of Theorem 1 still exists (it used only the family ceiling). *Tokenizer-exactness is not necessary for safety.*
2. **No tight** bound exists: for any `B` with `B(O) < bytes(x)` on some `O`, there is a family-member `κ'` (byte-fallback on the rare-script content of `O`) with `|κ'(x)| > B(O)`. *Tokenizer-exactness is necessary for tightness.*

**Proof.** (1) is Theorem 1. (2): pick `O` whose text is entirely outside `κ`'s learned merges (e.g. an unseen script); byte fallback gives `|κ'(x)| = bytes(x) > B(O)`. ∎

### Theorem 4 (Deployment-identity impossibility)
If the realized `Φ` may change between the moment of measurement and the moment of inference (version/template/gateway drift, `E_ver`) and the estimator is not notified, then **no** `B` computed before the change can guarantee (SAFE) after it. **Proof.** The post-change pipeline is a fresh unknown template; apply Theorem 2. ∎

---

## Part III — The exact frontier (synthesis)

Let `K` = the knowledge the estimator possesses. A safe upper bound exists **iff** `K` bounds the two downstream injectors:

| Knowledge held | Safe bound exists? | Tight bound exists? |
|---|---|---|
| content bytes only | **No** (Thm 2) | No |
| content + exact `κ`, but not `τ` | **No** (Thm 2 — template still unbounded) | No |
| content + `τ,ε` byte/spec bounds, `κ` family only | **Yes** — `B*` (Thm 1) | No (Thm 3.2) |
| content + exact `τ,ε,κ` (co-located) | Yes | **Yes** (Cor 1.2) |
| any of the above **but** deployment may drift unnotified | **No** (Thm 4) | No |

**The invariant made sharp:**
> A safe prompt-budget upper bound exists **if and only if** the estimator can bound the byte-length and special-token count that the **serialization + template** inject, over a tokenizer family with a known per-byte ceiling, **and** the deployment is stable (or change-notifying). The **exact tokenizer is sufficient but not necessary** (family ceiling suffices for safety, is required only for tightness). The **serialization/template is necessary** — it cannot be replaced by any family-level assumption, because template injection is additively unbounded from the outside.

---

## Part IV — Answer to the impossibility question posed

*"Can a system prove its budget without the exact tokenizer and the exact serialization?"*

- **Without the exact tokenizer:** **Yes, safely (Theorem 1)** — provided it knows the *tokenizer family's* byte ceiling and the template. It pays for this with looseness (Cor 1.1). Exact tokenizer buys tightness, not safety.
- **Without the serialization/template:** **No (Theorem 2)** — safety is *mathematically impossible* against an unknown, additively-unbounded template. Some knowledge of, or a trusted bound on, the serialization+template is **strictly necessary**.

Hence the two unknowns are **not symmetric.** The common phrasing "you need the exact tokenizer and serialization" is *too strong on the tokenizer and correctly binding on the serialization.* The precise necessary-and-sufficient condition is: **(bounded template + family-ceiling tokenizer + stable deployment).** Everything else follows.
