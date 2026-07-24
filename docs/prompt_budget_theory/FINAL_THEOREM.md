# FINAL_THEOREM.md
### Is byte-count the unique minimal universally-safe upper bound?

Pure mathematics. Synthesis of `OPTIMALITY / LOWER_BOUND / ADVERSARIAL_STRINGS /
IMPOSSIBILITY_OF_TIGHTER_BOUND / RELATED_LOWER_BOUND_RESULTS`. OBJECTIVE 7 +
FINAL QUESTION.

---

## The theorem

**Assumptions.**
- **(A-FAM+)** The true tokenizer lies in the byte-fallback BPE family `𝒦`, and
  `𝒦` is **unrestricted**: for every `x` some member attains one token per byte
  on `x` (guaranteed by the empty-merge member `κ₀∈𝒦`; corroborated by real
  tokenizers byte-falling-back on OOV input).
- **(A-REND)** `bytes(·)` is measured on the **rendered string the tokenizer
  actually consumes** (post any normalization `ν` that is part of the known
  serialization `ε`). For the Qwen byte-BPE family, `ν` is non-expanding at
  tokenization time (measured), so raw bytes suffice.
- Special tokens counted separately as `+q` (known-template special-token count).

**Theorem (Optimality of the byte ceiling).** Under (A-FAM+)+(A-REND), for the
text term:
1. `n_κ(x) ≤ bytes(x)` for all `κ∈𝒦, x`  — *safety* (Fact 2).
2. `sup_{κ∈𝒦} n_κ(x) = bytes(x)` for all `x` — *the envelope equals bytes*
   (Lemma L1).
3. Hence `bytes` is the **unique minimal universally-safe upper bound** (Lemma
   O1): every universally-safe `B` has `B ≥ bytes`, and `bytes` itself is safe.
4. No universally-safe estimator is strictly smaller at any point (Theorem I1);
   the "`B' < bytes` everywhere, still safe" construction is impossible
   (Cor I1.1).

The total optimal safe bound is `B*(x) = bytes(rendered text of x) + q(x)`, each
term individually minimal. **SUPPORTED**, conditional on (A-FAM+)+(A-REND).

## Answer to the FINAL QUESTION
> *Is byte-count merely a safe upper bound, or the unique minimal
> universally-safe upper bound under the stated assumptions?*

**The unique minimal universally-safe upper bound.** Not merely safe: it is the
family envelope itself. The theorem **survives** the attempt to destroy it.

**Exactly why it survives.** Byte-fallback guarantees that for *every* string
there is a tokenizer in the family that treats that string as pure bytes (the
degenerate `κ₀`, and — empirically — real tokenizers on OOV content). Therefore
the least bound that is safe against the *whole* family cannot dip below bytes at
any point: doing so would be unsafe against that one member. The supremum over the
family is attained at bytes, pointwise. There is no slack to reclaim.

## Where it is NOT optimal (destroyed, honestly)
The theorem is optimality **only in the universal/minimax sense**. It is
simultaneously the *loosest possible* bound against any **single** tokenizer:
- vs a known `κ`, `bytes/n_κ ≈ 3–5` (Latin), `≈17` (measured Thai) — byte-count
  wastes 70–95% of the window (Cor 1.1; `RELATED §4`). A client that knows the
  exact `κ` (or calls the server's tokenize/count endpoint) should use `n_κ`,
  the *tight* bound (Cor 1.2), and byte-count is then strictly dominated.
- Under a **restricted** family (A-FAM+ fails — some merge is universal across
  all members), `N(x) < bytes(x)` on inputs hitting that merge, a strictly
  tighter safe bound exists, and **byte-count optimality is FALSIFIED** for that
  family. This is the one assumption that carries the entire result.

So: *optimal iff you truly know only the unrestricted family; loose the instant
you know more.* Optimality and looseness are the same fact viewed against the
family vs against a member — the "price of universality."

## Confidence ledger (OBJECTIVE 7)
| Claim | Status |
|---|---|
| Safety `n_κ ≤ bytes` (rendered) | **SUPPORTED** (partition proof + 0/11 adversarial) |
| Envelope `N = bytes` under unrestricted family | **SUPPORTED** (route A degenerate; route C real-tokenizer witness) |
| `bytes` unique minimal universal safe bound | **SUPPORTED** (Lemma O1 + I1) |
| No tighter universal bound (OBJ 2 impossible) | **SUPPORTED** (Cor I1.1) |
| Normalization cannot break raw-byte safety for Qwen BPE | **SUPPORTED** (measured; U+FDFA 3→165 NFKC yet 15 tok ≤ 15 raw) |
| Same holds for the *production* qwen2.5-14b | **LIKELY** (U1: proxy tokenizer) |
| Holds for NFKC-normalizing SentencePiece families on raw bytes | **UNKNOWN** (U2: use `bytes(ν(x))`) |
| Optimality under a restricted (universal-merge) family | **FALSIFIED** (tighter `N` exists) |
| Kolmogorov / universal-coding formal equivalence | **SPECULATIVE** (analogy only; not reduced) |
| Robust-optimization support-function equivalence | **LIKELY** (genuine special case) |

## What observation would prove this wrong
A byte string `x` and a family member `κ∈𝒦` (consistent with "byte-fallback BPE,
exact merges unknown") for which the tokenizer emits **more** tokens than
`bytes(rendered x)` — breaking safety (would need a byte to become >1 token: only
an unknown expanding normalizer folded into `κ` could do it, excluded by
A-REND). Or: a proof that the client's family is *always* restricted enough that
a common merge is universal — which would move the deployment into R-restricted
and make `bytes` loose. The first attacks the theorem; the second attacks its
assumption. Neither was found this session; the first is structurally ruled out,
the second is a deployment fact tagged UNKNOWN and flagged as the load-bearing
condition.

**Final verdict:** SURVIVES as stated. Byte-count is the unique minimal
universally-safe upper bound under (A-FAM+)+(A-REND); its optimality is exactly
co-extensive with the client's ignorance of the specific tokenizer, and dissolves
the moment that ignorance is lifted.
