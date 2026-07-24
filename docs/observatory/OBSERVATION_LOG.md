# Observation Log — RFC-0001 Reality Grading Pilot

> **Commander's order (2026-07-20): Freeze Architecture. Enter Observation Mode.**
> During this window: no P1, no D1/D4, no judge changes, no ownership work, no trace
> work, no Learning-Loop modification of any kind. Record — do not fix.
> Window ends at the first rg-1 judgment: **2026-07-27 13:50** → first Evidence Review.
> Only after that review are P1, the D1 judge migration, and ADR-0016 decided —
> **by the evidence, not by the architect.**

Principle of this document: *the first dataset earns the right to tell us how the
system should evolve, before the architect tells the system what to be.*

---

## Pinned: Mission #1 — the First Living Episode

Mission #1 is **frozen as Baseline, not Benchmark** — never rerun, never overwritten,
never regenerated, flaws included. It is the reference specimen of Learning Loop rg-1:
*this is the system on the day it came alive.*

| Field | Value |
|---|---|
| Mission | 0001 — ADR-0014 Compliance Audit (read-only) |
| Date | 2026-07-20 |
| Outcome | COMPLETE (attempt 4 of 4) |
| Hypothesis | `pr_8233e7fcb794` — "Mission hypothesis: outcome COMPLETE will hold" |
| Judge | rg-1 (existence-based; version pinned in evidence payload) |
| Artifact | `mission-0001---adr-0014-compliance-audit-read-on.pdf` @ repo root — sha256 `779b4e1e…` pinned; git-protected (`0c8f985`); **must not move/change before grading** |
| First reality check | **2026-07-27 13:50** (7-day horizon, auto via outcome clock) |
| Dashboard transition | `WAITING_FIRST_HYPOTHESIS → AWAITING_REALITY` (the first heartbeat) |

### Day 0 — Observed Phenomena from Mission #1 (provisionally *Incidental* — n=1)

> **Correction (Standing Order 007, below):** an earlier draft called these "systemic
> findings." At n=1 that is an over-claim. They are **Observed Phenomena** — we know
> they *occurred*, not yet whether they *should be fixed*. Classified below as
> Recurring / Contextual / Incidental; until more missions arrive, all four are
> **Incidental**. None is a "Problem."

1. **Budget overflow** — a meta-classified task forces the full 25.4 KB prompt; with 29
   tool schemas it exceeded the 16k ceiling by 743 tokens at step 1; every model call
   then failed until the mission was scoped (`tool_allow` = 7 tools → −3.5k tokens).
2. **Workspace jail** — absolute paths outside the workspace are silently re-rooted
   into it; the agent's *correct* path returned "File not found," and its *correct*
   retries tripped the anti-loop guard. Fix was mission design (workspace = repo root,
   relative paths), not code.
3. **Anti-loop guard** — terminated attempt 3 after 3 identical calls; worked as designed.
4. **Learning Integrity held under fire** — three failed attempts (PROBLEM ×3) staked
   **zero** hypotheses. The system refused to claim success it did not have. *This — not
   the eventual COMPLETE — is the bigger victory: the system optimizes for telling the
   truth, not for looking good.*

**Honest deviation, deliberately preserved:** the deliverable is an auto-generated 2 KB
PDF at repo root, not the DoD's 6-section markdown in `docs/audit/`. It stays as-is —
fixing it now would contaminate the baseline by mixing "Mission #1's behavior" with
"system improvement." Mission quality: mediocre. Loop integrity: perfect. The gap
between those two is what reality grading exists to measure.

Learning-plane side effects recorded on Day 0 (for Q5 below): the failed attempts
synthesized 15 lessons (14 win-pattern / 1 fail), attribution logged `outcome: failure`
with 6 recalled lessons; the COMPLETE run signed off with the PDF artifact.

---

## Standing Order 007 — Observation precedes optimization
> Every item in the Backlog (A–E) may be **analyzed, ranked, and recorded** — but
> **NOT implemented** until the first rg-1 Evidence Review is complete.
>
> **Sole exception (integrity, not capability):** an immediate fix is permitted *only*
> if there is evidence the system is (a) **losing data**, (b) **destroying evidence**,
> or (c) **has stopped creating Validated Episodes**. These protect the experiment;
> they do not enhance the system. Nothing else qualifies.

## Language discipline — Observed Phenomena, not Bugs
- **Bug** = we already know it is wrong. **Observed Phenomenon** = we know it *happened*,
  not yet whether it should change. In Observation Mode we use the latter.
- Every phenomenon is tagged, and stays untagged-as-"Problem" until data supports it:
  - **Recurring** — appears across multiple missions → candidate for the review.
  - **Contextual** — appears only for certain mission types → scope-specific.
  - **Incidental** — seen once → held; no action, no name beyond "observed."

## Backlog (analyze / rank / record — do NOT implement; Standing Order 007)

| # | Item | Leverage | Arch cost | Gate |
|---|---|---|---|---|
| **A** | **Capability Tiering** — the router selects a *Capability Provider*, not a model. Today Local↔Cloud; tomorrow Local↔Cloud↔Specialist Agent↔Human. Fully within ADR-0013 (a provider need not be an LLM). | 🥇 highest | ~zero (adapter + router exist) | post-review |
| **A½** | **Provider Evaluation Matrix** — a *read-only study* (below): which mission types each provider mode can carry. No code, no Observatory change, no baseline contamination — so the review does not start from zero. | study | zero | may draft now |
| **B** | **Harness** — the three Day-0 Observed Phenomena (budget / workspace-jail visibility / anti-loop hinting). Held pending Recurring-vs-Incidental classification across missions. | med | low | post-review + n>1 |
| **C** | **MCP client** — reach the external connector ecosystem. | med | med (additive) | post-review |
| **D** | Roadmap: P1 → CTL (projection) → Capability Graph → ADR-0016 → evidence-derived Genome. | med | med–high | post-review |
| **E** | God Object decomposition (`main.py` 9,848 LOC). | low–med | high (refactor) | future ADR |
| **F** | **Conversational / Episodic Memory & memory-driven agency** — close the loop the learning plane already closed for missions, but for *conversations*: distill a finished conversation → persist durable facts → recall by relevance into future conversations and missions (the MEMORY.md pattern Claude Code uses). | high | med — **must be a recall layer over ADR-0014's canonical store, NOT a new silo** (else it trips `test_state_tripwire`) | **post-review + after ADR-0014** |

**Evidence for F (measured 2026-07-20, read-only):** the loop is *half-closed*. Present:
short-term rolling context (`agent_memory.json` "context" = last 3 exchanges), a write-only
audit mirror of all chats (`chat_history.db`, header: "Mirrors … for audit transparency" —
never recalled into reasoning), and mission-lesson recall (`lesson_synthesis` + proprioception:
mission → lesson → next mission). Missing: any distill→persist→recall pipeline for
*conversations*, and any relevance-based recall of past dialogues into a new one. Not
greenfield — it is the proven learning-plane recall pattern applied to a new modality, and
it should ride ADR-0014's provenance graph so conversation memory is a projection over One
Truth, not a seventh store. **Reason to defer is architectural, not just the freeze:
building it now would create the exact silo the tripwire forbids.**

**Refinement (2026-07-20, after SkynetClaw's own self-assessment + verification).** Correcting
my earlier under-count: a durable knowledge store DOES exist and is agent-recallable — the
Obsidian vault (`write/read/search_obsidian` tools + a `_vault_awareness_banner()` injected
into the preamble). So the gap is NOT "no memory store." The precise, verified gap is
**Available ≠ Automatic ≠ Used**:
- *Available, not automatic:* vault recall and `feedback_engine` (mounted as an endpoint,
  not auto-triggered post-mission) require the agent/operator to *choose* to invoke them —
  there is no automatic distill→persist→relevance-injection of a conversation.
- *Available, but unreliable / context-dependent:* **Mission 0001, the only real mission,
  made ZERO obsidian tool calls** despite the tools and the awareness banner. **Counter-
  evidence (same-day, honest correction):** in a *chat* context the vault WAS written —
  `SkynetClaw-Vault/Introduction.md` ("First memory recorded: User introduced themselves
  as ElmatadorZ…", 2026-07-21). So vault-write is not "never used"; it is **used in some
  contexts (chat), not others (missions), at the model's discretion** — which is exactly
  the reliability problem automatic recall (F) solves. The store works; the *guarantee*
  is missing.
This *sharpens* F rather than removing it, and ties it to Backlog A (Capability Tiering):
automatic recall matters MORE precisely because the model is weak and will not self-initiate.
It also verifies Learning Integrity #3 live — a system's confident self-assessment
("I learn fully") is a provider assertion, not evidence; the filesystem is the judge.

### A½ — Provider Evaluation Matrix (pre-review HYPOTHESIS, not measured)

> Reasoning-based first pass from n=1 (Mission #1) + known constraints. **Not benchmarked**
> — measuring it means running missions per provider, which is deferred (would run the loop).
> `Sovereign` = must stay on-box (data cannot leave). ✓ carries · ~ marginal · ✗ blocked.

| Mission type | Local | Cloud | Hybrid | Sovereign (local-only) |
|---|---|---|---|---|
| Audit (read-only, light) | ✓ (Mission #1, after tool-scoping) | ✓ | ✓ | ✓ |
| Meta (heavy prompt, planning) | ✗ (16k overflow · weak planning) | ✓ | ✓ | ✗ (needs > local context) |
| Coding (tool-heavy, multi-step) | ~ (local struggles long tool chains) | ✓ | ✓ | ~ |
| Long reasoning (deep chains) | ✗ (context + coherence) | ✓ | ✓ | ✗ |

*Reading (provisional): local is sufficient for light/sovereign work; cloud or a stronger
provider is the lever for meta/long-reasoning. To be confirmed by measured runs after the review.*

---

## Pre-registered protocol: the First Evidence Review (≥ 2026-07-27)

Written **before** any answer exists, so the review cannot be rationalized after the
fact. The review must answer five questions:

| # | Question | Data source (single observation surface) |
|---|---|---|
| 1 | What did the judge return? (correct / partial / incorrect / abstain) | `predictions.pr_8233e7fcb794.status` after the outcome clock's 7d pass |
| 2 | Did a Belief Revision occur? | `belief_changes` rows with `agent='Reality (outcome)'` |
| 3 | Was a Validated Episode created? | `reality_grading.validated_sessions()` |
| 4 | Did the loop complete with **zero human intervention**? | outcome-clock auto-judge log; absence of any manual `evaluate()` call |
| 5 | **Does what the mission taught us match what the system itself concluded?** | compare Day-0 findings (above) against the lessons/attributions the system synthesized — this measures whether the system *interprets* reality well, not merely whether files exist |

Q5 is the most important: it grades the system's understanding, not its bookkeeping.

**Decisions gated on this review (in order):** P1 (single ownership) · D1 judge
migration (rg-2 + Migration Note) · ADR-0016 (Mission Learning Architecture).

---

## Log entries (append-only; record, never fix)

### Day 0 — 2026-07-20
- Mission 0001 COMPLETE (above). Hypothesis staked. Verdict `AWAITING_REALITY`.
- Architecture frozen by Commander's order. Observation Mode entered.

### Day 3 — 2026-07-23 · read-only status probe (NOT a verdict)

A read-only dry-run of `judge_mission_hypothesis()` against the live staked hypothesis. Nothing
was written, graded, or settled; the outcome clock has **not** fired. Recorded because the window
exists to observe, and an early probe de-risks the review without pre-empting it.

| Field | Observed |
|---|---|
| Hypothesis | `pr_8233e7fcb794` · status `pending` |
| Judge pinned at stake | `rg-1` |
| Due | **2026-07-27 13:50** (≈90 h away at probe time) |
| Artifact | `mission-0001---adr-0014-compliance-audit-read-on.pdf` — **PRESENT** |
| Staked sha256 | `779b4e1e8e22bd8e…` (unchanged from Day 0) |
| Workspace | exists |
| Ledger `5a0319f1b2` | not overturned |
| **`rg-1` would currently return** | **`correct`** |
| `vital_signs().verdict` | `AWAITING_REALITY` — matches the Day-0 pin |

**What this is:** evidence that the artifact has survived three days untouched, and that the loop's
state machine is reporting itself correctly (`AWAITING_REALITY`, `abstain_rate` honestly `None`
rather than a fake `0`).

**What this is NOT:** a verdict. A dry-run at T+3d is not the graded outcome at T+7d, and recording
it as one would be precisely the Evidence-Normalization violation the loop exists to prevent. The
pre-registered questions in the review protocol remain unanswered until the clock fires.

**Not changed:** the judge, the hypothesis, the horizon, the artifact, the mission baseline. Probe
only.

<!-- Append Mission #2, #3 … entries here in the same shape. Do not edit prior entries. -->

---

## Maintenance Ledger (NOT observation entries — Operational Infrastructure only)

> Standing Order 007 forbids *capability* work in the freeze. It does **not** forbid
> keeping existing infrastructure alive. Entries here are the narrow, Commander-authorized
> class of change that repairs a failing external dependency **without** touching
> Interface, Semantics, Evidence, or the Learning Loop. Each entry states the four
> invariants it preserved. These are maintenance, not evolution.

### M-001 — 2026-07-21 · web_search External Provider Layer repair
- **Trigger:** operator-observed dependency failure — `web_search "Terng Dechanon GitHub"`
  returned "all sources failed"; free scrapers + dead public SearXNG, no keyed API. A live
  reproduction on this date: SearXNG (5 instances) all down, Brave scrape `HTTP 429`.
- **Change class (Commander ruling):** Operational Infrastructure Maintenance — *not* an
  architectural change, *not* an Observation-Freeze override. No ADR (public interface and
  semantic behaviour unchanged).
- **What changed:** the inline 6-source fallback chain in `main.py` was factored into a
  swappable Provider Layer, `backend/search_providers.py`, mirroring the Model Adapter
  pattern (ADR-0013: search is a Capability Provider). Added keyed providers
  (Brave API / Tavily / Serper) tried **first** when their env key is present; the free
  providers keep their exact prior order.
- **Four invariants preserved (the criteria of the ruling):**
  1. **Interface unchanged** — same tool schema, same `query`/`max_results` args, same
     return-string shape (header, `N. **title** 🔗 url snippet`, footer, FAILED message).
  2. **Semantics unchanged** — try providers in priority order, first non-empty wins;
     with **no key** the first available provider is DDG-Lite exactly as before → output
     byte-identical to pre-refactor.
  3. **Evidence unchanged** — total failure still returns the explicit FAILED list plus the
     anti-fabrication AI INSTRUCTION; **no fabricated results, ever.**
  4. **Determinism improved** — a keyed API replaces best-effort HTML scraping as the
     primary path (the one property the ruling asked to move).
- **Scope guard:** touched only the Provider Layer. Did **not** touch the Learning Loop,
  the judge (rg-1), the Observatory, or Mission #1's baseline/artifact. Keys are supplied
  by the **operator** via environment (`BRAVE_SEARCH_API_KEY` / `TAVILY_API_KEY` /
  `SERPER_API_KEY`); the agent writes only the env-reading integration and never handles a
  credential.
- **Verification:** `backend/tests/test_search_providers.py` — 6/6 offline, deterministic
  (format byte-identity, router order, keyed-skip-without-key, total-failure → no
  fabrication). Live free-path smoke reproduced the operator's failure (dependency down),
  confirming the diagnosis; keyed path activates on operator key.
