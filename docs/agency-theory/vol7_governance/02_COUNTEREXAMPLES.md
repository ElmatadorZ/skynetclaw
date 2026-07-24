# Agency — Volume VII · 02 — Counterexamples & Boundary Cases

> Pure philosophy. Ten cases, each ruled **Governance** or **Not-Governance** with the
> discriminating reason, tested against `governance = policy + separation + complete mediation
> + enforcement` (+ requisite variety for completeness, + legitimacy for stability). Several
> are drawn from this system, so the theory is testable against what was built.

---

## The ten verdicts

| Case | Verdict | Discriminating reason |
|---|---|---|
| **A law with no enforcement** | **Not-Governance** | policy + separation, no teeth (GA4) — advice |
| **A thermostat's setpoint** | **Not-Governance** | the "bound" is the agent's own goal, no separation (GA2) |
| **A New Year's resolution** | **Not-Governance** | self-restraint, overridable at will (GA2) |
| **A reference monitor** | **Governance** (paradigm) | policy + complete mediation + enforcement, separated |
| **A constitution (enforced)** | **Governance** | primary + secondary rules, mediated, legitimate |
| **Regulatory capture** | **Governance** (captured) | real governance whose governor was taken by the governed |
| **A dictator / unchecked power** | **Governance** (illegitimate) | bounds action, but coercive not legitimate (GA6) |
| **Ostrom commons rules** | **Governance** (collective) | crafted, monitored, graduated sanctions over a shared footprint |
| **RLHF guardrails / a prompt "please don't"** | **Not-Governance** (soft) | advisory, incompletely mediated, overridable — not a bound |
| **The GPS-2 gate (this system)** | **Governance** (partial) | mediates + enforces, but weak-governor variety gap (GA5) |

## Dissected — the cases that carry weight

### RLHF guardrails / prompt instructions — *soft alignment is not governance*
"Please don't do X" in a system prompt, or a model trained to refuse, *influences* behaviour
but does not **govern** it: it is not completely mediated (the model can be argued/injected
out of it), not separated (it lives *inside* the governed, overridable), and not enforced (no
mechanism prevents the act if the model complies with a jailbreak). By GA2–GA4 it is **soft
alignment, not governance** — a disposition, not a bound. This is the sharpest and most
consequential boundary for AI systems: **most "AI safety" that lives in weights or prompts is
influence, not governance**, and the audit proved why — the model's page-content prompt
injection + the http_request bypass both routed *around* the soft layer. Governance must be a
*separated, mediating, enforcing* wrap (the GPS-2 gate), not a request. SUPPORTED, and it is
the theory's operative warning.

### The thermostat's setpoint & the resolution — *self-restraint ≠ governance*
A thermostat is bounded by its setpoint, and a person by a resolution — but in both the bound
*is* the agent's own goal/will, liftable by the same agent (turn the dial; break the
resolution). No separation (GA2). Frankfurt's second-order volition (a desire about one's
desires) is the *internal limiting case* — real self-governance — but even it can be overridden
by the self it governs, so it is the *floor* of governance, not its paradigm. **Governance
proper requires the bound to be structurally beyond the governed's at-will reach.** This is
why a governed agent cannot be its own sufficient governor (the AI-self-oversight problem in
ontological form). SUPPORTED.

### A law with no enforcement — *teeth are constitutive*
A statute nobody enforces is, functionally, advice — it names a prohibition it cannot prevent
(GA4 fails). This shows enforcement is not an add-on to governance but part of what makes a
prohibition a *bound* rather than a *wish*. The Override/Veto (human gate) is the sharpest
teeth: it *halts* the action, not merely records disapproval. SUPPORTED.

### Regulatory capture & the dictator — *governance can be real yet defective*
Capture (the governor taken over by the governed) and tyranny (bounds without legitimacy) are
both **real governance with a broken node** — capture breaks separation (GA2) in practice
while preserving its form; tyranny breaks legitimacy (GA6) while preserving mediation +
enforcement. Counting them as *defective governance* (not non-governance) lets the theory
*explain* them structurally (Vol VII·03), exactly as superstition was broken-learning and the
confused deputy was broken-delegation. Governance is a **degreed** concept with quality nodes
— the recurring result across all volumes. SUPPORTED.

### The GPS-2 gate — *this system's governance, graded honestly*
SkynetClaw's gate has a policy (allow/escalate/deny), separation (it lives outside the model,
the model cannot rewrite it), complete-ish mediation (now fail-closed + SSRF-cut, after the
audit), and enforcement (it blocks + human-gates). By GA1–GA4 it **is** governance. But it
fails **GA5 (requisite variety)**: a weak model faces a rich tool-surface, and the governor
(a static allow-list + a human on escalate) has *less* variety than the governed's action
space — so its completeness is only as good as its enumeration (the P0 was an *un-enumerated*
path). **The system has governance's structure and lacks governance's variety** — the exact
frontier Vol VII·04 leaves open (scalable oversight). SUPPORTED, and self-diagnostic.

## What the counterexamples establish
1. **Soft alignment (RLHF/prompts) is not governance** — not separated, not mediated, not
   enforced; the most important boundary for AI, and the one the audit's bypasses crossed.
   SUPPORTED.
2. **Self-restraint is not governance** — the bound must be beyond the governed's at-will
   reach; an agent cannot fully govern itself. SUPPORTED.
3. **Governance is degreed** — capture, tyranny, and the partial GPS-2 gate are *defective*
   governance, not non-governance; the theory explains them by broken nodes. SUPPORTED.
4. **The system's own gate is governance minus variety** — structure present, GA5 absent —
   naming exactly what to build next. SUPPORTED.

## Falsifiers
Any verdict is refuted by showing the case has/lacks the discriminator claimed — e.g. exhibit
an RLHF guardrail that is completely mediated + separated + enforced (would make it governance
and refute the soft-alignment boundary), or a self-imposed bound that the self provably cannot
override (would make self-governance complete and refute GA2).
