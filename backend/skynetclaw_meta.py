"""
skynetclaw_meta.py
==================
Meta-cognition layer for SkynetClaw — drop-in module that adds programmatic
Genesis Mind L0 (Reality Anchor), L4 (Shadow Gate), and L7 (Echo Memory + Genome)
on top of the existing agent_run loop in main.py.

Design principles (FPCOS / ElmatadorZ Secret OS v1.0):
  - L0 / L4 / L7 are non-skippable.
  - Failure signatures are NEVER deleted (highest-value memory).
  - Every cognitive decision is hashed into AuditTrail (tamper-evident).
  - The model can ignore the system prompt; it CANNOT bypass these Python guards.

Wire-up (in main.py / agent_run):
  1. At top of agent_run:
        from skynetclaw_meta import meta_init, reality_anchor, retrieve_genome_hints
        meta = meta_init(req.task)
        anchor = reality_anchor(req.task)
        hints = retrieve_genome_hints(req.task)
        # inject `anchor` and `hints` as system messages

  2. Inside the tool-call loop, BEFORE exec_tool:
        from skynetclaw_meta import shadow_gate
        verdict = shadow_gate(name, args, action_sigs)
        if verdict.action == "BLOCK":
            yield agent_blocked event ; continue
        elif verdict.action == "CONFIRM":
            yield ask_user event ; halt
        # else CONSISTENT → proceed

  3. After exec_tool:
        from skynetclaw_meta import deposit_memory
        deposit_memory(name, args, result, ok=True/False)

  4. On TASK_COMPLETE:
        from skynetclaw_meta import extract_rules, audit_log
        extract_rules(meta, action_sigs, success=True)
        audit_log("session_complete", {...})

License: Apache-2.0 — ElmatadorZ / Bunyawat Dechanon
"""
from __future__ import annotations

import json
import re
import time
import hashlib
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

# ──────────────────────────────────────────────────────────────────────────────
# Paths — colocated with main.py
# ──────────────────────────────────────────────────────────────────────────────
_BASE = Path(__file__).parent
GENOME_PATH = _BASE / "atlas_genome.json"
AUDIT_PATH  = _BASE / "audit_trail.jsonl"
MEMORY_PATH = _BASE / "echo_memory.jsonl"

# ──────────────────────────────────────────────────────────────────────────────
# SAFETY DENYLIST (Bug 7 fix) — irreversible system commands
# ──────────────────────────────────────────────────────────────────────────────
# These regex patterns block the model from issuing destructive shell commands
# even if it tries. Match is case-insensitive on the joined command string.
DENYLIST_PATTERNS: List[str] = [
    r"\brm\s+-rf?\s+/",                 # rm -rf /
    r"\brm\s+-rf?\s+~",                 # rm -rf ~
    r"\brm\s+-rf?\s+[a-zA-Z]:[\\/]?\s*$",  # rm -rf D:\
    r"\bformat\s+[a-zA-Z]:",            # format C:
    r"\bdel\s+/[fsq]\s+[a-zA-Z]:[\\/]", # del /f /s /q C:\
    r"\bshutdown\b",                    # shutdown / shutdown -s
    r"\breboot\b",
    r"\bmkfs\b",                        # mkfs.ext4 etc
    r"\bdd\s+if=.*of=/dev/",            # dd if=... of=/dev/sda
    r"\b:>\s*/etc/",                    # truncate critical files
    r"\bnet\s+user\s+\S+\s+/(add|delete)\b",
    r"\breg\s+delete\b",                # registry delete
    r"\bicacls\s+.*\s+/grant\s+everyone",
    r"\bcurl\s+[^|]*\|\s*(bash|sh|powershell|cmd)\b",  # curl ... | bash
    r"\bwget\s+[^|]*\|\s*(bash|sh)\b",
]
_DENYLIST_RE = re.compile("|".join(DENYLIST_PATTERNS), re.IGNORECASE)

# Tools that need extra L4 scrutiny (destructive / irreversible)
_DESTRUCTIVE_TOOLS = {
    "delete_file", "shell_command", "run_python", "install_package",
    "kill_process", "move_file", "facebook_post", "telegram_send",
    "discord_send", "line_notify",
}

# ──────────────────────────────────────────────────────────────────────────────
# LIVE-DATA GATE — detects content that REQUIRES a tool call before being written
# ──────────────────────────────────────────────────────────────────────────────
# Maps category → patterns that indicate this category appears in text
_LIVE_DATA_PATTERNS = {
    "datetime": [
        r"\b\d{4}-\d{2}-\d{2}\b",            # 2026-05-06
        r"\bgenerated\s+on\b",
        r"\b\d{1,2}:\d{2}(:\d{2})?\s*(UTC|GMT|EST|JST|ICT|\+\d{2})", # 18:00 UTC
        r"วันที่.*\d|เวลา.*\d",
        r"\btoday\s+is\b",
    ],
    "gold": [
        r"\bgold\s+price\b", r"\busd\s*/\s*oz\b", r"\bthb\s*/\s*gram\b",
        r"\bspot\s+price\b.*gold", r"ราคาทอง", r"\b\d{2,3},?\d{3}\s*(usd|thb)\b.*oz",
    ],
    "crypto": [
        r"\bbtc\s+(price|ราคา)", r"\bbitcoin\s+(price|ราคา)",
        r"\beth\s+(price|ราคา)", r"\bethereum\s+(price|ราคา)",
        r"ราคา.*(bitcoin|btc|eth|crypto)",
    ],
    "forex": [
        r"\busd\s*/\s*thb\b", r"\beur\s*/\s*usd\b", r"\bgbp\s*/\s*usd\b",
        r"\bforex\s+rate\b", r"อัตราแลกเปลี่ยน", r"\bexchange\s+rate\b",
    ],
    "news": [
        r"\bbreaking\s+news\b", r"ข่าวล่าสุด", r"\blatest\s+news\b",
        r"\btoday'?s?\s+headlines?\b",
    ],
}

# Maps category → tools whose presence in the session SATISFIES the need
_LIVE_DATA_RESOLVERS = {
    "datetime": {"get_current_datetime"},
    "gold":     {"get_gold_price", "web_search", "get_news"},
    "crypto":   {"get_crypto_price", "web_search", "get_news"},
    "forex":    {"get_forex_rate", "web_search", "get_news"},
    "news":     {"get_news", "web_search"},
}


def detect_live_data_needs(text: str) -> Dict[str, List[str]]:
    """
    Scan text for live-data patterns. Returns {category: [satisfying tools]}.
    Empty dict = no live-data references detected.
    """
    if not text:
        return {}
    needs: Dict[str, List[str]] = {}
    for category, patterns in _LIVE_DATA_PATTERNS.items():
        for p in patterns:
            if re.search(p, text, re.IGNORECASE):
                needs[category] = sorted(_LIVE_DATA_RESOLVERS.get(category, set()))
                break
    return needs


def _tools_called_so_far(action_sigs: List[str]) -> set:
    """Extract tool names from action signatures. Handles the current format
    'tool_name(arg=val|...)' AND legacy 'tool_name:hint#hash' / 'tool_name#hash'.
    NOTE: the live-data gate depends on this — if it fails to extract the bare
    tool name, the gate thinks NO live tool was ever called and blocks every
    write that contains prices/dates."""
    out = set()
    for sig in (action_sigs or []):
        head = sig.split("(", 1)[0]   # 'get_crypto_price(symbols=BTC|...)' → name
        head = head.split("#", 1)[0]
        head = head.split(":", 1)[0]
        if head:
            out.add(head.strip())
    return out


# ──────────────────────────────────────────────────────────────────────────────
# VALUE-MATCH GATE — extract numbers from text, compare content vs tool results
# ──────────────────────────────────────────────────────────────────────────────
# Match: 12,345.67 | 12345.67 | 12,345 | 12.34 | 4,576.80
_NUMBER_RE = re.compile(
    r"(?<![A-Za-z\d])"                           # not preceded by letter/digit
    r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?![A-Za-z\d])"                            # not followed by letter/digit
)


def _canonical_number(n_str: str) -> Optional[str]:
    """'1,234.50' → '1234.5'.  '46798' → '46798'.  Returns None if unparsable."""
    try:
        v = float(n_str.replace(",", ""))
        if v == int(v):
            return str(int(v))
        # 4 decimal precision then strip trailing zeros
        s = f"{v:.4f}".rstrip("0").rstrip(".")
        return s if s else "0"
    except Exception:
        return None


def _extract_numbers(text: str) -> set:
    """Return canonical-string set of significant numbers in text."""
    if not text:
        return set()
    out = set()
    for m in _NUMBER_RE.findall(text):
        c = _canonical_number(m)
        if c is not None:
            out.add(c)
    return out


def value_match_check(content: str, tool_results_log: List[tuple],
                      threshold: float = 0.005) -> Dict[str, Any]:
    """
    Compare numeric values in `content` against those returned by tools so far.

    Args:
      content           — text the model is about to write
      tool_results_log  — [(tool_name, result_text), ...]
      threshold         — fuzzy match tolerance (0.005 = 0.5%)

    Returns dict:
      {
        "mismatches":  [list of canonical numbers in content NOT in tool history],
        "valid":       [sample of accepted numbers from tool results],
        "ok":          bool — True if no significant mismatches
      }

    Numbers below 100 or in 2020-2030 (year-like integers) are ignored.
    """
    content_nums = _extract_numbers(content)
    if not content_nums:
        return {"mismatches": [], "valid": [], "ok": True}

    tool_nums = set()
    for _name, _res in (tool_results_log or []):
        tool_nums |= _extract_numbers(_res or "")

    mismatches = []
    for n in content_nums:
        try:
            v = float(n)
        except Exception:
            continue
        # Skip trivial small numbers and year integers
        if v < 100:
            continue
        if 2020 <= v <= 2030 and "." not in n:
            continue
        # Skip pure-date-ish numbers (8-digit YYYYMMDD)
        if v >= 20200101 and v <= 20300101:
            continue
        if n in tool_nums:
            continue
        # Fuzzy match within threshold (handles 32.54 vs 32.54000, 46798 vs 46,798.00)
        close = False
        for tn in tool_nums:
            try:
                tv = float(tn)
                if tv > 0 and abs(v - tv) / max(abs(tv), 1.0) < threshold:
                    close = True
                    break
            except Exception:
                pass
        if not close:
            mismatches.append(n)

    # sort suspicious by magnitude (largest first — biggest red flags)
    mismatches.sort(key=lambda x: -float(x))
    valid_sample = sorted(
        (n for n in tool_nums if float(n) >= 100),
        key=lambda x: -float(x),
    )[:6]

    return {
        "mismatches": mismatches[:6],
        "valid": valid_sample,
        "ok": not mismatches,
    }

# ──────────────────────────────────────────────────────────────────────────────
# Datatypes
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class MetaSession:
    """Per-run cognitive context. Lives in memory for the duration of agent_run."""
    session_id: str
    task: str
    started_at: float
    anchor: Dict[str, List[str]] = field(default_factory=dict)
    hints: List[str] = field(default_factory=list)
    decisions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class GateVerdict:
    """L4 Shadow Gate output."""
    verdict: str            # CONSISTENT | FRAGILE | REBUILD
    action: str             # PROCEED | CONFIRM | BLOCK
    reason: str             # human-readable
    confidence: float       # 0.0–1.0
    blind_spot: Optional[str] = None


# ──────────────────────────────────────────────────────────────────────────────
# Genome I/O — atomic read/write (never lose Genome to a partial write)
# ──────────────────────────────────────────────────────────────────────────────
_DEFAULT_GENOME = {
    "version": 1,
    "updated_at": 0,
    "strategy_rules": [],
    "execution_paths": [],
    "failure_map": [],
    "scenario_weights": {},
}


def _load_genome() -> Dict[str, Any]:
    if not GENOME_PATH.exists():
        return dict(_DEFAULT_GENOME)
    try:
        return json.loads(GENOME_PATH.read_text(encoding="utf-8"))
    except Exception:
        # Genome corrupted — back it up and start fresh, but NEVER auto-delete
        backup = GENOME_PATH.with_suffix(f".corrupt.{int(time.time())}.json")
        try:
            GENOME_PATH.rename(backup)
        except Exception:
            pass
        return dict(_DEFAULT_GENOME)


def _save_genome(g: Dict[str, Any]) -> None:
    g["updated_at"] = int(time.time())
    tmp = GENOME_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(g, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(GENOME_PATH)  # atomic on same FS


# ──────────────────────────────────────────────────────────────────────────────
# AuditTrail — append-only, hash-chained (tamper-evident)
# ──────────────────────────────────────────────────────────────────────────────
def _last_audit_hash() -> str:
    if not AUDIT_PATH.exists():
        return "GENESIS"
    try:
        with AUDIT_PATH.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            # Read last ~2 KB to find last newline
            f.seek(max(0, size - 2048))
            tail = f.read().decode("utf-8", errors="replace").splitlines()
        for line in reversed(tail):
            if line.strip():
                return json.loads(line).get("hash", "GENESIS")
    except Exception:
        pass
    return "GENESIS"


def audit_log(event: str, payload: Dict[str, Any]) -> str:
    """Append a tamper-evident event. Returns the new hash."""
    prev = _last_audit_hash()
    ts = time.time()
    body = {
        "ts": ts,
        "event": event,
        "payload": payload,
        "prev": prev,
    }
    digest = hashlib.sha256(
        json.dumps(body, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    body["hash"] = digest
    with AUDIT_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(body, ensure_ascii=False) + "\n")
    return digest


# ──────────────────────────────────────────────────────────────────────────────
# Echo Memory (append-only deposit log)
# ──────────────────────────────────────────────────────────────────────────────
def deposit_memory(
    session_id: str,
    name: str,
    args: Dict[str, Any],
    result_preview: str,
    ok: bool,
) -> None:
    """Record one tool execution. Used later by extract_rules."""
    entry = {
        "ts": time.time(),
        "session_id": session_id,
        "tool": name,
        "args_sig": _stable_sig(name, args),
        "ok": ok,
        "preview": (result_preview or "")[:200],
    }
    try:
        with MEMORY_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # memory is best-effort; never break the agent loop on memory I/O


# ──────────────────────────────────────────────────────────────────────────────
# Stable action signature (Bug 4 fix — hash full content, no 80-char truncation)
# ──────────────────────────────────────────────────────────────────────────────
def _stable_sig(name: str, args: Dict[str, Any]) -> str:
    """Tool signature that does NOT collide on long file contents."""
    try:
        canonical = json.dumps(args or {}, ensure_ascii=False, sort_keys=True)
    except Exception:
        canonical = repr(args)
    h = hashlib.sha1(canonical.encode("utf-8")).hexdigest()[:12]
    # Keep a human hint for logs (path/cmd if present)
    hint = ""
    for k in ("path", "command", "url", "name", "source"):
        v = (args or {}).get(k)
        if v:
            hint = f":{str(v)[:60]}"
            break
    return f"{name}{hint}#{h}"


# ──────────────────────────────────────────────────────────────────────────────
# L0 — Reality Anchor
# ──────────────────────────────────────────────────────────────────────────────
def reality_anchor(task: str) -> Dict[str, List[str]]:
    """
    Split the user's task into Known / Inferred / Unknown bins.
    Pure heuristic — no LLM call. Cheap to run on every request.

    Known    : entities the task literally names (paths, URLs, numbers, quoted strings)
    Inferred : intent verbs we can map to tool categories
    Unknown  : pronouns / vague nouns that have no concrete referent
    """
    t = task or ""
    known: List[str] = []
    inferred: List[str] = []
    unknown: List[str] = []

    # Known: absolute paths, URLs, quoted strings, numbers with units
    known.extend(re.findall(r"[A-Za-z]:\\[^\s'\"]+", t))         # Windows paths
    known.extend(re.findall(r"/[\w\-./]+", t))                     # POSIX paths
    known.extend(re.findall(r"https?://\S+", t))                   # URLs
    known.extend(re.findall(r'"([^"]+)"', t))                      # double-quoted
    known.extend(re.findall(r"'([^']+)'", t))                      # single-quoted
    known.extend(re.findall(r"\b\d+(?:\.\d+)?\s*(?:KB|MB|GB|TB|s|ms|h|d)\b", t, re.I))

    # Inferred: intent verbs (Thai + English) → tool category guess
    intent_map = [
        (r"\b(create|build|make|generate|สร้าง|ทำ|เขียน)\b", "build → write_file/create_folder"),
        (r"\b(read|open|show|view|อ่าน|ดู|เปิด)\b",          "read → read_file/list_files"),
        (r"\b(delete|remove|rm|ลบ)\b",                       "destructive → delete_file (REQUIRES L4)"),
        (r"\b(install|pip|npm|ติดตั้ง)\b",                   "install → install_package"),
        (r"\b(run|execute|รัน|เรียกใช้)\b",                  "execute → run_python/shell_command"),
        (r"\b(search|find|grep|ค้นหา|หา)\b",                 "search → web_search/find_files"),
        (r"\b(send|post|message|ส่ง)\b",                     "outbound → telegram/discord (REQUIRES L4)"),
        (r"\b(price|ราคา)\b.*\b(gold|btc|ทอง|บิทคอย)\b",     "live data → get_gold_price/get_crypto_price"),
    ]
    for pat, label in intent_map:
        if re.search(pat, t, re.I):
            inferred.append(label)

    # Unknown: vague pronouns with no antecedent
    vague_terms = ["it", "this", "that", "อันนั้น", "อันนี้", "มัน", "the file", "the folder"]
    for v in vague_terms:
        if re.search(rf"\b{re.escape(v)}\b", t, re.I) and not known:
            unknown.append(v)

    # Empty bins are still useful — explicit "none"
    return {
        "Known":    known    or ["(none extracted from literal task)"],
        "Inferred": inferred or ["(no clear intent verbs)"],
        "Unknown":  unknown  or ["(no vague references — all referents resolvable)"],
    }


# ──────────────────────────────────────────────────────────────────────────────
# L7 — Genome retrieval (called at start of agent_run)
# ──────────────────────────────────────────────────────────────────────────────
def retrieve_genome_hints(task: str, top_k: int = 3) -> List[str]:
    """
    Pull the top-K most relevant Genome entries to inject as system hints.
    Relevance = simple keyword overlap (no embeddings needed for v1).
    Always includes ALL matching failure_map entries (failures > recency).
    """
    g = _load_genome()
    task_words = set(re.findall(r"\w+", (task or "").lower()))
    if not task_words:
        return []

    scored: List[tuple] = []
    for rule in g.get("strategy_rules", []):
        text = (rule.get("if", "") + " " + rule.get("then", "")).lower()
        rw = set(re.findall(r"\w+", text))
        overlap = len(task_words & rw)
        if overlap >= 2:
            scored.append((overlap * rule.get("confidence", 0.5), "RULE", rule))

    for path in g.get("execution_paths", []):
        rw = set(re.findall(r"\w+", path.get("task_pattern", "").lower()))
        overlap = len(task_words & rw)
        if overlap >= 2:
            scored.append((overlap * path.get("success_rate", 0.5), "PATH", path))

    scored.sort(key=lambda x: x[0], reverse=True)
    hints: List[str] = []
    for _, kind, item in scored[:top_k]:
        if kind == "RULE":
            hints.append(f"[GENOME RULE] IF {item.get('if')} THEN {item.get('then')} (confidence {item.get('confidence',0):.2f})")
        else:
            seq = " → ".join(item.get("successful_sequence", [])[:6])
            hints.append(f"[GENOME PATH] '{item.get('task_pattern')}' worked via: {seq} (success_rate {item.get('success_rate',0):.2f})")

    # ALWAYS include matching failures — failures are non-negotiable warnings
    for fail in g.get("failure_map", []):
        fw = set(re.findall(r"\w+", fail.get("signature", "").lower()))
        if len(task_words & fw) >= 1:
            hints.append(f"[GENOME FAILURE] Avoid: {fail.get('signature')} — {fail.get('rationale')}")

    return hints


# ──────────────────────────────────────────────────────────────────────────────
# L4 — Shadow Gate (programmatic, NOT prompt-only)
# ──────────────────────────────────────────────────────────────────────────────
def shadow_gate(
    name: str,
    args: Dict[str, Any],
    action_sigs: List[str],
    session_id: str = "",
    tool_results_log: Optional[List[tuple]] = None,
) -> GateVerdict:
    """
    Critique a proposed tool call BEFORE exec_tool runs.
    Returns CONSISTENT (proceed), FRAGILE (proceed with caveat), or
    REBUILD (block / ask user).

    Pure rule-based — zero LLM cost. Runs on every tool call.

    `tool_results_log` is an optional [(tool_name, result_text), ...] list
    used by the VALUE-MATCH GATE to detect numerical hallucination.
    """
    args = args or {}

    # --- Rule 0a: LIVE-DATA GATE — must call live tool before writing live data ---
    if name in ("write_file", "edit_file", "write_obsidian_note"):
        content = args.get("content", "") or args.get("new_text", "") or ""
        needs = detect_live_data_needs(content)
        if needs:
            called = _tools_called_so_far(action_sigs)
            unsatisfied = []
            for category, resolvers in needs.items():
                # If NONE of the satisfying tools were called → unsatisfied
                if not (set(resolvers) & called):
                    unsatisfied.append((category, resolvers))
            if unsatisfied:
                cats     = ", ".join(c[0] for c in unsatisfied)
                first    = unsatisfied[0]
                suggest  = first[1][0] if first[1] else "a live-data tool"
                _LIVE_TOOLS = {"get_news", "get_crypto_price", "get_gold_price",
                               "get_forex_rate", "web_search", "http_request"}
                # If the model already fetched SOME live data this session, do NOT
                # hard-block the write. Hard-blocking every multi-data dashboard
                # (e.g. gold+silver+crypto+news where only some categories were
                # fetched) deadlocks the agent — it can never produce the artifact
                # and gets stuck. Proceed with a caveat; the VALUE-MATCH gate below
                # still blocks fabricated NUMBERS. Hard-block only when the model
                # fetched ZERO live data at all (pure fabrication).
                if _LIVE_TOOLS & set(called):
                    audit_log("shadow_gate.soft", {
                        "session": session_id, "tool": name,
                        "reason": "partial_live_data",
                        "unsatisfied": [c[0] for c in unsatisfied],
                    })
                    return GateVerdict(
                        verdict="FRAGILE",
                        action="PROCEED",
                        reason=(f"partial live data: {cats} not individually fetched — "
                                f"proceeding (value-match gate still enforced)"),
                        confidence=0.55,
                        blind_spot="some live-data categories were not fetched per-item",
                    )
                audit_log("shadow_gate.block", {
                    "session": session_id, "tool": name,
                    "reason": "live_data_unsatisfied",
                    "unsatisfied": [c[0] for c in unsatisfied],
                })
                return GateVerdict(
                    verdict="REBUILD",
                    action="BLOCK",
                    reason=(
                        f"Content contains {cats} data but no live-data tool was called this session. "
                        f"Call {suggest} FIRST, then write the file using the real values. "
                        f"Do NOT hardcode prices/dates/rates."
                    ),
                    confidence=0.92,
                    blind_spot="model is fabricating market/time data instead of fetching it",
                )

        # --- Rule 0b: VALUE-MATCH GATE ---
        # Even if a live tool WAS called, check that the numbers being written
        # actually appear in the tool results. Catches the case where the model
        # calls get_gold_price → gets ฿46,798 → then writes "44,600" anyway.
        if tool_results_log:
            vm = value_match_check(content, tool_results_log)
            if not vm["ok"]:
                mism = vm["mismatches"]
                valid = vm["valid"]
                audit_log("shadow_gate.block", {
                    "session": session_id, "tool": name,
                    "reason": "value_match_failed",
                    "mismatches": mism, "valid_sample": valid,
                })
                return GateVerdict(
                    verdict="REBUILD",
                    action="BLOCK",
                    reason=(
                        f"VALUE-MATCH FAILED: Numbers {mism[:3]} in your content do NOT "
                        f"appear in any tool result this session. "
                        f"Tool results returned these values: {valid[:5]}. "
                        f"Re-write the file using the EXACT numbers from tool results. "
                        f"Do not paraphrase, do not substitute, do not round."
                    ),
                    confidence=0.88,
                    blind_spot="model fetched real data then wrote different numbers",
                )

    # --- Rule 1: SAFETY_DENYLIST hard block ---
    if name in ("shell_command", "run_python"):
        cmd_text = args.get("command", "") or args.get("code", "")
        if _DENYLIST_RE.search(cmd_text):
            audit_log("shadow_gate.block", {
                "session": session_id, "tool": name, "reason": "denylist",
                "snippet": cmd_text[:200],
            })
            return GateVerdict(
                verdict="REBUILD",
                action="BLOCK",
                reason=f"Command matches SAFETY_DENYLIST. Refusing to execute: {cmd_text[:120]}",
                confidence=1.0,
                blind_spot="model proposed irreversible system command",
            )

    # --- Rule 2: destructive on system folders → require user confirm ---
    if name in ("delete_file", "move_file"):
        target = (args.get("path") or args.get("source") or "").strip()
        if _is_system_folder(target):
            return GateVerdict(
                verdict="FRAGILE",
                action="CONFIRM",
                reason=f"Destructive operation on system folder: {target}",
                confidence=0.7,
                blind_spot="path may be load-bearing — user must confirm",
            )

    # --- Rule 3: oscillation detector (Bug 6 fix — A-B-A-B pattern) ---
    sig = _stable_sig(name, args)
    last6 = action_sigs[-6:]
    if len(last6) == 6 and len(set(last6)) <= 2:
        return GateVerdict(
            verdict="REBUILD",
            action="BLOCK",
            reason=f"Oscillation detected — last 6 actions cycle between {len(set(last6))} signatures",
            confidence=0.95,
            blind_spot="model is bouncing between two states; not progressing",
        )

    # --- Rule 4: outbound messaging without explicit user request ---
    if name in ("telegram_send", "discord_send", "line_notify", "facebook_post"):
        # If the session task didn't mention sending → flag
        return GateVerdict(
            verdict="FRAGILE",
            action="CONFIRM",
            reason=f"Outbound message via {name} — confirm recipient and content before send",
            confidence=0.6,
        )

    # --- Default: pass ---
    return GateVerdict(
        verdict="CONSISTENT",
        action="PROCEED",
        reason="no critical flag",
        confidence=0.85,
    )


def _is_system_folder(p: str) -> bool:
    if not p:
        return False
    pl = p.lower().replace("/", "\\")
    sys_prefixes = (
        "c:\\windows", "c:\\program files", "c:\\programdata",
        "c:\\users\\default", "/etc", "/usr", "/bin", "/sbin", "/var", "/boot",
    )
    return any(pl.startswith(s) for s in sys_prefixes) or pl in ("c:\\", "d:\\", "/")


# ──────────────────────────────────────────────────────────────────────────────
# Session lifecycle + rule extraction
# ──────────────────────────────────────────────────────────────────────────────
def meta_init(task: str) -> MetaSession:
    sid = hashlib.sha1(f"{task}:{time.time()}".encode()).hexdigest()[:10]
    s = MetaSession(
        session_id=sid,
        task=(task or "")[:500],
        started_at=time.time(),
        anchor=reality_anchor(task),
        hints=retrieve_genome_hints(task),
    )
    audit_log("session.start", {"session": sid, "task_preview": s.task[:200]})
    return s


def extract_rules(meta: MetaSession, action_sigs: List[str], success: bool) -> Dict[str, Any]:
    """
    After a session ends, distill what was learned and write to Genome.
    Conservative: only proposes rules with evidence_count >= 1 → caller
    can decide whether to auto-merge (LOW confidence) or ask user (HIGH).
    """
    g = _load_genome()
    delta: Dict[str, Any] = {"new_path": None, "new_failure": None}

    if success and len(action_sigs) >= 2:
        # Extract a tool-name sequence (ignore hashes/hints in sig)
        seq = [s.split(":", 1)[0].split("#", 1)[0] for s in action_sigs]
        # Look for an existing path with the same sequence prefix
        existing = next(
            (p for p in g["execution_paths"]
             if p.get("successful_sequence", [])[:len(seq)] == seq),
            None,
        )
        if existing:
            existing["n_runs"] = int(existing.get("n_runs", 0)) + 1
            existing["success_rate"] = (
                existing.get("success_rate", 0.5) * 0.85 + 1.0 * 0.15
            )
        else:
            new_path = {
                "task_pattern": meta.task[:120],
                "successful_sequence": seq,
                "success_rate": 0.6,  # provisional — needs more runs
                "n_runs": 1,
                "first_seen": int(meta.started_at),
            }
            g["execution_paths"].append(new_path)
            delta["new_path"] = new_path

    if not success and action_sigs:
        last_sig = action_sigs[-1]
        # Failures are NEVER auto-merged into rules — only logged for retrieval
        new_fail = {
            "id": f"fail_{hashlib.sha1(last_sig.encode()).hexdigest()[:8]}",
            "signature": last_sig,
            "first_seen": int(meta.started_at),
            "task_context": meta.task[:200],
            "resolution": "PENDING_REVIEW",
            "rationale": "session ended without TASK_COMPLETE — investigate manually",
        }
        # Dedupe by signature
        if not any(f.get("signature") == last_sig for f in g["failure_map"]):
            g["failure_map"].append(new_fail)
            delta["new_failure"] = new_fail

    _save_genome(g)
    audit_log("session.end", {
        "session": meta.session_id,
        "success": success,
        "n_actions": len(action_sigs),
        "delta": {k: bool(v) for k, v in delta.items()},
    })
    return delta


# ──────────────────────────────────────────────────────────────────────────────
# Convenience: format anchor + hints as a system-message string
# ──────────────────────────────────────────────────────────────────────────────
def format_meta_preamble(meta: MetaSession) -> str:
    a = meta.anchor
    lines = [
        "## L0 REALITY ANCHOR (programmatic — do not contradict):",
        f"  Known    : {', '.join(a.get('Known', []))[:300]}",
        f"  Inferred : {', '.join(a.get('Inferred', []))[:300]}",
        f"  Unknown  : {', '.join(a.get('Unknown', []))[:300]}",
    ]
    if meta.hints:
        lines.append("\n## L7 GENOME HINTS (from past sessions — use or override consciously):")
        for h in meta.hints:
            lines.append(f"  • {h}")
    lines.append(
        "\n## L4 SHADOW GATE is ACTIVE — destructive tool calls will be auto-blocked or require user confirm."
    )
    return "\n".join(lines)


def current_datetime_banner(tz: str = "Asia/Bangkok") -> str:
    """
    Build a system-prompt block with the ACTUAL current datetime so the model
    never has to guess. Cheap — no tool call needed; uses server clock.
    Includes both UTC and Bangkok time + ISO date.

    Returns a multiline string that can be prepended to any agent prompt.
    """
    import datetime as _dt
    try:
        from zoneinfo import ZoneInfo
        now_tz = _dt.datetime.now(ZoneInfo(tz))
    except Exception:
        now_tz = _dt.datetime.now()
    now_utc = _dt.datetime.now(_dt.timezone.utc)

    lines = [
        "## ⏰ ACTUAL CURRENT TIME (server clock — authoritative):",
        f"  Local ({tz}): {now_tz.strftime('%Y-%m-%d %H:%M:%S %Z')}",
        f"  UTC          : {now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}",
        f"  ISO date     : {now_tz.date().isoformat()}",
        f"  Day of week  : {now_tz.strftime('%A')}",
        "",
        "USE these values for any 'Generated on:', 'Today is:', timestamps in files.",
        "Do NOT guess the date or use training cutoff. Do NOT call get_current_datetime",
        "for the date itself — it is provided here. Call get_current_datetime ONLY if",
        "the user explicitly asks for fresh server time mid-session.",
    ]
    return "\n".join(lines)


def live_data_directive() -> str:
    """
    System-prompt addendum that tells the model: NEVER hardcode market data.
    Always call the corresponding live-data tool first. Shadow Gate will
    block write_file calls that violate this — surface the rule up-front
    so the model doesn't waste a step.
    """
    return (
        "## 🛡️ LIVE-DATA RULE (Shadow Gate enforces this — violations are auto-blocked):\n"
        "  When you intend to write/edit a file or note that contains:\n"
        "    • gold price (USD/oz, THB/gram)        → call get_gold_price FIRST\n"
        "    • crypto price (BTC, ETH, SOL, ฯลฯ)    → call get_crypto_price FIRST\n"
        "    • forex rate (USD/THB, EUR/USD, ฯลฯ)   → call get_forex_rate FIRST\n"
        "    • current news / breaking news         → call get_news FIRST\n"
        "    • a specific timestamp inside content  → use the ⏰ ACTUAL CURRENT TIME above\n"
        "\n"
        "  NEVER hardcode prices, rates, or fabricated 'spot price' values.\n"
        "  NEVER use training-cutoff prices as if they were current.\n"
        "  If the user asks for analysis with live data — fetch the data first, THEN write."
    )


# ──────────────────────────────────────────────────────────────────────────────
# Self-test (run: python skynetclaw_meta.py)
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    print("=== skynetclaw_meta self-test ===\n")

    # L0 test
    task = 'สร้าง Telegram Bot ที่ "D:\\Skynet_Bridge" ใช้ python และส่งราคาทอง'
    a = reality_anchor(task)
    print("[L0] Reality Anchor:")
    for k, v in a.items():
        print(f"  {k}: {v}")

    # L4 test — should BLOCK
    print("\n[L4] Shadow Gate on `rm -rf D:\\`:")
    v = shadow_gate("shell_command", {"command": "rm -rf D:\\"}, [])
    print(f"  verdict={v.verdict} action={v.action} reason={v.reason}")
    assert v.action == "BLOCK", "denylist must block rm -rf D:\\"

    # L4 test — should PROCEED
    print("\n[L4] Shadow Gate on benign write_file:")
    v = shadow_gate("write_file", {"path": "D:\\Skynet_Bridge\\bot.py", "content": "print('hi')"}, [])
    print(f"  verdict={v.verdict} action={v.action} reason={v.reason}")
    assert v.action == "PROCEED", "benign write must pass"

    # L4 test — oscillation
    print("\n[L4] Shadow Gate on A-B-A-B-A-B oscillation:")
    sigs = ["a#1", "b#2"] * 3
    v = shadow_gate("write_file", {"path": "x"}, sigs)
    print(f"  verdict={v.verdict} action={v.action} reason={v.reason}")

    # Session lifecycle
    print("\n[L7] Session init + rule extraction:")
    m = meta_init(task)
    print(f"  session_id={m.session_id}")
    print(f"  preamble:\n{format_meta_preamble(m)}")
    delta = extract_rules(m, ["create_folder#1", "write_file:bot.py#2"], success=True)
    print(f"  delta={delta}")

    print("\n[AUDIT] Tail:")
    if AUDIT_PATH.exists():
        for line in AUDIT_PATH.read_text(encoding="utf-8").strip().splitlines()[-3:]:
            print(f"  {line}")

    print("\n=== self-test OK ===")
