# M2 — Deliberation Briefing Engine
### The Council consumes briefings, never raw memories.

> Scope: the Briefing Engine only (Recall Quality already exists; no search/retrieval
> built here). Status: **delivered, 104 tests pass, deliberation_briefing 97% /
> recall_quality 96% / council_memory 92% coverage, brief generation ~5 ms.**

---

## 1. Architecture

Recall Quality (M2 Foundation) answers *"is this memory trustworthy?"* per item. But a
council handed twelve graded sessions would have to re-derive the lessons itself —
re-reading raw history mid-deliberation. The Briefing Engine closes that gap: it turns
validity-graded memories into **institutional guidance** the council can act on directly.

```
  directive
     │
     ▼
 ┌──────────────────────┐  council_memory.recall → recall_quality (M2 Foundation)
 │  RECALL QUALITY      │  validity-graded, justified prior sessions
 └──────────┬───────────┘
            │ cases [{validity, accuracy, calibration, confidence, verdict, participants...}]
            ▼
 ┌─────────────────────────────────────────────────────────────────┐
 │  DELIBERATION BRIEFING ENGINE  (deliberation_briefing.py)         │
 │                                                                   │
 │  • mine predictions of the recalled sessions (lessons/errors)     │
 │  • SYNTHESIZE — never dump a raw session:                         │
 │      validated_lessons   ← VALIDATED verdicts (what worked)       │
 │      failed_lessons      ← DISPROVEN verdicts + why they failed   │
 │      common_patterns     ← recurring terms / validity skew        │
 │      repeated_errors     ← same wrong call made ≥2×               │
 │      confidence_trends   ← stated vs realised (calibration gap)   │
 │      agent_perf_trends   ← reliability of who argued before       │
 │      known_blind_spots   ← untested / outdated / data gaps        │
 │      recommended_focus   ← derived from the above                 │
 │      executive_summary   ← one-paragraph synthesis                │
 │      relevant_cases      ← compressed REFS (gist), not records    │
 │  • empty-history guard — never invents a past                     │
 └──────────────────────────────┬──────────────────────────────────┘
                                │ format_brief_for_council()
                                ▼
              system message injected into deliberation context
                                │
         ┌──────────────────────┴───────────────────────┐
         ▼                                               ▼
  agent_council.run_council                       main.py agent_run
  (Analyst·Strategist·Skeptic·Forecaster·…)        (ATLAS counsel block)
  brief prepended to every role's prompt           brief appended before tools run
```

Synthesis is **deterministic** (assembled from the structured recall + outcomes +
reputation), so it is testable and never itself hallucinates. The council's LLM then
*reasons over* the brief.

---

## 2. Data Flow

| Stage | Source | Transformation |
|---|---|---|
| 1. Recall | `council_memory.recall` → `recall_quality` | validity-graded candidate sessions |
| 2. Mine | `predictions` table (for the recalled ids) | statements, status, metric/direction, invalidation per case |
| 3. Partition | by `validity` | VALIDATED / DISPROVEN / OUTDATED / UNKNOWN / PARTIALLY_VALID buckets |
| 4. Synthesize | per-section builders | the 10 brief sections (lessons, patterns, errors, trends, blind spots, focus) |
| 5. Summarize | `_exec_summary` | one paragraph: counts + top repeated error + established lesson + calibration |
| 6. Render | `format_brief_for_council` | compact system-message text |
| 7. Inject | `run_council` + `agent_run` | prepended to deliberation context, before the council reasons |

Generation is synchronous and cheap (~5 ms — one bounded recall + small in-memory
synthesis), generated **once** per deliberation and shared across all council roles.

---

## 3. Briefing Schema

```jsonc
{
  "directive": "...",
  "generated_at": 1781400000.0,
  "n_cases": 5,
  "coverage": { "VALIDATED": 1, "DISPROVEN": 3, "UNKNOWN": 1 },

  "executive_summary": "5 prior deliberation(s) … ⚠ Repeated error: predicted btc up. "
                       "Established lesson: Phase in, keep a hedge. Calibration: OVERCONFIDENT.",

  "relevant_historical_cases": [          // synthesized REFS — never raw sessions
    { "ref": "cs_…", "validity": "DISPROVEN", "warning": true,
      "gist": "YES max leverage, BTC moons", "accuracy": 0.0,
      "why_relevant": "matched terms: leverage, risk, btc" }
  ],

  "validated_lessons": [ { "lesson": "Phase in, keep a hedge", "from_case": "cs_…", "accuracy": 1.0 } ],
  "failed_lessons":    [ { "lesson": "YES max leverage…", "why_failed": "below 58k", "from_case": "cs_…" } ],
  "common_patterns":   [ { "pattern": "leverage", "occurrences": 3 },
                         { "pattern": "3 prior cases ended DISPROVEN", "occurrences": 3 } ],
  "repeated_errors":   [ { "error": "predicted btc up", "occurrences": 3, "example": "BTC rallies hard" } ],
  "confidence_trends": { "stated_avg": 0.825, "realized_accuracy": 0.25,
                         "calibration_gap": 0.575, "direction": "falling",
                         "note": "the House has been OVERCONFIDENT here" },
  "agent_performance_trends": [ { "agent": "Forecaster", "skill": 0.18, "calibration": 0.1,
                                  "accuracy_rate": 0.0, "reliability": "unreliable" } ],
  "recommended_focus_areas": [ "Do NOT repeat: predicted btc up (failed 3×) …",
                               "Counter known overconfidence: demand evidence …" ],
  "known_blind_spots": [ "1 recalled case(s) are UNTESTED …" ]
}
```

`format_brief_for_council(brief)` renders this to the labelled markdown system message
the council reads (Executive Summary → Validated/Failed Lessons → Repeated Errors →
Patterns → Confidence Trend → Agent Performance → Blind Spots → Recommended Focus, with
a closing instruction: *"Reason WITH this history. Do not repeat disproven reasoning;
do not rediscover validated lessons; surface new uncertainty."*).

---

## 4. Injection Strategy

The brief must exist **before** the thinking members reason. Two injection points:

1. **`agent_council.run_council` (the council deliberation).** Before the six-specialist
   fan-out, `build_brief(task)` runs and the formatted brief is placed in `context`
   under `historical_brief`. `_ask_role` prepends it to **every** role's prompt (Analyst,
   Strategist, Skeptic, Forecaster, Executor, Storyteller) ahead of the TASK, and strips
   internal `_`-prefixed keys from the context dump. Verified: brief precedes TASK in
   every role message.
2. **`main.py agent_run` (the ATLAS counsel path).** Immediately after the ATLAS counsel
   system message is appended (for non-trivial / analysis / strategy / market tasks), the
   brief is appended too — so ATLAS enters informed. Emits a `brief` SSE event with
   `n_cases` + `repeated_errors` for the UI.

Both are **best-effort** (`try/except`, guarded by availability flags): if the briefing
engine is unavailable or errors, deliberation proceeds unbriefed rather than failing.
The brief is generated once and reused — never per-role recomputation.

---

## 5. Failure Modes (and how each is handled)

| Failure mode | Handling |
|---|---|
| **No history** on the directive | `_empty_brief` returns an honest "no prior deliberations — reason from first principles, record a new baseline." **Never invents a past.** (tested) |
| **Raw-session leakage** (dumping a memory verbatim) | `relevant_historical_cases` are compressed refs with a fixed 6-key shape; a test asserts no `contributions`/`model`/`evidence_summary` keys ever appear. Verdicts are gisted to ≤110 chars. |
| **Disproven memory presented as authority** | Inherited from Recall Quality: disproven cases carry `warning`, sink in rank, and surface in the brief under *Failed Lessons* / *Repeated Errors*, never as a validated lesson. |
| **Briefing engine throws** | Both injection sites wrap in `try/except`; deliberation continues unbriefed. |
| **Stale / outdated lessons** | OUTDATED cases are flagged in `known_blind_spots` ("do not treat as current authority"), excluded from validated lessons. |
| **Overconfident history repeated** | `confidence_trends` computes the calibration gap; if > 0.15, `recommended_focus_areas` explicitly instructs the council to counter known overconfidence. |
| **Token / latency blowup at scale** | Brief operates on the ≤k recalled cases (default 8), not the whole table; cost is the bounded recall (~5 ms). |
| **Mislabeled "confidence"** (known debt from the audit) | Documented; the brief reports *stated* vs *realised* side-by-side so the gap is visible rather than hidden. |

---

## 6. Regression Tests (`tests/test_m2_briefing.py`, +12 → 104 total)

- **Structure:** all ten sections present.
- **No raw sessions:** cases are fixed-shape refs; no session-record keys leak.
- **Synthesis:** repeated error detected (≥2×); failed lessons carry a reason; validated
  lesson extracted; overconfidence trend detected (gap > 0.15); blind spots flag untested;
  focus areas warn against the repeated error; agent performance surfaces.
- **Empty history:** no invented past; lessons empty; honest summary.
- **Injection format:** `format_brief_for_council` surfaces warnings + the "do not repeat
  disproven reasoning" instruction; empty-history render is safe.
- **End-to-end:** `run_council` places the brief before TASK in every role prompt (integration test).

---

## Success criteria — met
- The Council consumes a **synthesized briefing**, never raw sessions.
- Recurring **patterns**, recurring **failures**, and **uncertainty** are always identified.
- The brief is generated **before** Atlas / Analyst / Strategist / Skeptic deliberate
  (council fan-out + ATLAS counsel injection).
- The House enters deliberation **already informed by its own graded history** — it will
  not rediscover validated lessons, and it is explicitly warned not to repeat disproven
  reasoning.

### Files
- `backend/deliberation_briefing.py` — the engine (new)
- `backend/agent_council.py` — brief generated + injected before the role fan-out
- `backend/main.py` — brief injected at the ATLAS counsel block in `agent_run`
- `backend/tests/test_m2_briefing.py` — 12 tests
