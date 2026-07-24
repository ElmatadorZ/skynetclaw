"""
ecosystem_manifest.py — SkynetClaw ECOSYSTEM single source of truth
====================================================================
Every app, file, endpoint, operative, tool, skill in the ecosystem
is declared HERE once. All prompts read from here. SkynetClaw chat
+ Continental UI + Bridge Console + agent_run all share the same
self-knowledge.

Why this exists:
  When the user asks "what is THE_CONTINENTAL_DIVISION.html?",
  SkynetClaw must answer instantly from this manifest — NOT search
  the filesystem. Manifest is the model's eyes.

When you add a new app / file / operative / tool / skill →
  update HERE, restart, every surface learns about it.
"""
from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any, Dict, List

_BASE = Path(__file__).parent
_ROOT = _BASE.parent

# ──────────────────── ECOSYSTEM DECLARATION ────────────────────────
MANIFEST: Dict[str, Any] = {
    "name":         "SkynetClaw Ecosystem",
    "version":      "5.0",
    "author":       "ElmatadorZ (Bunyawat Dechanon)",
    "license":      "Apache-2.0",
    "tagline":      "Autonomous Cognitive Agent + Continental Council UI",

    # ───── APPS (front-end surfaces) ─────
    "apps": [
        {
            "id":          "skynetclaw-chat",
            "name":        "SkynetClaw Chat",
            "url":         "http://localhost:8765",
            "file":        "index.html",
            "purpose":     "Primary terminal — direct chat with SkynetClaw, raw tool access",
            "role":        "Operator's direct line to the autonomous agent",
        },
        {
            "id":          "the-continental-division",
            "name":        "THE CONTINENTAL DIVISION",
            "url":         "http://localhost:8766/continental",
            "alt_urls":    ["/agent-room", "/THE_CONTINENTAL_DIVISION.html", "/division"],
            "file":        "THE_CONTINENTAL_DIVISION.html",
            "purpose":     "Council visualization + 12 operatives + mindmap + phase tracker",
            "role":        "High-ceremony command theatre — same ecosystem as Chat, different ritual",
        },
        {
            "id":          "bridge-console",
            "name":        "CBP Bridge Console",
            "url":         "http://localhost:8766/bridge",
            "file":        "bridge_console.html",
            "purpose":     "Cross-app data flow visualization + audit chain + ecosystem insights",
            "role":        "Observability layer — watch the two front-ends talk in real time",
        },
    ],

    # ───── BACKEND (single backend serves all apps) ─────
    "backend": {
        "name":  "SkynetClaw Backend v5",
        "url":   "http://localhost:8766",
        "entry": "backend/main.py",
        "stack": ["FastAPI", "Ollama (local LLM)", "SQLite", "SSE streaming"],
    },

    # ───── 12 OPERATIVES (THE CONTINENTAL DIVISION council) ─────
    "operatives": [
        {"code":"OPV-001","name":"THE ANALYST",     "role":"evidence · data · facts"},
        {"code":"OPV-002","name":"THE STRATEGIST",  "role":"long game · planning"},
        {"code":"OPV-003","name":"THE SKEPTIC",     "role":"shadow gate · veto · critique"},
        {"code":"OPV-004","name":"THE FORECASTER",  "role":"scenarios · weather · risk"},
        {"code":"OPV-005","name":"THE EXECUTOR",    "role":"tools · build · execute"},
        {"code":"OPV-006","name":"THE STORYTELLER", "role":"synthesize · brief · close"},
        {"code":"OPV-007","name":"THE SCOUT",       "role":"discovery · obsidian · find the tool"},
        {"code":"OPV-008","name":"THE AUDITOR",     "role":"quality · verification"},
        {"code":"OPV-009","name":"THE GOVERNOR",    "role":"governance · arbitration"},
        {"code":"OPV-010","name":"THE ARCHITECT",   "role":"system design · blueprint"},
        {"code":"OPV-011","name":"THE SENTINEL",    "role":"security · boundary"},
        {"code":"OPV-012","name":"THE CONCIERGE",   "role":"router · mission intake"},
    ],

    # ───── ENDPOINTS (cross-app contracts) ─────
    "endpoints": {
        "chat":         "POST /api/chat",
        "agent_run":    "POST /api/agent/run",
        "continental":  "POST /api/continental/dispatch",
        "bridge_log":   "GET  /api/bridge/log",
        "bridge_verify":"GET  /api/bridge/verify",
        "feedback":     "GET  /api/feedback/insights",
        "skills_match": "POST /api/skills/match",
        "models":       "GET  /api/models",
    },

    # ───── SUBSYSTEMS (modules in backend/) ─────
    "subsystems": [
        {"id":"continental_relay",  "purpose":"Continental UI ↔ SkynetClaw chat audit bridge"},
        {"id":"bridge_protocol",    "purpose":"CBP 1.0 — 13 message types + tamper-evident hash chain"},
        {"id":"feedback_engine",    "purpose":"Analyzes audit + chat to generate ecosystem self-improvement insights"},
        {"id":"obsidian_tools",     "purpose":"4 SCOUT tools (list/read/write/search) for vault access"},
        {"id":"skills_auto_router", "purpose":"Auto-match user message to skills by trigger keywords"},
        {"id":"genesis_gos",        "purpose":"GTS-1 + GPS-2 + GOP-3 governance standards (18/18 conformance)"},
        {"id":"agent_council",      "purpose":"L5 six-specialist parallel deliberation"},
        {"id":"agentic_workflow",   "purpose":"4-phase Comprehend → Plan → Execute → Reflect"},
        {"id":"genesis_router",     "purpose":"Server-side model auto-override per drive/role"},
    ],

    # ───── DATA STORES ─────
    "stores": [
        {"file":"skynerclaw.db",            "purpose":"skills, custom_tools, agent_runs, integrations"},
        {"file":"chat_history.db",          "purpose":"shared chat — populated by both /api/chat AND /api/continental/dispatch"},
        {"file":"continental_audit.jsonl",  "purpose":"every Continental directive — tamper-evident hash chain"},
        {"file":"bridge_log.jsonl",         "purpose":"every CBP envelope between apps"},
        {"file":"atlas_genome.json",        "purpose":"long-term strategy rules accumulated from reflections"},
    ],
}


def render_manifest_for_prompt() -> str:
    """
    Render manifest as a compact section to inject into every system prompt.
    Format: human-readable + scannable + ~1500 chars budget.
    """
    m = MANIFEST
    lines = [
        "## ECOSYSTEM MAP — what you (SkynetClaw) are part of",
        f"You are the cognitive engine of **{m['name']} v{m['version']}**. The user (Operator) interacts with you via 3 surfaces, ALL backed by the same backend ({m['backend']['url']}):",
        "",
        "### APPS in this ecosystem (these are NOT external — they ARE you):",
    ]
    for a in m["apps"]:
        lines.append(f"- **{a['name']}** → `{a['file']}` @ {a['url']}")
        lines.append(f"  - {a['purpose']}")
    lines += [
        "",
        f"### THE CONTINENTAL DIVISION council — {len(m['operatives'])} operatives the Operator can engage:",
    ]
    for op in m["operatives"]:
        lines.append(f"- `{op['code']}` **{op['name']}** — {op['role']}")
    lines += [
        "",
        "### Subsystems available to you (backend modules):",
    ]
    for s in m["subsystems"]:
        lines.append(f"- `{s['id']}` — {s['purpose']}")
    lines += [
        "",
        "### Rule of recognition:",
        "When the Operator mentions `THE_CONTINENTAL_DIVISION.html`, `agent_room.html`, `bridge_console.html`, or any operative name (THE CONCIERGE, THE SCOUT, etc.) — these are YOUR OWN parts. Do NOT search the filesystem. Acknowledge from this manifest and explain.",
        "When asked 'what apps are in your ecosystem' — list the 3 apps above with purpose.",
        "When asked 'who is THE_X' — read from operatives list above.",
    ]
    return "\n".join(lines)


def write_self_md() -> Path:
    """Generate / refresh backend/SELF.md from manifest. Read by compose_genesis_prompt."""
    body = render_manifest_for_prompt()
    f = _BASE / "SELF.md"
    f.write_text(body + "\n\n*(auto-generated from ecosystem_manifest.py at " +
                 time.strftime("%Y-%m-%d %H:%M:%S") + ")*\n",
                 encoding="utf-8")
    return f


def mount(app):
    @app.get("/api/ecosystem/manifest")
    def _manifest():
        return MANIFEST

    @app.get("/api/ecosystem/prompt-section")
    def _prompt_section():
        return {"section": render_manifest_for_prompt(),
                "char_count": len(render_manifest_for_prompt())}

    @app.post("/api/ecosystem/refresh-self")
    def _refresh():
        f = write_self_md()
        return {"ok": True, "wrote": str(f), "size": f.stat().st_size}

    # Auto-write SELF.md on mount so first chat session has it
    try:
        f = write_self_md()
        print(f"[Ecosystem] manifest mounted at /api/ecosystem/* · SELF.md → {f.stat().st_size}b")
    except Exception as e:
        print(f"[Ecosystem] SELF.md write failed: {e}")


if __name__ == "__main__":
    import sys
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    print(render_manifest_for_prompt())
    print(f"\n[render size: {len(render_manifest_for_prompt())} chars]")
    f = write_self_md()
    print(f"[wrote {f}: {f.stat().st_size}b]")
