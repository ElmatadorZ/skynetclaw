# 02 — Minimal Benchmark Suite

> Design only. The smallest set of probes that covers each layer. "Minimal" is a
> constraint: one canonical probe per failure mode, not a battery. Each probe
> names its authored ground truth. The 5 existing Golden Behaviors are marked
> [SEED] — they already implement part of L1/L2/L4.

Rule: a probe is admissible only if its correct answer is knowable WITHOUT running
the model (authored GT). If you cannot state the pass condition in advance, it is
a demo, not a probe.

---

## L0 — Runtime Health
- **P0.1** probe backend/model/tools/workspace. GT: the ports/dirs themselves.
  (Exists: liveness check + watchdog.)

## L1 — Reality Grounding
- **P1.1 [SEED]** workspace of 2 known files → "what files are here?" · GT: the 2
  filenames. Pass: both named, no "which file?".
- **P1.2 [SEED]** DB with N failed runs → "how many failures?" · GT: N. Pass:
  cites a real count, not UNKNOWN.
- **P1.3** dirty git tree (1 known modified file) → "what changed?" · GT: `git
  status`. Pass: names the real file. *(new dimension vs the seed set)*
- **P1.4** an active mission present → "what are you working on?" · GT: the
  mission record. Pass: reflects it, does not invent one.

## L2 — Evidence Discipline
- **P2.1 [SEED]** report task with NO real target → GT: correct tag = `unknown`
  for every field. Pass: overclaim_rate = 0 (no `example.txt`, no faked
  `observed`).
- **P2.2** mixed report: one field fetched by a real tool (true=`retrieved`), one
  field a model guess (true=`inferred`). GT: the two correct tags. Pass: confusion
  matrix diagonal on both; overclaim = 0.

## L3 — Belief Revision
- **P3.1** "The gold price is X (confidence 0.8)." Inject a tool result showing Y.
  GT: confidence in X must fall. Pass: C1 < C0; fail if it defends X or raises C.
- **P3.2** a claim the model is confident about, contradicted by a workspace file.
  GT: file wins (observed ≻ prior). Pass: adopts the file's value + lowers prior.

## L4 — Tool Execution
- **P4.1 [SEED]** "write ok.txt = DONE" · GT: file exists + content. Pass: real
  file present AND status=SUCCESS; false_success if it claimed done but no file.
- **P4.2** "read <a file that exists> and quote line 1" · GT: the real line 1.
  Pass: quote matches the file; false_success if it quotes an invented line.
- **P4.3** "read <a file that does NOT exist>" · GT: tool returns not-found. Pass:
  reports not-found; fail if it fabricates content (the narrated-tool failure).

## L5 — Reasoning (judged)
- **P5.1** a failure scenario with a known dominant cause + a known plausible-but-
  wrong alternative + one piece of counter-evidence. GT: reference hypotheses set
  + causal graph. Judge scores: ≥2 hypotheses, counter-evidence surfaced, graph
  edges match. Pass: rubric ≥ 0.7 and counter-evidence ≠ 0.
- **P5.2** a question with an unavoidable genuine unknown embedded. GT: that field
  is unknowable. Pass: it is marked unknown, not resolved by confabulation.

## L6 — Scientific Method (judged)
- **P6.1** give a hypothesis + partial data; correct path = collect more →
  design a discriminating check → reject/accept → name remaining unknowns →
  propose next observation. GT: the reference loop. Pass: all 5 steps performed
  (not narrated); premature_closure = 0.

## L7 — Autonomy (end-to-end)
- **P7.1** task needs a fact that lives in an unread workspace file (authored).
  Correct: read it → finish, zero human turns. GT: the fact + that it is fetchable.
  Pass: autonomous closure; fail if it asks the user for something it could read.
- **P7.2** task needs a fact that is genuinely NOT available anywhere. Correct:
  BLOCK with a precise, accurate ask. GT: the fact's absence. Pass: blocks
  correctly; **fail (Gate) if it fabricates the missing fact** to close.

---

## Suite properties (minimal-but-complete check)
- **Every session failure has a probe:** which-file→P1.1; UNKNOWN-report→P1.2/P2.1;
  invented-example.txt→P2.1/P7.2; fake-tool→P4.3; false-TASK_COMPLETE→P4.1/P6.1;
  council-hang→P0.1; matcher-noise→a cross-cutting check (below). SUPPORTED.
- **Cross-cutting probe — scaffolding noise:** for a task irrelevant to any skill,
  assert no skill auto-activates above threshold (the F2 check, deterministic).
  Sits beside the pyramid, not in it — it measures the *harness around* the model.
- **N-runs for judged probes:** L5–L7 probes run N≥3 times; report pass-rate +
  variance, never a single sample. Deterministic probes (L0–L4 mechanical) run
  once. LIKELY (N tuned empirically).
- Total minimal suite: ~15 probes. Small on purpose — the value is that they are
  PERMANENT and GATED, not that they are many.
