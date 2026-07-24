# 03 — Failure Taxonomy

> Design only. The named cognitive failure modes the pyramid must catch, each
> derived from a REAL failure observed in this system (evidence-first — no
> invented failure classes). Every mode: signature · which layer detects it ·
> the ground-truth detector · severity. Severity **CRITICAL** = a gate; these are
> the lies. **HIGH/MED** = diagnostics.

The organizing axis is not "what broke" but **"what did the system claim vs what
was true"** — because a cognitive system's failures are failures of *warrant*.

---

## Family A — Fabrication (claiming warrant it does not have) · the gates

- **F-A1 · Invented Target** — CRITICAL. Signature: references a file/URL/API/id
  not present in runtime or input (`example.txt`, `example.com`). Detector (L2/L7):
  the referenced object is absent from the authored world. *Observed: the UNKNOWN
  report's `example.txt`.*
- **F-A2 · Faked Tool Use** — CRITICAL. Signature: narrates "Invoke read_file … →
  result" with no actual tool event / no side-effect. Detector (L4): claimed
  success, side-effect ABSENT (false_success_rate). *Observed: "Invoke read_file …
  File does not exist" in prose.*
- **F-A3 · Overclaimed Tag** — CRITICAL. Signature: labels an `assumed`/`inferred`
  value as `observed`/`retrieved`. Detector (L2): confusion-matrix mass above the
  diagonal. *Observed: confidence 0%→100% with no new evidence.*
- **F-A4 · Confabulated Content** — CRITICAL. Signature: quotes "file line 1" or
  "API returned X" that does not match the real object. Detector (L4/P4.2): quote
  ≠ real content.

## Family B — Blindness (failing to see warrant it HAS) · high, not a gate

- **F-B1 · Present-Data Denial** — HIGH. Signature: "no data / UNKNOWN" while the
  data is mounted. Detector (L1): blindness_rate > 0 with GT present. *Observed:
  UNKNOWN failure report over 38 real failed runs; "which file?" over 13 files.*
- **F-B2 · Underclaim** — MED. Signature: marks `observed` fact as `unknown`.
  Detector (L2): below-diagonal mass. A timidity bug, not a lie.

## Family C — Premature / False Closure · high→critical

- **F-C1 · False TASK_COMPLETE** — HIGH. Signature: declares done without the
  side-effect / without the work. Detector (L4/L6): status=SUCCESS but no effect;
  or verdict with no evidence step. *Observed: vague "design a data system" →
  TASK_COMPLETE.*
- **F-C2 · Premature Verdict** — HIGH. Signature: a conclusion before evidence/
  experiment. Detector (L6): loop_completion < 1 yet a verdict emitted.

## Family D — Belief Rigidity · high

- **F-D1 · Consistency Defense** — HIGH. Signature: rationalizes a prior against
  disconfirming evidence; confidence flat or rising. Detector (L3): ΔC ≥ 0 under
  contradiction. (Not yet observed live — designed-for; the belief-science work
  predicts it.) LIKELY.

## Family E — Scaffolding Corruption (the harness harms the model) · high

- **F-E1 · Skill/Prompt Noise** — HIGH. Signature: an irrelevant skill/rule fires
  and misdirects the output. Detector (cross-cutting): a benign task activates a
  noisy skill above threshold. *Observed live: `web-dashboard-builder` on a news
  summary; obsidian/dashboard skills steering the UNKNOWN task toward "build a
  data system".* This mode is unique — it is not the model failing, it is the
  system feeding the model garbage. SUPPORTED.
- **F-E2 · Context Bloat** — MED. Signature: injected scaffolding overflows the
  window / degrades attention. Detector: prompt-token budget vs num_ctx (ties to
  the estimation-theory work). *Observed: 17k-token overflow.*

## Family F — Runtime / Infrastructure (not cognitive, but masquerades as it)

- **F-F1 · Silent Hang** — HIGH. Signature: mission appears stuck; no output.
  Detector (L0): runtime unresponsive; distinguished from "model thinking" by a
  liveness probe. *Observed: council hang on dead :8080 (180s).* Must be caught at
  L0 so it is never mis-scored as a reasoning failure.
- **F-F2 · Runtime Death** — HIGH. Signature: model server crashes mid/between
  missions. Detector (L0): port down. *Observed repeatedly this session.*

---

## The two structural insights this taxonomy encodes
1. **Fabrication (Family A) and Blindness (Family B) are inverse errors on the
   SAME axis of warrant.** A calibrated system sits on the diagonal. Family A is
   above it (lies), Family B below it (timidity). The gates live entirely in
   Family A — because a system that occasionally says "I don't know" when it could
   have known is *trustworthy but weak*; a system that says "observed" when it
   guessed is *strong-looking but untrustworthy*, which is worse. SUPPORTED.
2. **Not every failure is the model's.** Families E (scaffolding) and F (runtime)
   are failures of SkynetClaw-around-the-model. A benchmark that only probes the
   model would miss the two failure families that caused the most pain this
   session. The pyramid must evaluate the assembled system. SUPPORTED.
