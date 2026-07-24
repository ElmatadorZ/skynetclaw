# MATHEMATICAL_MODEL.md
### The transformation chain from visible prompt to context sequence, as composed functions

Pure theory. Each stage is a function; we state its domain, codomain, and algebraic properties. `OBJECTIVE 3` (lossless/lossy, invertible/not, deterministic/model-dependent/unknown) is answered inline and summarized in §6.

---

## 1. Objects and alphabets

- `Σ` — a Unicode alphabet (code points). `Σ*` strings over it. `bytes(x)` = UTF-8 byte length of `x ∈ Σ*`.
- `V` — the model vocabulary (token ids), including a distinguished set `V_spec ⊂ V` of special/control tokens. `V*` = token sequences. `|s|` = length.
- `𝒪` — the **message algebra**: a request object `O ∈ 𝒪` is a tuple `O = (⟨m_1,…,m_k⟩, T, θ)` where each message `m_i = (role_i, content_i, extras_i)` (extras = tool_calls, name, ids…), `T` is a tool-schema set, `θ` are decoding parameters. `𝒪` is what a human/agent authors and is the **visible prompt**.

Define the semantic byte content `‖O‖_b = Σ_i bytes(content_i) + Σ_i bytes(extras_i) + bytes(render_raw(T))` — the total byte mass of authored payload (types 1–7 of the ontology). This is the largest object measurable *without* τ or κ.

---

## 2. The stage functions

```
        σ            σ⁻¹           τ              ε              κ
  𝒪  ──────►  W  ──────►  𝒪  ──────►  Σ*  ──────►  Σ*_• ──────►  V*
 (author)  (wire)     (parsed)   (rendered)    (embedded)     (tokens)
```

**(S1) Serialization** `σ : 𝒪 → W`, and server-side parse `σ⁻¹ : W → 𝒪`.
Encodes `O` as a transport string (JSON) `w = σ(O)`; the server recovers `Ô = σ⁻¹(w)`.
- **Deterministic** (given a fixed encoder).
- **Lossy in principle, near-lossless in practice:** JSON is insensitive to key order and whitespace, so `σ⁻¹∘σ` is the identity on semantic content but *not* on byte form; unicode normalization or escaping choices can alter byte content. Write `Ô ≈ O` with a residual `δ_σ`.

**(S2) Template / chat formatting** `τ : 𝒪 → Σ*`.
Renders the structured object into a single prompt string with special-token placeholders. `τ` injects: role markers, tool-schema wrapper `ρ(T)`, tool-call and tool-result delimiters, and the generation prompt. Formally
`τ(O) = g_0 ⊕ ρ(T) ⊕ ⊕_{i=1}^{k} ( a_i ⊕ h(m_i) ⊕ b_i ) ⊕ g_1`
where `h(m_i)` is the message body, `a_i,b_i` are per-message prefix/suffix markers, `g_0,g_1` are global preamble/generation-prompt strings, `⊕` is concatenation.
- **Deterministic** given a fixed template; **model-dependent** (each model family ships its own `τ`).
- **Non-injective in general** (two distinct objects can render to the same string; e.g. an empty-content message vs. an absent one).
- **Additive, unbounded from the client's view:** `g_0, a_i, b_i, ρ` are chosen by `τ`, not by the author.

**(S3) Special-token embedding & normalization** `ε : Σ* → Σ*_•`.
Resolves BOS/EOS/control markers, applies unicode normalization `N` (NFC/NFKC), and any pre-tokenizer prefixing (e.g. SentencePiece `▁`). Output lives in a mixed alphabet `Σ*_•` (text + resolved special-token atoms).
- **Deterministic**, **model/tokenizer-dependent**.
- **Expanding but boundedly:** `N` can turn one code point into a fixed, small number; prefix spacing adds a bounded constant per segment.

**(S4) Tokenization** `κ : Σ*_• → V*`.
Segments into ids. For BPE/SentencePiece with a fixed merge table, `κ` is a **deterministic, greedy, lossless** map with an inverse decode `κ⁻¹` such that `κ⁻¹∘κ = id` on well-formed strings.
- **Deterministic** given fixed merges; **model-dependent** (each vocabulary differs).
- **Context-free per pre-token but non-local within a pre-token:** merges act inside pre-tokenizer chunks; boundaries introduced by `τ`/`ε` prevent cross-chunk merges.

**Composite (server pipeline)** `Φ := κ ∘ ε ∘ τ ∘ σ⁻¹`. The realized context is
`s = Φ(σ(O))`, and the binding constraint is `n(O) := |s| ≤ C − n_gen`, with `n_gen` the reserved generation length.

A **budget estimator** is any `B : 𝒪 → ℝ_{≥0}` intended to predict `n(O)`. Safety = `B(O) ≥ n(O)` for all reachable `O`.

---

## 3. The key algebraic facts about `κ` (these drive every bound)

**Fact 1 — Sub-additivity under concatenation (merge monotonicity).**
For any strings `u,v`: `|κ(u ⊕ v)| ≤ |κ(u)| + |κ(v)|`.
*Reason:* segmenting the whole permits all merges available to the parts **plus** possible cross-boundary merges, and merges only ever reduce count. Splitting can only *increase* tokens. Hence tokenizing pieces separately over-counts the whole — a usable **upper-bound direction**.

**Fact 2 — Byte-fallback ceiling.**
For a byte-level BPE / SentencePiece tokenizer with full byte coverage, the *coarsest* valid segmentation is one token per byte. Since the actual segmentation is at least as merged,
`|κ(x)| ≤ bytes(x)`.
This is a **content-independent, tokenizer-family-level upper bound** (it needs the *family*, not the exact merges).

**Fact 3 — No universal positive lower bound on chars/token.**
There is no constant `ρ_min>0` with `|κ(x)| ≤ bytes(x)/ρ_min − c` for all `x`: adversarial/rare-script input drives the realized ratio toward 1 token/byte (byte fallback). So the *tight* count is genuinely `κ`-specific; only the loose ceiling (Fact 2) is family-level.

**Fact 4 — Special tokens are atoms.**
Each injected special marker contributes exactly 1 to `|s|`, independent of its textual width. So counting them requires counting *structural events in `τ/ε`*, not bytes.

---

## 4. Decomposition of `n(O)`

Using Facts 1 and 4 on the template expansion of §2:

```
n(O) = |κ(ε(τ(Ô)))|
     = Σ_i |κ(ε(h(m_i)))|            ← semantic payload tokens        (types 1–7)
       + Σ_i (|κ(ε(a_i))| + |κ(ε(b_i))|)   ← per-message scaffolding  (types 8,10)
       + |κ(ε(g_0))| + |κ(ε(ρ(T)))| + |κ(ε(g_1))|  ← global + tools + genprompt (types 9,11)
       + n_spec                      ← BOS/EOS/control atoms          (type 12)
       − Δ_merge                     ← cross-boundary merge savings (≥0, Fact 1)
```

`Δ_merge ≥ 0` means the sum of parts is an **upper bound** on the whole. Every term except the first is born in L2–L4 and is invisible to an L0/L1 estimator.

---

## 5. What a typical estimator computes, and the formal gap

A content-only estimator is `B_0(O) = f(‖O‖_b)` for some monotone `f` (e.g. `bytes/4`, or `|κ̃(content)|` under a *surrogate* tokenizer `κ̃ ≠ κ`). Its defect against §4:

```
n(O) − B_0(O) = [ Σ semantic tokens under κ  −  f(‖O‖_b) ]     (E_tok: tokenizer/surrogate error)
              + [ scaffolding + tools-wrapper + genprompt ]     (E_tmpl: template injection ≥ 0)
              + n_spec                                          (E_spec: specials ≥ 0)
              − Δ_merge                                         (≤ 0)
              + [ tokens from extras_i not in f's input ]       (E_struct: omitted structural payload ≥ 0)
```

`E_tmpl, E_spec, E_struct ≥ 0` push `n` **above** `B_0`; `E_tok` and `−Δ_merge` are **sign-indefinite**. This is the formal statement that a content-only budget is **not sign-stable** and carries an **always-nonnegative injected remainder** it never sees. (Full taxonomy: `ERROR_TAXONOMY.md`.)

---

## 6. Property table (OBJECTIVE 3)

| Stage | Lossless? | Invertible? | Deterministic? | Dependence |
|---|---|---|---|---|
| `σ` serialization | semantically yes / byte-wise no | yes (semantic) | yes | encoder |
| `σ⁻¹` parse | yes (semantic) | — | yes | encoder |
| `τ` template | **lossy** (non-injective) | **no** | yes (fixed template) | **model/template** |
| `ε` embed+normalize | lossy (`N` many-to-one) | **no** | yes | **tokenizer/model** |
| `κ` tokenize | **lossless** | **yes** (`κ⁻¹`) | yes (fixed merges) | **model vocabulary** |
| `Φ = κ∘ε∘τ∘σ⁻¹` | lossy | no | yes if all fixed | model | 
| across an unknown model version | — | — | **unknown** | version drift |

**Reading:** the only cleanly invertible, lossless stage is the tokenizer itself. The *irreversible* information loss is in `τ` and `ε` — precisely the stages a client cannot see. Determinism holds **per fixed model+template+version**; across an *unknown* deployment/version the whole composite is **unknown**, which is the hook `UPPER_BOUND_THEOREM.md` turns into an impossibility condition.

---

## 7. The invariant, as an equation

> `n(O) = ⟨semantic⟩_κ + ⟨scaffolding⟩_κ + ⟨specials⟩ − Δ_merge`, where only `⟨semantic⟩` is a function of the visible object's content and `⟨scaffolding⟩, ⟨specials⟩` are functions of `(τ, ε)` — the deployment — not of the prompt. A budget is a function of the prompt; the quantity it must bound is a function of the prompt **and** the deployment. Equality of the two is possible only when the budget is also given the deployment.
