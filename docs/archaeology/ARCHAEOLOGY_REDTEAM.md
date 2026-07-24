# Archaeology Red-Team — falsifying my own report

> Objective: **destroy the prior archaeology, not defend it.** Every conclusion assumed
> wrong until it survives an attack backed by fresh git forensics. The prior docs
> (GENESIS_ARCHAEOLOGY / EVOLUTION_MAP / RESPONSIBILITY_MATRIX / … / SELECTIVE_PRESSURES /
> EVOLUTION_TIMELINE / FUTURE_PRESSURES) are treated as immutable; **where this document
> and they disagree, this document wins** for the specific claim. Tags: SUPPORTED / LIKELY
> / SPECULATIVE / UNKNOWN.
>
> Forensic method: `git log -S` (pickaxe) over code only, `--diff-filter=A` add-dates,
> initial file sizes, and message-content analysis — run *against* my own conclusions.

## Attacks that LANDED — casualties

### ✘ C1 — "The additive, read-only policy is THE dominant / master pressure"
- **Attack:** recount. `additive|read-only|read-side` appears in **24 of 137 commits (~17.5%)**
  — a **minority**, concentrated in the 06-22/23 epistemic burst.
- **Verdict:** **OVERCLAIM — DOWNGRADED.** It is the most prevalent *explicit policy tag* and
  it plausibly shaped the *epistemic era*, but it does **not** govern the organism (5 of 6
  commits carry no such tag). Calling it "the master pressure that explains most mutations"
  is not supported. **New status: LIKELY driver of G-γ only; NOT SUPPORTED as global.**

### ✘ C2 — "Truth→Epistemic was driven by anti-hallucination pressure (P-TRUST)"
- **Attack:** read the burst's own messages. They are **research-flavored, not truth-flavored**:
  "Theory Formation", "Experiment Design", "Paradigm Evolution", "Research Agenda", "First
  Principle Extraction", "Belief Revision", "Gap Discovery", "Causal Discovery". **Zero**
  mention truth / hallucination / verify.
- **Verdict:** **FALSIFIED for the burst.** A better-fitting explanation is **P-RESEARCH
  (scientific / cognitive ambition)**, not truth-guarding. My P-TRUST evidence (`OX-1.6
  "prove completion, don't assert it"`, shadow_gate fixes) belongs to *execution-completion*
  (06-17) and *news/write* fixes (06-29) — a **different era and concern** that I conflated
  with the research suite. **New status: the epistemic suite = P-RESEARCH (LIKELY); P-TRUST
  is real but only for execution-completion, not the suite.**

### ✘ C3 — Timeline methodology: "git witnessed the growth / add-date ≈ birth"
- **Attack:** initial sizes. `agent_council.py` entered git **already 485 lines** (mature)
  at its first appearance (06-15); even the root file `house_sync.py` entered at 259 lines.
- **Verdict:** **PARTIALLY FALSIFIED.** Several organs were **mature-on-arrival** — committed
  whole, not grown in-repo. So EVOLUTION_TIMELINE's eras are **commit eras, not birth eras**;
  they capture *when code entered version control*, which is **not** when the responsibility
  was born. Relative *ordering of in-window additions* still holds; *birth dating* does not.

### ✘ C4 — (my own mid-red-team error) "V1 constructs lived in git code!"
- **Attack:** the alarming `-S` counts (CompoundMind×2, FactFlagger×2, …) were a **false
  positive** — the matches were in **my own archaeology docs** quoting the identifiers, not
  in code. Code-only re-run: **FactFlagger=0, SEED_BRANDS=0, StyleProfile=0, science_ratio=0.**
- **Verdict:** **RETRACTED.** The scare was wrong; see S1 for what actually survives.

### ✘ C5 — Implicit assumption: "the cognitive organs were human-designed"
- **Attack:** `skynetclaw_codex.py` and `commander.py` were added by commit
  `65be120 "skynetclaw [33cd61] step 5 — write_file"` — a message shaped like an **agent
  mission step**, i.e. possibly **agent-authored code**, not a human design act.
- **Verdict:** **ASSUMPTION UNSAFE.** Design *intentionality* of at least some organs is
  **UNKNOWN / possibly emergent (agent-written)**. Any narrative implying deliberate human
  architecture for those organs is unsupported.

## Attacks that FAILED — survivors (stronger now, because tested)

### ✔ S1 — "V1's Style & Fact constructs left no trace in code or its git history"
- **Attack & result:** code-only pickaxe = **0 commits** for FactFlagger / SEED_BRANDS /
  StyleProfile / science_ratio across all history.
- **Verdict:** **SURVIVES — now actually tested** (previously asserted from a current-code
  grep; now confirmed against full history). The Style/Fact models vanished with **no git
  trace** → their disappearance is real and un-provenanced.
- **Caveat:** the *name* "CompoundMind" **did** appear in **1 code commit** (`b5b687f`, inside
  `agent_council.py`/`main.py`, 06-15). So "nothing survived by name" is **slightly wrong**:
  the CompoundMind *token* existed early in council code. Whether it is V1's construct or a
  namesake = **UNKNOWN**.

### ✔ S2 — "The Council's birth predates git; its origin is UNKNOWN"
- **Attack & result:** `agent_council.py` arrived **mature (485 lines)** on its first commit —
  it was written *before* being committed.
- **Verdict:** **SURVIVES, STRENGTHENED.** Git did not witness the council's birth; the WHY
  remains **UNKNOWN**. (This same evidence is what sinks C3.)

### ✔ S3 — "The epistemic suite genuinely emerged in the observed window"
- **Attack & result:** `first_principles.py` (06-23), `calibration.py` (06-23) have real
  in-window add-dates and did **not** exist at the root commit.
- **Verdict:** **SURVIVES** as *chronology* (the suite is genuinely new in-window). Only its
  *pressure label* was wrong (C2). Emergence real; motive re-attributed.

### ✔ S4 — "The world became live within the observed window" (M-6)
- **Attack & result:** at the root commit only `house_sync.py` existed (1 file); realtime /
  news / epistemic / codex organs were **all absent** and added later.
- **Verdict:** **SURVIVES.** The live-world/execution organs are genuinely in-window
  additions (even if some arrived mature).

### ✔ S5 — "Proprioception never shipped" (M-8)
- **Attack & result:** no commit implements a self-state aggregator (searched; none found).
- **Verdict:** **SURVIVES** (unattacked successfully). The gap is real.

### ✔ S6 — "A consolidation counter-pressure existed but was weaker"
- **Attack & result:** the single-source/unified-intent/single-orchestration commits are
  real and few relative to additive ones.
- **Verdict:** **SURVIVES** (this was already a hedged claim; evidence holds).

## Net verdict — what remains standing
| Prior claim | Status after red-team |
|---|---|
| Style/Fact model vanished without git trace (S1) | **SURVIVES** (now tested) |
| Council birth UNKNOWN / mature-on-arrival (S2) | **SURVIVES, stronger** |
| Epistemic suite emerged in-window (S3) | **SURVIVES (chronology)** |
| Live-world organs are in-window (S4) | **SURVIVES** |
| Proprioception never shipped (S5) | **SURVIVES** |
| Consolidation was the weaker counter-force (S6) | **SURVIVES** |
| Additive policy = *dominant/master* pressure (C1) | **DOWNGRADED** → epistemic-era driver only |
| Epistemic suite driven by anti-hallucination (C2) | **FALSIFIED** → research-ambition fits better |
| Timeline add-dates ≈ birth dates (C3) | **PARTIALLY FALSIFIED** → commit eras ≠ birth eras |
| "V1 lived in git code" (my own scare, C4) | **RETRACTED** (doc false-positive) |
| Organs were human-designed (C5) | **UNSAFE** → some possibly agent-written |

## UNKNOWNs after the red-team (some reduced, some hardened)
- **Reduced:** V1 Style/Fact provenance — now positively *absent* from git code (was "assumed absent").
- **Hardened:** council origin (mature-on-arrival ⇒ definitively pre-git) — UNKNOWN and *provably* so.
- **New:** whether the epistemic organs were human- or agent-authored (C5). **UNKNOWN.**
- **Open (unchanged):** whether the many owners actually duplicate vs partition (DEC-1/2/3 —
  still unrun; this red-team did not settle it).

## Honesty note
The single most important correction is **C2 + C1**: my headline "additive policy → truth
became epistemic" was **two errors stacked** — the policy is not dominant (minority %), and
the suite is research-driven, not truth-driven. The prior SELECTIVE_PRESSURES/TIMELINE
overstated a tidy causal story. What genuinely survives is narrower and less elegant:
a mature-on-arrival council of unknown origin, a real but era-local additive habit, a
research-ambition explosion, a live-world build-out, and a self-perception gap that never
shipped — with the deepest *why*s still **UNKNOWN**.
