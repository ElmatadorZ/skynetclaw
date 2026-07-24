# LITERATURE_REVIEW.md
### Prior work bearing on the prompt-budget upper-bound problem

Pure theory survey. Question: **does a proof (or a productized guarantee) of a prompt-budget upper bound already exist?** Findings grouped by the piece of the pipeline each line of work addresses, mapped back to `MATHEMATICAL_MODEL.md`'s stages.

---

## 1. Tokenizer determinism and the byte ceiling (stage `κ`)

- **BPE / byte-level BPE determinism.** BPE with a fixed, ordered merge table is a deterministic, lossless map; identical merges ⇒ identical token sequences, verified reproducible across CPU/GPU implementations. SentencePiece imposes a globally deterministic leftmost-first merge order, removing the residual ambiguity that can differ between, e.g., HuggingFace and SentencePiece back-ends. → Supports Fact 4 (determinism *given fixed merges*) and warns of cross-implementation drift (`E_ver`). Sources below (Binary BPE, GPUTOK, SentencePiece topic).
- **Byte fallback / byte-level coverage.** Byte-level BPE guarantees every input is representable; the coarsest segmentation is one-token-per-byte. This is the theoretical basis of **Fact 2** (`|κ(x)| ≤ bytes(x)`), the ingredient that makes a *safe-but-loose* bound possible without exact merges. No paper I found states the budget corollary explicitly, but it is immediate from byte-level coverage.
- **Sub-word tokenization surveys** establish that chars/token is content- and language-dependent with no universal positive lower bound — the basis of **Fact 3** and `E_lang`.

**Gap:** the literature proves κ is deterministic and byte-bounded but does **not** publish `|κ(x)| ≤ bytes(x)` *as a safety theorem for context budgeting*. The bound is folklore, not a cited result.

---

## 2. Template / serialization coupling (stages `σ, τ, ε`)

- **Chat templates in inference engines.** llama.cpp renders messages via a Jinja (minja) chat-template engine, model-specific, including tool-calling. This is `τ` made concrete and confirms it is **model-dependent and non-injective**.
- **Known template/tokenizer defects.** Documented issues: **double-BOS** when both the template and the loader prepend BOS; templates that omit a BOS defined in metadata; trailing-whitespace sensitivity that changes tokenization. These are empirical confirmations that `E_spec` and `E_ser` are **not even reliably equal to their "intended" values** — the injector can misbehave. Directly supports Theorem 4 (`E_ver`) and the caution in `ERROR_TAXONOMY` T3.
- **"num_tokens_from_messages" folklore (OpenAI ChatML).** The widely-copied recipe adds fixed per-message and per-reply overheads (e.g. `+3` tokens/message, priming tokens) precisely because the template scaffolding (`E_tmpl`, `E_spec`) is not in the content. This is an *empirical, model-version-specific* patch, explicitly caveated as breaking across model versions — an instance of `E_ver`, and evidence that **no closed-form template bound is published**; practitioners hard-code observed constants.

**Gap:** template injection is treated as an engineering constant to be measured per model, never as a bounded function with a proof. This is exactly the term Theorem 2 shows is unbounded without template knowledge.

---

## 3. Provider-side exact counting (the co-location route, Cor 1.2)

- **Anthropic `messages/count_tokens`.** Accepts the *same* inputs as message creation (system, messages, tools, images, PDFs) and returns `input_tokens`. It is the co-located oracle of Corollary 1.2 — the provider owns `τ, ε, κ`. Notably, the docs state the result **"should be considered an estimate; the actual number … may differ by a small amount."** → Even with the exact tokenizer *and* serialization, the provider declines to promise equality — direct evidence for residual `E_samp`/`E_ver` (T10) and that **exactness is asymptotic, not absolute**.
- **OpenAI `tiktoken`.** Open-sources the *tokenizer* (`κ`) but **not** the chat serialization; users must reconstruct `E_tmpl`/`E_spec` themselves — the asymmetry Theorem 3 predicts (κ known, τ not ⇒ still no safe bound).
- **Google Gemini / Bedrock count-token endpoints.** Same co-location pattern: exact counts require calling the service that owns the pipeline.
- **llama.cpp `/tokenize` endpoint.** Returns the server's own token ids ⇒ ground-truth `n` for a *fixed* loaded model+template. The only fully-local realization of Cor 1.2.

**Finding:** the industry's *actual* solution to "prove the budget" is **co-location** — ask the component that owns `κ,ε,τ`. Every vendor that offers a guarantee offers it this way, and even then hedges to "estimate."

---

## 4. Prompt compression & context engineering (the budget *controller*, not the *bound*)

- **LLMLingua (EMNLP 2023)** and **LongLLMLingua** introduce a **budget controller** that allocates compression ratios across prompt sections using a small LM's perplexity, achieving up to ~20× compression with ~1.5-pt quality loss. Crucially, the "budget" here is a *target allocation for compression*, **not a safety upper bound on realized tokens**. It manages `E_tok`-relevant content but assumes the downstream tokenizer/template as given.
- **LLMLingua-2** and follow-ups (e.g. graph-prior, training-free variants) refine *which* tokens to drop — again optimizing quality-under-a-budget, not *proving* a budget.
- **"Compress the Context, Keep the Commitments: A Formal Framework for Verifiable LLM Context Compression"** is the closest to a *formal* treatment — it formalizes guarantees about *what compression preserves*, adjacent to but not the same as a *token-count upper bound* on the rendered prompt.

**Finding:** the compression literature owns the *allocation* problem ("spend a budget wisely") and increasingly the *verifiability of content preservation*, but **not** the *measurement* problem ("prove the realized token count ≤ C"). The two are orthogonal; the budget-controller literature *presumes* an accurate count exists.

---

## 5. KV-cache / serving-systems literature

- Work on paged KV cache, context-window extension, and continuous batching (serving-systems track) treats the sequence length `n` as a **given input** to memory planning; it optimizes *storage of* `n` tokens, never *prediction of* `n` from a pre-tokenized request. It therefore sits entirely downstream of our question and offers no upper-bound proof.

---

## 6. Verdict: is the problem solved?

| Sub-question | Status in literature |
|---|---|
| Is `κ` deterministic & byte-bounded? | **Solved** (folklore/standard); not stated as a budget theorem. |
| Is template injection bounded from outside? | **Not addressed as theory**; handled by measured constants per model (fragile, `E_ver`). |
| Exact count given co-location? | **Solved in practice** (count-token endpoints) — and even vendors hedge to "estimate." |
| Safe upper bound *without* co-location? | **No published proof either way** before this note's Theorems 1–4. |
| Compression under a budget? | **Solved** (LLMLingua family) — a *different* problem. |

**Conclusion.** The two halves are each addressed in isolation — tokenizer determinism on one side, budget-aware compression on the other — but **the specific object of this mission (a proven upper bound on realized context tokens computed from the visible prompt) is not established in the literature.** The nearest guarantees are *empirical* (measured template constants) or *co-located* (provider counts the tokens for you, and still says "estimate"). The clean necessary-and-sufficient condition (bounded template + family-ceiling tokenizer + stable deployment) of `UPPER_BOUND_THEOREM.md` is, to the reach of this survey, **not stated as such anywhere** — which is the substance of `OPEN_PROBLEMS.md`.

---

## Sources
- [LLMLingua: Compressing Prompts for Accelerated Inference (EMNLP 2023)](https://arxiv.org/abs/2310.05736) · [ACL Anthology](https://aclanthology.org/2023.emnlp-main.825/)
- [LongLLMLingua: Accelerating and Enhancing LLMs in Long Context via Prompt Compression](https://arxiv.org/html/2310.06839v2)
- [Compress the Context, Keep the Commitments: A Formal Framework for Verifiable LLM Context Compression](https://arxiv.org/pdf/2605.17304)
- [Binary BPE: A Family of Cross-Platform Tokenizers](https://arxiv.org/html/2511.17573v1) · [GPUTOK: GPU Accelerated Byte Level BPE Tokenization](https://arxiv.org/html/2603.02597v1)
- [SentencePiece BPE Tokenizer (overview)](https://www.emergentmind.com/topics/sentencepiece-bpe-tokenizer) · [Byte-level BPE Tokenizers (overview)](https://www.emergentmind.com/topics/byte-level-bpe-tokenizers)
- [Anthropic — Count tokens in a Message (API reference)](https://docs.anthropic.com/en/api/messages-count-tokens) · [Token counting (platform docs)](https://docs.anthropic.com/en/docs/build-with-claude/token-counting)
- [Token Counting Explained: tiktoken, Anthropic, Gemini (2025)](https://www.propelcode.ai/blog/token-counting-tiktoken-anthropic-gemini-guide-2025)
- [llama.cpp — Chat Templates and Message Parsing (DeepWiki)](https://deepwiki.com/ggml-org/llama.cpp/3.9-chat-templates-and-message-parsing) · [Double-BOS / template tokenization issue #21634](https://github.com/ggml-org/llama.cpp/issues/21634) · [template BOS/think-tag issue #12107](https://github.com/ggml-org/llama.cpp/issues/12107)
- [Amazon Bedrock — Count tokens before inference](https://docs.aws.amazon.com/bedrock/latest/userguide/count-tokens.html)
