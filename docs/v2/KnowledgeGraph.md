# Knowledge Graph + Memory

> Replaces isolated, duplicated memory with one **graph of referenced objects**, and
> defines the Working / Long-term memory tiers that index into it.
> Parent: [Architecture](Architecture.md) · Built on `system_graph.py`, Obsidian tools,
> `lesson_synthesis.py`, `reinforcement.py`, per-module JSON/SQLite stores.

## 1. Problem
V1 memory is scattered: council memory, lesson files, Obsidian notes, mission ledger,
per-tool caches — each isolated, each re-storing the same facts. V2 unifies them into
a single **Knowledge Graph (KG)**: every fact lives once, as a node, and other nodes
**reference** it instead of copying it.

## 2. Node types (objects)
`Project · Repository · Skill · File · Tool · Agent · Person · Document · Task ·
Goal · Mission · Conversation · Decision · Lesson · Pattern · FailureCase · Source`.
Each node:
```jsonc
{ "id":"kg:doc:abc","type":"Document","label":"...","props":{...},
  "created_at":..,"updated_at":..,"version":3,"mission_refs":["OX-.."] }
```
## 3. Edge types (relations)
`references · depends_on · produced_by · belongs_to_mission · authored_by ·
derived_from · contradicts · supersedes · about · used_tool · learned_from`.
Edges are first-class (typed, directional, timestamped) so the graph is queryable,
not just a blob. `system_graph.py` already emits typed nodes/edges for
runtimes/agents/skills/tools — that becomes the *system* subgraph; V2 adds the
*knowledge* subgraph alongside it.

## 4. No duplicated memory
- A price, a source URL, a lesson, a person — stored **once** as a node.
- A mission "remembers" by holding **edges** to nodes, not copies.
- Writes go through a `dedupe(node)` step (content hash + semantic match) →
  returns an existing id or creates one. This kills the V1 duplication.

## 5. Memory tiers (both index into the KG)
### Working memory (RAM, auto-expiring)
```jsonc
{ "context_window":[...], "recent_decisions":[...], "temp_facts":[...],
  "open_questions":[...], "pending_tasks":[...], "current_assumptions":[...] }
```
Scoped per mission (`wm:OX-..`). Every item has a **TTL**; a sweeper expires items
(by age, by mission state change, or by token-budget pressure on the context window).
Nothing here is durable — promotion to long-term is explicit (see Reflection).

### Long-term memory (durable, versioned)
Stores: mission history, architecture decisions, lessons learned, patterns, failure
cases, successful strategies. Each is a **versioned KG node** (`version`,
`supersedes` edges) so memory has history, not overwrite-in-place. Built on
`lesson_synthesis.py` + `reinforcement.py`.

## 6. Retrieval (four indexes over one graph)
| Mode | Mechanism | Use |
|---|---|---|
| **semantic** | embeddings (`nomic-embed-text`) over node text | "what do we know about X" |
| **graph** | edge traversal from a seed node | "what depends on / contradicts this" |
| **timeline** | `created_at`/`version` ordering | "what did we decide, in order" |
| **mission** | `belongs_to_mission` edges | "everything this mission touched" |

```python
class KnowledgeGraph(Protocol):
    def upsert(self, node) -> str          # dedupe-aware
    def link(self, src, rel, dst) -> None
    def get(self, nid) -> Node
    def query_semantic(self, text, k=8) -> list[Node]
    def query_graph(self, seed, rels, depth=2) -> Subgraph
    def query_timeline(self, **f) -> list[Node]
    def query_mission(self, mid) -> Subgraph

class MemoryService:                       # facade injected everywhere
    def __init__(self, kg: KnowledgeGraph, working: WorkingMemory): ...
    def remember(self, fact, *, durable=False, mission=None): ...
    def recall(self, query, *, mode="semantic", mission=None): ...
    def promote(self, wm_item) -> str      # working → long-term (versioned)
    def forget(self, nid, *, reason): ...   # tombstone, never hard-delete
```

## 7. Events & observability
`memory.write`, `memory.promote`, `memory.forget`, `memory.recall` (with hit/miss).
The **memory hit-ratio** telemetry metric comes from `recall` hit/miss counts.

## 8. Storage & compatibility
- Backed by SQLite (`knowledge_graph.db`: `kg_nodes`, `kg_edges`, `kg_embeddings`)
  + the existing Obsidian vault as a *mirror* for human-browsable notes.
- V1 stores keep working; an importer ingests existing lessons/council memory/notes
  into KG nodes (one-time, idempotent via dedupe). Behind `knowledge_graph` flag.
- No external graph DB — start with SQLite; the `KnowledgeGraph` interface lets a
  Neo4j/pgvector backend slot in later with zero caller changes.
