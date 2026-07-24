"""
governance.py — Genesis Governance OS layer for SkynetClaw
===========================================================
Implements:
  GPS-2  Permission Gate — deny-by-default allow/deny/escalate, evaluated
         BEFORE every tool call. Irreversible actions require a human gate.
  GOS-0  Constitution declarations — 12 operatives mapped to 7 branches,
         core laws, capability-as-constitutional-act (install_package gated).
  GTS-1  Honest blocked-state — a gated run halts as 'blocked_awaiting_gate',
         never silently proceeds or fakes done.

Human-gate flow (zero frontend changes — rides the existing ask_user UI):
  1. Agent hits an ESCALATE tool → gate stores a pending entry (gate_xxxxxxxxxx)
     and emits ask_user with approve/deny options. Run halts honestly.
  2. Operator clicks an option → it arrives as the next directive.
  3. resolve_directive() intercepts it, records the decision in ExecApprovals
     (ALWAYS exact / ALWAYS tool-wide / DENY), and re-issues the ORIGINAL task.
  4. On re-run the gate finds the recorded decision and proceeds or blocks.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

_BASE = Path(__file__).parent.resolve()
CONFIG_PATH = _BASE / "governance_config.json"
PENDING_PATH = _BASE / "pending_gates.json"

# ── Default GPS-2 policy ──────────────────────────────────────────────────────
# allow    — safe reads + workspace-scoped writes (revertible: auto-git + shadow gate)
# escalate — irreversible / outward-facing / scope-widening → human gate
# deny     — hard-blocked
# unknown tool → DENY (capability-as-constitutional-act: new tools enter via config)
DEFAULT_CONFIG: Dict[str, Any] = {
    "version": 6,  # v2: +grep_search · v3: +dev_server · v4: classify 7 orphan · v5: +system_diagnostics · v6: +system_repair (escalate)
                   # (read-only discovery + read_document + build_news_report) so
                   # capability-coverage = 100% — paradigm ratified 2026-07-09
    "_doc": "GPS-2 deny-by-default permission policy. Edit lists then restart backend. "
            "Unknown tools are DENIED until added here (GOS-0: capability is a constitutional act).",
    "allow": [
        # read-only
        "read_file", "read_document", "list_files", "find_files", "grep_search", "file_info",
        "get_system_info", "list_processes", "take_screenshot", "clipboard_read", "get_current_datetime",
        "calculator",           # pure deterministic arithmetic (safe_math, no eval) — safe like a computation
        "analyze_image",        # read a local image with a local vision model — read-only, offline, no side effect
        "system_diagnostics",   # read-only OS diagnosis — safe like read_file (repair stays shell_command→escalate)
        "get_crypto_price", "get_gold_price", "get_forex_rate", "get_news",
        "web_search", "http_request", "download_file", "build_news_report",
        "search_obsidian", "read_obsidian_note",
        "obsidian_list_notes", "obsidian_read_note", "obsidian_search",
        # read-only discovery over the House's own registries
        "query_missions", "query_learning", "query_timeline", "read_house_mind", "recall_archive",
        "ask_user_options",
        # workspace-scoped writes (auto-git revertible + shadow gate already applies)
        "write_file", "edit_file", "create_folder", "copy_file", "move_file",
        "write_obsidian_note", "obsidian_write_note",
        "clipboard_write", "open_browser",
    ],
    "escalate": [
        # shell-equivalent execution
        "shell_command", "run_python", "dev_server",
        # destructive / hard-to-undo
        "delete_file", "kill_process",
        # curated state-changing system repair (menu is exempted read-only above)
        "system_repair",
        # scope-widening (GOS-0 capability request → Judicial gate)
        "install_package",
        # outward-facing sends/publishes
        "telegram_send", "discord_send", "line_notify", "facebook_post",
        "call_integration",
    ],
    "deny": [],
    # ── GOS-0: constitutional declarations (consumed by reports / future council) ──
    "branches": {
        "Legislative":  ["OPV-009 THE GOVERNOR"],
        "Executive":    ["OPV-005 THE EXECUTOR", "OPV-012 THE CONCIERGE"],
        "Judicial":     ["OPV-003 THE SKEPTIC", "OPV-011 THE SENTINEL"],
        "Intelligence": ["OPV-001 THE ANALYST", "OPV-004 THE FORECASTER", "OPV-007 THE SCOUT"],
        "Development":  ["OPV-010 THE ARCHITECT"],
        "External":     ["OPV-006 THE STORYTELLER"],
        "Security":     ["OPV-011 THE SENTINEL", "OPV-008 THE AUDITOR"],
    },
    "core_laws": [
        "separation-of-powers", "accountability", "human-decides",
        "honest-failure", "capability-as-constitutional-act",
    ],
}

_GATE_RE = re.compile(r"\b(approve-tool|approve|deny)\s+(gate_[0-9a-f]{10})\b", re.IGNORECASE)


def _load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, data: Any) -> None:
    try:
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception as e:
        print(f"[Governance] save {path.name} failed: {e}")


class GPS2Gate:
    """Deny-by-default permission gate. Evaluate BEFORE acting."""

    def __init__(self, config_path: Path = CONFIG_PATH, pending_path: Path = PENDING_PATH):
        self.config_path = config_path
        self.pending_path = pending_path
        if not config_path.exists():
            _save_json(config_path, DEFAULT_CONFIG)
            print(f"[Governance] wrote default policy → {config_path.name}")
        self.config = _load_json(config_path, DEFAULT_CONFIG)
        # merge missing keys from defaults (forward-compatible config upgrades)
        for k, v in DEFAULT_CONFIG.items():
            self.config.setdefault(k, v)
        # ── GOS-0 capability migration: newer DEFAULT version admits new tools
        # by UNION (never removes operator's own additions/removals of old tools).
        if int(self.config.get("version", 1)) < int(DEFAULT_CONFIG["version"]):
            for k in ("allow", "escalate", "deny"):
                self.config[k] = list(dict.fromkeys(
                    list(self.config.get(k, [])) + list(DEFAULT_CONFIG.get(k, []))))
            self.config["version"] = DEFAULT_CONFIG["version"]
            _save_json(config_path, self.config)
            print(f"[Governance] policy migrated to v{DEFAULT_CONFIG['version']} — new capabilities admitted")
        self.pending: Dict[str, Any] = _load_json(pending_path, {})

    # ── GPS-2 decision order: deny → escalate → allow → DENY ────────────────
    def evaluate(self, tool: str, args: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
        if tool in self.config.get("deny", []):
            return "DENY", f"'{tool}' is on the deny list"
        # READ-ONLY DIAGNOSTIC EXEMPTION: a shell_command that is provably a
        # single read-only diagnostic (netsh show / ipconfig / ping / driverquery
        # …, no mutating verb, no shell chaining) is the same safety class as
        # read_file → ALLOW. This lets the agent SEE the machine (Wi-Fi, drivers,
        # network) without stalling on the human gate, while every state-changing
        # command still escalates. Verified command-by-command, not by trust.
        if tool == "shell_command":
            try:
                import system_doctor as _sd
                if _sd.is_readonly_diagnostic((args or {}).get("command", "")):
                    return "ALLOW", "read-only diagnostic — same class as read_file"
            except Exception:
                pass
        # system_repair listing the MENU is read-only; RUNNING a repair escalates
        if tool == "system_repair" and (args or {}).get("list") and not (args or {}).get("repair"):
            return "ALLOW", "repair menu is read-only"
        if tool in self.config.get("escalate", []):
            return "ESCALATE", f"'{tool}' is irreversible/outward-facing — human gate required"
        if tool in self.config.get("allow", []):
            return "ALLOW", ""
        return "DENY", f"'{tool}' is not in the permission config — unknown capability (GOS-0: add it to governance_config.json deliberately)"

    # ── Human gate: open a pending decision ──────────────────────────────────
    def open_gate(self, tool: str, args: Dict[str, Any], task: str) -> Dict[str, Any]:
        gid = "gate_" + uuid.uuid4().hex[:10]
        preview = ""
        for k in ("command", "code", "path", "package", "url", "name", "message", "text"):
            v = (args or {}).get(k)
            if v:
                preview = f"{k}={str(v)[:160]}"
                break
        self.pending[gid] = {
            "id": gid, "tool": tool, "args": args, "task": task,
            "ts": time.time(), "status": "pending",
        }
        # keep only the latest 50 pending entries
        if len(self.pending) > 50:
            for k in sorted(self.pending, key=lambda x: self.pending[x].get("ts", 0))[:-50]:
                self.pending.pop(k, None)
        _save_json(self.pending_path, self.pending)
        question = (
            f"🛡 SENTINEL · GPS-2 HUMAN GATE\n"
            f"Operative requests irreversible action: {tool}({preview})\n"
            f"Gate id: {gid} — choose below; the original mission resumes automatically."
        )
        options = [
            f"approve {gid} — อนุมัติครั้งนี้",
            f"approve-tool {gid} — อนุมัติ {tool} ถาวร",
            f"deny {gid} — ปฏิเสธ",
        ]
        return {"id": gid, "question": question, "options": options}

    # ── Directive intercept: approve/deny clicked in UI ─────────────────────
    def resolve_directive(self, text: str, approvals: Any) -> Optional[Dict[str, str]]:
        """If `text` is a gate decision, record it and return the original task to re-run."""
        m = _GATE_RE.search(text or "")
        if not m:
            return None
        action, gid = m.group(1).lower(), m.group(2)
        entry = self.pending.get(gid)
        if not entry:
            return {"task": text, "note": f"gate {gid} not found or already resolved — running directive as-is"}
        tool, args, task = entry["tool"], entry.get("args") or {}, entry.get("task") or ""
        try:
            if action == "approve":
                approvals.record(tool, args, "ALWAYS", scope="exact", note=f"GPS-2 {gid} one-time-pattern approval")
                note = f"GPS-2: operator approved {tool} (exact args) via {gid} — resuming mission"
            elif action == "approve-tool":
                approvals.record(tool, {}, "ALWAYS", scope="prefix", note=f"GPS-2 {gid} tool-wide approval")
                note = f"GPS-2: operator approved {tool} TOOL-WIDE via {gid} — resuming mission"
            else:
                approvals.record(tool, args, "DENY", scope="exact", note=f"GPS-2 {gid} denial")
                note = f"GPS-2: operator DENIED {tool} via {gid} — resuming mission without it"
        except Exception as e:
            return {"task": text, "note": f"gate decision failed to record: {e}"}
        entry["status"] = "resolved:" + action
        entry["resolved_ts"] = time.time()
        _save_json(self.pending_path, self.pending)
        return {"task": task or text, "note": note}

    def status(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "policy": {k: self.config.get(k, []) for k in ("allow", "escalate", "deny")},
            "branches": self.config.get("branches", {}),
            "core_laws": self.config.get("core_laws", []),
            "pending_gates": [v for v in self.pending.values() if v.get("status") == "pending"],
        }


def mount_governance(app: Any, gate: GPS2Gate) -> None:
    """Read-only governance endpoints (audit transparency)."""
    @app.get("/api/governance/status")
    def _gov_status():
        return gate.status()

    @app.get("/api/governance/pending")
    def _gov_pending():
        return {"ok": True, "pending": [v for v in gate.pending.values() if v.get("status") == "pending"]}

    print("[Governance] endpoints mounted at /api/governance/*")
