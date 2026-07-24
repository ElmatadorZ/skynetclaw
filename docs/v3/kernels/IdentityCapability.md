# Identity & Capability Kernel

> One kernel, two planes. **Identity** = who a principal is (authentication).
> **Capability** = what a principal may do right now (scoped, time-bound authorization).
> Closes the V2 gap: governance gated actions but never actors.
> Parent: [V3-Architecture](../V3-Architecture.md)

## 1. Why a kernel
A distributed, autonomous, multi-tenant organization is impossible without an actor
model. Every event, mission, tool call, and memory write must be **attributable** to a
principal, and every privileged action must be **least-privilege**. This is below the
engines because every engine action carries an identity and a capability.

## 2. Principals (Identity plane)
```jsonc
{ "id":"agent:analyst@tenantA", "kind":"user|agent|tenant|service",
  "tenant":"tenantA", "parent":"council:OX-..",   // delegation chain
  "attrs":{"tier":"advisor","authority":0.6},
  "pubkey":"...", "created_at":.. }
```
- **user** — a human operator. **agent** — a council member or worker. **tenant** — an
  organizational boundary (the unit of isolation/quota). **service** — an engine or
  kernel acting on its own behalf.
- Agents get identity by **delegation** from the principal that spawned them
  (`parent`), forming an auditable chain back to a human or a cron.

## 3. Capabilities (Capability plane)
A capability is a **scoped, time-bound, signed grant** — not an ambient permission:
```jsonc
{ "id":"cap:..", "principal":"agent:analyst@tenantA",
  "grants":[{"resource":"tool:get_news","action":"invoke"},
            {"resource":"runtime:execution","action":"complete","limit":{"tokens":50000}}],
  "constraints":{"mission":"OX-..","not_after":"...","once":false},
  "issued_by":"capability-kernel", "sig":"..." }
```
- Capabilities are **attenuating**: a parent can only delegate a subset of what it
  holds (no privilege escalation — a Constitutional article).
- Bound to a **mission** and a **deadline** by default → least-privilege, auto-expiring.
- Every action presents a capability; the gate verifies signature + scope + constraints.

## 4. Interface
```python
class IdentityKernel:
    def principal(self, pid: str) -> Principal
    def authenticate(self, credential) -> Principal
    def delegate(self, parent: Principal, attrs) -> Principal   # spawn an agent identity

class CapabilityKernel:
    def issue(self, principal, grants, constraints) -> Capability   # attenuating
    def verify(self, cap: Capability, action: Action) -> bool
    def attenuate(self, cap: Capability, subset) -> Capability
    def revoke(self, cap_id: str) -> None
```

## 5. Enforcement order (per action)
```
action → Constitution.check  →  Capability.verify  →  Governance.policy  →  execute
         (immutable bound)      (least-privilege)     (mutable risk/approval)
```
Identity is established once per principal; capability is checked on every action.

## 6. Events
`identity.created`, `identity.delegated`, `capability.issued`, `capability.verified`,
`capability.denied`, `capability.revoked`, `capability.expired`. All journaled, so the
full who-did-what-under-what-grant is replayable.

## 7. Single → distributed
Workstation: local principals, locally-signed capabilities, in-proc verification.
Organization: Identity backed by an external IdP; capabilities are signed tokens
verifiable offline on any node (no central call in the hot path); revocation via a
journaled revocation list. Interface unchanged.

## 8. Compatibility
V2 had implicit "the agent" with no identity. V3 assigns the existing 14-agent roster
real delegated identities and binds tool access to capabilities. When the
`identity_kernel` flag is off, a single default principal with a broad capability
preserves V2 behavior exactly.
