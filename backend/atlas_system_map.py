"""
atlas_system_map.py — PART 6: ATLAS V2 (System Modeller)
========================================================
Atlas no longer only analyses assets — it models systems. Every query is mapped
across seven civilization layers, with drivers, dependencies, feedback loops,
and second- and third-order effects made explicit (First Principle × System Thinking).

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

# The seven civilization layers Atlas reasons across
LAYERS: List[Dict[str, Any]] = [
    {"n": 1, "name": "Liquidity",   "core": "money supply, credit, rates, capital flows",
     "keys": ["liquidity", "money", "credit", "rate", "fed", "debt", "currency", "สภาพคล่อง"]},
    {"n": 2, "name": "Technology",  "core": "compute, automation, productivity frontier",
     "keys": ["tech", "compute", "software", "automation", "chip", "semiconductor", "เทคโนโลยี"]},
    {"n": 3, "name": "Energy",      "core": "cost and availability of usable power",
     "keys": ["energy", "oil", "gas", "power", "grid", "nuclear", "solar", "พลังงาน"]},
    {"n": 4, "name": "Demographics","core": "population structure, labour, dependency",
     "keys": ["population", "ageing", "labour", "labor", "migration", "birth", "ประชากร"]},
    {"n": 5, "name": "Geopolitics", "core": "power balance, conflict, trade blocs",
     "keys": ["geopolit", "war", "trade", "sanction", "alliance", "china", "tariff", "ภูมิรัฐศาสตร์"]},
    {"n": 6, "name": "Culture",     "core": "trust, narrative, values, coordination",
     "keys": ["culture", "trust", "narrative", "belief", "social", "media", "วัฒนธรรม"]},
    {"n": 7, "name": "Artificial Intelligence", "core": "cognition as infrastructure",
     "keys": ["ai", "artificial intelligence", "model", "agent", "llm", "ปัญญาประดิษฐ์"]},
]

# Canonical cross-layer transmission links (system thinking)
LINKS: List[Dict[str, str]] = [
    {"from": "Liquidity", "to": "Technology", "mechanism": "cheap capital funds R&D and risk-taking"},
    {"from": "Energy", "to": "Liquidity", "mechanism": "energy price → inflation → rates → liquidity"},
    {"from": "Technology", "to": "Energy", "mechanism": "compute/AI demand raises baseload energy need"},
    {"from": "Artificial Intelligence", "to": "Demographics", "mechanism": "automation offsets shrinking labour"},
    {"from": "Geopolitics", "to": "Energy", "mechanism": "conflict / sanctions reprice energy supply"},
    {"from": "Demographics", "to": "Liquidity", "mechanism": "ageing → savings glut / fiscal strain"},
    {"from": "Culture", "to": "Geopolitics", "mechanism": "narrative & trust set the appetite for conflict or cooperation"},
    {"from": "Artificial Intelligence", "to": "Culture", "mechanism": "AI reshapes information → trust and narrative"},
]


def _score_layer(layer: Dict[str, Any], text: str) -> int:
    low = text.lower()
    return sum(1 for k in layer["keys"] if k in low)


def relevant_layers(query: str) -> List[Dict[str, Any]]:
    scored = [(l, _score_layer(l, query)) for l in LAYERS]
    hit = [l for l, s in scored if s > 0]
    return hit or LAYERS  # if nothing matches, the whole system is in scope


def map_system(query: str) -> Dict[str, Any]:
    """Return a structured systems map: drivers, dependencies, feedback loops,
    and 2nd/3rd-order effects across the relevant civilization layers."""
    layers = relevant_layers(query)
    layer_names = {l["name"] for l in layers}

    drivers = [{"layer": l["name"], "driver": l["core"]} for l in layers]
    dependencies = [lk for lk in LINKS
                    if lk["from"] in layer_names or lk["to"] in layer_names]

    # feedback loops = pairs where A->B and B->...->A reachable (1-2 hops)
    edge = {(lk["from"], lk["to"]) for lk in LINKS}
    loops: List[str] = []
    for a, b in edge:
        if (b, a) in edge:
            loops.append(f"{a} ⇄ {b}")
        else:
            for c in LAYERS:
                cn = c["name"]
                if (b, cn) in edge and (cn, a) in edge:
                    loops.append(f"{a} → {b} → {cn} → {a}")
    loops = sorted(set(loops))

    second = [f"{lk['from']} shift → {lk['to']} ({lk['mechanism']})" for lk in dependencies[:6]]
    third: List[str] = []
    for lk in dependencies[:6]:
        for lk2 in LINKS:
            if lk2["from"] == lk["to"] and lk2["to"] not in (lk["from"], lk["to"]):
                third.append(f"{lk['from']} → {lk['to']} → {lk2['to']} ({lk2['mechanism']})")
    third = sorted(set(third))[:6]

    return {
        "query": query,
        "layers_in_scope": [l["name"] for l in layers],
        "drivers": drivers,
        "dependencies": dependencies,
        "feedback_loops": loops,
        "second_order": second,
        "third_order": third,
    }


def format_system_map(m: Dict[str, Any]) -> str:
    L = ["## ATLAS SYSTEM MAP (7-layer civilization model)",
         f"Layers in scope: {', '.join(m['layers_in_scope'])}", "", "### Drivers"]
    L += [f"  - {d['layer']}: {d['driver']}" for d in m["drivers"]]
    L += ["", "### Dependencies"]
    L += [f"  - {d['from']} → {d['to']}: {d['mechanism']}" for d in m["dependencies"]] or ["  (none)"]
    L += ["", "### Feedback loops"]
    L += [f"  - {x}" for x in m["feedback_loops"]] or ["  (none detected)"]
    L += ["", "### Second-order effects"]
    L += [f"  - {x}" for x in m["second_order"]] or ["  (none)"]
    L += ["", "### Third-order effects"]
    L += [f"  - {x}" for x in m["third_order"]] or ["  (none)"]
    L += ["", "Atlas closes with scenarios (bull/base/bear), confidence, and invalidation — never a single prediction."]
    return "\n".join(L)
