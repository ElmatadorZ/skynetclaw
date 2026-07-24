"""
discovery.py — OX-1 DISCOVERY LAYER (read-only)
===============================================
THE HOUSE is an institution: it begins with RECORDS, not assumptions.

This layer lets the reasoning loop INVESTIGATE the House's own registries before
it plans. It is strictly READ-ONLY — it wraps existing read surfaces, creates no
state, no persistence, no shadow truth, and never writes.

    Request → DISCOVER → CLASSIFY → ROUTE → ACT
                                      ├─ STATE_LOOKUP → answer from records (no plan/council)
                                      ├─ MISSION      → hand discovery context to comprehend/plan
                                      └─ AMBIGUOUS    → context recovery → reclassify → (answer | ask)

Phase A: five query primitives over existing registries.
Phase B: priority order  Mission → House Mind → Timeline → Archive → Learning.
Phase C: classification AFTER discovery.
Phase D: every match carries confidence (likely + alternatives; never false certainty).
Phase E: read-through TTL cache (no persistence).
Phase F/G: route() orchestrator; clarification is the LAST resort.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

# ── existing read surfaces (read-only) ────────────────────────────────────────
import mission_command as _mc
import house_cognition as _hcog
import belief_timeline as _btl
import learning_engine as _le
try:
    import house_state as _hs
except Exception:
    _hs = None
try:
    import deliberation_archive as _arc
except Exception:
    _arc = None
try:
    import council_memory as _mem
except Exception:
    _mem = None

STATE_LOOKUP = "STATE_LOOKUP"
MISSION = "MISSION"
AMBIGUOUS = "AMBIGUOUS"
CHAT = "CHAT"

# Small talk is not an inquiry into owned state. Observed 2026-07-10:
# "สวัสดี skynet" (2 tokens) classified AMBIGUOUS → deictic recovery →
# no mission matched → fell back to a House Mind dump instead of a greeting.
# A greeting opener on a SHORT message routes to plain chat.
# NOTE: no \b after the group — Python's \b is unreliable around Thai
# characters; the ^ anchor plus the <=4-token gate in classify() do the work.
_GREETING_RE = re.compile(
    r"^(สวัสดี|หวัดดี|ดีครับ|ดีค่ะ|ดีจ้า|ทักทาย|ขอบคุณ|สบายดี|"
    r"(hello|hi|hey|yo|thanks)(?![a-z])|good\s*(morning|evening|afternoon|night)|thank\s+you)", re.I)

# ── Phase E: read-through cache (TTL only — NO persistence) ───────────────────
_TTL = 10.0  # seconds (within the 5–30s band)
_CACHE: Dict[str, Tuple[float, Any]] = {}


def _cached(key: str, fn: Callable[[], Any]) -> Any:
    now = time.time()
    hit = _CACHE.get(key)
    if hit and (now - hit[0]) < _TTL:
        return hit[1]
    try:
        val = fn()
    except Exception:
        val = None
    _CACHE[key] = (now, val)
    return val


def clear_cache() -> None:
    _CACHE.clear()


_WORD = re.compile(r"[\w฀-๿]+")


def _tokens(s: str) -> set:
    return {t.lower() for t in _WORD.findall(s or "") if len(t) > 1}


# ══════════════════════════════════════════════════════════════════════════════
# Phase A — the five discovery primitives (read-only)
# ══════════════════════════════════════════════════════════════════════════════
def query_missions() -> Dict[str, Any]:
    """Mission Center: active / paused / failed / completed + health + next action."""
    snap = _cached("missions", lambda: _mc.snapshot()) or {}
    return {
        "active": snap.get("active", []),
        "paused": snap.get("paused", []),
        "completed": snap.get("completed", []),
        "failed": snap.get("failed", []),
        "incomplete": snap.get("incomplete", []),      # ran out of steps (not errors)
        "interrupted": snap.get("interrupted", []),   # operator context switches
        "counts": snap.get("counts", {}),
        "house_next_action": snap.get("house_next_action", ""),
    }


def read_house_mind() -> Dict[str, Any]:
    """House Mind: objective / belief / confidence / known / unknown / risks / hypotheses."""
    s = _cached("housemind", lambda: _hcog.snapshot()) or {}
    risks: List[str] = []
    if _hs is not None:
        cur = _cached("hm_current", lambda: _hs.current())
        if cur:
            ans = _cached("hm_answer_" + cur["id"], lambda: _hs.answer(cur["id"])) or {}
            risks = list(ans.get("contradictions", []) or [])
    beliefs = s.get("beliefs", []) or []
    return {
        "objective": s.get("mission", ""),
        "belief": beliefs[0].get("belief", "") if beliefs else "",
        "confidence": s.get("confidence", 0.0),
        "known": s.get("known", []),
        "unknown": s.get("unknown", []),
        "risks": risks,
        "hypotheses": s.get("hypotheses", []),
        "next_action": s.get("next_action", {}),
        "state_id": s.get("state_id", ""),
    }


def query_timeline() -> Dict[str, Any]:
    """Timeline: recent activity / belief changes (the current belief-evolution chain)."""
    tl = _cached("timeline", lambda: _btl.timeline()) or {}
    nodes = tl.get("nodes", []) or []
    recent = sorted(nodes, key=lambda n: n.get("timestamp") or 0, reverse=True)[:8]
    return {"question": tl.get("question", ""), "recent": recent,
            "gaps": tl.get("gaps", []), "node_count": len(nodes)}


def query_learning() -> Dict[str, Any]:
    """Learning Registry: lessons / repeat failures / repeat successes / behavior changes."""
    l = _cached("learning", lambda: _le.snapshot()) or {}
    return {
        "lessons": l.get("lessons", []),
        "repeat_failures": l.get("repeat_failures", []),
        "repeat_successes": l.get("repeat_successes", []),
        "behavior_changes": l.get("behavior_changes", []),
        "counts": l.get("counts", {}),
    }


def recall_archive(directive: str = "") -> Dict[str, Any]:
    """Council Archive: prior deliberations + similar past missions (by recall)."""
    out: Dict[str, Any] = {"prior_deliberations": [], "similar": []}
    if _arc is not None:
        rows = _cached("archive", lambda: _arc.recent(limit=10))
        out["prior_deliberations"] = rows or []
    if _mem is not None and directive:
        try:
            out["similar"] = _mem.recall(directive, limit=5) or []
        except Exception:
            out["similar"] = []
    return out


# ══════════════════════════════════════════════════════════════════════════════
# Phase C — classification (runs AFTER discovery; rule-based, model-free)
# ══════════════════════════════════════════════════════════════════════════════
_LOOKUP_RE = re.compile(
    r"(งานค้าง|ค้าง|ล่าสุด|สถานะ|checkpoint|มีอะไร|อยู่ไหน|กี่|สรุป|คืบหน้า|"
    r"เรียนรู้|บทเรียน|ประวัติ|เปลี่ยน|what changed|what happened|status|pending|"
    r"progress|recent|history|learned|lesson|summary)", re.I)
_MISSION_RE = re.compile(
    r"(สร้าง|วิเคราะห์|แก้|เขียน|ออกแบบ|ทำให้|build|create|analy|fix|make|write|"
    r"implement|design|generate|add|refactor|deploy|set ?up|scaffold)", re.I)
_DEICTIC_RE = re.compile(
    r"^\s*(อันนี้|ตัวนี้|ตรงนั้น|อันนั้น|นี่|นั่น|ต่อ|ทำต่อ|continue|resume|this|that|it)\s*$",
    re.I)
# A status query that ALSO asks for reasoning ("why", "which tools are the
# bottleneck", "technically", "recommend", "analyze") must NOT be answered by
# the canned count template — it needs the model to reason over the records.
_ANALYTICAL_RE = re.compile(
    r"(คอขวด|เชิงเทคนิค|เจาะลึก|ทำไม|วิเคราะห์|ประเมิน|แนะนำ|ควร\w*|เพราะ|อย่างไร|จุดอ่อน|"
    r"ปรับปรุง|เครื่องมือ|bottleneck|why|analy|assess|recommend|evaluate|deep|technical|"
    r"weak|improve|which\s+tool|how\s+(can|do|to)|root\s*cause)", re.I)


def classify(request: str) -> str:
    r = (request or "").strip()
    # greetings/small talk first — a short hello is chat, not a state inquiry
    # (a greeting that CONTINUES into a task is longer and falls through)
    if _GREETING_RE.match(r) and len(_tokens(r)) <= 4:
        return CHAT
    if _DEICTIC_RE.match(r):
        return AMBIGUOUS
    has_lookup = bool(_LOOKUP_RE.search(r))
    has_mission = bool(_MISSION_RE.search(r))
    if has_lookup and not has_mission:
        return STATE_LOOKUP
    if has_mission and not has_lookup:
        return MISSION
    if has_mission and has_lookup:
        return MISSION          # an imperative with a status word is still new work
    # Brief / no clear verb → CONVERSATIONAL (respond, ask back). It used to
    # return AMBIGUOUS, which made the House silently RESUME a stale active
    # mission for any short input ("Resuming '<old mission>'…") instead of
    # talking to the operator. Only an EXPLICIT deictic/continuation ("ต่อ",
    # "อันนี้", "continue" — caught above) resumes now. A longer descriptive
    # line is treated as new mission intent.
    return CHAT if len(_tokens(r)) <= 3 else MISSION


# ── Phase D — confidence matching (resolve deictic against owned state) ───────
def _match_missions(request: str, missions: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], float]]:
    """Score each mission against the request. Empty-content requests (e.g. 'ต่อ')
    score by RECENCY; content requests score by token overlap. Returns sorted desc."""
    want = _tokens(request) - {"ต่อ", "continue", "resume", "this", "that", "it", "อันนี้"}
    scored: List[Tuple[Dict[str, Any], float]] = []
    n = len(missions) or 1
    for i, m in enumerate(sorted(missions, key=lambda x: x.get("updated_at") or 0, reverse=True)):
        if want:
            have = _tokens(m.get("objective", ""))
            j = len(want & have) / len(want | have) if (want | have) else 0.0
            score = round(j, 3)
        else:
            score = round((n - i) / n, 3)     # recency rank → confidence
        scored.append((m, score))
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored


# ══════════════════════════════════════════════════════════════════════════════
# Phase F/G — route orchestrator: Discover → Classify → Route
# ══════════════════════════════════════════════════════════════════════════════
def route(request: str) -> Dict[str, Any]:
    """The institution investigates first. Returns:
       {category, answer, evidence, confidence, alternatives, needs_clarification,
        options, discovery_order}
    For STATE_LOOKUP an `answer` is composed from records (no plan/council/comprehend).
    For MISSION, discovery `evidence` is attached for grounded comprehension.
    For AMBIGUOUS, context recovery is attempted, then reclassify, then clarify LAST."""
    req = (request or "").strip()
    order: List[str] = []
    cls = classify(req)

    # ── CHAT: small talk — no discovery, no records; the caller routes to
    # the conversational model (a greeting deserves a greeting)
    if cls == CHAT:
        return {"category": CHAT, "answer": "", "confidence": 1.0, "alternatives": [],
                "evidence": {}, "needs_clarification": False, "discovery_order": order}

    # ── Phase B priority: Mission → House Mind → Timeline → Archive → Learning ──
    def disc_mission():  order.append("mission");   return query_missions()
    def disc_mind():     order.append("house_mind"); return read_house_mind()
    def disc_timeline(): order.append("timeline");  return query_timeline()
    def disc_learning(): order.append("learning");  return query_learning()
    def disc_archive():  order.append("archive");   return recall_archive(req)

    # ── AMBIGUOUS: recover context from owned state, then reclassify ──
    if cls == AMBIGUOUS:
        miss = disc_mission()
        mind = disc_mind()
        active = miss["active"]
        ranked = _match_missions(req, active)
        if ranked and ranked[0][1] > 0:
            top, conf = ranked[0]
            alts = [{"objective": m.get("objective", ""), "confidence": c}
                    for m, c in ranked[1:3] if c > 0]
            # resolved against an active mission → answer as a checkpoint
            return {
                "category": STATE_LOOKUP, "resolved_from": AMBIGUOUS,
                "answer": _compose_checkpoint(top, mind),
                "confidence": conf, "alternatives": alts,
                "evidence": {"mission": top, "house_mind": mind},
                "needs_clarification": False, "discovery_order": order,
            }
        if mind.get("objective"):
            return {"category": STATE_LOOKUP, "resolved_from": AMBIGUOUS,
                    "answer": _compose_mind(mind), "confidence": mind.get("confidence", 0.0),
                    "alternatives": [], "evidence": {"house_mind": mind},
                    "needs_clarification": False, "discovery_order": order}
        # Phase G: clarification is the LAST resort — options derived from discovery
        opts = [m.get("objective", "")[:60] for m in active[:4]]
        return {"category": AMBIGUOUS, "answer": "", "confidence": 0.0, "alternatives": [],
                "evidence": {"mission": miss, "house_mind": mind},
                "needs_clarification": True,
                "options": opts or ["Start a new mission", "Show recent activity"],
                "discovery_order": order}

    # ── STATE_LOOKUP: discover the relevant records, answer directly ──
    if cls == STATE_LOOKUP:
        ev: Dict[str, Any] = {}
        rl = (req or "").lower()
        ev["mission"] = disc_mission()
        ev["house_mind"] = disc_mind()
        if re.search(r"เรียนรู้|บทเรียน|learn|lesson|failed|fail", rl):
            ev["learning"] = disc_learning()
        if re.search(r"ล่าสุด|ประวัติ|เปลี่ยน|recent|history|changed|happened", rl):
            ev["timeline"] = disc_timeline()
        # ANALYTICAL status question ("… เชิงเทคนิค เครื่องมือที่เป็นคอขวด",
        # "ทำไม", "วิเคราะห์") → the canned count doesn't answer it. Hand the
        # records to the conversational model AS CONTEXT so it reasons and
        # actually answers, instead of dumping "N failed." (The MISSION pipeline
        # was wrong — it tries to execute tools and produces no answer.)
        if _ANALYTICAL_RE.search(req or ""):
            return {"category": CHAT, "answer": "",
                    "context": _compose_status(ev), "evidence": ev,
                    "needs_clarification": False, "discovery_order": order,
                    "reason_over_records": True}
        return {"category": STATE_LOOKUP, "answer": _compose_status(ev),
                "confidence": 1.0, "alternatives": [], "evidence": ev,
                "needs_clarification": False, "discovery_order": order}

    # ── MISSION: discover to GROUND comprehension, then hand off (caller plans) ──
    ev = {"mission": disc_mission(), "house_mind": disc_mind(),
          "archive": disc_archive(), "learning": disc_learning()}
    similar = ev["archive"].get("similar", [])
    return {"category": MISSION, "answer": "", "confidence": 0.0, "alternatives": [],
            "evidence": ev, "similar_prior_work": similar,
            "needs_clarification": False, "discovery_order": order}


# ── answer composition (templated, deterministic — NO model, NO fabrication) ──
def _compose_status(ev: Dict[str, Any]) -> str:
    m = ev.get("mission", {}); mind = ev.get("house_mind", {})
    a = m.get("active", []); f = m.get("failed", [])
    parts: List[str] = []
    if a:
        names = "; ".join(f"{x.get('objective','')[:50]}"
                          + (f" ({int((x.get('confidence') or 0)*100)}%)" if x.get("confidence") is not None else "")
                          for x in a[:5])
        parts.append(f"{len(a)} open mission(s): {names}")
    else:
        parts.append("No open missions.")
    # stratified truth (audit 2026-07-10): failed = system-attributable only;
    # operator interruptions and human-gate waits are reported as what they are
    if f:
        parts.append(f"{len(f)} failed.")
    _inc = m.get("incomplete", []); _intr = m.get("interrupted", []); _paus = m.get("paused", [])
    if _inc:
        parts.append(f"{len(_inc)} incomplete (hit step limit — often deliberations, not errors).")
    if _intr:
        parts.append(f"{len(_intr)} interrupted by operator.")
    if _paus:
        parts.append(f"{len(_paus)} waiting at a human gate.")
    if mind.get("objective"):
        parts.append(f"House Mind is investigating “{mind['objective'][:60]}” "
                     f"({int((mind.get('confidence') or 0)*100)}% confidence).")
    na = (mind.get("next_action") or {}).get("action") or m.get("house_next_action")
    if na:
        parts.append(f"Next action: {na}.")
    if "learning" in ev:
        c = ev["learning"].get("counts", {})
        if c.get("lessons"):
            parts.append(f"{c['lessons']} lesson(s) on record"
                         + (f", {c.get('repeat_failures',0)} repeat-failure pattern(s)" if c.get("repeat_failures") else "")
                         + ".")
    if "timeline" in ev and ev["timeline"].get("recent"):
        last = ev["timeline"]["recent"][0]
        parts.append(f"Most recent: {last.get('node','')} — {str(last.get('content',''))[:60]}.")
    return " ".join(parts)


def _compose_mind(mind: Dict[str, Any]) -> str:
    s = [f"Current objective: “{mind.get('objective','')[:70]}” "
         f"({int((mind.get('confidence') or 0)*100)}% confidence)."]
    if mind.get("belief"):
        s.append(f"Belief: {mind['belief'][:80]}.")
    if mind.get("unknown"):
        s.append(f"Open unknowns: {len(mind['unknown'])}.")
    if mind.get("risks"):
        s.append(f"Risks: {len(mind['risks'])}.")
    return " ".join(s)


def _compose_checkpoint(mission: Dict[str, Any], mind: Dict[str, Any]) -> str:
    s = [f"Resuming “{mission.get('objective','')[:70]}” (status {mission.get('status','')}"
         + (f", {int((mission.get('confidence') or 0)*100)}%" if mission.get("confidence") is not None else "")
         + ")."]
    na = mission.get("next_action") or (mind.get("next_action") or {}).get("action")
    if na:
        s.append(f"Next action: {na}.")
    if mind.get("belief"):
        s.append(f"Current belief: {mind['belief'][:80]}.")
    return " ".join(s)
