"""
knowledge_seeking.py — OX-KNOWLEDGE-1 KNOWLEDGE SEEKING ENGINE
==============================================================
The House knew what TOOLS exist and which SUCCEEDED (OX-SKILL-1). It did NOT know
what KNOWLEDGE was missing, WHERE it lived, or HOW to acquire it — so an absent
capability became a hard stop, and the reflex was to ask the operator.

This engine adds ONLY a knowledge-seeking capability (no governance, council,
doctrine, runtime or architecture change). Pure execution intelligence: a
dependency-free, deterministic, model-free read-model — same convention as
knowledge_frontier / tool_intelligence. It distinguishes three states:

    KNOWN     — information already available (no gap).
    KNOWABLE  — not known, but a SOURCE is known → search it.
    UNKNOWN   — not known and no source can resolve it → operator (last resort).

Capabilities (exactly the OX-KNOWLEDGE-1 spec):

  1. KNOWLEDGE GAP DETECTION  — plan(): before execution, split a task into what
                                is KNOWN vs. KNOWABLE vs. UNKNOWN.
  2. KNOWLEDGE SOURCE REGISTRY— SOURCES / describe_sources(): the concrete places
                                knowledge lives (Skills · Artifacts · Workspace ·
                                Obsidian · GitHub · Documentation · Existing code),
                                each with HOW to search it (which tool).
  3. ACQUISITION ROUTING      — acquisition_order(): when a gap exists, SEARCH the
                                known sources first — do NOT immediately ask.
  4. LAST-RESORT CLARIFICATION— should_clarify(): ask the operator ONLY when the
                                information cannot be found and no source resolves
                                it (i.e. after discovery fails, or no source exists).

Ownership: owns NO persistent state. Pure functions over the task string + a few
environment probes (available tools, workspace path, vault, known facts).

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# ── 2. KNOWLEDGE SOURCE REGISTRY ─────────────────────────────────────────────
# Read-only. Each source: where knowledge lives + HOW the House searches it
# (which builtin tool) + the ordering priority (cheapest/most-local first).
SOURCES: Dict[str, Dict[str, Any]] = {
    "workspace":     {"label": "Workspace files", "priority": 1,
                      "tools": ["list_files", "find_files", "read_file"],
                      "how": "list/find/read files in the active workspace"},
    "code":          {"label": "Existing code", "priority": 2,
                      "tools": ["grep_search", "find_files", "read_file"],
                      "how": "grep the codebase for the symbol/module, then read it"},
    "artifacts":     {"label": "Artifacts", "priority": 3,
                      "tools": ["list_files", "read_file"],
                      "how": "read prior deliverables (artifacts/ + the mission ledger)"},
    "obsidian":      {"label": "Obsidian vault", "priority": 4,
                      "tools": ["search_obsidian", "read_obsidian_note"],
                      "how": "search the vault for a note that already captured it"},
    "skills":        {"label": "Skills", "priority": 5,
                      "tools": ["recall_archive", "query_learning"],
                      "how": "check the House's own skills/lessons for the capability"},
    "github":        {"label": "GitHub repositories", "priority": 6,
                      "tools": ["http_request", "web_search", "shell_command"],
                      "how": "fetch the repo (raw URL / git) or web-search the project"},
    "documentation": {"label": "Documentation / web", "priority": 7,
                      "tools": ["web_search", "http_request"],
                      "how": "search official docs / the web for the external fact"},
}


def describe_sources(available: Optional[Dict[str, bool]] = None) -> List[Dict[str, Any]]:
    """The registry as a discoverable, read-only list. `available` (optional)
    marks which sources the current environment can actually reach."""
    av = available or {}
    out = []
    for sid, s in sorted(SOURCES.items(), key=lambda kv: kv[1]["priority"]):
        out.append({"id": sid, "label": s["label"], "tools": list(s["tools"]),
                    "how": s["how"], "priority": s["priority"],
                    "available": av.get(sid, True)})
    return out


# ── 1. KNOWLEDGE GAP DETECTION — need signals → source ───────────────────────
# A "gap" is information the task must LOCATE or LEARN before it can proceed.
# Direct, fully-specified actions (list a given path, fetch a live price) are NOT
# gaps — the tool produces the answer directly. Each rule: (regex, source,
# operator_only, label). Operator-only needs have NO authoritative source; they
# still get a best-effort discovery source (so the House SEARCHES before asking).
_GAP_RULES: List[tuple] = [
    # explicit learning intent
    (re.compile(r"\b(how (do|can|to)\b|figure out|find out|look up|research|investigate|what is the|what'?s the|unfamiliar|don'?t know how)\b", re.I),
     "documentation", False, "explicit learning need"),
    # external systems / facts not built in
    (re.compile(r"\b(api|sdk|endpoint|webhook|oauth|library|package|dependency|framework|protocol|spec(ification)?|standard)\b", re.I),
     "documentation", False, "external system / API knowledge"),
    # a repo to fetch
    (re.compile(r"\b(repo|repository|github|gitlab|clone|upstream|pull request|\bPR\b)\b", re.I),
     "github", False, "repository knowledge"),
    # named-but-unlocated code targets (must find the thing first)
    (re.compile(r"\b(the|that|this|existing|current)\s+(auth|login|config(uration)?|module|function|class|method|component|handler|route|endpoint|schema|model|service|bug|error|regression|test|script|helper|util)s?\b", re.I),
     "code", False, "must locate existing code"),
    (re.compile(r"\bin (the|this|our) (code|repo|project|codebase|source)\b", re.I),
     "code", False, "must locate existing code"),
    # prior deliverables (allow an adjective or two: "previous quarterly report")
    (re.compile(r"\b(previous|earlier|last|prior|the)\s+(?:\w+\s+){0,2}(report|dashboard|artifact|output|pdf|deliverable|analysis|summary)\b", re.I),
     "artifacts", False, "prior artifact reference"),
    # captured knowledge in the vault
    (re.compile(r"\b(note|notes|vault|obsidian|knowledge ?base|second brain|wiki)\b", re.I),
     "obsidian", False, "captured-knowledge reference"),
    # a capability question
    (re.compile(r"\b(do you (support|have)|are you able|is there a (skill|capability)|which skill)\b", re.I),
     "skills", False, "capability / skill knowledge"),
    # ── operator-only (UNKNOWN: no authoritative source) — still try discovery ──
    (re.compile(r"\b(password|secret|api[- ]?key|token|credential|passphrase|private key|login details?)\b", re.I),
     None, True, "secret only the operator holds"),
    (re.compile(r"\bsend (it|this|that|the .{0,30}?) to\b|\b(my|the) (manager|boss|client|recipient|team lead)\b", re.I),
     "artifacts", True, "recipient the operator must name"),
    (re.compile(r"\b(which (one|option|format|approach)\b|do you (want|prefer)|your preference|prefer.{0,20}\?)", re.I),
     None, True, "preference only the operator can choose"),
]


def _available_map(available_tools: Optional[List[str]], workspace: Optional[str],
                   vault: Optional[str]) -> Dict[str, bool]:
    tools = set(available_tools or [])
    has = lambda *names: (not tools) or any(n in tools for n in names)  # empty list = assume all
    return {
        "workspace":     bool(workspace) and has("list_files", "find_files", "read_file"),
        "code":          bool(workspace) and has("grep_search", "find_files", "read_file"),
        "artifacts":     has("list_files", "read_file"),
        "obsidian":      bool(vault) and has("search_obsidian", "read_obsidian_note"),
        "skills":        has("recall_archive", "query_learning"),
        "github":        has("http_request", "web_search", "shell_command"),
        "documentation": has("web_search", "http_request"),
    }


def _fallback_source(av: Dict[str, bool]) -> Optional[str]:
    """A best-effort place to LOOK before asking the operator (the answer may
    have been recorded somewhere). None only if nothing is reachable."""
    for sid in ("artifacts", "obsidian", "workspace", "documentation"):
        if av.get(sid):
            return sid
    return None


def plan(task: str, *, available_tools: Optional[List[str]] = None,
         workspace: Optional[str] = None, vault: Optional[str] = None,
         known_facts: Optional[List[str]] = None,
         suppress_artifact_source: bool = False) -> Dict[str, Any]:
    """KNOWLEDGE GAP DETECTION. Returns the task split into KNOWN / KNOWABLE /
    UNKNOWN plus the acquisition routing. `known_facts` (e.g. house_state's
    what_we_know) lets an otherwise-knowable need be marked already-KNOWN.

    OX-INTENT-1: when `suppress_artifact_source` is set (the Artifact Registry
    already resolved an artifact for this request), gaps routed to the `artifacts`
    source are dropped so Knowledge Seeking stops re-interpreting the same
    reference — the Registry is the single source of truth for artifacts."""
    t = task or ""
    av = _available_map(available_tools, workspace, vault)
    known_blob = " \n".join(known_facts or []).lower()

    knowable: List[Dict[str, Any]] = []
    unknown: List[Dict[str, Any]] = []
    seen = set()
    for rx, src, operator_only, label in _GAP_RULES:
        m = rx.search(t)
        if not m:
            continue
        frag = m.group(0).strip().lower()[:60]
        key = (label, frag)
        if key in seen:
            continue
        seen.add(key)
        # already covered by a known fact → not a gap
        if frag and frag in known_blob:
            continue
        # OX-INTENT-1: the Artifact Registry already owns this reference
        if suppress_artifact_source and src == "artifacts":
            continue
        if operator_only:
            # UNKNOWN: no authoritative source. Attach a best-effort discovery
            # source so the House SEARCHES before it asks (search-first doctrine).
            disc = src if (src and av.get(src)) else _fallback_source(av)
            entry = {"need": label, "match": m.group(0).strip()[:80],
                     "source": disc, "operator_only": True,
                     "tools": list(SOURCES[disc]["tools"]) if disc else [],
                     "how": SOURCES[disc]["how"] if disc else "no source — must ask the operator"}
            unknown.append(entry)
        else:
            use = src if av.get(src) else ("documentation" if av.get("documentation") else _fallback_source(av))
            if not use:
                unknown.append({"need": label, "match": m.group(0).strip()[:80],
                                "source": None, "operator_only": True, "tools": [],
                                "how": "no reachable source — must ask the operator"})
                continue
            knowable.append({"need": label, "match": m.group(0).strip()[:80],
                             "source": use, "operator_only": False,
                             "tools": list(SOURCES[use]["tools"]), "how": SOURCES[use]["how"]})

    has_gap = bool(knowable or unknown)
    # KNOWN: the task references no missing knowledge — capabilities/inputs are
    # already in hand; proceed directly (no knowledge search needed).
    known_state = not has_gap
    return {
        "task": t[:200],
        "known": known_state,                 # True = nothing to seek
        "knowable": knowable,                  # gaps with a source → SEARCH
        "unknown": unknown,                    # gaps without a real source → operator
        "needs_search": any(g.get("source") for g in (knowable + unknown)),
        "sources": describe_sources(av),
    }


# ── 3. ACQUISITION ROUTING ────────────────────────────────────────────────────
def acquisition_order(p: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The ordered search plan: for every gap with a source, the source + tools,
    cheapest/most-local first. This is what the House does BEFORE asking."""
    steps: Dict[str, Dict[str, Any]] = {}
    for g in (p.get("knowable", []) + p.get("unknown", [])):
        sid = g.get("source")
        if not sid:
            continue
        slot = steps.setdefault(sid, {"source": sid, "label": SOURCES[sid]["label"],
                                      "tools": SOURCES[sid]["tools"],
                                      "priority": SOURCES[sid]["priority"], "needs": []})
        slot["needs"].append(g["need"])
    return sorted(steps.values(), key=lambda s: s["priority"])


# ── 4. LAST-RESORT CLARIFICATION GATE ─────────────────────────────────────────
def should_clarify(p: Dict[str, Any], discovered: Optional[Dict[str, bool]] = None) -> bool:
    """Ask the operator ONLY as a last resort.

    discovered=None (BEFORE search): never clarify while anything is still
      searchable — the House must search first. Clarify pre-search only when a
      gap exists for which NO source is reachable at all.
    discovered given (AFTER search, {need: found?}): clarify when a required gap
      remains unresolved despite discovery."""
    gaps = (p.get("knowable", []) + p.get("unknown", []))
    if not gaps:
        return False
    if discovered is None:
        # search-first: if any gap can still be searched, do NOT ask yet.
        if any(g.get("source") for g in gaps):
            return False
        # nothing is searchable → asking is the only remaining move.
        return True
    # post-discovery: anything still missing → ask.
    for g in gaps:
        if not discovered.get(g["need"], False):
            return True
    return False


# ── prompt rendering ──────────────────────────────────────────────────────────
def render_brief(p: Dict[str, Any]) -> str:
    """The KNOWLEDGE SEEKING prompt block injected before execution. Empty when
    the task is fully KNOWN (nothing to seek — avoid noise)."""
    if p.get("known") and not (p.get("knowable") or p.get("unknown")):
        return ""  # Test A: known capability → no knowledge-search guidance
    order = acquisition_order(p)
    L = ["## KNOWLEDGE SEEKING (resolve gaps by DISCOVERY first — ask the operator last):"]
    if p.get("knowable"):
        L.append("  KNOWABLE — missing, but the source is known. SEARCH before you ask:")
        for s in order:
            L.append(f"    • {s['label']}: {', '.join(s['tools'][:3])}  "
                     f"(for: {', '.join(sorted(set(s['needs'])))})")
    only_ask = [g for g in p.get("unknown", []) if not g.get("source")]
    if only_ask:
        L.append("  UNKNOWN — no source can resolve these; ask_user_options is justified:")
        for g in only_ask[:4]:
            L.append(f"    ? {g['need']}")
    L.append("  ROUTING: when a gap exists, search the sources above FIRST. "
             "Use ask_user_options ONLY after discovery fails or no source exists.")
    return "\n".join(L)
