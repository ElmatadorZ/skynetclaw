# Journal Kernel (Event Log / Source of Truth)

> "The log is the system." A durable, append-only, causally-ordered event log is the
> single source of truth. Mission, Memory, Knowledge, Reflection are **projections** of
> it. Absorbs the "Semantic Clock" insight as a property, not a kernel.
> Parent: [V3-Architecture](../V3-Architecture.md) · Justification: [DecisionLog](../DecisionLog.md)

## 1. Why a kernel
The V2 EventBus is in-proc and dies on crash — losing history. An OS cannot lose
history. The Journal makes events **durable, ordered, replayable**, which simultaneously
delivers: crash recovery, audit (with the Constitution making it immutable),
time-travel debugging, and — critically — the *only* mechanism that turns
in-proc → distributed into a config change. Engines integrate by appending to and
projecting from the Journal, never by calling each other.

## 2. Event shape (the contract)
```jsonc
{ "id":"evt:ULID",                 // globally unique, lexically sortable
  "type":"mission.created",        // versioned via Contract Registry
  "schema_v":3,
  "stream":"mission:OX-..",        // the aggregate this belongs to
  "actor":"agent:analyst@tenantA", // Identity
  "cap":"cap:..",                  // Capability under which it was produced
  "lamport": 184293,               // logical clock (total-orderable)
  "vclock":{"nodeA":12,"nodeB":7}, // vector clock (causality across nodes)
  "causes":["evt:..."],            // explicit causal parents
  "ts":"...",                      // wall-clock (advisory only)
  "payload":{...},
  "prev_hash":"...","hash":"..." } // hash chain → tamper-evident (Constitution Art.1)
```

## 3. Guarantees
- **Append-only, immutable** (Constitution Article 2). Corrections are *new* events
  (`mission.corrected`), never edits.
- **Tamper-evident**: each event chains `prev_hash`; the audit log is a view of the
  Journal, so it inherits immutability.
- **Idempotent append**: `(stream, dedupe_key)` makes retries safe (exactly-once effect).
- **Ordered**: total order via Lamport within a node; causal order via vector clocks
  across nodes.

## 4. Projections (everything else is a read model)
```
Journal  ──project──▶  Mission state      (current mission graph, completion %)
         ──project──▶  Working/Long-term Memory
         ──project──▶  Knowledge / Epistemic Graph
         ──project──▶  Audit log (immutable view)
         ──project──▶  Semantic Timeline (see §5)
         ──project──▶  Observability metrics
```
A projection is a deterministic fold over events. Rebuild = replay. Lost a read store?
Replay the Journal. This is what makes engines **stateless** (state is external = the
Journal + its projections).

## 5. Causal & semantic ordering (the absorbed "Semantic Clock")
"Semantic Clock" is **not a separate kernel** — it is two things the Journal already
owns plus one projection:
1. **Causal order** — Lamport + vector clocks are stamped on every event (required for
   a correct distributed log anyway). This *is* the system clock.
2. **Semantic Timeline** — a **projection** that orders events by
   `dependency → decision → meaning` (using `causes` edges + mission graph + epistemic
   links) instead of wall-clock `ts`. It answers "in what *meaningful* order did this
   mission unfold", which is what the dashboard timeline shows.

Wall-clock `ts` is advisory only; reasoning and ordering use logical/causal time.

## 5b. Agreement, not just ordering (red-team amendment)
Causal/logical clocks give **partial order** and *detect* concurrency — they are **not
consensus** and do not *resolve* a conflict. A correct distributed append log therefore
also needs an **agreement protocol** (quorum replication / total-order broadcast, e.g.
Raft) plus a **membership/quorum** notion. Split-brain counterexample: two nodes append
to `mission:OX-1` concurrently → on heal, two truths, no winner; agreement picks one.
This lives **inside** the Journal kernel — consensus is *how you implement* a distributed
log, the same way causal ordering is (and the same reason the "Semantic Clock" was
rejected as a separate kernel). **No new kernel; the Journal's charter includes
agreement.** Single-node deployments run a trivial single-voter quorum (V2 behavior).
See [RedTeam Finding 1](../RedTeam-KernelStressTest.md#3-finding-1--journal-conflated-ordering-with-agreement-amended-not-a-new-kernel).

## 6. Interface
```python
class Journal:
    def append(self, event: Event) -> str            # idempotent on (stream,dedupe_key)
    def read(self, stream: str, *, since=None) -> Iterator[Event]
    def subscribe(self, types: list[str], handler)   # the "EventBus" is this
    def replay(self, projection: Projection) -> None # rebuild a read model
    def causal_after(self, evt_id: str) -> Iterator[Event]

class Projection(Protocol):                          # deterministic fold
    name: str
    def apply(self, event: Event, state) -> state
```

## 7. Single → distributed
Workstation: a SQLite-backed append log; `subscribe` is in-proc fan-out (the V2
EventBus API, preserved). Organization: the same interface over an external log/broker;
consumers run on other nodes; vector clocks already make cross-node causality correct.
**No caller changes** — the EventBus API and projections are identical.

## 8. Compatibility
`os_ipc.EventBus` becomes a thin in-proc subscriber over the Journal (same publish/
subscribe API), so existing emitters keep working. Existing SQLite stores
(`house_state`, KG, telemetry) become **projections** populated by Journal subscribers
via an outbox, retaining their current read APIs while the Journal becomes the truth.
