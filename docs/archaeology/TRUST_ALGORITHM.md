# Trust Algorithm — does a belief survive? (reverse-engineered, pseudocode only)

> The decision procedure that determines whether a belief is trusted, recovered from the
> **thresholds actually stated** in the organs' docstrings/commit evidence. **Pseudocode
> only — no implementation, no proposal.** Numbers are quoted from evidence where present;
> anything not evidenced is marked UNKNOWN inline. Tags at the end.

## Inputs (all evidence-sourced)
```
belief := {
  support_count,          # how many episodes back it        (first_principles: ≥5)
  confidence,             # predicted probability            (first_principles: ≥0.70)
  independent_systems,    # distinct detectors agreeing       (first_principles: ≥2)
  calibration_error,      # |predicted − observed|            (calibration organ)
  recent_contradiction,   # accumulating counter-evidence     (belief_revision)
  domains_generalised,    # how many domains it holds in      (theory: ≥2 → theory)
  lift_over_baseline,     # outcome delta vs not-using-it     (reinforcement/attribution)
  sourced_by_tool,        # was underlying live-data tool-sourced?  (shadow_gate)
  reversibility,          # is acting on it reversible?        (Constitution / Trust)
}
```

## The survival procedure
```
function belief_survives(belief) -> {TRUSTED, CANDIDATE, CHALLENGED, REJECTED, GATED}:

    # ── Gate 0: source integrity (shadow_gate) ── a claim about live reality
    #    that no tool sourced is not even admissible.
    if belief.is_live_data and not belief.sourced_by_tool:
        return REJECTED            # "must call a live tool before writing live data"

    # ── Gate 1: anti-single-source (first_principles) ── corroboration is mandatory
    if belief.independent_systems < 2:
        return CANDIDATE           # noticed, never promoted — "no single noisy detector"

    # ── Gate 2: sample-size + confidence floor (first_principles) ──
    if belief.support_count < 5 or belief.confidence < 0.70:
        return CANDIDATE

    # ── Gate 3: calibration (calibration) ── predicted must match observed
    if belief.calibration_error > TOL:          # TOL = UNKNOWN (organ measures it; threshold not quoted)
        return CHALLENGED          # over/under-confident → self-assessment not trusted here

    # ── Gate 4: falsification pressure (belief_revision) ── recent counter-evidence wins
    if belief.recent_contradiction:
        return CHALLENGED          # drift detected — but note: DETECTION ONLY

    # ── Promotion tier (theory) ──
    tier := "principle"
    if belief.domains_generalised >= 2:
        tier := "theory"           # cross-domain generalisation

    # ── The actuation seam (the decisive human/auto split) ──
    if change_is_behavioural(belief):
        if belief is capability_weight:
            # the ONE automatic loop, rate-limited (reinforcement)
            weight += clamp(ALPHA*(target - weight), ±MAX_STEP)   # MAX_STEP=0.15, weight∈[0.5,1.5]
            return TRUSTED         # AUTO — but bounded so no single mission dominates
        else:
            return GATED           # "candidates; humans / later protocols decide"
    else:
        return TRUSTED as tier     # trusted as an OBSERVATION/recommendation, not an action

    # ── Constitution overlay (Trust) ── never act-as-true if irreversible w/o human
    # applied around any behavioural use:
    #   if not belief.reversibility and no_human_gate: return GATED
```

## What the algorithm reveals (SUPPORTED)
1. **Multiplicative, not additive, trust.** A belief must pass *every* gate (source ∧ ≥2
   systems ∧ ≥5 support ∧ ≥0.70 conf ∧ calibrated ∧ not-contradicted). One failed gate →
   demotion. Trust is a conjunction of independent filters.
2. **Corroboration is the hard floor.** `independent_systems < 2 → CANDIDATE` is the first
   non-negotiable after source-integrity. The organism structurally cannot trust itself
   from one place.
3. **The human gate is a *state*, not an afterthought.** `GATED` is a legitimate terminal
   output for almost all behavioural change — the algorithm is *designed* to stop short of
   acting and hand off.
4. **One automatic edge, deliberately bounded.** Capability-weight reinforcement is the sole
   auto-actuation, and it is rate-limited so no single experiment can move it far.

## Confidence
- Gate structure & the corroboration/support/confidence thresholds: **SUPPORTED** (quoted).
- `TOL` for calibration and the exact `ALPHA`: **UNKNOWN** (organs measure/clamp; precise
  constants not in the evidence I read — MAX_STEP=0.15 and clamp[0.5,1.5] *are* quoted).
- The Constitution overlay: **SUPPORTED as design** (Trust/Constitution docs) / **N/A as
  running code** (kernel is design-only) — so treat that overlay as *intended*, not proven-active.
