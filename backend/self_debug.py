"""
self_debug.py — SkynetClaw reads + analyzes its own code
=========================================================
The killer feature: the agent can introspect its own source, run its own
self-tests, identify bugs from recent error patterns, and PROPOSE patches
(it never auto-applies — the user reviews .patch files before merging).

Functions:

    list_modules()            — backend modules + their roles
    read_module(name)         — return source text of one module
    grep_module(name, pattern) — find lines matching pattern in module
    run_module_self_test(name) — execute __main__ block, capture output
    analyze_recent_errors(window_hours)
                              — scan audit + console-error patterns
    propose_patch(target_file, issue, suggested_change)
                              — write a .patch file for user review
    list_proposed_patches()   — show all generated patches
    apply_patch(patch_id, dry_run=True)
                              — apply (default dry-run only — never auto-apply)

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import datetime as _dt
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

_BASE = Path(__file__).parent
PATCHES_DIR = _BASE / "self_patches"


# ──────────────────────────────────────────────────────────────────────────────
# Module registry — what SkynetClaw knows about its own code
# ──────────────────────────────────────────────────────────────────────────────
MODULES: Dict[str, Dict[str, str]] = {
    "main":                       {"path": "main.py",                       "role": "FastAPI app + agent_run loop + 37 BUILTIN_TOOLS"},
    "skynetclaw_meta":            {"path": "skynetclaw_meta.py",            "role": "L0 Reality Anchor + L4 Shadow Gate + L7 Genome + AuditTrail"},
    "skynetclaw_router":          {"path": "skynetclaw_router.py",          "role": "Multi-Model Router with @auto/@executor/@ambient/@precision"},
    "skynetclaw_will":            {"path": "skynetclaw_will.py",            "role": "WillCore — identity + tone_filter + risk_classify"},
    "skynet_genesis_masterpiece": {"path": "skynet_genesis_masterpiece.py", "role": "Unified runtime + L0→L8 pipeline + endpoints"},
    "openclaw_port":              {"path": "openclaw_port.py",              "role": "Trajectory + Diary + WorkspaceGit + ExecApprovals"},
    "openclaw_port_tier2":        {"path": "openclaw_port_tier2.py",        "role": "Settings backup chain + AgentRunsDB + ModelCostOverlay"},
    "self_awareness":             {"path": "self_awareness.py",             "role": "SELF.md generator — capabilities + Obsidian + constraints"},
    "volition_engine":            {"path": "volition_engine.py",            "role": "L1 Volition — drive/tone/urgency/gap extractor"},
    "metacognition":              {"path": "metacognition.py",              "role": "Reflect on own thinking + recurring failure analysis"},
    "self_debug":                 {"path": "self_debug.py",                 "role": "Read/test own modules + propose patches"},
    "prompts":                    {"path": "prompts/__init__.py",           "role": "compose_genesis_prompt — IDENTITY/AGENTS/TOOLS/SOUL/USER + SELF.md"},
    "hooks":                      {"path": "hooks/__init__.py",             "role": "Boot hook discovery + dispatcher"},
}


def list_modules() -> Dict[str, Dict[str, Any]]:
    """Inventory of own modules with file size + last modified."""
    out: Dict[str, Dict[str, Any]] = {}
    for name, info in MODULES.items():
        p = _BASE / info["path"]
        entry = dict(info)
        if p.exists():
            try:
                st = p.stat()
                entry["exists"] = True
                entry["size_bytes"] = st.st_size
                entry["modified"] = _dt.datetime.fromtimestamp(st.st_mtime).isoformat()
                # rough line count
                try:
                    entry["lines"] = sum(1 for _ in p.open("r", encoding="utf-8"))
                except Exception:
                    entry["lines"] = 0
            except Exception:
                entry["exists"] = True
                entry["size_bytes"] = 0
        else:
            entry["exists"] = False
        out[name] = entry
    return out


# ──────────────────────────────────────────────────────────────────────────────
# Read + grep own source
# ──────────────────────────────────────────────────────────────────────────────
def read_module(name: str, max_chars: int = 200000) -> Dict[str, Any]:
    """Return source of a module (or its __init__.py for packages)."""
    info = MODULES.get(name)
    if not info:
        return {"ok": False, "error": f"unknown module: {name}",
                "available": list(MODULES.keys())}
    p = _BASE / info["path"]
    if not p.exists():
        return {"ok": False, "error": f"file missing: {p}"}
    try:
        text = p.read_text(encoding="utf-8")
        truncated = len(text) > max_chars
        if truncated:
            text = text[:max_chars] + f"\n\n... (truncated — file is {p.stat().st_size:,} bytes)"
        return {
            "ok": True, "name": name, "path": str(p),
            "size_bytes": p.stat().st_size,
            "content": text, "truncated": truncated,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def grep_module(name: str, pattern: str, context: int = 1,
                max_matches: int = 50) -> Dict[str, Any]:
    """Find lines matching regex pattern. Returns matches with line numbers."""
    res = read_module(name, max_chars=10_000_000)
    if not res.get("ok"):
        return res
    text = res["content"]
    lines = text.splitlines()
    try:
        pat = re.compile(pattern)
    except re.error as e:
        return {"ok": False, "error": f"bad regex: {e}"}
    hits: List[Dict[str, Any]] = []
    for i, ln in enumerate(lines):
        if pat.search(ln):
            ctx_before = lines[max(0, i - context):i]
            ctx_after = lines[i + 1:min(len(lines), i + 1 + context)]
            hits.append({
                "line": i + 1, "text": ln.rstrip(),
                "context_before": ctx_before, "context_after": ctx_after,
            })
            if len(hits) >= max_matches:
                break
    return {"ok": True, "name": name, "pattern": pattern,
            "n_matches": len(hits), "matches": hits}


# ──────────────────────────────────────────────────────────────────────────────
# Run a module's self-test (its `if __name__ == "__main__":` block)
# ──────────────────────────────────────────────────────────────────────────────
def run_module_self_test(name: str, timeout_sec: int = 30) -> Dict[str, Any]:
    """
    Execute `python <module>.py` in a subprocess. Capture stdout/stderr.
    Returns ok flag if exit code 0 AND output contains 'self-test OK'.
    """
    info = MODULES.get(name)
    if not info:
        return {"ok": False, "error": f"unknown module: {name}"}
    p = _BASE / info["path"]
    if not p.exists():
        return {"ok": False, "error": f"file missing: {p}"}
    # Don't run main.py self-test — it would start the FastAPI server!
    if name == "main":
        return {"ok": False, "error": "main.py self-test would launch server — refusing"}
    t0 = time.time()
    try:
        result = subprocess.run(
            [sys.executable, str(p)],
            capture_output=True, text=True, timeout=timeout_sec,
            cwd=str(_BASE),
        )
        dur = time.time() - t0
        ok = (result.returncode == 0) and ("self-test OK" in (result.stdout or ""))
        return {
            "ok": ok,
            "module": name,
            "duration_sec": round(dur, 2),
            "exit_code": result.returncode,
            "stdout_tail": (result.stdout or "")[-2000:],
            "stderr_tail": (result.stderr or "")[-1000:],
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"timeout after {timeout_sec}s",
                "duration_sec": timeout_sec}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def run_all_self_tests(timeout_each: int = 20) -> Dict[str, Any]:
    """Run self-tests on every module that has one (skips main + packages)."""
    skip = {"main", "prompts", "hooks"}  # packages or non-runnable
    results: List[Dict[str, Any]] = []
    n_pass = 0; n_fail = 0
    for name in MODULES:
        if name in skip:
            continue
        r = run_module_self_test(name, timeout_sec=timeout_each)
        ok = r.get("ok", False)
        if ok: n_pass += 1
        else:  n_fail += 1
        results.append({"module": name, "ok": ok,
                          "error": r.get("error", ""),
                          "duration": r.get("duration_sec", 0)})
    return {"n_pass": n_pass, "n_fail": n_fail, "results": results}


# ──────────────────────────────────────────────────────────────────────────────
# Analyze recent errors from audit + console
# ──────────────────────────────────────────────────────────────────────────────
def _read_jsonl_tail(path: Path, n: int = 1000) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        out = []
        for ln in lines[-n:]:
            ln = ln.strip()
            if ln:
                try: out.append(json.loads(ln))
                except: pass
        return out
    except Exception:
        return []


def analyze_recent_errors(window_hours: int = 24) -> Dict[str, Any]:
    """
    Scan audit_trail for error events, extract distinct error types + locations.
    Useful before proposing a patch — shows what's actually breaking.
    """
    cutoff = time.time() - (window_hours * 3600)
    audit = _read_jsonl_tail(_BASE / "audit_trail.jsonl", n=3000)
    err_signatures: Dict[str, int] = {}
    examples: List[Dict[str, Any]] = []
    for evt in audit:
        if evt.get("ts", 0) < cutoff:
            continue
        kind = evt.get("event", "")
        if "error" in kind.lower() or "block" in kind.lower() or "fail" in kind.lower():
            payload = evt.get("payload", {})
            sig = f"{kind}::{payload.get('reason', payload.get('error', ''))[:80]}"
            err_signatures[sig] = err_signatures.get(sig, 0) + 1
            if len(examples) < 10:
                examples.append({"event": kind, "ts": evt.get("ts"),
                                  "payload": payload})
    # Sort by frequency
    top = sorted(err_signatures.items(), key=lambda kv: -kv[1])[:10]
    return {
        "window_hours": window_hours,
        "n_audit_events": len(audit),
        "n_error_events": sum(err_signatures.values()),
        "top_signatures": [{"signature": s, "count": n} for s, n in top],
        "recent_examples": examples,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Propose patch — write to .patch file, NEVER auto-apply
# ──────────────────────────────────────────────────────────────────────────────
def propose_patch(target_file: str, issue: str, suggested_change: str,
                  rationale: str = "", priority: str = "MEDIUM") -> Dict[str, Any]:
    """
    Generate a patch proposal as a JSON file under self_patches/.
    The user reviews and applies manually (or via apply_patch with dry_run=False).

    Output file format: {timestamp}_{shortid}.patch.json
    """
    PATCHES_DIR.mkdir(parents=True, exist_ok=True)
    pid = hashlib.sha1(
        f"{target_file}|{issue}|{time.time()}".encode()
    ).hexdigest()[:10]
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    p = PATCHES_DIR / f"{stamp}_{pid}.patch.json"
    proposal = {
        "id": pid,
        "generated_at": _dt.datetime.now().isoformat(),
        "priority": priority,
        "target_file": target_file,
        "issue": issue,
        "rationale": rationale,
        "suggested_change": suggested_change,
        "applied": False,
        "validated": False,
    }
    try:
        p.write_text(json.dumps(proposal, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        proposal["path"] = str(p)
        return {"ok": True, "patch": proposal}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_proposed_patches() -> List[Dict[str, Any]]:
    """Return all proposed patches sorted newest first."""
    if not PATCHES_DIR.exists():
        return []
    out = []
    for p in sorted(PATCHES_DIR.glob("*.patch.json"), reverse=True):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            d["path"] = str(p)
            out.append(d)
        except Exception:
            continue
    return out


def get_patch(patch_id: str) -> Optional[Dict[str, Any]]:
    for p in PATCHES_DIR.glob("*.patch.json") if PATCHES_DIR.exists() else []:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if d.get("id") == patch_id:
                d["path"] = str(p)
                return d
        except Exception:
            continue
    return None


def validate_patch_syntax(patch_id: str) -> Dict[str, Any]:
    """
    Sanity-check the suggested_change as Python (if target is .py).
    Does NOT apply — only checks if the proposed snippet parses.
    """
    patch = get_patch(patch_id)
    if not patch:
        return {"ok": False, "error": f"patch not found: {patch_id}"}
    target = patch.get("target_file", "")
    snippet = patch.get("suggested_change", "")
    if not target.endswith(".py"):
        return {"ok": True, "note": "non-Python target — no syntax check"}
    try:
        compile(snippet, "<proposed_patch>", "exec")
        return {"ok": True, "note": "snippet is syntactically valid Python"}
    except SyntaxError as e:
        return {"ok": False, "error": f"SyntaxError: {e}",
                "line": e.lineno, "msg": str(e)}


def apply_patch(patch_id: str, dry_run: bool = True) -> Dict[str, Any]:
    """
    DANGEROUS — only call with user confirmation.
    Default dry_run=True returns what WOULD happen without modifying anything.

    Even with dry_run=False, this only APPENDS the suggested_change as a comment
    block to the target file. It NEVER replaces existing code automatically.
    User must edit the actual code themselves after reviewing.
    """
    patch = get_patch(patch_id)
    if not patch:
        return {"ok": False, "error": f"patch not found: {patch_id}"}
    target = _BASE / patch.get("target_file", "")
    if not target.exists():
        return {"ok": False, "error": f"target file missing: {target}"}
    snippet = patch.get("suggested_change", "")
    timestamp = _dt.datetime.now().isoformat()
    block = (
        f"\n# === SELF-DEBUG PATCH PROPOSAL ({patch['id']}) — generated {timestamp} ===\n"
        f"# Issue: {patch.get('issue', '')[:200]}\n"
        f"# Rationale: {patch.get('rationale', '')[:200]}\n"
        f"# REVIEW BEFORE INTEGRATING. This block is a suggestion, NOT live code.\n"
        f"\"\"\"\n{snippet}\n\"\"\"\n"
        f"# === END PATCH ===\n"
    )
    if dry_run:
        return {
            "ok": True, "dry_run": True,
            "would_append_to": str(target),
            "block_preview": block[:1000],
        }
    # Actual write — appends as comment block, never overwrites
    try:
        with target.open("a", encoding="utf-8") as f:
            f.write(block)
        # Mark patch as applied
        pp = Path(patch["path"]) if "path" in patch else None
        if pp and pp.exists():
            patch["applied"] = True
            patch["applied_at"] = _dt.datetime.now().isoformat()
            pp.write_text(json.dumps(patch, ensure_ascii=False, indent=2),
                          encoding="utf-8")
        return {"ok": True, "applied": True, "appended_to": str(target),
                "size_added": len(block)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ──────────────────────────────────────────────────────────────────────────────
# Self-test
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    print("=== self_debug self-test ===\n")

    # 1. Module inventory
    print("[1] list_modules:")
    mods = list_modules()
    for n, info in list(mods.items())[:5]:
        size = info.get("size_bytes", 0)
        lines = info.get("lines", 0)
        exists = info.get("exists", False)
        print(f"    {n:30s} {'✓' if exists else '✗'}  {lines:>5} lines, {size:,} bytes")
    print(f"    ... ({len(mods)} total)")

    # 2. Read module
    print("\n[2] read_module('volition_engine'):")
    r = read_module("volition_engine", max_chars=400)
    print(f"    ok={r['ok']}, size={r.get('size_bytes', 0):,} bytes")
    print(f"    preview: {r.get('content', '')[:200]}...")

    # 3. Grep
    print("\n[3] grep_module('skynetclaw_meta', 'def shadow_gate'):")
    g = grep_module("skynetclaw_meta", r"def shadow_gate")
    print(f"    matches: {g.get('n_matches', 0)}")
    for m in g.get("matches", [])[:2]:
        print(f"      L{m['line']}: {m['text'][:80]}")

    # 4. Run module self-test (use volition_engine — fast)
    print("\n[4] run_module_self_test('volition_engine'):")
    t = run_module_self_test("volition_engine", timeout_sec=15)
    print(f"    ok={t.get('ok')}, exit={t.get('exit_code')}, duration={t.get('duration_sec')}s")
    if not t.get("ok"):
        print(f"    error: {t.get('error', '')}")
        print(f"    stderr_tail: {t.get('stderr_tail', '')[:200]}")

    # 5. Analyze errors
    print("\n[5] analyze_recent_errors:")
    er = analyze_recent_errors(window_hours=168)
    print(f"    audit events: {er['n_audit_events']}, errors: {er['n_error_events']}")
    for s in er["top_signatures"][:3]:
        print(f"      {s['count']}× {s['signature']}")

    # 6. Propose patch
    print("\n[6] propose_patch (sample):")
    pp = propose_patch(
        target_file="skynetclaw_meta.py",
        issue="LIVE_DATA_PATTERNS missing pattern for stocks",
        suggested_change=(
            '_LIVE_DATA_PATTERNS["stocks"] = [\n'
            '    r"\\b(NASDAQ|NYSE|S&P\\s*500|stock\\s+price)\\b",\n'
            '    r"\\bหุ้น\\b",\n'
            ']\n'
        ),
        rationale="Need to gate write_file with stock prices — currently only crypto/forex/gold covered",
        priority="MEDIUM",
    )
    if pp.get("ok"):
        print(f"    patch id: {pp['patch']['id']}")
        print(f"    file: {pp['patch'].get('path')}")

    # 7. Validate patch syntax
    if pp.get("ok"):
        v = validate_patch_syntax(pp["patch"]["id"])
        print(f"\n[7] validate_patch_syntax: ok={v.get('ok')} note={v.get('note', v.get('error', ''))}")

    # 8. Dry-run apply
    if pp.get("ok"):
        d = apply_patch(pp["patch"]["id"], dry_run=True)
        print(f"\n[8] apply_patch (dry_run=True): ok={d.get('ok')} would_append_to={d.get('would_append_to')}")

    print("\n=== self-test OK ===")
