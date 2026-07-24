# Epistemic Kernel (Truth / Belief)

> Knowledge is not facts in a graph — it is **justified belief**. Every knowledge object
> carries confidence, evidence, source, contradiction, freshness, and consensus. The
> Knowledge Graph is the *data plane*; this kernel is the *trust plane* over it. Councils
> vote on **truth**, not prompts.
> Parent: [V3-Architecture](../V3-Architecture.md) · Justification: [DecisionLog](../DecisionLog.md)
> · Data plane: [KnowledgeGraph (V2)](../../v2/KnowledgeGraph.md)

## 1. Why a kernel (and not part of the KG)
The Knowledge Graph stores nodes/edges (a storage responsibility). **Truth maintenance**
— assigning confidence, tracking evidence, detecting contradictions, decaying freshness,
computing consensus, and revising belief when new evidence arrives — is *behavior over*
that data. Putting it in the store couples retrieval to reasoning and violates the
store's single responsibility. Hence a separate kernel layered over the KG.

## 2. Epistemic envelope (wraps every knowledge object)
```jsonc
{ "node":"kg:claim:gold-up-2pct",
  "confidence":0.72,                    // [0..1], calibrated
  "evidence":[{"event":"evt:..","weight":0.6,"source":"src:reuters"}],
  "sources":["src:reuters","src:bloomberg"],
  "contradictions":["kg:claim:gold-flat"],   // open conflicts
  "freshness":{"observed_at":"...","half_life":"6h","decayed_conf":0.41},
  "consensus":{"agree":["analyst","scout"],"dissent":["skeptic"],"score":0.66},
  "status":"believed|disputed|stale|retracted" }
```
Confidence reuses the existing `calibration.py`; sources/evidence reference Journal
events (so belief is traceable to what produced it).

## 3. Operations (truth maintenance)
- **Assert** a claim with evidence → compute initial confidence.
- **Corroborate / refute** → update confidence as evidence accrues (Bayesian-style).
- **Detect contradiction** → mark conflicting claims `disputed`; surface to the Council.
- **Decay** → freshness half-life lowers confidence over time; `stale` claims are
  flagged for re-verification.
- **Consensus** → aggregate agent agreement/dissent (weighted by Identity authority).
- **Revise / retract** → belief change is a *new event* (never an overwrite — Journal).

## 4. How the Council uses it
Council members opine and vote **referencing epistemic claims**, not raw prompt text.
A vote carries the confidence of its supporting claims; the Skeptic's veto fires on
`disputed`/`stale` evidence (this is the V2 `shadow_gate` anti-hallucination role, now
grounded in an explicit truth model). Decisions record *which beliefs* justified them.

## 5. Interface
```python
class EpistemicKernel:
    def assert_(self, claim, evidence, source, by: Principal) -> ClaimRef
    def corroborate(self, claim, evidence) -> Belief
    def refute(self, claim, evidence) -> Belief
    def contradictions(self, claim) -> list[ClaimRef]
    def confidence(self, claim) -> float            # freshness-decayed, calibrated
    def consensus(self, claim) -> Consensus
    def believe(self, claim) -> Belief              # full envelope
    def retract(self, claim, *, reason, by) -> None # new event, not delete
```

## 6. Events
`claim.asserted`, `claim.corroborated`, `claim.refuted`, `claim.contradicted`,
`claim.stale`, `claim.consensus`, `claim.retracted`. Journaled → the epistemic graph is
a projection; belief history is replayable.

## 7. Single → distributed
Workstation: confidence/consensus computed in-proc over the local KG. Organization:
claims and evidence are journaled events; consensus aggregates beliefs from agents
across nodes/tenants; the envelope and interface are identical. Vector index for
semantic retrieval is a swappable backend behind the KG data plane.

## 8. Compatibility
Wraps the V2 Knowledge Graph + `calibration.py`. Existing KG nodes get a default
envelope (`confidence` unknown, `status: believed`) on import — additive. With the
`epistemic_kernel` flag off, knowledge behaves as flat V2 facts. Turning it on is what
lets "Council votes on truth" become literally true.
