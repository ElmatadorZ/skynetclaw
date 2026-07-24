"""
knowledge_asset.py — H4 KNOWLEDGE ASSET ENGINE (stateless)
==========================================================
FIRST PRINCIPLE: collecting information does not reduce uncertainty — only
TRANSFORMING it into a usable asset does. "search → save markdown → stop" is
insufficient. Before a mission may be called complete, the House must answer:

  "What artifact should this knowledge become?"

This module infers the best ASSET TYPE from the mission's shape (directive
language + the files/tools it actually produced), with a confidence and a
reason, and verifies whether that asset was actually created.

  Research          → PDF Report / Executive Brief
  Comparison        → Comparison Matrix / Interactive HTML Dashboard
  Registry/Map      → Knowledge Graph
  Learning set      → Obsidian Knowledge Base
  Market analysis   → Executive Brief

Deterministic, model-free, stateless. The completion check ties into OX-1.6
(evidence-based completion): an asset is "delivered" only if a file of the
recommended kind actually exists.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# (asset_type, signal regex, expected file extensions, reason). Ordered: the
# first strong match wins; ties broken by produced-artifact evidence.
_ASSET_RULES: List[Tuple[str, Any, Tuple[str, ...], str]] = [
    ("Interactive HTML Dashboard",
     re.compile(r"\b(dashboard|interactive|visuali[sz]e|chart|graph view|monitor|live view)\b", re.I),
     (".html",), "the knowledge is multi-dimensional and benefits from interactive exploration"),
    ("Comparison Matrix",
     re.compile(r"\b(compare|comparison|versus|vs\.?|matrix|framework survey|trade-?off|benchmark)\b", re.I),
     (".html", ".csv", ".md"), "the mission contrasts options — a matrix makes differences legible"),
    ("Knowledge Graph",
     re.compile(r"\b(registry|graph|relationship|ontology|map of|network of|dependency|agents?)\b", re.I),
     (".json", ".html", ".svg"), "the knowledge is relational — a graph exposes structure"),
    ("Executive Brief",
     re.compile(r"\b(market analysis|executive|brief|for (the )?(ceo|board|leadership)|decision|recommendation)\b", re.I),
     (".pdf", ".md"), "a decision-maker needs the signal, not the raw data"),
    ("Obsidian Knowledge Base",
     re.compile(r"\b(learning|lessons|notes|knowledge ?base|collection|wiki|second brain|vault)\b", re.I),
     (".md",), "recurring knowledge should accrue in the durable vault, not a one-off file"),
    ("PDF Report",
     re.compile(r"\b(research|report|study|investigat|deep dive|whitepaper|survey)\b", re.I),
     (".pdf", ".md"), "a research result should be a citable, self-contained document"),
]

_DEFAULT = ("Markdown Note", (".md",),
            "no strong asset signal — a structured note is the minimum durable form")

_EXT_RE = re.compile(r"\.[A-Za-z0-9]{1,5}$")


def _ext(path: str) -> str:
    m = _EXT_RE.search((path or "").strip())
    return m.group(0).lower() if m else ""


def recommend(directive: str, files_touched: Optional[List[str]] = None,
              tool_names: Optional[List[str]] = None) -> Dict[str, Any]:
    """Infer the best asset for this mission's knowledge.

    directive     — the clean mission identity (NOT the model prompt).
    files_touched — artifacts the run actually produced (evidence).
    tool_names    — tools used (secondary signal).
    """
    text = directive or ""
    produced_exts = {_ext(f) for f in (files_touched or []) if _ext(f)}
    scored: List[Tuple[float, str, Tuple[str, ...], str]] = []
    for asset, rx, exts, reason in _ASSET_RULES:
        if rx.search(text):
            conf = 0.6
            # produced-artifact evidence raises confidence
            if produced_exts & set(exts):
                conf = 0.9
            scored.append((conf, asset, exts, reason))
    if not scored:
        asset, exts, reason = _DEFAULT
        conf = 0.85 if (produced_exts & set(exts)) else 0.4
        return {"asset_type": asset, "confidence": conf, "reason": reason,
                "expected_ext": list(exts), "evidence_ext": sorted(produced_exts)}
    scored.sort(key=lambda s: s[0], reverse=True)
    conf, asset, exts, reason = scored[0]
    return {"asset_type": asset, "confidence": round(conf, 3), "reason": reason,
            "expected_ext": list(exts), "evidence_ext": sorted(produced_exts),
            "alternatives": [a for _, a, _, _ in scored[1:3]]}


def is_delivered(recommendation: Dict[str, Any], files_touched: Optional[List[str]]) -> bool:
    """True when a file of the recommended asset kind was actually produced —
    i.e. knowledge was TRANSFORMED, not merely collected."""
    exts = set(recommendation.get("expected_ext") or [])
    produced = {_ext(f) for f in (files_touched or []) if _ext(f)}
    return bool(exts & produced)


def render(recommendation: Dict[str, Any], delivered: bool) -> str:
    """An ASSET PLAN block for the prompt / completion gate."""
    r = recommendation or {}
    status = "✓ DELIVERED" if delivered else "✗ NOT YET CREATED"
    L = [f"## KNOWLEDGE ASSET PLAN — this mission's knowledge should become:",
         f"  → {r.get('asset_type','?')}  (confidence {r.get('confidence',0)})  [{status}]",
         f"    why: {r.get('reason','')}"]
    if not delivered:
        L.append(f"    Mission is NOT complete until a {', '.join(r.get('expected_ext', []))} asset exists. "
                 "Collecting is not creating.")
    return "\n".join(L)
