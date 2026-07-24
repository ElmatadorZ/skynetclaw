"""
curiosity.py — OX-CURIOSITY-1 GAP DISCOVERY PROTOCOL (additive, read-only)
==========================================================================
Discover the House's knowledge BLIND SPOTS — never/rarely explored domains,
underexplored sources, low-evidence hypotheses, single-source dependencies, and
capabilities with weak evidence. Builds on Acquisition / MetaLearning /
Exploration / Causal Discovery / Telemetry.

Pure read-model over the existing stores. Additive — no redesign of runtime,
workflow, reinforcement, governance or control. It does NOT create goals, does
NOT self-initiate, does NOT schedule. It only IDENTIFIES gaps and surfaces them
as recall context before acquisition.

Insight schema:
  {category, type, target, evidence_count, severity, reason, insight}

Severity by evidence: 0 → high · <3 → medium · <5 → low · >=5 → not flagged.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# curated reference vocabulary of domains the House may need — absence of any of
# these from all episodes is a blind spot worth surfacing (not a goal).
KNOWN_DOMAINS = [
    "oauth", "authentication", "authorization", "payments", "billing", "pdf",
    "csv", "excel", "database", "sql", "api", "webhook", "encryption", "security",
    "deployment", "docker", "kubernetes", "testing", "logging", "caching",
    "graphql", "websocket", "scraping", "email", "notification", "scheduling",
]

# searchable sources (the acquisition hierarchy minus the operator escalation)
_SOURCES = ["existing_code", "workspace_files", "artifact_registry", "lesson_registry",
            "capability_registry", "documentation", "github", "obsidian", "web_search"]

SINGLE_SOURCE_MIN_EPISODES = 3


def severity(evidence_count: int) -> Optional[str]:
    if evidence_count == 0:
        return "high"
    if evidence_count < 3:
        return "medium"
    if evidence_count < 5:
        return "low"
    return None        # >= 5 → well-explored, not flagged


def _insight(category: str, type_: str, target: str, n: int, sev: str, reason: str) -> Dict[str, Any]:
    return {"category": category, "type": type_, "target": target,
            "evidence_count": n, "severity": sev, "reason": reason,
            "insight": f"{type_.replace('_',' ')}: '{target}' ({reason}, evidence={n})"}


# ── source loaders (best-effort over the existing stores) ────────────────────
def _load_records(records):
    if records is not None:
        return records
    try:
        import acquisition as _aq
        return _aq.load_records()
    except Exception:
        return []


def _load_capabilities(caps):
    if caps is not None:
        return caps
    try:
        import capability_promotion as _cp
        c = _cp.load()
        return list(c.values()) if isinstance(c, dict) else (c or [])
    except Exception:
        return []


def _load_hypotheses(hyps):
    if hyps is not None:
        return hyps
    try:
        import causal as _ca
        return _ca.discover()
    except Exception:
        return []


# ── BLIND SPOT SCAN ───────────────────────────────────────────────────────────
def scan(records: Optional[List[Dict[str, Any]]] = None,
         capabilities: Optional[List[Dict[str, Any]]] = None,
         hypotheses: Optional[List[Dict[str, Any]]] = None,
         domains: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    records = _load_records(records)
    capabilities = _load_capabilities(capabilities)
    hypotheses = _load_hypotheses(hypotheses)
    domains = domains if domains is not None else KNOWN_DOMAINS
    insights: List[Dict[str, Any]] = []

    # 1+2. never / rarely explored DOMAINS (reference vocabulary vs episodes)
    blob = [(str(r.get("gap_type", "")) + " " + str(r.get("knowledge_gap", "")) +
             " " + str(r.get("task", ""))).lower() for r in records]
    for d in domains:
        n = sum(1 for b in blob if d.lower() in b)
        sev = severity(n)
        if sev:
            type_ = "blind_spot" if n == 0 else "underexplored_domain"
            reason = "No acquisition episodes found" if n == 0 else "Rarely explored domain"
            insights.append(_insight("domain", type_, d, n, sev, reason))

    # 3. underexplored SOURCES (how often each source was actually used)
    src_count: Dict[str, int] = {s: 0 for s in _SOURCES}
    for r in records:
        for s in (r.get("sources_checked") or []):
            if s in src_count:
                src_count[s] += 1
    for s, n in src_count.items():
        sev = severity(n)
        if sev:
            type_ = "blind_spot" if n == 0 else "underexplored_source"
            reason = "Source never used" if n == 0 else "Source rarely used"
            insights.append(_insight("source", type_, s, n, sev, reason))

    # 4. low-evidence HYPOTHESES (promising but under-supported)
    for h in hypotheses:
        n = int(h.get("supporting_evidence", 0) or 0)
        if h.get("discriminating") is False:
            continue                      # don't nag about non-discriminating factors
        sev = severity(n)
        if sev:
            tgt = h.get("factor") or h.get("hypothesis", "")[:40]
            insights.append(_insight("hypothesis", "weak_hypothesis", tgt, n, sev,
                                     "Hypothesis lacks supporting evidence"))

    # 5. weak-evidence CAPABILITIES
    for c in capabilities:
        if c.get("polarity") == "warning":
            continue
        n = int(c.get("evidence_count", 0) or 0)
        sev = severity(n)
        if sev:
            insights.append(_insight("capability", "weak_capability",
                                     c.get("name", "?"), n, sev,
                                     "Capability rests on weak evidence"))

    # 6. SINGLE-SOURCE dependencies (a gap_type whose successes all rely on one source)
    by_gap: Dict[str, set] = {}
    by_gap_n: Dict[str, int] = {}
    for r in records:
        if r.get("knowledge_found"):
            gt = r.get("gap_type", "?")
            by_gap_n[gt] = by_gap_n.get(gt, 0) + 1
            for s in (r.get("sources_successful") or []):
                by_gap.setdefault(gt, set()).add(s)
    for gt, srcs in by_gap.items():
        if len(srcs) == 1 and by_gap_n.get(gt, 0) >= SINGLE_SOURCE_MIN_EPISODES:
            insights.append(_insight("dependency", "single_source_dependency", gt,
                                     by_gap_n[gt], "medium",
                                     f"All successes depend on a single source: {next(iter(srcs))}"))

    _rank = {"high": 0, "medium": 1, "low": 2}
    insights.sort(key=lambda i: _rank.get(i["severity"], 3))
    return insights


# ── RECALL — strengths / weaknesses / blind spots ────────────────────────────
def strengths(records=None, capabilities=None) -> List[Dict[str, Any]]:
    """Well-explored sources/capabilities (evidence >= 5) — the inverse of scan."""
    records = _load_records(records)
    capabilities = _load_capabilities(capabilities)
    out = []
    src_count: Dict[str, int] = {}
    for r in records:
        for s in (r.get("sources_checked") or []):
            src_count[s] = src_count.get(s, 0) + 1
    for s, n in src_count.items():
        if n >= 5:
            out.append({"type": "strong_source", "target": s, "evidence_count": n})
    for c in capabilities:
        if int(c.get("evidence_count", 0) or 0) >= 5 and c.get("polarity") != "warning":
            out.append({"type": "strong_capability", "target": c.get("name", "?"),
                        "evidence_count": int(c.get("evidence_count", 0))})
    return out


def render_brief(records=None, capabilities=None, hypotheses=None,
                 domains=None, limit: int = 5) -> str:
    ins = scan(records, capabilities, hypotheses, domains)
    strong = strengths(records, capabilities)
    if not ins and not strong:
        return ""
    L = ["## CURIOSITY (blind-spot awareness — not a goal; just context):"]
    if strong:
        L.append("  KNOWN STRENGTHS: " + ", ".join(
            f"{s['target']}({s['evidence_count']})" for s in strong[:5]))
    weak = [i for i in ins if i["severity"] in ("medium", "low")]
    blind = [i for i in ins if i["severity"] == "high"]
    if blind:
        L.append("  BLIND SPOTS (no evidence): " + ", ".join(i["target"] for i in blind[:limit]))
    if weak:
        L.append("  WEAK / UNDEREXPLORED: " + ", ".join(
            f"{i['target']}({i['evidence_count']})" for i in weak[:limit]))
    return "\n".join(L)


# ── METRICS ────────────────────────────────────────────────────────────────--
def metrics(records=None, capabilities=None, hypotheses=None, domains=None) -> Dict[str, Any]:
    ins = scan(records, capabilities, hypotheses, domains)
    by_sev: Dict[str, int] = {}
    by_cat: Dict[str, int] = {}
    for i in ins:
        by_sev[i["severity"]] = by_sev.get(i["severity"], 0) + 1
        by_cat[i["category"]] = by_cat.get(i["category"], 0) + 1
    return {
        "total_insights": len(ins),
        "by_severity": by_sev,
        "by_category": by_cat,
        "blind_spots": [i["target"] for i in ins if i["severity"] == "high"][:10],
        "strengths": [s["target"] for s in strengths(records, capabilities)][:10],
    }
