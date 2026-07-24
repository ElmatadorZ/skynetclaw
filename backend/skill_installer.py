"""
skill_installer.py — install external Agent Skills (Claude format) into SkynetClaw
==================================================================================
Ingests a SKILL.md from a public GitHub repo. Anthropic/Vercel "Agent Skills"
carry frontmatter of only `name` + `description` (verified against
github.com/anthropics/skills) and NO `triggers`. SkynetClaw's auto-router is
trigger-driven, so an imported skill would never auto-activate (red-team F9).

This module therefore:
  1. fetches the external SKILL.md (github.com / raw.githubusercontent.com only),
  2. parses its frontmatter + body,
  3. AUTO-GENERATES triggers from the name + description,
  4. re-emits a SkynetClaw-format SKILL.md (with `source:` provenance),
  5. offers a dry-run REVIEW before writing (the body becomes an injected system
     prompt, so it must be seen first — red-team F11).

Writing the folder + DB sync is done via skills_loader / skills_auto_router, so
the imported skill plugs into the existing pipeline unchanged.

Pure helpers (parse/candidates/triggers/compose) are unit-tested offline; only
`fetch_text` and `resolve_and_fetch` touch the network.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_BASE = Path(__file__).parent
SKILLS_DIR = _BASE / "skills"

ALLOWED_HOSTS = ("github.com", "www.github.com", "raw.githubusercontent.com")
MAX_BODY = 60_000  # cap an imported skill body

# Stopwords (EN + a few Thai) so generated triggers are salient, not noise.
_STOP = {
    "the", "a", "an", "and", "or", "of", "to", "for", "in", "on", "at", "by",
    "with", "from", "into", "this", "that", "these", "those", "is", "are", "be",
    "as", "it", "its", "you", "your", "when", "how", "what", "which", "use",
    "using", "used", "can", "will", "should", "helps", "help", "clear", "skill",
    "agent", "claude", "any", "all", "not", "no", "yes", "also", "such",
    "about", "over", "under", "then", "than", "them", "they", "their", "been",
    "being", "only", "most", "more", "some", "each", "other", "out", "up",
    "so", "if", "but", "via", "per", "e.g", "eg", "etc", "may", "must", "who",
    "whom", "where", "while", "before", "after", "during", "across", "between",
    # generic verbs/fillers that produced garbage triggers on real imports
    # ("don", "like", "ask", "one", "user", "creating", "existing", ...)
    "user", "users", "ask", "asks", "asked", "like", "likes", "want", "wants",
    "need", "needs", "one", "two", "new", "make", "makes", "making", "made",
    "create", "creates", "creating", "created", "add", "adds", "adding",
    "get", "gets", "getting", "do", "does", "doing", "don", "dont", "won",
    "anything", "something", "everything", "here", "there", "into", "onto",
    "apart", "existing", "own", "well", "way", "ways", "work", "works",
    "working", "task", "tasks", "file", "files", "text", "content", "based",
    "และ", "หรือ", "ของ", "ให้", "ได้", "ที่", "เป็น", "กับ", "ใน", "การ",
}
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9+\-]{1,}|[฀-๿]{2,}")


# ── frontmatter (Claude flavour: name + description, description may be `|`) ──
def frontmatter_and_body(text: str) -> Tuple[Dict[str, Any], str]:
    """Split a SKILL.md into (frontmatter dict, body markdown)."""
    if not text.startswith("---"):
        return {}, text.strip()
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text.strip()
    fm_text = text[4:end]
    body = text[end + 4:].lstrip("\n")
    meta: Dict[str, Any] = {}
    key: Optional[str] = None
    multi: Optional[List[str]] = None
    lst: Optional[List[str]] = None
    for raw in fm_text.splitlines():
        line = raw.rstrip()
        if not line.strip():
            continue
        if lst is not None and line.lstrip().startswith("-"):
            v = line.lstrip()[1:].strip().strip('"\'')
            lst.append(v); continue
        if multi is not None and (line.startswith("  ") or line.startswith("\t")):
            multi.append(line.strip()); continue
        if multi is not None and key:
            meta[key] = " ".join(multi).strip(); multi = None
        if ":" in line and not line.startswith((" ", "\t")):
            lst = None
            k, _, v = line.partition(":")
            k = k.strip(); v = v.strip()
            key = k
            if v == "":
                lst = []; meta[k] = lst; continue
            if v == "|" or v == ">":
                multi = []; continue
            meta[k] = v.strip('"\'')
    if multi is not None and key:
        meta[key] = " ".join(multi).strip()
    return meta, body.strip()


# ── GitHub URL handling ──
def parse_github(repo_url: str) -> Optional[Tuple[str, str]]:
    """('owner','repo') from a github URL or 'owner/repo'. None if not github."""
    s = (repo_url or "").strip()
    m = re.search(r"github\.com[/:]+([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", s)
    if not m:
        m2 = re.fullmatch(r"([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", s)
        if not m2:
            return None
        owner, repo = m2.group(1), m2.group(2)
    else:
        owner, repo = m.group(1), m.group(2)
    repo = re.sub(r"\.git$", "", repo)
    return owner, repo


def raw_candidates(owner: str, repo: str, skill: Optional[str],
                   ref: Optional[str] = None) -> List[str]:
    """Ordered raw-URL guesses for a skill's SKILL.md across common layouts."""
    refs = [ref] if ref else ["main", "master"]
    sk = sanitize_name(skill) if skill else ""
    layouts: List[str] = []
    for r in refs:
        base = f"https://raw.githubusercontent.com/{owner}/{repo}/{r}"
        if sk:
            layouts += [
                f"{base}/skills/{sk}/SKILL.md",   # anthropics/skills layout
                f"{base}/{sk}/SKILL.md",          # flat layout
                f"{base}/skills/{sk}/skill.md",
                f"{base}/{sk}/skill.md",
            ]
        else:
            layouts += [f"{base}/SKILL.md", f"{base}/skill.md"]
    return layouts


# ── name + trigger generation ──
def sanitize_name(name: str) -> str:
    n = re.sub(r"[^a-z0-9_-]+", "-", (name or "").strip().lower()).strip("-")
    return n or "imported-skill"


def gen_triggers(name: str, description: str, extra: Tuple[str, ...] = ()) -> List[str]:
    """Salient trigger phrases from name+description (Claude skills have none).
    Deterministic: name words + name-as-phrase + top description keywords."""
    triggers: List[str] = []
    seen = set()

    def _add(t: str):
        t = t.strip().lower()
        if t and t not in seen and len(t) >= 2:
            seen.add(t); triggers.append(t)

    # name → phrase and its words
    nm = (name or "").replace("_", " ").replace("-", " ").strip()
    if nm:
        _add(nm)
        for w in nm.split():
            if w not in _STOP:
                _add(w)
    # description → salient PHRASES first (bigrams are far more precise than
    # single words — single-word triggers were the false-fire factory), then a
    # few salient single keywords.
    words = [w.lower() for w in _WORD.findall(description or "")]
    bi_freq: Dict[str, int] = {}
    for w1, w2 in zip(words, words[1:]):
        if w1 in _STOP or w2 in _STOP or len(w1) < 3 or len(w2) < 3:
            continue
        bg = f"{w1} {w2}"
        bi_freq[bg] = bi_freq.get(bg, 0) + 1
    for bg, _c in sorted(bi_freq.items(), key=lambda kv: (-kv[1], kv[0]))[:5]:
        _add(bg)
    freq: Dict[str, int] = {}
    for w in words:
        if w in _STOP or len(w) < 4:
            continue
        freq[w] = freq.get(w, 0) + 1
    for w, _c in sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))[:6]:
        _add(w)
    for e in extra:
        _add(e)
    return triggers[:16]


# ── compose SkynetClaw-format SKILL.md ──
def compose_skill_md(name: str, description: str, body: str, source: str,
                     triggers: List[str], version: str = "1.0") -> str:
    safe = sanitize_name(name)
    desc = (description or "").strip()
    body = (body or "").strip()[:MAX_BODY]
    desc_lines = "\n".join("  " + ln for ln in desc.splitlines()) or "  (imported skill)"
    trig_lines = "\n".join(f"  - {t}" for t in triggers) or "  - " + safe
    return (
        "---\n"
        f"name: {safe}\n"
        f"version: {version}\n"
        f"role: {safe}\n"
        f"source: {source}\n"
        "origin: imported (Agent Skill, Claude format)\n"
        "description: |\n"
        f"{desc_lines}\n"
        "triggers:\n"
        f"{trig_lines}\n"
        "---\n\n"
        f"{body}\n"
    )


def write_skill_folder(name: str, md_content: str) -> str:
    """Write backend/skills/<name>/SKILL.md; returns the folder path."""
    safe = sanitize_name(name)
    folder = SKILLS_DIR / safe
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(md_content, encoding="utf-8")
    return str(folder)


# ── network ──
async def fetch_text(url: str, client) -> Optional[str]:
    from urllib.parse import urlparse
    host = (urlparse(url).hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        return None
    try:
        r = await client.get(url, timeout=20, follow_redirects=True)
        if r.status_code == 200 and r.text.strip():
            return r.text
    except Exception:
        pass
    return None


async def resolve_and_fetch(repo_url: str, skill: Optional[str],
                            ref: Optional[str], client) -> Dict[str, Any]:
    """Fetch + parse the external skill. Returns a preview dict (no writes)."""
    gh = parse_github(repo_url)
    if not gh:
        return {"ok": False, "error": "not a GitHub repo url (owner/repo required)"}
    owner, repo = gh
    urls = raw_candidates(owner, repo, skill, ref)
    text = None; used = None
    for u in urls:
        text = await fetch_text(u, client)
        if text:
            used = u; break
    if not text:
        return {"ok": False, "error": "SKILL.md not found",
                "tried": urls, "owner": owner, "repo": repo}
    meta, body = frontmatter_and_body(text)
    name = sanitize_name(meta.get("name") or skill or repo)
    description = (meta.get("description") or "").strip()
    triggers = gen_triggers(name, description)
    md = compose_skill_md(name, description, body, used, triggers)
    return {
        "ok": True, "name": name, "description": description,
        "triggers": triggers, "source": used,
        "body_preview": body[:1200], "body_len": len(body),
        "target_folder": str(SKILLS_DIR / name),
        "skill_md": md,
        "has_frontmatter_name": bool(meta.get("name")),
    }
