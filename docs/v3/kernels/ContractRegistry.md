# Contract Registry Kernel

> If events are the integration contract, they must be **versioned**. The Contract
> Registry owns the schemas of every event and API so the system can evolve without
> breaking subscribers.
> Parent: [V3-Architecture](../V3-Architecture.md)

## 1. Why a kernel
V3 makes the [Journal](Journal.md) the integration backbone — engines couple to *event
shapes*, not to each other. The moment an event shape can change, you need a registry
that (a) validates events on append, (b) versions schemas, and (c) enforces
compatibility rules. Without it, one event change silently breaks every consumer — the
classic distributed-systems failure. No other kernel owns "the shape of messages".

## 2. What it registers
- **Event schemas** — every `type` + `schema_v` (e.g. `mission.created` v3).
- **API/command schemas** — request/response shapes for kernel and engine RPC.
- **Capability grant shapes** and **projection output shapes** (so dashboards/read
  models have a contract too).

## 3. Compatibility rules (enforced)
- **Backward compatible** changes only by default: add optional fields, never remove or
  retype required fields within a major version.
- **Breaking** changes require a **new major** (`schema_v+1`); both versions coexist
  during migration; an **upcaster** converts old events to the new shape on read.
- Producers declare the versions they emit; consumers declare the versions they accept;
  the registry rejects an append whose schema is unknown or incompatible.

## 4. Interface
```python
class ContractRegistry:
    def register(self, schema: Schema) -> None            # versioned, immutable once published
    def validate(self, event_or_msg) -> Result            # called by Journal.append
    def upcast(self, event: Event, to_v: int) -> Event    # old → new on read
    def compatible(self, producer_v, consumer_v) -> bool
    def schema(self, type: str, v: int) -> Schema
```

## 5. Events
`contract.registered`, `contract.deprecated`, `contract.validation_failed`,
`contract.upcast`. Journaled — schema evolution is itself auditable.

## 6. Single → distributed
Workstation: schemas in `config/contracts/` loaded in-proc; validation on append.
Organization: a shared registry service every node consults (cached locally), so all
nodes agree on message shapes; upcasters let a rolling deployment run mixed versions.
Interface unchanged.

## 7. Compatibility
V2 had no event versioning. V3 seeds the registry with the current event types
(`mission.*`, `council.*`, `agent.*`, `governance.*`, `memory.*`) at v1. With the
`contract_registry` flag off, validation is a no-op and events flow as in V2 — but the
Freeze recommends turning it on early, since contracts are cheap before there are many
consumers and expensive after.
