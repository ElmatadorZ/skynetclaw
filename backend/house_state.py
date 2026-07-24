"""
house_state.py — THE HOUSE MIND: a shared, living cognitive state
=================================================================
Memory is the past. Recall is retrieval. This is the PRESENT — the House's
current understanding, shared by all fourteen members so they behave as one mind,
not fourteen.

At any moment the House can answer:
  What do we know?          → known_fact items
  What don't we know?       → unknown_fact + open_question items
  What do we believe?       → current (non-superseded) belief items + confidence
  Why do we believe it?     → evidence items + each belief's recorded reason
  What changed our mind?    → belief_changes (who, why, evidence, confidence impact)

Item kinds: known_fact · unknown_fact · hypothesis · belief · contradiction ·
            blind_spot · open_question · minority · evidence

Consciousness rule (enforced by wiring):
  every member READS the House State before deliberation;
  every member MAY UPDATE it; every update is LOGGED.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import hashlib
import re
import time
from typing import Any, Dict, List, Optional

import institutional_db as _db

KINDS = ("known_fact", "unknown_fact", "hypothesis", "belief", "contradiction",
         "blind_spot", "open_question", "minority", "evidence")

_WORD = re.compile(r"[\w฀-๿]+")
_SELF_RE = re.compile(r"\b(blueprint|agent|skill|council|สภา|ตัวเอง|ourselv|the house|roster|"
                      r"member|who are we|what are we|how many agent)\b", re.I)


def _tokens(s: str) -> set:
    return {t.lower() for t in _WORD.findall(s or "") if len(t) > 2}


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _nid(prefix: str, *parts: Any) -> str:
    return prefix + hashlib.sha1(("|".join(str(p) for p in parts)).encode("utf-8", "ignore")).hexdigest()[:12]


# ══════════════════════════════════════════════════════════════════════════════
# Open / find a living state for a question
# ══════════════════════════════════════════════════════════════════════════════
def open_state(question: str, session_id: Optional[str] = None,
               reuse: bool = True, bootstrap: bool = True,
               path: Optional[str] = None) -> str:
    """Get-or-create the living state for a question. Reuses an open state on the
    same question so understanding accumulates instead of resetting each time."""
    _db.init_once(path)
    now = time.time()
    if reuse:
        existing = _find_state(question, path)
        if existing:
            return existing
    sid = _nid("hs_", question[:80], now)
    with _db.connect(path) as c:
        c.execute("INSERT OR REPLACE INTO house_state "
                  "(id, session_id, question, status, confidence, summary, created_at, updated_at) "
                  "VALUES (?,?,?, 'open', 0.0, '', ?, ?)",
                  (sid, session_id, question, now, now))
        c.commit()
    if bootstrap and _SELF_RE.search(question or ""):
        bootstrap_self_facts(sid, path)
    return sid


def _find_state(question: str, path: Optional[str] = None) -> Optional[str]:
    want = _tokens(question)
    if not want:
        return None
    with _db.connect(path) as c:
        rows = c.execute("SELECT id, question FROM house_state WHERE status='open' "
                         "ORDER BY updated_at DESC LIMIT 200").fetchall()
    best, best_j = None, 0.0
    for r in rows:
        have = _tokens(r["question"])
        if not have:
            continue
        j = len(want & have) / len(want | have)
        if j > best_j:
            best, best_j = r["id"], j
    return best if best_j >= 0.6 else None


# ══════════════════════════════════════════════════════════════════════════════
# Add items (the building blocks of understanding)
# ══════════════════════════════════════════════════════════════════════════════
def add_item(state_id: str, kind: str, content: str, confidence: float = 0.0,
             agent: str = "", evidence: str = "", path: Optional[str] = None) -> str:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    _db.init_once(path)
    now = time.time()
    iid = _nid("si_", state_id, kind, content[:80])
    with _db.connect(path) as c:
        c.execute("INSERT OR REPLACE INTO state_items "
                  "(id, state_id, kind, content, confidence, agent, evidence, status, superseded, ts) "
                  "VALUES (?,?,?,?,?,?,?, 'active', 0, ?)",
                  (iid, state_id, kind, content[:1000], float(confidence), agent, evidence[:500], now))
        c.execute("UPDATE house_state SET updated_at=? WHERE id=?", (now, state_id))
        c.commit()
    _recompute_confidence(state_id, path)
    return iid


def add_known_fact(state_id, content, evidence="", agent="", confidence=0.9, path=None):
    return add_item(state_id, "known_fact", content, confidence, agent, evidence, path)
def add_unknown_fact(state_id, content, agent="", path=None):
    return add_item(state_id, "unknown_fact", content, 0.0, agent, "", path)
def add_hypothesis(state_id, content, confidence=0.5, agent="", evidence="", path=None):
    return add_item(state_id, "hypothesis", content, confidence, agent, evidence, path)
def add_contradiction(state_id, content, agent="", evidence="", path=None):
    return add_item(state_id, "contradiction", content, 0.0, agent, evidence, path)
def add_blind_spot(state_id, content, agent="", path=None):
    return add_item(state_id, "blind_spot", content, 0.0, agent, "", path)
def add_open_question(state_id, content, agent="", path=None):
    return add_item(state_id, "open_question", content, 0.0, agent, "", path)
def add_minority(state_id, content, agent="", evidence="", path=None):
    return add_item(state_id, "minority", content, 0.0, agent, evidence, path)
def add_evidence(state_id, content, agent="", path=None):
    return add_item(state_id, "evidence", content, 0.0, agent, "", path)


# ══════════════════════════════════════════════════════════════════════════════
# Belief evolution — the thing that makes it a MIND (what changed our mind)
# ══════════════════════════════════════════════════════════════════════════════
def _current_belief(c, state_id: str):
    return c.execute("SELECT * FROM state_items WHERE state_id=? AND kind='belief' "
                     "AND superseded=0 ORDER BY ts DESC LIMIT 1", (state_id,)).fetchone()


def add_belief(state_id: str, content: str, confidence: float = 0.5, agent: str = "",
               evidence: str = "", reason: str = "", path: Optional[str] = None) -> Dict[str, Any]:
    """Set/evolve the House's current belief. If a belief already exists it is
    superseded and the change is logged (previous→new, confidence impact, agent)."""
    _db.init_once(path)
    now = time.time()
    with _db.connect(path) as c:
        prev = _current_belief(c, state_id)
        prev_content = prev["content"] if prev else ""
        prev_conf = prev["confidence"] if prev else 0.0
        if prev:
            c.execute("UPDATE state_items SET superseded=1, status='superseded' WHERE id=?", (prev["id"],))
        iid = _nid("si_", state_id, "belief", content[:60], now)
        c.execute("INSERT OR REPLACE INTO state_items "
                  "(id, state_id, kind, content, confidence, agent, evidence, status, superseded, ts) "
                  "VALUES (?,?, 'belief', ?,?,?,?, 'active', 0, ?)",
                  (iid, state_id, content[:1000], float(confidence), agent, evidence[:500], now))
        cid = _nid("bc_", state_id, now, content[:40])
        c.execute("INSERT OR REPLACE INTO belief_changes "
                  "(id, state_id, item_id, previous, new, prev_confidence, new_confidence, "
                  " reason, evidence, agent, ts) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (cid, state_id, iid, prev_content, content[:1000], prev_conf, float(confidence),
                   reason[:500], evidence[:500], agent, now))
        c.execute("UPDATE house_state SET updated_at=? WHERE id=?", (now, state_id))
        c.commit()
    _recompute_confidence(state_id, path)
    return {"belief_id": iid, "change_id": cid, "previous": prev_content, "new": content,
            "prev_confidence": prev_conf, "new_confidence": confidence,
            "confidence_impact": round(confidence - prev_conf, 3), "agent": agent}


# alias for the explicit "update mind" call
update_belief = add_belief


def _recompute_confidence(state_id: str, path: Optional[str] = None) -> float:
    with _db.connect(path) as c:
        beliefs = c.execute("SELECT confidence FROM state_items WHERE state_id=? AND kind='belief' "
                            "AND superseded=0", (state_id,)).fetchall()
        contra = c.execute("SELECT COUNT(*) n FROM state_items WHERE state_id=? AND kind='contradiction' "
                           "AND status='active'", (state_id,)).fetchone()["n"]
        unknown = c.execute("SELECT COUNT(*) n FROM state_items WHERE state_id=? AND kind='unknown_fact' "
                            "AND status='active'", (state_id,)).fetchone()["n"]
        if beliefs:
            base = sum(b["confidence"] for b in beliefs) / len(beliefs)
        else:
            hyp = c.execute("SELECT AVG(confidence) a FROM state_items WHERE state_id=? AND kind='hypothesis'",
                            (state_id,)).fetchone()["a"]
            base = (hyp or 0.0) * 0.7   # hypotheses are weaker than beliefs
        conf = _clamp(base - 0.1 * contra - 0.03 * unknown)
        c.execute("UPDATE house_state SET confidence=? WHERE id=?", (round(conf, 3), state_id))
        c.commit()
    return round(conf, 3)


# ══════════════════════════════════════════════════════════════════════════════
# Read the current understanding
# ══════════════════════════════════════════════════════════════════════════════
def read_state(state_id: str, path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    _db.init_once(path)
    with _db.connect(path) as c:
        st = c.execute("SELECT * FROM house_state WHERE id=?", (state_id,)).fetchone()
        if not st:
            return None
        items = [dict(r) for r in c.execute(
            "SELECT * FROM state_items WHERE state_id=? AND superseded=0 ORDER BY ts", (state_id,)).fetchall()]
        changes = [dict(r) for r in c.execute(
            "SELECT * FROM belief_changes WHERE state_id=? ORDER BY ts DESC LIMIT 10", (state_id,)).fetchall()]
    grouped: Dict[str, List[Dict[str, Any]]] = {k: [] for k in KINDS}
    for it in items:
        grouped.setdefault(it["kind"], []).append(it)
    out = dict(st)
    out["items"] = grouped
    out["recent_changes"] = changes
    out["counts"] = {k: len(v) for k, v in grouped.items()}
    return out


def answer(state_id: str, path: Optional[str] = None) -> Dict[str, Any]:
    """The House answers the five questions about itself."""
    s = read_state(state_id, path)
    if not s:
        return {}
    g = s["items"]
    beliefs = [{"belief": b["content"], "confidence": b["confidence"], "agent": b["agent"]}
               for b in g["belief"]]
    return {
        "question": s["question"],
        "overall_confidence": s["confidence"],
        "what_we_know": [i["content"] for i in g["known_fact"]],
        "what_we_dont_know": [i["content"] for i in g["unknown_fact"]] +
                             [i["content"] for i in g["open_question"]],
        "what_we_believe": beliefs,
        "why_we_believe": [i["content"] for i in g["evidence"]] +
                          [f"{c['new'][:60]} ⟵ {c['reason']}" for c in s["recent_changes"] if c["reason"]],
        "what_changed_our_mind": [{
            "agent": c["agent"], "from": c["previous"][:80], "to": c["new"][:80],
            "reason": c["reason"], "evidence": c["evidence"],
            "confidence_impact": round((c["new_confidence"] or 0) - (c["prev_confidence"] or 0), 3),
        } for c in s["recent_changes"] if c["previous"] or c["new"]],
        "contradictions": [i["content"] for i in g["contradiction"]],
        "minority_view": [i["content"] for i in g["minority"]],
        "blind_spots": [i["content"] for i in g["blind_spot"]],
        "hypotheses": [{"hypothesis": h["content"], "confidence": h["confidence"]} for h in g["hypothesis"]],
    }


def current(path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """The most recently updated VALID open state — the House's current focus.

    OX-HOUSE-GUARD-1: read-side protection. Walks open states newest-first and
    returns the first that is a high-quality mission — skipping error-generated,
    punctuation-only and zero-information (0% confidence, no cognitive content)
    rows even if they still exist in the DB. Falls back to the raw newest open
    row only if the integrity guard is unavailable. Returns None when no valid
    open mission exists (House Mind honestly blank)."""
    _db.init_once(path)
    with _db.connect(path) as c:
        rows = c.execute(
            "SELECT h.id, h.question, h.confidence, "
            "(SELECT COUNT(*) FROM state_items s WHERE s.state_id=h.id AND s.superseded=0) AS n_items "
            "FROM house_state h WHERE h.status='open' "
            "ORDER BY h.updated_at DESC LIMIT 40").fetchall()
    if not rows:
        return None
    try:
        import runtime_integrity as _ri
        for r in rows:
            if _ri.valid_mission_row(r["question"], r["confidence"], r["n_items"]):
                return read_state(r["id"], path)
        return None                      # garbage exists but nothing valid → blank
    except Exception:
        return read_state(rows[0]["id"], path)   # guard unavailable → prior behavior


def recent_changes(state_id: str, limit: int = 20, path: Optional[str] = None) -> List[Dict[str, Any]]:
    _db.init_once(path)
    with _db.connect(path) as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM belief_changes WHERE state_id=? ORDER BY ts DESC LIMIT ?",
            (state_id, limit))]


def close_state(state_id: str, summary: str = "", path: Optional[str] = None,
                status: str = "closed") -> None:
    _db.init_once(path)
    with _db.connect(path) as c:
        c.execute("UPDATE house_state SET status=?, summary=?, updated_at=? WHERE id=?",
                  (status, summary[:1000], time.time(), state_id))
        c.commit()


# ══════════════════════════════════════════════════════════════════════════════
# OX-STABILITY-1 Phase 3 — STATE LIFECYCLE INTEGRITY
# Lifecycle: open → (active) → completed | failed → archived. No permanent OPEN:
# stale open states are aged out to 'archived' so the active count stays truthful
# and learning never reads abandoned state. (Read-model statuses; no schema change.)
# ══════════════════════════════════════════════════════════════════════════════
_ACTIVE_STATUSES = ("open", "active")
_TERMINAL_STATUSES = ("completed", "failed", "closed", "archived")


def active_count(path: Optional[str] = None) -> int:
    """How many missions are ACTUALLY active (open/active, not concluded)."""
    _db.init_once(path)
    with _db.connect(path) as c:
        return int(c.execute(
            "SELECT COUNT(*) n FROM house_state WHERE status IN ('open','active')"
        ).fetchone()["n"])


def lifecycle_counts(path: Optional[str] = None) -> Dict[str, int]:
    _db.init_once(path)
    with _db.connect(path) as c:
        return {r["status"]: int(r["n"]) for r in c.execute(
            "SELECT status, COUNT(*) n FROM house_state GROUP BY status")}


def archive_stale(max_age_seconds: float = 7 * 86400.0,
                  path: Optional[str] = None) -> int:
    """STATE AGING — archive open states that have not been touched in
    max_age_seconds (default 7 days). Prevents indefinite OPEN accumulation so
    the active count reflects reality. Returns how many were archived."""
    _db.init_once(path)
    cutoff = time.time() - float(max_age_seconds)
    with _db.connect(path) as c:
        cur = c.execute(
            "UPDATE house_state SET status='archived', updated_at=? "
            "WHERE status IN ('open','active') AND updated_at < ?",
            (time.time(), cutoff))
        c.commit()
        n = cur.rowcount
    if n:
        print(f"[house_state.archive_stale] archived {n} stale open state(s)")
    return n


# ══════════════════════════════════════════════════════════════════════════════
# Self-knowledge — the House knows its own composition (fixes "ไม่รู้ตัวเอง")
# ══════════════════════════════════════════════════════════════════════════════
def _self_facts(path: Optional[str] = None) -> List[Dict[str, str]]:
    facts: List[Dict[str, str]] = []
    # roster (authoritative: the reputation roster = the 14 members)
    try:
        import agent_reputation as _rep
        members = _rep.HOUSE
        facts.append({"content": f"THE HOUSE is a council of {len(members)} members: "
                                 + ", ".join(members), "evidence": "agent_reputation.HOUSE"})
    except Exception:
        members = []
    # installed skills + which members have one
    try:
        from pathlib import Path
        skdir = Path(__file__).parent / "skills"
        bound = {}
        names = []
        if skdir.exists():
            for sub in skdir.iterdir():
                md = sub / "SKILL.md"
                if not md.is_dir() and md.exists():
                    txt = md.read_text(encoding="utf-8", errors="ignore")[:600]
                    names.append(sub.name)
                    m = re.search(r"codename:\s*(.+)", txt)
                    if m:
                        bound[m.group(1).strip()] = sub.name
        facts.append({"content": f"{len(names)} skills are installed in backend/skills/: "
                                 + ", ".join(sorted(names)), "evidence": "backend/skills/"})
        if members:
            covered = {b.split()[-1] for b in bound}  # rough surname match
            uncovered = [m for m in members if not any(m.lower() in k.lower() for k in bound)]
            if uncovered:
                facts.append({"content": "Council members without a dedicated installed skill: "
                                         + ", ".join(uncovered), "evidence": "skills/ codename binding"})
    except Exception:
        pass
    # vault path (tolerant parse — settings.json may carry trailing data)
    try:
        from pathlib import Path
        import json as _json
        sp = Path(__file__).parent / "settings.json"
        if sp.exists():
            raw = sp.read_text(encoding="utf-8", errors="ignore")
            obj = _json.JSONDecoder().raw_decode(raw.lstrip())[0]
            vault = obj.get("vault_path") or obj.get("obsidian_vault")
            if vault:
                facts.append({"content": f"The Obsidian vault is at {vault}", "evidence": "settings.json"})
    except Exception:
        pass
    return facts


def bootstrap_self_facts(state_id: str, path: Optional[str] = None) -> int:
    """Seed the state with KNOWN facts about the House itself, so a self-referential
    directive starts from introspection, not a blank unknown."""
    n = 0
    for f in _self_facts(path):
        add_known_fact(state_id, f["content"], evidence=f["evidence"],
                       agent="House (self-model)", confidence=0.95, path=path)
        n += 1
    return n


# ══════════════════════════════════════════════════════════════════════════════
# Update the state FROM a council verdict (the "House State Update" step)
# ══════════════════════════════════════════════════════════════════════════════
def update_from_verdict(state_id: str, verdict: Dict[str, Any],
                        path: Optional[str] = None) -> Dict[str, Any]:
    """Fold a council verdict into the shared mind: facts learned, the new belief,
    contradictions and the minority view, evidence — with belief evolution logged."""
    import json as _json
    def _txt(b): return _json.dumps(b, ensure_ascii=False) if isinstance(b, dict) else str(b or "")
    analyst = verdict.get("analyst") or {}
    for f in (analyst.get("known") or []):
        add_known_fact(state_id, str(f)[:200], evidence="Analyst", agent="Analyst", path=path)
    for u in (analyst.get("unknown") or []) + (analyst.get("data_gaps") or []):
        add_unknown_fact(state_id, str(u)[:200], agent="Analyst", path=path)

    forecaster = verdict.get("forecaster") or {}
    if forecaster.get("scenario"):
        conf = forecaster.get("confidence") if isinstance(forecaster.get("confidence"), (int, float)) else 0.5
        add_hypothesis(state_id, _txt(forecaster.get("scenario"))[:200], confidence=conf,
                       agent="Forecaster", path=path)

    skeptic = verdict.get("skeptic") or {}
    if str(skeptic.get("verdict", "")).upper() in ("REBUILD", "FRAGILE", "VETO", "BLOCKED"):
        reason = str(skeptic.get("rebuild_trigger") or skeptic.get("reason") or "")[:200]
        add_contradiction(state_id, f"Skeptic: {skeptic.get('verdict')} — {reason}",
                          agent="Skeptic", path=path)
        add_minority(state_id, reason or str(skeptic.get("verdict")), agent="Skeptic", path=path)

    # the aggregate recommendation becomes the House's current belief (evolution logged)
    agg = str(verdict.get("aggregate_recommendation") or "").strip()
    change = None
    if agg:
        gov = verdict.get("governance") or {}
        conf = gov.get("governance_score") if isinstance(gov.get("governance_score"), (int, float)) else 0.6
        change = add_belief(state_id, agg[:300], confidence=conf, agent="Council",
                            reason="council deliberation verdict", path=path)
    return {"state_id": state_id, "belief_change": change}


# ══════════════════════════════════════════════════════════════════════════════
# Close the loop: a graded prediction outcome revises the shared belief
# (ผิด/ถูก → เรียนรู้ → เปลี่ยนความเชื่อ). The House changes its mind not only
# from another verdict, but from REALITY proving it right or wrong.
# ══════════════════════════════════════════════════════════════════════════════
def _find_state_any(question: str, path: Optional[str] = None) -> Optional[str]:
    """Like _find_state but matches states in ANY status (a deliberation's state
    may have been closed by the time its prediction is graded)."""
    want = _tokens(question)
    if not want:
        return None
    with _db.connect(path) as c:
        rows = c.execute("SELECT id, question FROM house_state "
                         "ORDER BY updated_at DESC LIMIT 300").fetchall()
    best, best_j = None, 0.0
    for r in rows:
        have = _tokens(r["question"])
        if not have:
            continue
        j = len(want & have) / len(want | have)
        if j > best_j:
            best, best_j = r["id"], j
    return best if best_j >= 0.6 else None


def revise_from_outcome(directive: str, result: str, horizon: str = "",
                        path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Fold a graded prediction back into the shared mind. Locates the House State
    for the originating deliberation (by directive), then:
      incorrect → halve the belief's confidence + log a contradiction (DISPROVEN)
      partial   → small downward revision
      correct   → reinforce the belief toward certainty (CONFIRMED)
    Every revision is logged as a belief_change attributed to "Reality (outcome)",
    so "what changed our mind" reflects evidence from the world, not just debate.
    Returns the belief_change dict (or None if no matching state/belief)."""
    _db.init_once(path)
    sid = _find_state(directive, path) or _find_state_any(directive, path)
    if not sid:
        return None
    hz = f" at {horizon}d" if horizon else ""
    with _db.connect(path) as c:
        belief = _current_belief(c, sid)
    if not belief:
        add_known_fact(sid, f"A prediction from this deliberation was graded {result}{hz}.",
                       evidence="graded outcome (reality)", agent="Reality (outcome)",
                       confidence=0.9, path=path)
        return None
    prev_conf = belief["confidence"] or 0.0
    content = belief["content"]
    if result == "incorrect":
        new_conf = max(0.0, prev_conf * 0.5 - 0.1)
        add_contradiction(sid, f"Reality disproved a prediction from this deliberation{hz}.",
                          agent="Reality (outcome)", evidence="graded outcome", path=path)
        reason = f"a prediction from this deliberation was DISPROVEN{hz}"
    elif result == "partial":
        new_conf = max(0.0, prev_conf - 0.1)
        reason = f"a prediction from this deliberation was only PARTIALLY correct{hz}"
    else:  # correct
        new_conf = min(1.0, prev_conf + (1.0 - prev_conf) * 0.3)
        reason = f"a prediction from this deliberation was CONFIRMED{hz}"
    change = update_belief(sid, content, confidence=new_conf, agent="Reality (outcome)",
                           reason=reason, evidence="graded prediction outcome", path=path)
    return {"state_id": sid, "result": result, "reason": reason, **change}


# ══════════════════════════════════════════════════════════════════════════════
# Render the House Mind for council injection (consciousness rule: read first)
# ══════════════════════════════════════════════════════════════════════════════
def format_state_for_council(state: Dict[str, Any]) -> str:
    if not state:
        return ""
    g = state.get("items", {})
    L = ["## THE HOUSE MIND — current shared understanding (read before you deliberate)",
         f"Question: {state.get('question','')}",
         f"Overall confidence: {int((state.get('confidence') or 0)*100)}%"]
    def _sec(title, items, fmt):
        if items:
            L.append(f"\n### {title}")
            L.extend("  " + fmt(i) for i in items[:6])
    _sec("Known facts", g.get("known_fact", []), lambda i: f"✓ {i['content']}")
    _sec("Unknown / open questions", g.get("unknown_fact", []) + g.get("open_question", []),
         lambda i: f"? {i['content']}")
    _sec("Current beliefs", g.get("belief", []),
         lambda i: f"• {i['content']}  [{int((i['confidence'] or 0)*100)}%]")
    _sec("Hypotheses", g.get("hypothesis", []),
         lambda i: f"~ {i['content']}  [{int((i['confidence'] or 0)*100)}%]")
    _sec("Contradictions", g.get("contradiction", []), lambda i: f"⚡ {i['content']}")
    _sec("Minority view (preserved)", g.get("minority", []), lambda i: f"⚖ {i['content']}")
    _sec("Blind spots", g.get("blind_spot", []), lambda i: f"◌ {i['content']}")
    if state.get("recent_changes"):
        L.append("\n### What recently changed our mind")
        for ch in state["recent_changes"][:4]:
            imp = round((ch.get("new_confidence") or 0) - (ch.get("prev_confidence") or 0), 2)
            L.append(f"  → {ch.get('agent','?')}: \"{(ch.get('previous') or '∅')[:40]}\" → "
                     f"\"{(ch.get('new') or '')[:40]}\" ({imp:+}) — {ch.get('reason','')[:60]}")
    L.append("\nYou are ONE mind. Build on this shared state; if you change a belief, say why "
             "and with what evidence. Surface new unknowns and contradictions explicitly.")
    return "\n".join(L)
