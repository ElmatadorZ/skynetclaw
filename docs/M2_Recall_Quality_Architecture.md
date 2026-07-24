# M2 Foundation — Recall Quality Architecture
### The House must not recall information. It must recall *justified* information.

> Scope: the Recall Quality Layer only. The Convener is **not** built here — first we
> make the information being recalled trustworthy. Status: **delivered, 92 tests
> pass, recall_quality 96% / council_memory 92% coverage, 5.5 ms recall @ 100k sessions.**

---

## 1. Recall Quality Architecture

Before M2, `recall()` answered *"what past sessions look like this query?"* It could
not answer *why* a memory surfaced, *whether* it was correct, or *whether* it still
holds. M2 inserts a dedicated layer between retrieval and consumption so every
recalled memory arrives **annotated and justified**.

```
   directive
       │
       ▼
 ┌───────────────┐   bounded token match over council_sessions
 │  RETRIEVAL    │   (council_memory.recall — the only DB scan)
 │ council_memory│──────────────► candidate sessions [{id, directive, ts, confidence}]
 └───────┬───────┘
         │ candidates
         ▼
 ┌──────────────────────────────────────────────────────────────┐
 │  RECALL QUALITY LAYER  (recall_quality.py — pure, deterministic)│
 │                                                                │
 │  1. gather_outcomes()     join predictions → per-session       │
 │                           n_correct / n_partial / n_incorrect  │
 │  2. detect_supersession() newer NON-disproven ruling on the    │
 │                           same ground supersedes the older     │
 │  3. assess() per candidate → attach the FIVE scores:           │
 │       • similarity      (token Jaccard, query vs directive)    │
 │       • accuracy_score  (graded-prediction accuracy)           │
 │       • calibration     (1 − |stated_conf − accuracy|)         │
 │       • outcome_status  (counts of correct/partial/incorrect)  │
 │       • validity        (one of 5 states, below)               │
 │  4. justification{}      why_recalled · why_relevant ·         │
 │                          whether_correct · whether_valid       │
 │  5. rank + sort          trusted first, warned sink            │
 └───────────────────────────────┬──────────────────────────────┘
                                  ▼
                  justified, ranked, labelled memories
                  (ready for the Convener — M2 proper — to consume)
```

Separation of concerns is deliberate: `council_memory` owns **retrieval + storage**;
`recall_quality` owns **judgement**. The layer is pure (its only I/O is a read of
`predictions`), so the Convener can call it deterministically and testably.

---

## 2. Retrieval Pipeline

| Stage | Module | Responsibility | Cost @100k |
|---|---|---|---|
| 1. Retrieve | `council_memory.recall` | Token-match query against a bounded recent window (`_RECALL_SCAN=1000`) of `council_sessions`, ordered by recency. | ~1.3 ms scan |
| 2. Outcomes | `recall_quality.gather_outcomes` | One grouped query: join candidate sessions → their graded `predictions`. | sub-ms |
| 3. Supersession | `recall_quality.detect_supersession` | Pairwise (small candidate set) — a newer, **non-disproven** near-duplicate supersedes the older. | sub-ms |
| 4. Assess | `recall_quality.assess` | Compute the five scores + validity + justification per candidate. | sub-ms |
| 5. Rank | `recall_quality.annotate` | Sort: trusted (no warning) first, then by justified rank. | sub-ms |

Total: **~5.5 ms warm at 100,000 sessions**, returning 5 justified memories.

The retrieval window is the one **known ceiling** (audit finding H2): at very large
scale a 1000-row recent window cannot see deep history. It is intentionally *not*
fixed here — M2's mandate is *quality*, not *reach*. The Scaling Strategy (§5) defines
the FTS5/vector upgrade that lifts it.

---

## 3. Memory Ranking Logic

### Validity states (current validity of a memory)

| State | Meaning | Warning | Trust factor |
|---|---|---|---|
| `VALIDATED` | graded, accurate (≥0.6), current, not superseded | no | 1.00 |
| `UNKNOWN` | no graded outcomes yet — untested, not untrusted | no | 0.50 |
| `PARTIALLY_VALID` | mixed outcomes, or correct-but-aging (>270d) | **yes** | 0.60 |
| `OUTDATED` | superseded by a newer ruling, or past staleness horizon (>540d) | **yes** | 0.25 |
| `DISPROVEN` | graded predictions resolved incorrect (<0.4) | **yes** | 0.10 |

State priority (highest wins): **DISPROVEN → OUTDATED → UNKNOWN → VALIDATED/PARTIALLY_VALID.**

### The ranking law

```
rank = similarity
     × accuracy_factor          (0.1 + 0.9·accuracy   if graded, else 0.5 neutral)
     × (0.5 + 0.5·calibration)  (penalise miscalibrated past confidence)
     × VALIDITY_FACTOR[state]   (crush disproven/outdated)

sort key = (trusted_before_warned, rank desc, similarity desc)
```

Two invariants this enforces — the heart of "justified, not just recalled":
1. **Correctness beats similarity.** A `DISPROVEN` memory with the *highest* textual
   similarity ranks *below* a `VALIDATED` one (verified: sim 0.83 disproven loses to
   a lower-sim validated).
2. **No untrustworthy memory is ever surfaced as unqualified authority.** Every
   `DISPROVEN`/`OUTDATED`/`PARTIALLY_VALID` result carries `warning=True` and a
   `justification.whether_valid` explaining why, and sorts below all trusted results.

### Justification (attached to every result)
```
why_recalled  : "matched terms: inflation, regime, gold"
why_relevant  : "similarity 0.20"
whether_correct: "VALIDATED: accuracy 1.0 over 2 graded prediction(s)"
whether_valid : "OUTDATED — superseded by cs_ab12cd34"   (or staleness reason)
```

### Supersession nuance
A newer ruling only supersedes an older one if the newer is **not disproven** — a
proven-wrong "update" cannot retire a validated precedent. (Caught by a regression
test after it broke an M1.5 invariant.)

---

## 4. Performance Analysis

| Scenario | Result |
|---|---|
| recall + full quality pass @ 100k sessions | **5.5 ms warm / 6.6 ms cold** |
| retrieval window scan (1000 rows) | 1.3 ms (the dominant, bounded cost) |
| quality annotation (outcomes + supersession + assess) | < 1 ms for a 5–30 candidate set |
| DB size @ 100k sessions | ~15 MB |
| Reads | lock-free (M1.5 C4 `init_once`); recall never writes |

The quality layer adds **negligible latency** — it operates on the small retrieved
candidate set, not the whole table. The cost is and remains the retrieval scan, which
is constant-bounded by `_RECALL_SCAN`.

---

## 5. Scaling Strategy

The quality layer scales trivially (works on ≤ candidate-window rows). The **retrieval
window is the scaling axis**:

1. **Now (≤ ~50k active sessions):** bounded recent-window token match is correct and
   fast. Quality weighting compensates for the small window because the most relevant
   recent precedent is usually within it.
2. **Next (FTS5):** replace the `LIKE`/Python token scan with a SQLite **FTS5** virtual
   table over `directive` (+ verdict). Retrieval becomes an indexed full-text query over
   *all* history at sub-10ms, feeding the same quality layer unchanged. This is the
   direct fix for audit finding **H2** (recall blindness beyond the window).
3. **Later (semantic):** add an embedding sidecar (`recall_vectors`) for meaning-based
   retrieval; the quality layer is the consumer either way — **only the retrieval stage
   changes, never the judgement stage.** That clean seam is the point of the layer split.
4. **Archive growth:** orthogonal (Obsidian file-count) — tracked separately.

Because retrieval and judgement are decoupled, each can scale on its own timeline
without touching the other.

---

## Success criteria — met
- Every recalled session carries **similarity · accuracy · calibration · outcome_status
  · validity** — verified by test.
- All five validity states (`VALIDATED`, `PARTIALLY_VALID`, `OUTDATED`, `DISPROVEN`,
  `UNKNOWN`) are produced and tested, including OUTDATED via **both** supersession and
  staleness.
- The House knows, per memory, **why it was recalled, why it's relevant, whether it was
  correct, and whether it remains valid** — the `justification` block.
- Disproven/outdated memory can never outrank validated precedent and never appears
  without a warning.

**The House now recalls justified information.** The Convener (M2 proper) can be built
on top of this layer next.

---

### Files
- `backend/recall_quality.py` — the layer (new)
- `backend/council_memory.py` — `recall()` now retrieves then delegates (refactored;
  duplicated outcome helpers removed)
- `backend/tests/test_m2_recall_quality.py` — 13 tests (validity states, scores,
  justification, ranking law, supersession)
