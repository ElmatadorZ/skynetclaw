"""
capability_skill_registry.py — Capability-Skill Architecture (CSA v1)
=====================================================================
Skills are assets BOUND TO CAPABILITIES, not prompt blobs matched by
bag-of-words. See docs/skills/CAPABILITY_SKILL_ARCHITECTURE.md.

Pipeline:
    task text (th/en)
      -> resolve()   : weighted bilingual keywords -> capabilities
      -> bind()      : SKILL.md `capabilities:` frontmatter + DEFAULT_BINDINGS
      -> activate()  : PRIMARY skill full body + compact cards, budget-capped
Runtime discovery (novel tasks):
      find_skills(query)  -> ranked metadata (never bodies)
      skill_body(name)    -> one full playbook on demand

Matching rules:
    - Thai keywords are SUBSTRING-matched (Thai has no word boundaries).
    - English keywords are token-matched; multiword phrases substring-matched.
    - Capability activates at score >= 2.0 (one strong hit or two weak) —
      preserves the g4 no-false-positive golden.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_BASE = Path(__file__).parent
SKILLS_DIR = _BASE / "skills"
INDEX_PATH = _BASE / "skills_capability_index.json"

ACTIVATION_BUDGET = 7000   # total chars injected per task (16k-ceiling law)
PRIMARY_BODY_CAP  = 5000   # full body for the top skill
CARD_CAP          = 420    # compact card for every other skill
ACTIVATE_THRESHOLD = 2.0

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")
_THAI_RE  = re.compile(r"[฀-๿]")


# ══════════════════════════════════════════════════════════════════════
# Capability taxonomy — bilingual weighted keywords
#   weight 2.0 = strong (activates alone) · 1.0 = weak (needs a partner)
# ══════════════════════════════════════════════════════════════════════
TAXONOMY: Dict[str, Dict[str, Any]] = {
    "design.frontend": {
        "label": "Frontend & Visual Design",
        "keywords": {
            "ออกแบบ": 2.0, "ดีไซน์": 2.0, "สวยงาม": 2.0, "หน้าตา ui": 2.0,
            "ปรับปรุง ui": 2.0, "หน้าเว็บ": 2.0, "สร้างเว็บ": 2.0,
            "landing page": 2.0, "frontend": 2.0, "redesign": 2.0,
            "aesthetic": 2.0, "typography": 2.0, "โทนสี": 2.0, "ธีม": 1.0,
            "สวย": 1.0, "design": 1.0, "ui": 1.0, "ux": 1.0, "css": 1.0,
            "layout": 1.0, "web page": 1.0, "webpage": 1.0, "html": 1.0,
            "style": 1.0, "theme": 1.0,
        },
        "skills": ["frontend-design", "web-dashboard-builder"],
    },
    "design.dashboard": {
        "label": "Dashboards & Data Visualization",
        "keywords": {
            "dashboard": 2.0, "แดชบอร์ด": 2.0, "แสดงผลข้อมูล": 2.0,
            "data visualization": 2.0, "visualize": 2.0, "กราฟ": 1.0,
            "chart": 1.0, "graph": 1.0, "รายงาน html": 2.0, "report page": 2.0,
        },
        "skills": ["web-dashboard-builder", "frontend-design"],
    },
    "design.review": {
        "label": "UI Review & Accessibility",
        "keywords": {
            "accessibility": 2.0, "review ui": 2.0, "audit design": 2.0,
            "ตรวจ ui": 2.0, "ตรวจหน้าเว็บ": 2.0, "a11y": 2.0,
            "review ux": 2.0, "usability": 1.0,
        },
        "skills": ["web-design-guidelines"],
    },
    "engineering.debugging": {
        "label": "Debugging & Root Cause",
        "keywords": {
            "debug": 2.0, "ดีบัก": 2.0, "แก้บั๊ก": 2.0, "traceback": 2.0,
            "stack trace": 2.0, "root cause": 2.0, "หาสาเหตุ": 2.0,
            "bug": 1.0, "บั๊ก": 1.0, "error": 1.0, "crash": 1.0, "พัง": 1.0,
        },
        "skills": ["systematic-debugging"],
    },
    "discovery.search": {
        "label": "Tool & Skill Discovery",
        "keywords": {
            "find a tool": 2.0, "find skill": 2.0, "find a skill": 2.0,
            "หาเครื่องมือ": 2.0, "หา skill": 2.0, "which library": 2.0,
            "which framework": 2.0, "best library": 2.0, "best framework": 2.0,
            "vector database": 2.0, "ocr": 2.0, "find library": 2.0,
            "มี skill ไหม": 2.0, "มีเครื่องมือ": 2.0,
        },
        "skills": ["agent-find-skill", "find-skills"],
    },
    "planning.strategic": {
        "label": "Strategic Planning",
        "keywords": {
            "วางแผน": 2.0, "roadmap": 2.0, "strategy": 2.0, "กลยุทธ์": 2.0,
            "strategic plan": 2.0, "แผนงาน": 2.0, "milestone": 1.0,
        },
        "skills": ["strategic-planning", "scenario-forecasting"],
    },
    "analysis.macro": {
        "label": "Macro & Market Analysis",
        "keywords": {
            "วิเคราะห์เศรษฐกิจ": 2.0, "macro analysis": 2.0, "เงินเฟ้อ": 2.0,
            "inflation": 2.0, "ดอกเบี้ยนโยบาย": 2.0, "fed": 1.0,
            "เศรษฐกิจ": 1.0, "macro": 1.0,
        },
        "skills": ["atlas-macro-analysis"],
    },
    "knowledge.vault": {
        "label": "Obsidian Knowledge Vault",
        "keywords": {
            "obsidian": 2.0, "vault": 2.0, "second brain": 2.0,
            "โน้ตความรู้": 2.0, "คลังความรู้": 2.0,
        },
        "skills": ["obsidian-knowledge-protocol"],
    },
    "document.pdf": {
        "label": "PDF Processing",
        "keywords": {"pdf": 2.0, "ไฟล์ pdf": 2.0},
        "skills": ["pdf"],
    },
    "authoring.skill": {
        "label": "Skill Authoring",
        "keywords": {
            "create skill": 2.0, "สร้าง skill": 2.0, "new skill": 2.0,
            "write a skill": 2.0, "เขียน skill": 2.0,
        },
        "skills": ["skill-creator"],
    },
    "security.boundary": {
        "label": "Security Boundaries",
        "keywords": {
            "security": 2.0, "ความปลอดภัย": 2.0, "prompt injection": 2.0,
            "secret": 1.0, "credential": 2.0, "ช่องโหว่": 2.0,
        },
        "skills": ["security-boundary"],
    },
    "quality.verification": {
        "label": "Quality Verification",
        "keywords": {
            "verify": 2.0, "ตรวจสอบผลงาน": 2.0, "ทดสอบการใช้งาน": 2.0,
            "quality check": 2.0, "ตรวจคุณภาพ": 2.0, "acceptance": 1.0,
        },
        "skills": ["quality-verification", "web-design-guidelines"],
    },
    "orchestration.mission": {
        "label": "Mission Orchestration",
        "keywords": {
            "orchestrate": 2.0, "หลายภารกิจ": 2.0, "multi-agent": 2.0,
            "ประสานงาน agent": 2.0, "delegate": 1.0,
        },
        "skills": ["commander-orchestration", "mission-intake-routing"],
    },
    "reasoning.evidence": {
        "label": "Evidence & Grounding",
        "keywords": {
            "evidence": 2.0, "หลักฐาน": 2.0, "grounding": 2.0,
            "อ้างอิงจริง": 2.0, "no fabrication": 2.0,
        },
        "skills": ["evidence-grounding", "execution-discipline"],
    },
    "architecture.system": {
        "label": "System Architecture",
        "keywords": {
            "architecture": 2.0, "สถาปัตยกรรม": 2.0, "system design": 2.0,
            "ออกแบบระบบ": 2.0, "adr": 2.0,
        },
        "skills": ["system-architecture", "shadow-gate-critique"],
    },
    "synthesis.briefing": {
        "label": "Synthesis & Briefing",
        "keywords": {
            "brief": 2.0, "บรีฟ": 2.0, "synthesize": 2.0, "executive summary": 2.0,
            "สรุปผู้บริหาร": 2.0,
        },
        "skills": ["synthesis-briefing"],
    },
    "governance.arbitration": {
        "label": "Governance & Arbitration",
        "keywords": {
            "governance": 2.0, "arbitration": 2.0, "ธรรมาภิบาล": 2.0,
            "ตัดสินข้อขัดแย้ง": 2.0,
        },
        "skills": ["governance-arbitration"],
    },
}

# Skills not (yet) declaring `capabilities:` in frontmatter fall back to the
# reverse of TAXONOMY's skills lists — built once at index time.


# ══════════════════════════════════════════════════════════════════════
# Index — reuses the router's frontmatter parser (single parsing flavor)
# ══════════════════════════════════════════════════════════════════════
def _default_bindings() -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for cap, spec in TAXONOMY.items():
        for name in spec.get("skills", []):
            out.setdefault(name, [])
            if cap not in out[name]:
                out[name].append(cap)
    return out


def build_index() -> Dict[str, Any]:
    """Walk backend/skills/*/SKILL.md into skills_capability_index.json."""
    from skills_auto_router import _parse_frontmatter  # same flavor, one parser
    bindings = _default_bindings()
    entries: List[Dict[str, Any]] = []
    if SKILLS_DIR.exists():
        for sub in sorted(SKILLS_DIR.iterdir()):
            sk = sub / "SKILL.md"
            if not sub.is_dir() or not sk.exists():
                continue
            try:
                text = sk.read_text(encoding="utf-8")
            except Exception:
                continue
            meta = _parse_frontmatter(text) or {}
            name = meta.get("name", sub.name)
            caps = meta.get("capabilities") or bindings.get(name, [])
            if isinstance(caps, str):
                caps = [caps]
            entries.append({
                "name":         name,
                "role":         meta.get("role", ""),
                "version":      meta.get("version", "1.0"),
                "description":  (meta.get("description") or "")[:400],
                "capabilities": caps,
                "triggers":     meta.get("triggers", []) or [],
                "folder":       str(sub),
            })
    index = {"built_at": time.time(), "skills": entries}
    try:
        tmp = INDEX_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(INDEX_PATH)
    except Exception as e:
        print(f"[capability_registry.build_index] write failed: {e}")
    return index


def load_index() -> Dict[str, Any]:
    if not INDEX_PATH.exists():
        return build_index()
    try:
        idx = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        # auto-rebuild when any SKILL.md is newer than the index
        built = float(idx.get("built_at", 0))
        if SKILLS_DIR.exists():
            for sub in SKILLS_DIR.iterdir():
                sk = sub / "SKILL.md"
                if sk.exists() and sk.stat().st_mtime > built:
                    return build_index()
        return idx
    except Exception:
        return build_index()


# ══════════════════════════════════════════════════════════════════════
# Resolution — task text -> capabilities
# ══════════════════════════════════════════════════════════════════════
def _score_keywords(text: str, keywords: Dict[str, float]) -> Tuple[float, List[str]]:
    text_low = text.lower()
    tokens = set(t.lower() for t in _TOKEN_RE.findall(text))
    score, hits = 0.0, []
    for kw, w in keywords.items():
        kwl = kw.lower()
        if _THAI_RE.search(kwl) or " " in kwl:
            if kwl in text_low:
                score += w; hits.append(kw)
        else:
            if kwl in tokens:
                score += w; hits.append(kw)
    return score, hits


def resolve(text: str, threshold: float = ACTIVATE_THRESHOLD) -> List[Dict[str, Any]]:
    """Return activated capabilities sorted by score desc."""
    if not text:
        return []
    out = []
    for cap, spec in TAXONOMY.items():
        score, hits = _score_keywords(text, spec["keywords"])
        if score >= threshold:
            out.append({"capability": cap, "label": spec.get("label", cap),
                        "score": round(score, 2), "matched": hits[:6]})
    out.sort(key=lambda c: -c["score"])
    return out


# ══════════════════════════════════════════════════════════════════════
# Binding + trust
# ══════════════════════════════════════════════════════════════════════
def _trust_factors() -> Dict[str, float]:
    try:
        import skill_ledger
        from openclaw_port_tier2 import AgentRunsDB  # type: ignore
        runs = AgentRunsDB(_BASE / "skynerclaw.db").recent(limit=200) or []
        return skill_ledger.trust_factors(runs)
    except Exception:
        return {}


def bind(caps: List[Dict[str, Any]], max_skills: int = 3) -> List[Dict[str, Any]]:
    """Capabilities -> ranked, deduped skills (trust-weighted)."""
    idx = {s["name"]: s for s in load_index().get("skills", [])}
    factors = _trust_factors()
    ranked: Dict[str, Dict[str, Any]] = {}
    for c in caps:
        spec = TAXONOMY.get(c["capability"], {})
        for pos, name in enumerate(spec.get("skills", [])):
            if name not in idx:
                continue
            trust = float(factors.get(name, 1.0))
            # earlier position in the capability's skill list = stronger binding
            s = c["score"] * (1.0 - 0.15 * pos) * trust
            cur = ranked.get(name)
            if not cur or s > cur["rank_score"]:
                ranked[name] = {
                    "name": name, "capability": c["capability"],
                    "rank_score": round(s, 2), "trust": round(trust, 2),
                    "description": idx[name].get("description", ""),
                    "folder": idx[name].get("folder", ""),
                }
    out = sorted(ranked.values(), key=lambda s: -s["rank_score"])
    return out[:max_skills]


# ══════════════════════════════════════════════════════════════════════
# Bodies + activation (budgeted injection)
# ══════════════════════════════════════════════════════════════════════
def skill_body(name: str, max_chars: int = PRIMARY_BODY_CAP) -> str:
    """Full playbook for one skill: DB system_prompt first, SKILL.md fallback."""
    body = ""
    try:
        from skills_auto_router import fetch_system_prompt
        body = fetch_system_prompt(f"skill_{name.replace('-', '_')}") or ""
    except Exception:
        pass
    if not body:
        for s in load_index().get("skills", []):
            if s["name"] == name:
                try:
                    text = (Path(s["folder"]) / "SKILL.md").read_text(encoding="utf-8")
                    if text.startswith("---"):
                        end = text.find("\n---", 4)
                        if end >= 0:
                            text = text[end + 4:]
                    body = text.strip()
                except Exception:
                    pass
                break
    if len(body) > max_chars:
        body = body[:max_chars] + "\n\n[... truncated - full playbook via use_skill ...]"
    return body


def activate_for_task(text: str, top_k: int = 3, **_legacy_kw) -> List[Dict[str, Any]]:
    """Drop-in for skills_auto_router.auto_skill_messages().

    Returns [{"role":"system","content":...,"skill_meta":{...}}].
    PRIMARY (top-ranked) skill -> full body; others -> compact cards that
    teach the model to pull the rest itself via use_skill(). Total chars
    never exceed ACTIVATION_BUDGET (the 16k-ceiling law).
    """
    caps = resolve(text)
    skills = bind(caps, max_skills=top_k) if caps else []

    # Strangler-fig fallback: legacy trigger router at a CONSERVATIVE threshold
    if not skills:
        try:
            from skills_auto_router import auto_skill_messages
            return auto_skill_messages(text, top_k=1, min_score=3.0,
                                       max_prompt_chars=PRIMARY_BODY_CAP)
        except Exception:
            return []

    out: List[Dict[str, Any]] = []
    used = 0
    for i, s in enumerate(skills):
        if i == 0:
            body = skill_body(s["name"], max_chars=min(PRIMARY_BODY_CAP,
                                                       ACTIVATION_BUDGET - used))
            if not body:
                continue
            content = (
                f"=== CAPABILITY-ACTIVATED SKILL: {s['name']} "
                f"[{s['capability']}] (rank {s['rank_score']}) ===\n\n"
                f"{body}\n\n=== END SKILL ==="
            )
        else:
            desc = (s["description"] or "").strip()[:CARD_CAP]
            content = (
                f"[SKILL AVAILABLE: {s['name']} - {s['capability']}] {desc}\n"
                f"-> If this task needs it, call use_skill(\"{s['name']}\") "
                f"for the full playbook."
            )
        if used + len(content) > ACTIVATION_BUDGET and out:
            break
        used += len(content)
        out.append({
            "role": "system", "content": content,
            "skill_meta": {"name": s["name"], "capability": s["capability"],
                           "score": s["rank_score"], "trust": s["trust"],
                           "mode": "primary" if i == 0 else "card"},
        })
    return out


# ══════════════════════════════════════════════════════════════════════
# Runtime discovery — find_skill / use_skill tool backends
# ══════════════════════════════════════════════════════════════════════
def find_skills(query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Bilingual ranked search over the registry: capabilities, name,
    description, triggers. Returns metadata only (bodies via skill_body)."""
    if not query:
        return []
    q_low = query.lower()
    q_tokens = set(t.lower() for t in _TOKEN_RE.findall(query))
    cap_scores = {c["capability"]: c["score"] for c in resolve(query, threshold=1.0)}
    out = []
    for s in load_index().get("skills", []):
        score = 0.0
        why = []
        for cap in s.get("capabilities", []):
            if cap in cap_scores:
                score += 2.0 * cap_scores[cap]; why.append(f"capability:{cap}")
        name_l = s["name"].lower()
        if name_l in q_low or any(t in name_l for t in q_tokens):
            score += 2.0; why.append("name")
        d_tokens = set(t.lower() for t in _TOKEN_RE.findall(s.get("description", "")))
        overlap = q_tokens & d_tokens
        if overlap:
            score += 0.5 * len(overlap); why.append("description")
        for trig in s.get("triggers", []):
            tl = str(trig).lower()
            if (_THAI_RE.search(tl) or " " in tl) and tl in q_low:
                score += 1.5; why.append(f"trigger:{trig}")
            elif tl in q_tokens:
                score += 1.0; why.append(f"trigger:{trig}")
        if score > 0:
            out.append({"name": s["name"], "score": round(score, 2),
                        "capabilities": s.get("capabilities", []),
                        "description": s.get("description", "")[:220],
                        "matched_on": why[:4]})
    out.sort(key=lambda s: -s["score"])
    return out[:top_k]


def architecture() -> Dict[str, Any]:
    """Capability -> skills tree for the UI / endpoint."""
    idx = {s["name"]: s for s in load_index().get("skills", [])}
    caps = []
    bound = set()
    for cap, spec in TAXONOMY.items():
        skills = []
        for name in spec.get("skills", []):
            s = idx.get(name)
            if s:
                bound.add(name)
                skills.append({"name": name,
                               "description": s.get("description", "")[:160]})
        caps.append({"capability": cap, "label": spec.get("label", cap),
                     "n_keywords": len(spec.get("keywords", {})),
                     "skills": skills})
    unbound = [{"name": n, "description": s.get("description", "")[:160]}
               for n, s in sorted(idx.items()) if n not in bound]
    return {"capabilities": sorted(caps, key=lambda c: c["capability"]),
            "unbound_skills": unbound,
            "n_skills": len(idx), "n_capabilities": len(TAXONOMY)}


# ══════════════════════════════════════════════════════════════════════
# Self-test (ASCII-only output — cp1252 consoles)
# ══════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

    idx = build_index()
    print(f"index: {len(idx['skills'])} skills")

    cases = [
        "ปรับปรุง UI dashboard ให้สวยงามและใช้งานง่าย",
        "debug this traceback in main.py",
        "find a tool for vector database",
        "สวัสดีครับ สบายดีไหม",
        "ช่วยคำนวณ 15 คูณ 3 หน่อย",
        "สรุปข่าวราคาทองวันนี้",
    ]
    for c in cases:
        caps = resolve(c)
        names = [f"{x['capability']}({x['score']})" for x in caps]
        msgs = activate_for_task(c)
        act = [m["skill_meta"]["name"] + ":" + m["skill_meta"].get("mode", "?")
               for m in msgs]
        total = sum(len(m["content"]) for m in msgs)
        print(f"- caps={names or '[]'} skills={act or '[]'} chars={total}")
        assert total <= ACTIVATION_BUDGET, "budget exceeded"

    fs = find_skills("ocr thai language")
    print("find_skills('ocr thai language'):", [f['name'] for f in fs])
    print("self-test OK")
