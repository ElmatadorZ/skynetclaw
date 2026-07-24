# ONTOLOGY_OF_CONTEXT.md
### The minimal complete ontology of what occupies a model's context window

Pure theory. No implementation. The goal is the **smallest set of categories** such that every token consumed by an autoregressive LLM belongs to exactly one, and none is missing.

---

## 0. The primitive

The model consumes a finite sequence `s ∈ V*` of token ids drawn from a fixed vocabulary `V`. The context window is a constant `C = |V*|_max` the model can attend to. **Everything in this ontology exists only to explain how `|s|` is produced.** A "contributor" is any process that adds symbols to `s`.

We separate contributors by **who authors them** and **at which layer they materialize**, because those two axes determine visibility to any budgeting agent.

---

## 1. Axis I — Provenance (who authored the symbols)

| Class | Definition | Visible to the author of the request? |
|---|---|---|
| **P1 Human-intended payload** | Semantic content a human meant to send: instructions, questions, documents, examples. | Yes |
| **P2 Agent-generated payload** | Content produced by the model in prior turns and fed back: prior replies, chain-of-thought that is retained, emitted tool calls. | Yes, but often stored in non-`content` fields |
| **P3 Environment payload** | Content returned by tools/retrieval/environment: tool results, RAG chunks, API responses. | Yes, size often unbounded/variable |
| **P4 Interface scaffolding** | Structural symbols the *protocol* requires to delimit P1–P3: role markers, turn separators, the generation prompt. | Only if the template is known |
| **P5 Model/tokenizer artifacts** | Symbols the *tokenizer/model* requires: BOS/EOS, byte-fallback fragments, dummy prefix spaces, normalization expansions. | Only if the tokenizer is known |

Provenance is the load-bearing axis: **P1–P3 are semantic and roughly measurable by their author; P4–P5 are injected downstream and are invisible unless the author also possesses the template and the tokenizer.**

---

## 2. Axis II — Layer of materialization (where the symbols first exist)

The same content passes through layers; some contributors are born at each.

| Layer | What is born here | Formal object |
|---|---|---|
| **L0 Semantic** | The structured request: messages, roles, tool schemas, parameters. | An object `O` in a message algebra |
| **L1 Serialization** | Wire encoding (JSON), escaping of nested strings, unicode normalization. | A string over a transport alphabet |
| **L2 Template** | Role markers, tool-schema rendering, tool-call rendering, generation prompt. | A prompt string with special-token placeholders |
| **L3 Special-token embedding** | BOS/EOS, control tokens resolved to ids; prefix spaces. | A mixed string/id stream |
| **L4 Tokenization** | Sub-word / byte segmentation into final ids. | `s ∈ V*` |

A budgeting agent typically measures at **L0–L1**. The window constraint binds at **L4**. Every contributor born in **L2–L4 is added after an L0/L1 measurement** and is the entire reason a gap can exist.

---

## 3. The minimal complete contributor list

Cross-cutting the two axes, the exhaustive set of contributor **types** (each is a nonzero-in-general summand of `|s|`):

1. **User text** (P1/L0) — instructions, questions, pasted documents.
2. **System / policy text** (P1/L0) — standing instructions, constitutions, personas.
3. **Assistant free text** (P2/L0) — retained prior replies and retained reasoning.
4. **Assistant tool-call payload** (P2/L0) — function name + arguments, stored structurally, *rendered back* into the prompt.
5. **Tool / environment result** (P3/L0) — returned content, often variable-length.
6. **Tool-schema declarations** (P1/L0) — names, descriptions, JSON-schema of callable functions.
7. **Multimodal placeholders** (P1/P3, L2) — image/audio expanded to a fixed or content-dependent token count.
8. **Role markers & turn separators** (P4/L2) — one envelope per message.
9. **Tool-schema template wrapper** (P4/L2) — preamble prose + per-tool formatting that differs from the raw schema string.
10. **Tool-call / tool-result wrappers** (P4/L2) — call/response delimiters, ids.
11. **Generation prompt** (P4/L2) — the trailing "assistant begins here" marker.
12. **BOS / EOS / control tokens** (P5/L3) — sequence and turn boundaries as ids.
13. **Normalization & serialization artifacts** (P5/L1+L3) — JSON escaping, NFC/NFKC expansion, SentencePiece prefix space (`▁`), byte-fallback fragments.
14. **Tokenizer segmentation itself** (P5/L4) — the map from characters to a variable number of ids (the dominant, content-dependent multiplier).

Claim of **completeness**: any symbol in `s` is either semantic content (types 1–7), protocol scaffolding (8–11), or tokenizer/model machinery (12–14). There is no fourth kind — the sequence is, by construction, only content + delimiters + encoding. Claim of **minimality**: removing any one type leaves a reachable prompt whose token count it alone explains (e.g. remove type 4 and a tool-calling turn is mis-modeled; remove type 12 and byte-fallback languages are mis-modeled).

---

## 4. The invisibility frontier

Draw the line between what a request author can measure from `O` alone and what requires downstream knowledge:

```
   MEASURABLE FROM O          |   REQUIRES TEMPLATE τ      |   REQUIRES TOKENIZER κ
   (semantic byte content)    |   (structural injection)   |   (segmentation + specials)
   types 1–7  (their bytes)   |   types 8–11               |   types 12–14
```

- Left of the first line: an author can bound the **byte content** of semantic payload (even type 4, if it inspects the structural fields — a frequent omission, not a theoretical limit).
- Between the lines: bounded **only if τ is known** — the number and size of injected markers.
- Right line: the character→token multiplier and special-token counts — bounded **only if κ (or its family's expansion factor) is known**.

This frontier is the object that `MATHEMATICAL_MODEL.md` formalizes, `ERROR_TAXONOMY.md` decomposes, and `UPPER_BOUND_THEOREM.md` proves a bound across.

---

## 5. Invariant (the one sentence to keep if all else is deleted)

> **Model context = Σ(semantic payload) + Σ(protocol scaffolding) + Σ(tokenizer/model artifacts).**
> The first summand is authored upstream and measurable in bytes; the second is injected by the serialization+template; the third is injected by the tokenizer. Any budget that observes only the first is measuring a **strict lower-information object** than the quantity the window constrains.
