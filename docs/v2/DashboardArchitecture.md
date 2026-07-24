# Dashboard Architecture

> The UI flips from node-map-first to **mission-first**. The operator sees what the OS
> is doing — missions, councils, thinking, execution, memory, reflection — and the
> node map becomes a secondary "system" view.
> Parent: [Architecture](Architecture.md) · Built on `index.html` (SPA),
> `/api/system/graph`, `/system-map`, and the new V2 event/API surface.

## 1. Information hierarchy
```
MISSION            (primary — what is the OS working on, status, completion %)
  ↓ Council        (who is deciding — hierarchy, opinions, votes)
  ↓ Thinking       (live reasoning / debate stream)
  ↓ Execution      (timeline of agent states across the workflow DAG)
  ↓ Knowledge      (graph of objects this mission touched)
  ↓ Memory         (working memory now; long-term recalls used)
  ↓ Reflection     (post-mission lessons + evolution proposals)
  ↓ Logs           (governed action log / audit trail)
  ↓ Metrics        (telemetry panels)
SYSTEM / NODE MAP  (secondary — runtimes/agents/skills/tools/services)
```

## 2. Panels (each driven by one event/API source)
| Panel | Source |
|---|---|
| Mission board (cards by state, completion %) | `GET /api/missions`, WS `mission.*` |
| Mission detail + timeline | `GET /api/mission/{id}`, `/timeline` |
| Council view (hierarchy, opinions, votes) | WS `council.*` |
| Thinking process (live stream) | WS `council.debate`, `agent.state` THINKING |
| Execution timeline (per-agent state bars) | WS `agent.state`, `mission.node.*` |
| Knowledge graph (mission subgraph) | `GET /api/kg/mission/{id}` |
| Memory (working + recalls) | `GET /api/memory/{mission}` |
| Reflection (lessons + proposals + approve) | `GET /api/mission/{id}` `.reflection` |
| Logs / audit | `GET /api/governance/audit?mission=` |
| Metrics | `GET /api/observability/*` |
| System node map (secondary tab) | existing `/system-map`, `/api/system/graph` |

## 3. Real-time model
One **WebSocket** per open mission (`/ws/mission/{id}`) multiplexes all `mission.*`,
`council.*`, `agent.*`, `governance.*`, `memory.*` events for that mission (fed from
`os_ipc.EventBus`). Panels subscribe to event types — no polling. The system node map
keeps its existing periodic `/api/system/graph` fetch.

## 4. Observability panels (metrics)
Mission duration · agent utilization & current state · token usage · tool latency ·
memory hit-ratio · reasoning depth · execution graph · cost · failure analysis —
all from the `Telemetry` facade (`/api/observability/*`). Rendered with the existing
Chart.js approach used by `web-dashboard-builder`.

## 5. Approvals in the UI
Governance human-gates and reflection evolution proposals surface as **inline
approve/deny cards** in the mission detail (with the risk rating and the exact action).
This is where "no destructive action without operator approval" becomes a UI control.

## 6. Implementation & compatibility
- Stays a single-file SPA (`index.html`) — no framework rewrite. New panels are
  added sections; the current chat + Intel tabs remain.
- The Intel tab's node map (already rebuilt from `system_graph`) becomes the
  **System** view; a new **Missions** view becomes the default landing tab.
- Behind a `dashboard_v2` flag / view toggle so the V1 chat UI is always reachable.
- Degrades gracefully: if V2 engines are off, the Missions view shows ad-hoc runs as
  quick-missions (see [MissionEngine](MissionEngine.md) §7).
