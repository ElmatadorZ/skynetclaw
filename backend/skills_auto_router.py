"""
skills_auto_router.py — automatic skill activation by trigger match
=====================================================================
Lets SkynetClaw auto-load relevant skills based on what the user typed —
no manual UI activation needed.

Pipeline:
    user message -> tokenize -> score against trigger index -> top-K skills
                -> fetch each skill's system_prompt from skills DB
                -> return list of system messages to prepend before LLM call

Index source:
    backend/skills/<name>/SKILL.md  (frontmatter: triggers + description)
    Built into:  backend/skills_index.json  (sidecar, auto-rebuilt on boot)

Match algorithm:
    score = sum of:
      - exact trigger phrase appearance (weight 3.0)
      - any trigger word appearance     (weight 1.0)
      - description keyword overlap     (weight 0.4)
    Bilingual: Thai chars handled.

Threshold:
    score >= 1.0  ->  match
    Multi-match allowed (default top 2 skills, max 3).

License: Apache-2.0
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

_BASE   = Path(__file__).parent
DB_PATH = _BASE / "skynerclaw.db"
INDEX   = _BASE / "skills_index.json"


# ----------------------------------------------------------------------
# Tokenize - bilingual (English + Thai)
# ----------------------------------------------------------------------
_TOKEN_RE = re.compile(r"[\w฀-๿]+")


def _tokenize(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "")]


# ----------------------------------------------------------------------
# Frontmatter parser (matches skills_loader's flavor)
# ----------------------------------------------------------------------
def _parse_frontmatter(text: str) -> Dict[str, Any]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    out: Dict[str, Any] = {}
    current_key = None
    current_list: Optional[List[str]] = None
    multi: Optional[List[str]] = None
    for raw in text[4:end].splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if current_list is not None and line.startswith("  -"):
            v = line.strip()[1:].strip()
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            current_list.append(v); continue
        if multi is not None and (line.startswith("  ") or line.startswith("\t")):
            multi.append(line.strip()); continue
        if multi is not None and current_key:
            out[current_key] = " ".join(multi).strip(); multi = None
        if ":" in line and not line.startswith(" "):
            current_list = None
            k, _, v = line.partition(":")
            k = k.strip(); v = v.strip()
            current_key = k
            if v == "" or v == "|":
                if v == "|": multi = []
                else:
                    current_list = []
                    out[k] = current_list
                continue
            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                v = v[1:-1]
            out[k] = v
    if multi is not None and current_key:
        out[current_key] = " ".join(multi).strip()
    return out


# ----------------------------------------------------------------------
# Index builder
# ----------------------------------------------------------------------
def build_index() -> Dict[str, Any]:
    """Walk backend/skills/*/SKILL.md and write skills_index.json."""
    import time as _time
    skills_dir = _BASE / "skills"
    entries: List[Dict[str, Any]] = []
    if skills_dir.exists():
        for sub in sorted(skills_dir.iterdir()):
            if not sub.is_dir():
                continue
            sk = sub / "SKILL.md"
            if not sk.exists():
                continue
            try:
                text = sk.read_text(encoding="utf-8")
            except Exception:
                continue
            meta = _parse_frontmatter(text) or {}
            name = meta.get("name", sub.name)
            triggers = meta.get("triggers", []) or []
            description = (meta.get("description") or "")[:1200]
            role = meta.get("role", "")
            desc_tokens = list(set(_tokenize(description)))[:60]
            trig_tokens: List[str] = []
            for t in triggers:
                trig_tokens.extend(_tokenize(t))
            entries.append({
                "id":          f"skill_{name.replace('-','_')}",
                "name":        name,
                "version":     meta.get("version", "1.0"),
                "role":        role,
                "description": description[:300],
                "trigger_phrases": triggers,
                "trigger_tokens":  list(set(trig_tokens)),
                "desc_tokens":     desc_tokens,
                "folder":      str(sub),
            })
    index = {"built_at": _time.time(), "skills": entries}
    try:
        tmp = INDEX.with_suffix(".tmp")
        tmp.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(INDEX)
    except Exception as e:
        print(f"[skills_auto_router.build_index] write failed: {e}")
    return index


def load_index() -> Dict[str, Any]:
    if not INDEX.exists():
        return build_index()
    try:
        return json.loads(INDEX.read_text(encoding="utf-8"))
    except Exception:
        return build_index()


# ----------------------------------------------------------------------
# Matcher
# ----------------------------------------------------------------------
def _trust_factors() -> Dict[str, float]:
    """OX-SKILL-2: per-skill trust from the usage ledger joined to run outcomes.
    A skill that keeps failing is deprioritized (never silenced); a skill that
    keeps succeeding rises. Best-effort — routing must never break on this."""
    try:
        import skill_ledger
        from openclaw_port_tier2 import AgentRunsDB  # type: ignore
        runs = AgentRunsDB(DB_PATH).recent(limit=200) or []
        return skill_ledger.trust_factors(runs)
    except Exception:
        return {}


def match(text: str, top_k: int = 2, min_score: float = 1.0) -> List[Dict[str, Any]]:
    """Return up to top_k matching skills sorted by score desc.

    The raw trigger score is weighted by the skill's TRACK RECORD
    (skill_ledger trust factor, 0.6..1.4; unused skill = 1.0 neutral) — a
    skill develops standing through outcomes instead of being trusted
    equally forever."""
    if not text:
        return []
    idx = load_index()
    text_lower = text.lower()
    user_tokens = set(_tokenize(text))
    factors = _trust_factors()
    out: List[Dict[str, Any]] = []
    for sk in idx.get("skills", []):
        score = 0.0
        matched_phrases: List[str] = []
        matched_tokens:  List[str] = []
        for phrase in sk.get("trigger_phrases", []):
            if phrase and phrase.lower() in text_lower:
                score += 3.0
                matched_phrases.append(phrase)
        trig_overlap = user_tokens & set(sk.get("trigger_tokens", []))
        if trig_overlap:
            score += 1.0 * len(trig_overlap)
            matched_tokens.extend(sorted(trig_overlap)[:6])
        desc_overlap = user_tokens & set(sk.get("desc_tokens", []))
        if desc_overlap:
            score += 0.4 * len(desc_overlap)
        factor = float(factors.get(sk["name"], 1.0))
        weighted = score * factor
        if weighted >= min_score:
            out.append({
                "id":              sk["id"],
                "name":            sk["name"],
                "role":            sk.get("role", ""),
                "score":           round(weighted, 2),
                "raw_score":       round(score, 2),
                "trust_factor":    round(factor, 2),
                "matched_phrases": matched_phrases[:5],
                "matched_tokens":  matched_tokens[:5],
            })
    out.sort(key=lambda m: -m["score"])
    return out[:top_k]


# ----------------------------------------------------------------------
# Fetch system_prompt from DB
# ----------------------------------------------------------------------
def fetch_system_prompt(skill_id: str) -> str:
    if not DB_PATH.exists():
        return ""
    try:
        with sqlite3.connect(DB_PATH) as c:
            row = c.execute(
                "SELECT system_prompt FROM skills WHERE id=?", (skill_id,)
            ).fetchone()
        return row[0] if row else ""
    except Exception:
        return ""


def auto_skill_messages(text: str, top_k: int = 2,
                         min_score: float = 1.0,
                         max_prompt_chars: int = 6000) -> List[Dict[str, Any]]:
    """
    Returns a list of system messages (role=system) to prepend before the
    user task, one per matched skill.

    Each entry is shaped like {role: "system", content: "...", skill_meta: {...}}
    """
    matches = match(text, top_k=top_k, min_score=min_score)
    out: List[Dict[str, Any]] = []
    for m in matches:
        prompt = fetch_system_prompt(m["id"])
        if not prompt:
            # Fallback: if DB row missing, try reading SKILL.md body directly
            idx = load_index()
            for sk in idx.get("skills", []):
                if sk["id"] == m["id"]:
                    try:
                        sk_md = Path(sk["folder"]) / "SKILL.md"
                        body = sk_md.read_text(encoding="utf-8")
                        # strip frontmatter
                        if body.startswith("---"):
                            end = body.find("\n---", 4)
                            if end >= 0:
                                body = body[end+4:].strip()
                        prompt = body
                    except Exception:
                        pass
                    break
        if not prompt:
            continue
        if len(prompt) > max_prompt_chars:
            prompt = prompt[:max_prompt_chars] + "\n\n[... skill body truncated ...]"
        matched_label = ', '.join(m['matched_phrases'] or m['matched_tokens'])
        wrapped = (
            f"=== AUTO-ACTIVATED SKILL: {m['name']} "
            f"(score {m['score']}, matched: {matched_label}) ===\n\n"
            f"{prompt}\n\n"
            f"=== END SKILL ==="
        )
        out.append({
            "role":       "system",
            "content":    wrapped,
            "skill_meta": m,
        })
    return out


# ----------------------------------------------------------------------
# Self-test
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass

    print("=== skills_auto_router self-test ===\n")
    idx = build_index()
    print(f"Index built: {len(idx.get('skills', []))} skill(s)\n")

    cases = [
        "find a tool for vector database for local python",
        "best library for OCR Thai language",
        "compare Chroma vs FAISS vs Qdrant",
        "hello what should we eat today",
        "what framework should we use",
        "learn how to do RAG locally",
    ]
    for c in cases:
        matches = match(c, top_k=2)
        if matches:
            print(f"\n>>> \"{c[:70]}\"")
            for m in matches:
                phrases = ", ".join(m['matched_phrases'][:2])
                tokens  = ", ".join(m['matched_tokens'][:3])
                print(f"   [+] {m['name']:25s} score={m['score']:5.1f}")
                if phrases: print(f"       phrases: {phrases}")
                if tokens:  print(f"       tokens : {tokens}")
        else:
            print(f"\n>>> \"{c[:70]}\"  ->  (no skill match)")

    print(f"\n=== auto_skill_messages test ===")
    msgs = auto_skill_messages(
        "find a tool for vector database for local python", top_k=1)
    for m in msgs:
        meta = m["skill_meta"]
        print(f"  injecting: {meta['name']} (score {meta['score']})")
        print(f"  prompt size: {len(m['content']):,} chars")
        print(f"  preview: {m['content'][:200]}...")

    print(f"\n=== self-test OK ===")
