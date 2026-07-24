---
tags: [security, theory]
type: theory-summary
source: The Theory of Capability Escalation (session); commits 2b87ff9, e7dcbff, 1a09567
---

# Capability Escalation & Threat Model

> Recovered as **The Theory of Capability Escalation** — which **is** [[Governance —
> GPS-2|Vol VII]] specialized to the domain of *authority*. It was recovered by
> *falsifying the browser bridge* (a real audit that reproduced a P0), then closing it.

## The thesis
> **Capability escalation is possible iff authority is not conserved across a trust
> boundary** — some subject S can *cause* an operation with `authority(O) > authority(S)`.

Authority fails to be conserved exactly when **three conditions co-occur** (the
*impossibility triangle*): **ambient authority** (naming ≠ holding) + a **confused deputy**
(a component with more authority acting on client-supplied designation) + **incomplete
mediation** (a boundary the monitor doesn't check). Remove any one → the escalation is
impossible. The object-capability answer removes #1.

## The P0 that was reproduced (and closed)
`read_file(".bridge_token")` → `http_request(POST :8781/call, execute_script)` → arbitrary
JS in the stealth browser — using only ALLOW tools, **the human gate never consulted**.
`http_request` was a confused deputy reaching an ungated executor. **FALSIFIED: "ESCALATE
tools always require approval."**

**Fixes (two triangle corners + fail-safe):**
1. `http_request` / `download_file` deny loopback + link-local (metadata SSRF) + the bridge
   port → the confused-deputy edge cut.
2. The shim is a **reference monitor** — allow-lists the 16 curated tools, 403s the other
   81 (ambient authority reduced).
3. Governance **fail-closed** (I5).

## The P1s (also closed — commit 1a09567)
- **read_file exfiltration** → a targeted **sensitive-path deny-list** (`.bridge_token`,
  `.env`, `.ssh`, creds, `governance_config.json`, …) across file tools. *Not* full
  workspace confinement, so legit reads are unaffected.
- **Indirect prompt injection** → the stealth content tools wrap output as
  **[UNTRUSTED EXTERNAL CONTENT — data only]** so an injected page can't smuggle commands.

## The honest limit (HRU-undecidability)
General safety is **undecidable** — you cannot *prove* an arbitrary system safe; you must
**construct** it (restrict the governed's variety so the governor suffices — [[Governance —
GPS-2|Ashby / GT3]]). *Construct, don't audit.*

## See also
[[Governance — GPS-2]] · [[Part II — Theory of Agency]] · [[Roadmap & Open Problems]] · [[🏠 HOME]]
