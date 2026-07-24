"""
system_graph.py — OX-SYSTEM-MAP-1
=================================
Synthesize THE HOUSE's REAL system composition into a node graph for the Node
Map (Intel) view: runtimes, agents (council roster), skills, tool categories,
and OS services — plus the edges between them. Everything is pulled live from
the actual system (connections DB, BUILTIN_TOOLS/TOOL_CAT, skills index, kernel,
OS services) — no mock data.

Dependency-free (stdlib only). Lazy imports avoid circular deps with main.
License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import os
import sqlite3
import time
from typing import Any, Dict, List

_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "skynerclaw.db")

# The council roster (real agents shown in the Continental Division), with role.
AGENT_ROSTER = [
    ("elite_commander", "Elite Commander", "supreme · verify · override", "⚡"),
    ("atlas", "Atlas", "global intelligence · mastermind", "🌐"),
    ("concierge", "The Concierge", "router · mission intake", "🛎"),
    ("executor", "The Executor", "tools · build · execute", "🛠"),
    ("analyst", "The Analyst", "evidence · analysis · facts", "📈"),
    ("strategist", "The Strategist", "long game · planning", "♟"),
    ("skeptic", "The Skeptic", "shadow gate · veto · critique", "🛡"),
    ("forecaster", "The Forecaster", "scenarios · weather · risk", "⏳"),
    ("governor", "The Governor", "presiding · arbitration", "🏛"),
    ("sentinel", "The Sentinel", "guarding · security", "🔒"),
    ("architect", "The Architect", "drafting · design", "📐"),
    ("auditor", "The Auditor", "weighing · quality", "⚖"),
    ("scout", "The Scout", "discovery · research", "🔍"),
    ("storyteller", "The Storyteller", "composing · synthesis", "✍"),
]

CAT_ICON = {"filesystem": "📁", "network": "🌐", "realtime": "⏱", "system": "💻",
            "code": "🐍", "obsidian": "📓", "social": "📱", "memory": "🧠",
            "web": "🌐", "media": "🎬", "math": "🧮", "vision": "🖼", "default": "🔧"}


def _connections() -> List[Dict[str, Any]]:
    try:
        c = sqlite3.connect(_DB); c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute(
            "SELECT id,name,base_url,api_type,is_active FROM connections")]
        c.close()
        return rows
    except Exception:
        return []


def _online(url: str, api_type: str = "") -> bool:
    import urllib.request
    # one quick probe on the path that matches the runtime type
    path = "/api/tags" if api_type == "ollama" else "/v1/models"
    try:
        with urllib.request.urlopen(url.rstrip("/") + path, timeout=1.2) as r:
            return r.status == 200
    except Exception:
        return False


def build_graph() -> Dict[str, Any]:
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    def add(nid, label, typ, group, **meta):
        nodes.append({"id": nid, "label": label, "type": typ, "group": group, **meta})

    # ── RUNTIMES (live connections + GPU server) ──────────────────────────────
    exec_conn_id = None
    for cn in _connections():
        nid = f"rt:{cn['id']}"
        online = _online(cn["base_url"], cn.get("api_type", "")) if cn.get("base_url") else False
        active = bool(cn.get("is_active"))
        if active:
            exec_conn_id = nid
        add(nid, cn.get("name") or cn["id"], "runtime", "Runtimes",
            icon="🦙" if cn.get("api_type") == "ollama" else "⚙",
            sub=cn.get("base_url", ""), online=online, active=active,
            api_type=cn.get("api_type"))
    # exec model name (settings.exec_model) → a model node under the active runtime
    try:
        import json
        s = json.loads(open(os.path.join(os.path.dirname(_DB), "settings.json"),
                            encoding="utf-8").read())
        em = (s.get("exec_model") or "").strip()
        if em:
            add("model:exec", em, "model", "Runtimes", icon="🤖",
                sub="execution model", online=True, active=True)
            if exec_conn_id:
                edges.append({"from": exec_conn_id, "to": "model:exec", "kind": "serves"})
    except Exception:
        pass

    # ── AGENTS (council roster) ───────────────────────────────────────────────
    for aid, name, role, ic in AGENT_ROSTER:
        add(f"ag:{aid}", name, "agent", "Agents", icon=ic, sub=role, online=True)
        # every agent ultimately executes via the active runtime
        if exec_conn_id:
            edges.append({"from": f"ag:{aid}", "to": exec_conn_id, "kind": "executes-on"})

    # ── SKILLS (auto-router index) ────────────────────────────────────────────
    try:
        import skills_auto_router as _sr
        for sk in _sr.load_index().get("skills", []):
            sid = f"sk:{sk['name']}"
            add(sid, sk["name"], "skill", "Skills", icon="✨",
                sub=(sk.get("role") or (sk.get("description") or "")[:48]),
                triggers=sk.get("trigger_phrases", [])[:8])
    except Exception:
        pass

    # ── TOOLS (grouped by category) ───────────────────────────────────────────
    try:
        import main as _m
        cat_tools: Dict[str, List[str]] = {}
        names = []
        for t in getattr(_m, "BUILTIN_TOOLS", []):
            nm = t.get("function", {}).get("name")
            if not nm:
                continue
            names.append(nm)
            try:
                cat = _m.get_tool_cat(nm)
            except Exception:
                cat = "other"
            cat_tools.setdefault(cat or "other", []).append(nm)
        for cat, tools in sorted(cat_tools.items()):
            cid = f"cat:{cat}"
            add(cid, cat.title(), "toolcat", "Tools",
                icon=CAT_ICON.get(cat, CAT_ICON["default"]),
                sub=f"{len(tools)} tools", tools=sorted(tools))
            # the executor agent wields tools; the active runtime executes them
            edges.append({"from": "ag:executor", "to": cid, "kind": "uses"})
        # connect a few skills to obvious tool categories (capability links)
        _skill_links = {"web-dashboard-builder": ["network", "filesystem"],
                        "obsidian-knowledge-protocol": ["obsidian"],
                        "agent-find-skill": ["network"]}
        for sname, cats in _skill_links.items():
            for cat in cats:
                if f"cat:{cat}" in {n["id"] for n in nodes}:
                    edges.append({"from": f"sk:{sname}", "to": f"cat:{cat}", "kind": "needs"})
    except Exception:
        pass

    # ── OS SERVICES (if the OS layer is booted) ───────────────────────────────
    try:
        import genesis_os as _os
        o = _os.get_os()
        # list services WITHOUT calling health() (on_health can trigger kernel
        # discovery → slow). Use the registered name + cached state only.
        for name in o.services.names():
            svc = o.services.get(name)
            state = getattr(svc, "state", "stopped")
            add(f"svc:{name}", name.title(), "service", "Services", icon="🧩",
                sub=state, online=(state == "running"))
    except Exception:
        pass

    groups = {}
    for n in nodes:
        groups.setdefault(n["group"], 0)
        groups[n["group"]] += 1
    return {"ts": time.time(), "nodes": nodes, "edges": edges,
            "stats": {"nodes": len(nodes), "edges": len(edges),
                      "online": sum(1 for n in nodes if n.get("online")),
                      "groups": groups}}


# ── OX-ARCH-MAP-1 — layered OS / Cognitive-Kernel architecture ────────────────
# A systematic, plane-by-plane view of the whole stack (Interface → OS Core →
# Cognitive Kernel → Subsystems → Runtime Kernel → Runtimes) with the live status
# of every component and the relationships (calls ↓, events ↑) between planes.
# Grounded in real state — genesis_os, runtime_kernel, cognitive_validation,
# live connection probes — never mock. Cognitive-Kernel services are tagged
# live/planned by probing whether their backing module actually exists yet, so the
# view doubles as a migration dashboard for COGNITIVE_KERNEL_SPEC.

def _mod_exists(mod: str) -> bool:
    """Cheap existence check — does a backing module exist, without importing it."""
    try:
        import importlib.util
        return importlib.util.find_spec(mod) is not None
    except Exception:
        return False


# Cognitive Kernel services (COGNITIVE_KERNEL_SPEC §3). Each maps to the KERNEL
# module that now owns it (ADR-0003 migration), falling back to the legacy module
# it used to live in. Status:
#   migrated — a kernel_* module that ships conforms_to() (amendment A6: a subsystem
#              counts as migrated ONLY when its conformance gate is green)
#   live     — real code exists, but still scattered in the legacy module
#   planned  — spec only
_KERNEL_SERVICES = [
    ("event",      "Event",      "📡", "envelope · 2-tier audit spine · authority",   "kernel_events",    ["house_sync"]),
    ("context",    "Context",    "⚖", "owns the 16k budget · never-overflow",        "kernel_context",   ["main"]),
    ("memory",     "Memory",     "🧠", "recall/persist over the vault",               "kernel_memory",    ["house_sync"]),
    ("policy",     "Policy",     "📜", "governance on hook points (Constitution)",    "kernel_policy",    ["guidance_check", "warrant_check"]),
    ("execution",  "Execution",  "🛠", "guards the act · fail-closed · idempotent",   "kernel_execution", ["main"]),
    ("validation", "Validation", "🛡", "CVL cognitive quality gate",                  "",                 ["cognitive_validation"]),
    ("scheduling", "Scheduling", "🧭", "route CHAT / mission / council · lifecycle",  "",                 ["continental_relay", "discovery"]),
    ("governance", "Governance", "🏛", "deliberation council · ADR gate · escalation","",                 ["agent_council", "governance"]),
    ("telemetry",  "Telemetry",  "📊", "Explain records · Outcome Clock · eval",      "",                 ["observability"]),
]

# Cognitive subsystems (SPEC §7) → the module implementing them. `conforms` = ships
# a conforms_to() gate, i.e. actually implements the kernel ABI.
_SUBSYSTEMS = [
    ("sub:memory",     "Memory",     "🧠", "recall/persist over the vault",            "kernel_memory"),
    ("sub:planning",   "Planning",   "🗺", "decompose goal → steps (_pcall, legacy)",  "main"),
    ("sub:validation", "Validation", "🛡", "CVL — the reference subsystem",             "cognitive_validation"),
    ("sub:execution",  "Execution",  "🛠", "guards the act (PRE_ACT) · fail-closed",   "kernel_execution"),
    ("sub:governance", "Governance", "🏛", "council deliberation + policy authoring",  "agent_council"),
]

# The kernel's fixed enforcement surface (SPEC §5) — rendered with the policies
# actually registered on each hook, read LIVE from the policy engine.
_HOOKS = [
    ("PRE_PLAN",     "before planning a goal"),
    ("PRE_ACT",      "before a side-effecting tool"),
    ("PRE_VALIDATE", "before the quality gate"),
    ("PRE_COMMIT",   "before accepting an answer"),
    ("PRE_RESPONSE", "before surfacing to the human"),
]


def _conforms(mod: str) -> bool:
    """Does the module ship a conforms_to() gate? (A6 definition of 'migrated'.)
    Structural check only — we never CALL conforms_to() from a request: some
    conformance tests monkeypatch the live policy engine."""
    if not mod or not _mod_exists(mod):
        return False
    try:
        import importlib
        return callable(getattr(importlib.import_module(mod), "conforms_to", None))
    except Exception:
        return False

# The cognitive lifecycle (SPEC §2) — the process pipeline shown as a ribbon.
_LIFECYCLE = ["Perceive", "Contextualize", "Deliberate", "Plan",
              "Execute", "Validate", "Commit", "Reflect"]


def build_architecture() -> Dict[str, Any]:
    planes: List[Dict[str, Any]] = []

    def plane(pid, name, sub, kind, nodes):
        planes.append({"id": pid, "name": name, "sub": sub, "kind": kind, "nodes": nodes})

    # ── OS state (services / apps / ipc / permissions) — live if booted ────────
    os_state = "halted"; os_services = {}; os_apps = []; ipc_topics = 0; audited = 0; denials = 0
    try:
        import genesis_os as _g
        o = _g.get_os()
        os_state = o.state
        for nm in o.services.names():
            svc = o.services.get(nm)
            os_services[nm] = getattr(svc, "state", "stopped")
        os_apps = list(getattr(o.apps, "apps", {}).keys())
        try:
            ipc_topics = len(o.ipc.topics()); subs = len(o.ipc.subscriptions())
        except Exception:
            subs = 0
        try:
            audited = len(o.audit.entries(limit=10_000)); denials = len(o.audit.denials(limit=10_000))
        except Exception:
            pass
    except Exception:
        subs = 0

    def _svc_status(nm):
        st = os_services.get(nm)
        return "online" if st == "running" else ("idle" if st else "planned")

    # Plane 1 — Interface / Apps
    app_nodes = [{"id": f"app:{a}", "label": a.title(), "sub": "app", "icon": "🪟",
                  "status": "online" if os_state == "running" else "idle"} for a in os_apps]
    if not app_nodes:
        app_nodes = [{"id": "app:ui", "label": "Continental UI", "sub": "chat · council · intel",
                      "icon": "🪟", "status": "online"}]
    plane("interface", "Interface · Apps", "user-facing surfaces", "live", app_nodes)

    # Plane 2 — OS Core (genesis_os: services + IPC + permissions + workspace + packages)
    os_nodes = [
        {"id": "os:ipc", "label": "IPC Event Bus", "sub": f"{ipc_topics} topics · {subs} subs",
         "icon": "📡", "status": "online" if os_state == "running" else "idle"},
        {"id": "os:perm", "label": "Permissions · Audit", "sub": f"{audited} audited · {denials} denials",
         "icon": "🔐", "status": "online" if os_state == "running" else "idle"},
        {"id": "os:workspace", "label": "Workspace", "sub": "sandboxed FS", "icon": "🗂",
         "status": "online" if os_state == "running" else "idle"},
        {"id": "os:packages", "label": "Package Mgr", "sub": "skills/apps install", "icon": "📦",
         "status": "online" if os_state == "running" else "idle"},
    ]
    for nm in ("runtime", "workflow", "memory", "monitoring", "scheduler"):
        os_nodes.append({"id": f"os:svc:{nm}", "label": f"{nm.title()} Service", "sub": "service",
                         "icon": "🧩", "status": _svc_status(nm)})
    plane("os_core", "OS Core · Genesis OS", "IPC · permissions · service manager", "live", os_nodes)

    # Plane 3 — Cognitive Kernel (SPEC v0.2 / ADR-0003) — the MIGRATION dashboard.
    # "migrated" = a kernel_* module that ships conforms_to() (A6).
    ck_migrated = 0
    ck_nodes = []
    for sid, label, icon, sub, kmod, legacy in _KERNEL_SERVICES:
        migrated = _conforms(kmod)
        if migrated:
            ck_migrated += 1
            status, backing = "migrated", kmod
        elif any(_mod_exists(m) for m in legacy):
            status, backing = "live", ", ".join(legacy) + " (legacy — not yet migrated)"
        else:
            status, backing = "planned", ", ".join(legacy)
        ck_nodes.append({"id": f"ck:{sid}", "label": label, "sub": sub, "icon": icon,
                         "status": status, "backing": backing})
    plane("cognitive_kernel",
          f"Cognitive Kernel · Spec v0.2  ({ck_migrated}/{len(_KERNEL_SERVICES)} migrated)",
          "lifecycle · services · hooks — the cognitive quality gate", "kernel", ck_nodes)

    # Plane 4 — Policy hook surface (SPEC §5) — the policies actually registered,
    # read LIVE from the engine. This is where the kernel CONTROLS (step 5).
    hook_nodes = []
    n_pol = 0
    try:
        import kernel_policy as _kp
        for hk, desc in _HOOKS:
            pols = [getattr(p, "id", "?") for p in _kp.policies_for(hk)]
            n_pol += len(pols)
            hook_nodes.append({"id": f"hook:{hk}", "label": hk, "icon": "🪝",
                               "sub": (" · ".join(pols) if pols else desc),
                               "status": "online" if pols else "idle",
                               "backing": f"{len(pols)} policy(ies) — {desc}"})
    except Exception:
        hook_nodes = [{"id": "hook:none", "label": "policy engine", "sub": "not loaded",
                       "icon": "🪝", "status": "idle"}]
    plane("hooks", f"Policy Hook Surface  ({n_pol} policies armed)",
          "most-restrictive wins · fail-closed · every decision audited", "kernel", hook_nodes)

    # Plane 5 — Cognitive Subsystems (drivers on the kernel ABI)
    sub_nodes = []
    for sid, label, icon, sub, mod in _SUBSYSTEMS:
        live = _mod_exists(mod)
        conforms = _conforms(mod) or sid == "sub:validation"   # CVL is the reference subsystem
        sub_nodes.append({"id": sid, "label": label, "sub": sub, "icon": icon,
                          "status": "online" if live else "planned",
                          "conforms": conforms, "backing": mod})
    _n_conf = sum(1 for n in sub_nodes if n["conforms"])
    plane("subsystems", f"Cognitive Subsystems  ({_n_conf}/{len(sub_nodes)} conform to the ABI)",
          "memory · planning · validation · execution · governance", "live", sub_nodes)

    # Plane 5 — Runtime Kernel (runtime_kernel: drivers + model pools)
    rk_nodes = []
    try:
        import runtime_kernel as _rk
        k = _rk.get_kernel(rediscover=False)
        snap = k.snapshot()
        for d in snap.get("drivers", []):
            rk_nodes.append({"id": f"rk:drv:{d.get('name', '?')}", "label": d.get("name", "driver"),
                             "sub": "driver", "icon": "🔌", "status": "online"})
        pools = snap.get("pools", {})
        if pools:
            rk_nodes.append({"id": "rk:pools", "label": "Model Pools",
                             "sub": " · ".join(f"{k2}:{v}" for k2, v in pools.items()) or "—",
                             "icon": "🎱", "status": "online"})
        # Vision honesty: how many of the Vision pool are PROBE-verified (not just
        # declared). Trust-but-verify — see vision_probe.
        try:
            import vision_probe as _vp
            _c = _vp.cache()
            _vis_total = pools.get("Vision", 0)
            _vis_ok = sum(1 for v in _c.values() if v is True)
            _vis_bad = sum(1 for v in _c.values() if v is False)
            if _vis_total:
                rk_nodes.append({"id": "rk:vision_verified", "label": "Vision verified",
                                 "sub": f"{_vis_ok}/{_vis_total} probe-confirmed"
                                        + (f" · {_vis_bad} rejected" if _vis_bad else ""),
                                 "icon": "🔎", "status": "online" if _vis_ok else "idle"})
        except Exception:
            pass
        rk_nodes.append({"id": "rk:sessions", "label": "Sessions",
                         "sub": f"{snap.get('sessions', 0)} active", "icon": "🧵", "status": "online"})
    except Exception:
        rk_nodes.append({"id": "rk:kernel", "label": "Runtime Kernel", "sub": "not booted",
                         "icon": "⚙", "status": "idle"})
    plane("runtime_kernel", "Runtime Kernel", "drivers · model pools · sessions", "live", rk_nodes)

    # Plane 6 — Runtimes / Hardware (live connection probes)
    rt_nodes = []
    for cn in _connections():
        online = _online(cn["base_url"], cn.get("api_type", "")) if cn.get("base_url") else False
        rt_nodes.append({"id": f"rt:{cn['id']}", "label": cn.get("name") or cn["id"],
                         "sub": cn.get("base_url", ""), "icon": "🦙" if cn.get("api_type") == "ollama" else "⚙",
                         "status": "online" if online else "offline"})
    if not rt_nodes:
        rt_nodes = [{"id": "rt:none", "label": "No runtimes", "sub": "add a connection",
                     "icon": "⚙", "status": "offline"}]
    plane("runtimes", "Runtimes · Hardware", "llama.cpp · Ollama — CPU-bound · 16k ceiling", "live", rt_nodes)

    # ── Relationships between planes: calls (↓) and events (↑) ────────────────
    flows = [
        {"from": "interface", "to": "os_core", "kind": "call", "label": "syscall"},
        {"from": "os_core", "to": "cognitive_kernel", "kind": "call", "label": "dispatch"},
        {"from": "cognitive_kernel", "to": "os_core", "kind": "event", "label": "lifecycle.*"},
        {"from": "cognitive_kernel", "to": "hooks", "kind": "call", "label": "enforce"},
        {"from": "hooks", "to": "cognitive_kernel", "kind": "event", "label": "policy.* (audited)"},
        {"from": "hooks", "to": "subsystems", "kind": "call", "label": "guard → allow / deny"},
        {"from": "subsystems", "to": "hooks", "kind": "event", "label": "cognitive.*"},
        {"from": "subsystems", "to": "runtime_kernel", "kind": "call", "label": "infer"},
        {"from": "runtime_kernel", "to": "runtimes", "kind": "call", "label": "execute"},
        {"from": "runtimes", "to": "runtime_kernel", "kind": "event", "label": "tokens"},
    ]

    # ── The audit spine (kernel_events durable log) — live counts ─────────────
    audit = {"events": 0, "policy": 0, "cognitive": 0}
    try:
        import kernel_events as _ke
        _tail = _ke.audit_tail(500)
        audit["events"] = len(_tail)
        audit["policy"] = sum(1 for e in _tail if str(e.get("type", "")).startswith("policy."))
        audit["cognitive"] = sum(1 for e in _tail if str(e.get("type", "")).startswith("cognitive."))
    except Exception:
        pass

    total = sum(len(p["nodes"]) for p in planes)
    online = sum(1 for p in planes for n in p["nodes"]
                 if n["status"] in ("online", "migrated"))
    planned = sum(1 for p in planes for n in p["nodes"] if n["status"] == "planned")
    return {"ts": time.time(), "planes": planes, "flows": flows, "lifecycle": _LIFECYCLE,
            "os_state": os_state, "audit": audit,
            "stats": {"planes": len(planes), "components": total, "online": online,
                      "planned": planned, "kernel_migrated": ck_migrated,
                      "kernel_total": len(_KERNEL_SERVICES), "policies": n_pol,
                      "subsystems_conform": _n_conf}}
