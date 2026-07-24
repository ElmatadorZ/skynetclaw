"""
self_awareness.py — SkynetClaw self-introspection module
=========================================================
Genesis Mind L0 Reality Anchor at the system level.

Runs on every backend start (via hooks/05_self_aware.py) and writes a fresh
`backend/SELF.md` that the agent reads at session boot. Tells SkynetClaw:

  • What I AM (version, modules loaded, active model)
  • What I CAN do (tools, integrations, skills, connections)
  • What I KNOW (Obsidian vault: notes, topics, recent activity)
  • What I DON'T know / CAN'T do (explicit limitations)
  • Genome status (compound learning state)
  • Recent activity (agent_runs in last 24h)

Without this, SkynetClaw boots blind every session — it has tools but doesn't
know what's in its own memory or what it doesn't have access to.

Author: ElmatadorZ — Apache-2.0
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import sqlite3
import datetime as _dt
from pathlib import Path
from collections import Counter
from typing import Any, Dict, List, Optional

_BASE = Path(__file__).parent
SELF_PATH = _BASE / "SELF.md"


# ──────────────────────────────────────────────────────────────────────────────
# 1. CAPABILITIES — what I can do (tools + integrations + skills + models)
# ──────────────────────────────────────────────────────────────────────────────
def gather_capabilities(app: Optional[Any] = None) -> Dict[str, Any]:
    """Inventory of tools, integrations, skills, custom code, connections."""
    cap: Dict[str, Any] = {
        "builtin_tools": [],
        "custom_tools": [],
        "integrations": [],
        "skills": [],
        "connections": [],
        "models": [],
        "modules_loaded": [],
        "endpoints": [],
    }

    # --- BUILTIN_TOOLS (read live from main module if available) ---
    try:
        # Try: maybe main.py is already imported as module
        import importlib
        main_mod = sys.modules.get("main") or sys.modules.get("__main__")
        if main_mod and hasattr(main_mod, "BUILTIN_TOOLS"):
            for t in main_mod.BUILTIN_TOOLS:
                fn = t.get("function", {}) if isinstance(t, dict) else {}
                cap["builtin_tools"].append({
                    "name": fn.get("name", "?"),
                    "description": (fn.get("description") or "")[:160],
                })
    except Exception:
        pass

    # --- Custom tools, integrations, skills, connections (from skynerclaw.db) ---
    db_path = _BASE / "skynerclaw.db"
    if db_path.exists():
        try:
            conn = sqlite3.connect(db_path); c = conn.cursor()
            try:
                rows = c.execute("SELECT name, description FROM custom_tools").fetchall()
                cap["custom_tools"] = [{"name": r[0], "description": (r[1] or "")[:120]}
                                        for r in rows]
            except sqlite3.OperationalError:
                pass
            try:
                rows = c.execute("SELECT service, name, enabled FROM integrations").fetchall()
                cap["integrations"] = [
                    {"service": r[0], "name": r[1] or r[0], "enabled": bool(r[2])}
                    for r in rows
                ]
            except sqlite3.OperationalError:
                pass
            try:
                rows = c.execute("SELECT name, description FROM skills").fetchall()
                cap["skills"] = [{"name": r[0], "description": (r[1] or "")[:120]}
                                  for r in rows]
            except sqlite3.OperationalError:
                pass
            try:
                rows = c.execute(
                    "SELECT name, base_url, api_type, is_active FROM connections"
                ).fetchall()
                cap["connections"] = [
                    {"name": r[0], "base_url": r[1], "api_type": r[2], "active": bool(r[3])}
                    for r in rows
                ]
            except sqlite3.OperationalError:
                pass
            conn.close()
        except Exception as e:
            print(f"[self.capabilities.db] {e}")

    # --- Available Ollama models (best effort, short timeout) ---
    try:
        import urllib.request as ureq
        # Use the active connection's base_url if discoverable
        base_url = "http://localhost:11434"
        for c in cap.get("connections", []):
            if c.get("active") and c.get("base_url"):
                base_url = c["base_url"].rstrip("/"); break
        req = ureq.Request(f"{base_url}/api/tags",
                            headers={"Accept": "application/json"})
        with ureq.urlopen(req, timeout=4) as r:
            d = json.loads(r.read().decode())
        for m in d.get("models", []):
            cap["models"].append({
                "name": m.get("name", "?"),
                "size_gb": round((m.get("size", 0) or 0) / 1e9, 2),
            })
    except Exception:
        pass

    # --- Loaded Masterpiece / OpenClaw modules ---
    for name, label in [
        ("skynet_genesis_masterpiece", "Masterpiece"),
        ("skynetclaw_router",          "MultiModelRouter"),
        ("skynetclaw_meta",            "MetaCognition"),
        ("skynetclaw_will",            "WillCore"),
        ("openclaw_port",              "OpenClawPort.Tier1"),
        ("openclaw_port_tier2",        "OpenClawPort.Tier2"),
        ("prompts",                    "ModularPrompts"),
        ("hooks",                      "BootHooks"),
    ]:
        try:
            __import__(name); cap["modules_loaded"].append(label)
        except Exception:
            pass

    # --- Registered FastAPI routes (if app passed) ---
    if app is not None:
        try:
            for r in getattr(app, "routes", []):
                path = getattr(r, "path", None)
                methods = getattr(r, "methods", None) or set()
                if path and methods and not path.startswith("/openapi"):
                    cap["endpoints"].append({
                        "path": path,
                        "methods": sorted(m for m in methods if m != "HEAD"),
                    })
        except Exception:
            pass

    return cap


# ──────────────────────────────────────────────────────────────────────────────
# 2. OBSIDIAN VAULT — what I know
# ──────────────────────────────────────────────────────────────────────────────
def _read_settings() -> Dict[str, Any]:
    p = _BASE / "settings.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


# Frequent words to ignore when extracting topics from headings
_STOPWORDS = {
    "the","a","an","and","or","but","of","to","in","on","for","with","at","by",
    "is","are","was","were","be","been","being","this","that","these","those","my",
    "your","his","her","its","our","their","i","you","he","she","it","we","they",
    "from","as","if","then","than","so","not","no","do","does","did","what","why",
    "how","when","where","who","which","can","will","would","should","could","may",
    "all","any","some","one","two","three","note","notes","page","md",
}


def gather_obsidian(max_files_to_scan: int = 600,
                    max_recent: int = 5,
                    max_topics: int = 10) -> Dict[str, Any]:
    """Scan the configured Obsidian vault. Best-effort, time-bounded."""
    out: Dict[str, Any] = {
        "configured": False, "vault_path": "", "exists": False,
        "total_notes": 0, "total_size_mb": 0.0,
        "recent_notes": [], "top_topics": [],
        "folders": [], "scanned": 0, "elapsed_ms": 0,
    }
    settings = _read_settings()
    vp = (settings.get("vault_path") or "").strip()
    if not vp:
        return out
    out["configured"] = True
    out["vault_path"] = vp
    p = Path(vp)
    if not p.exists() or not p.is_dir():
        return out
    out["exists"] = True

    t0 = time.time()
    notes: List[Path] = []
    try:
        # rglob with cap so we don't stall on huge vaults
        count = 0
        for md in p.rglob("*.md"):
            notes.append(md)
            count += 1
            if count >= max_files_to_scan:
                break
        out["scanned"] = count
        out["total_notes"] = count
        # Could be more files than scanned — note that limit was hit
        if count >= max_files_to_scan:
            out["scan_truncated"] = True
    except Exception as e:
        print(f"[self.obsidian.scan] {e}")
        return out

    # Aggregate stats
    total_bytes = 0
    word_freq: Counter = Counter()
    folders: Counter = Counter()
    recent: List[tuple] = []  # (mtime, path)

    for md in notes:
        try:
            st = md.stat()
            total_bytes += st.st_size
            recent.append((st.st_mtime, md))
            try:
                rel = md.relative_to(p)
                if len(rel.parts) > 1:
                    folders[rel.parts[0]] += 1
            except Exception:
                pass
            # Sample first ~4KB per file for headings
            with md.open("rb") as f:
                chunk = f.read(4096).decode("utf-8", "replace")
            for line in chunk.splitlines():
                ln = line.strip()
                if ln.startswith("#"):
                    text = re.sub(r"^#+\s*", "", ln)
                    for w in re.findall(r"[A-Za-z฀-๿]{3,}", text.lower()):
                        if w not in _STOPWORDS:
                            word_freq[w] += 1
        except Exception:
            continue

    out["total_size_mb"] = round(total_bytes / 1e6, 2)
    recent.sort(reverse=True)
    out["recent_notes"] = [
        {"name": str(r[1].relative_to(p)),
         "modified": _dt.datetime.fromtimestamp(r[0]).strftime("%Y-%m-%d %H:%M")}
        for r in recent[:max_recent]
    ]
    out["top_topics"] = [{"topic": w, "count": n}
                          for w, n in word_freq.most_common(max_topics)]
    out["folders"] = [{"name": f, "n_notes": n}
                       for f, n in folders.most_common(8)]
    out["elapsed_ms"] = int((time.time() - t0) * 1000)
    return out


# ──────────────────────────────────────────────────────────────────────────────
# 3. CONSTRAINTS — what I CAN'T do (explicit limitations)
# ──────────────────────────────────────────────────────────────────────────────
def gather_constraints(capabilities: Dict[str, Any]) -> List[str]:
    """Surface known limits so the agent doesn't promise things it can't deliver."""
    limits: List[str] = []

    integ_services = {i.get("service") for i in capabilities.get("integrations", [])
                       if i.get("enabled")}
    if "telegram" not in integ_services:
        limits.append("Cannot send Telegram messages — no integration configured")
    if "discord" not in integ_services:
        limits.append("Cannot send Discord messages — no integration configured")
    if "line" not in integ_services:
        limits.append("Cannot send Line Notify — no integration configured")
    if "facebook" not in integ_services:
        limits.append("Cannot post to Facebook — no integration configured")

    if not capabilities.get("models"):
        limits.append("No Ollama models reachable — verify Ollama server is running")

    # Always-true caveats inherent to this stack
    limits.extend([
        "No paid market data feeds (Bloomberg / Refinitiv / TradingView Pro)",
        "Stock-level real-time prices unavailable — only crypto/forex/gold/PAXG",
        "Yahoo Finance API often returns 401 — fallback to CoinGecko/Stooq/GoldPrice.org",
        "Cannot access user's local files outside the workspace folder",
        "Cannot run Windows GUI automation (no PyAutoGUI) — must stay tool-based",
        "Camera capture / screen recording explicitly DENIED by deny-list policy",
        "SMS sending NOT available — no Twilio / channel adapter wired",
        "Cannot create OS-level scheduled tasks — only in-process /api/cron and heartbeats",
    ])
    return limits


# ──────────────────────────────────────────────────────────────────────────────
# 4. GENOME + RECENT ACTIVITY
# ──────────────────────────────────────────────────────────────────────────────
def gather_genome() -> Dict[str, Any]:
    out = {"strategy_rules": 0, "execution_paths": 0,
           "failure_signatures": 0, "updated_at": 0,
           "audit_chain_size_kb": 0.0, "echo_memory_size_kb": 0.0}
    try:
        gp = _BASE / "atlas_genome.json"
        if gp.exists():
            g = json.loads(gp.read_text(encoding="utf-8"))
            out["strategy_rules"]      = len(g.get("strategy_rules", []))
            out["execution_paths"]     = len(g.get("execution_paths", []))
            out["failure_signatures"]  = len(g.get("failure_map", []))
            out["updated_at"]          = int(g.get("updated_at", 0) or 0)
    except Exception:
        pass
    try:
        ap = _BASE / "audit_trail.jsonl"
        if ap.exists():
            out["audit_chain_size_kb"] = round(ap.stat().st_size / 1024, 1)
    except Exception:
        pass
    try:
        ep = _BASE / "echo_memory.jsonl"
        if ep.exists():
            out["echo_memory_size_kb"] = round(ep.stat().st_size / 1024, 1)
    except Exception:
        pass
    return out


def gather_recent_runs(limit: int = 5) -> List[Dict[str, Any]]:
    db = _BASE / "skynerclaw.db"
    if not db.exists():
        return []
    try:
        conn = sqlite3.connect(db)
        rows = conn.execute(
            "SELECT id, started_at, status, n_steps, n_tools, task FROM agent_runs "
            "ORDER BY started_at DESC LIMIT ?", (limit,),
        ).fetchall()
        conn.close()
        return [{
            "id": r[0],
            "when": _dt.datetime.fromtimestamp(r[1]).strftime("%Y-%m-%d %H:%M") if r[1] else "?",
            "status": r[2], "n_steps": r[3], "n_tools": r[4],
            "task": (r[5] or "")[:80],
        } for r in rows]
    except sqlite3.OperationalError:
        # agent_runs table may not exist yet
        return []
    except Exception:
        return []


# ──────────────────────────────────────────────────────────────────────────────
# 5. ASSEMBLE & WRITE  →  SELF.md
# ──────────────────────────────────────────────────────────────────────────────
def build_self_state(app: Optional[Any] = None) -> Dict[str, Any]:
    """Run all introspection. Returns dict — caller decides serialization."""
    cap = gather_capabilities(app)
    obs = gather_obsidian()
    genome = gather_genome()
    runs = gather_recent_runs()
    constraints = gather_constraints(cap)
    return {
        "generated_at": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "capabilities": cap,
        "obsidian": obs,
        "constraints": constraints,
        "genome": genome,
        "recent_runs": runs,
    }


def render_self_md(state: Dict[str, Any]) -> str:
    """Render state dict into the SELF.md markdown."""
    cap = state.get("capabilities", {})
    obs = state.get("obsidian", {})
    gen = state.get("genome", {})
    runs = state.get("recent_runs", [])
    cons = state.get("constraints", [])

    L = []
    L.append("# SELF — SkynetClaw self-awareness snapshot")
    L.append("")
    L.append(f"_Auto-generated by `self_awareness.py` — refreshed every backend start._")
    L.append(f"_Generated: **{state.get('generated_at')}**_")
    L.append("")
    L.append("Read this on session boot. It tells you what you are, what you can do, "
             "what you know, and (importantly) what you DON'T have access to.")
    L.append("")

    # ── I AM ──
    L.append("## I AM")
    L.append("")
    L.append(f"- **System**: SkynetClaw v5 (Masterpiece runtime + OpenClaw Tier 1+2 ports)")
    L.append(f"- **Modules loaded**: {', '.join(cap.get('modules_loaded') or []) or '(none detected)'}")
    L.append(f"- **Endpoints registered**: {len(cap.get('endpoints') or [])}")
    L.append(f"- **Active model connection**: " + (
        next((c.get("name", "?") + " — " + c.get("base_url", "?")
              for c in cap.get("connections", []) if c.get("active")),
             "(none active)")
    ))
    L.append("")

    # ── I CAN DO ──
    L.append("## I CAN DO")
    L.append("")
    L.append(f"### Built-in tools ({len(cap.get('builtin_tools') or [])})")
    L.append("")
    if cap.get("builtin_tools"):
        # Group by name prefix to make it scannable
        names = [t["name"] for t in cap["builtin_tools"]]
        L.append(", ".join(f"`{n}`" for n in names[:60]))
    else:
        L.append("_(no tool inventory available — main module not imported)_")
    L.append("")

    if cap.get("custom_tools"):
        L.append(f"### Custom tools ({len(cap['custom_tools'])})")
        L.append("")
        for t in cap["custom_tools"][:10]:
            L.append(f"- `{t['name']}` — {t['description']}")
        L.append("")

    L.append(f"### Integrations ({sum(1 for i in cap.get('integrations', []) if i.get('enabled'))} enabled)")
    L.append("")
    if cap.get("integrations"):
        for i in cap["integrations"][:12]:
            mark = "✓" if i.get("enabled") else "·"
            L.append(f"- {mark} **{i.get('service','?')}**: {i.get('name','?')}")
    else:
        L.append("_(none configured)_")
    L.append("")

    L.append(f"### Skills ({len(cap.get('skills') or [])})")
    L.append("")
    if cap.get("skills"):
        for s in cap["skills"][:10]:
            L.append(f"- **{s['name']}** — {s['description']}")
    else:
        L.append("_(no skills installed via DB)_")
    L.append("")

    L.append(f"### Models available ({len(cap.get('models') or [])})")
    L.append("")
    if cap.get("models"):
        for m in cap["models"][:20]:
            L.append(f"- `{m['name']}` ({m.get('size_gb', '?')} GB)")
    else:
        L.append("_(Ollama unreachable at boot)_")
    L.append("")

    # ── I KNOW (Obsidian) ──
    L.append("## I KNOW")
    L.append("")
    if not obs.get("configured"):
        L.append("_No Obsidian vault configured. Set `vault_path` in settings to enable._")
    elif not obs.get("exists"):
        L.append(f"_Vault path configured but missing on disk: `{obs.get('vault_path')}`_")
    else:
        L.append(f"- **Vault**: `{obs.get('vault_path')}`")
        L.append(f"- **Notes scanned**: {obs.get('total_notes', 0)}"
                 + (" (truncated — large vault)" if obs.get("scan_truncated") else ""))
        L.append(f"- **Total size**: {obs.get('total_size_mb', 0)} MB")
        L.append(f"- **Scan time**: {obs.get('elapsed_ms', 0)} ms")
        L.append("")
        if obs.get("folders"):
            L.append("**Top folders:**")
            L.append("")
            for f in obs["folders"]:
                L.append(f"- `{f['name']}/` — {f['n_notes']} notes")
            L.append("")
        if obs.get("top_topics"):
            L.append("**Top topics in headings (frequency):**")
            L.append("")
            L.append(", ".join(f"{t['topic']}({t['count']})"
                               for t in obs["top_topics"]))
            L.append("")
        if obs.get("recent_notes"):
            L.append("**Recently modified notes:**")
            L.append("")
            for r in obs["recent_notes"]:
                L.append(f"- `{r['name']}` — {r['modified']}")
            L.append("")
    L.append("")

    # ── I DON'T KNOW / CAN'T DO ──
    L.append("## I DON'T KNOW / CAN'T DO")
    L.append("")
    L.append("Be honest about these. Don't promise; surface the limit.")
    L.append("")
    for c in cons:
        L.append(f"- {c}")
    L.append("")

    # ── GENOME (compound learning state) ──
    L.append("## GENOME (compound learning)")
    L.append("")
    if gen.get("updated_at"):
        L.append(f"- Last update: {_dt.datetime.fromtimestamp(gen['updated_at']).strftime('%Y-%m-%d %H:%M')}")
    L.append(f"- Strategy rules learned: **{gen.get('strategy_rules', 0)}**")
    L.append(f"- Execution paths recorded: **{gen.get('execution_paths', 0)}**")
    L.append(f"- Failure signatures (never deleted): **{gen.get('failure_signatures', 0)}**")
    L.append(f"- AuditTrail size: {gen.get('audit_chain_size_kb', 0)} KB")
    L.append(f"- Echo memory size: {gen.get('echo_memory_size_kb', 0)} KB")
    L.append("")

    # ── RECENT ACTIVITY ──
    L.append("## RECENT AGENT RUNS")
    L.append("")
    if not runs:
        L.append("_(no runs recorded yet — agent_runs table empty)_")
    else:
        for r in runs:
            L.append(f"- `{r['id']}` · {r['when']} · **{r['status']}** "
                     f"· {r['n_steps']} steps · {r['n_tools']} tools — "
                     f"_{r['task']}_")
    L.append("")

    L.append("---")
    L.append("")
    L.append("_End of SELF.md — regenerated next backend start._")
    return "\n".join(L)


def write_self_state(app: Optional[Any] = None,
                     out_path: Optional[Path] = None) -> Path:
    """Build state, render markdown, write atomically. Returns the file path."""
    state = build_self_state(app)
    md = render_self_md(state)
    p = out_path or SELF_PATH
    try:
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(md, encoding="utf-8")
        tmp.replace(p)
    except Exception as e:
        print(f"[self_awareness.write] {e}")
        # last-ditch direct write
        try:
            p.write_text(md, encoding="utf-8")
        except Exception:
            pass
    return p


def compose_brief() -> str:
    """One-paragraph self-summary for prompt injection (cheaper than full SELF.md)."""
    state = build_self_state()
    cap = state["capabilities"]; obs = state["obsidian"]; gen = state["genome"]
    bits = []
    bits.append(f"I am SkynetClaw v5 with {len(cap.get('modules_loaded') or [])} cognitive modules loaded "
                f"({', '.join(cap.get('modules_loaded') or [])[:120]}).")
    bits.append(f"I have {len(cap.get('builtin_tools') or [])} built-in tools, "
                f"{sum(1 for i in cap.get('integrations', []) if i.get('enabled'))} active integrations, "
                f"{len(cap.get('skills') or [])} skills, "
                f"{len(cap.get('models') or [])} models reachable.")
    if obs.get("exists"):
        bits.append(f"My Obsidian vault has {obs.get('total_notes', 0)} notes "
                    f"covering: {', '.join(t['topic'] for t in (obs.get('top_topics') or [])[:6])}.")
    else:
        bits.append("No Obsidian vault is configured.")
    bits.append(f"Genome state: {gen.get('strategy_rules',0)} rules, "
                f"{gen.get('execution_paths',0)} paths, "
                f"{gen.get('failure_signatures',0)} failure signatures.")
    return " ".join(bits)


# ──────────────────────────────────────────────────────────────────────────────
# Self-test  —  python self_awareness.py
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("=== self_awareness self-test ===\n")

    state = build_self_state()
    print(f"Capabilities — modules: {state['capabilities']['modules_loaded']}")
    print(f"Capabilities — builtin tools: {len(state['capabilities']['builtin_tools'])}")
    print(f"Capabilities — integrations: {len(state['capabilities']['integrations'])}")
    print(f"Capabilities — skills: {len(state['capabilities']['skills'])}")
    print(f"Capabilities — models: {len(state['capabilities']['models'])}")
    print(f"Obsidian configured: {state['obsidian']['configured']} | exists: {state['obsidian']['exists']}")
    if state['obsidian'].get('exists'):
        print(f"  notes: {state['obsidian']['total_notes']}, "
              f"size: {state['obsidian']['total_size_mb']} MB, "
              f"scan: {state['obsidian']['elapsed_ms']} ms")
        print(f"  top topics: {[t['topic'] for t in state['obsidian']['top_topics'][:5]]}")
    print(f"Constraints: {len(state['constraints'])} items")
    print(f"Genome: rules={state['genome']['strategy_rules']} "
          f"paths={state['genome']['execution_paths']} "
          f"failures={state['genome']['failure_signatures']}")
    print(f"Recent runs: {len(state['recent_runs'])}")

    # Write SELF.md
    p = write_self_state()
    print(f"\nWrote {p} ({p.stat().st_size if p.exists() else 0} bytes)")

    # Compose brief
    brief = compose_brief()
    print(f"\nBrief preview ({len(brief)} chars):\n{brief[:500]}...")
    print("\n=== self-test OK ===")
