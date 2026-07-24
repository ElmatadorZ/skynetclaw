# Maturity Model — computed capability scoring

**Version:** 0.1 (DRAFT — design only) · **Date:** 2026-07-13 · **Owner:** ElmatadorZ
**Under:** ADR-0007 · **Depends on:** CAPABILITY_DEPENDENCY_GRAPH, BENCHMARK_OS, CVL/CAE.
Makes maturity a **computed, falsifiable measurement**, not a hand-assigned label.
"Present" must *mean* something and be provable.

---

## 1. The four factors

Each in [0, 100], measured by an existing/planned subsystem:

| Factor | Definition | Measured by |
|---|---|---|
| **B — Benchmark** | the capability's score on its Benchmark-OS category | Benchmark OS |
| **V — Validator** | assurance coverage: % of the capability's claims with a green Validator × pass-rate | CVL / CAE |
| **C — Coverage** | % of the capability's `composes-from` surface (primitives + sub-caps) actually implemented | CDG |
| **R — Reliability** | measured trustworthiness: `1 − FP-rate`, calibration (1 − ECE), uptime | Benchmark OS + CAE |

None is self-reported; every factor traces to a subsystem measurement.

---

## 2. The score (reconciling the two formulas)

The Chief Architect gave two candidate formulas — a product (`B × V × C × R`, where any
zero fails) and a weighted sum (`0.35B + 0.25V + …`). They encode different intents:
the product is a **safety gate**, the sum is a **smooth score**. The correct model is a
**hybrid** — a weighted sum for the number, *hard gates* for the safety intent:

```
RawScore  = 0.35·B + 0.25·V + 0.20·C + 0.20·R        # smooth, human-readable

# Hard gates (the product's safety intent, without its brittleness):
if V < 60  → cap band at "Emerging"    # unassured capability may never be Present
if R < 70  → cap band at "Partial"     # unreliable capability may never be Present
if C < 50  → cap band at "Emerging"    # half-built capability is not real

# Dependency ceiling (from the CDG — the key structural law):
Effective = min( RawScore , min over deps of Effective(dep) )
```

**Why the dependency ceiling matters most:** it encodes "a capability is only as mature
as its weakest dependency." A Decision capability scoring 92 whose Forecast dependency
is at 55 is *capped at 55* — because a decision built on a shaky forecast is shaky. This
single law prevents a composite capability from claiming a maturity its foundations
don't support, and it is only computable because the CDG exists.

*(Weights are the initial calibration; the **shape** — weighted sum + gates + ceiling —
is the design. Weights are tunable from outcome data.)*

---

## 3. Bands

| Band | Score | Meaning |
|---|---|---|
| **Missing** | 0 – 39 | not built, or no measurement exists |
| **Emerging** | 40 – 69 | exists, partially assured/measured |
| **Partial** | 70 – 84 | works, but below production bar |
| **Present** | 85 – 94 | production-grade: assured + measured |
| **Trusted** | 95 – 100 | production-grade + calibrated + battle-tested; eligible for autonomy |

The `Trusted` band is the hook for the CVL-v3 *dissolving scaffold*: only a Trusted
capability may have its external assurance relaxed toward advisory.

---

## 4. Auto-promotion / auto-demotion (governed)

- Recomputed by the **Benchmark OS** on every run (nightly + on change).
- A band change emits an **audit-critical `capability.maturity` event** on the kernel
  spine — no silent maturity change.
- **Demotion is automatic and immediate** (reliability drop, benchmark regression, a
  dependency demoted → ceiling drops). Safety fails safe.
- **Promotion to `Present`/`Trusted` requires a human ratification ack** (governance) —
  granting production/autonomy status is consequential; the *score* promotes
  automatically, the *authority* is human-gated. (Promotion to Emerging/Partial is
  automatic.)

This makes maturity a live control signal, not documentation: a capability that
regresses loses standing the same night, visibly.

---

## 5. Anti-gaming

- **Hard gates** stop a high-benchmark-but-unvalidated or unreliable capability from
  reaching Present (the product-formula intent).
- **Reliability includes calibration** (ECE) — you cannot buy a high score with
  confident-but-wrong outputs.
- **Dependency ceiling** stops importing maturity you didn't earn.
- **Human gate on Present/Trusted** stops metric-optimization from silently granting
  production authority.

---

## 6. Worked example

```
Decision:  B=88  V=100  C=72  R=94
RawScore = .35·88 + .25·100 + .20·72 + .20·94 = 30.8 + 25 + 14.4 + 18.8 = 88.4  → "Present" band
Gates:     V≥60 ✓  R≥70 ✓  C≥50 ✓                                             → no cap
Ceiling:   deps = {Forecast: Effective 82, Risk: 90, Constraint: 95}
           Effective = min(88.4, 82) = 82.0                                    → "Partial"
Result:    Decision is PARTIAL (82.0) — capped by Forecast(82), NOT Present —
           and cannot promote until Forecast improves. Human ack not yet requested.
```

The number `88.4` the architect wrote is the RawScore; the *system* reports **82.0
Partial** because the CDG says a decision can't outrun its forecast. That is the model
working.
