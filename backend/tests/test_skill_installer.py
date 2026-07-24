"""
test_skill_installer.py — external Agent-Skill installer + F1 schema fix
=======================================================================
Locks the P0+P1 work:
  * F1 regression: POST /api/skills no longer breaks on the co-owned 10-column
    skills table (explicit columns).
  * Installer pure helpers: GitHub URL parse, raw-URL candidates, name
    sanitisation, deterministic trigger generation, Claude-frontmatter parse.
  * Round-trip: the SkynetClaw SKILL.md the installer composes MUST re-parse in
    skills_auto_router (else the imported skill gets no triggers → never
    activates, defeating the whole point / F9).
  * Live (network, auto-skips offline): fetch a real Agent Skill from
    github.com/anthropics/skills and confirm triggers are generated.

    python backend/tests/test_skill_installer.py
"""
from __future__ import annotations
import sys, os, json, sqlite3, tempfile, asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import skill_installer as si
import skills_auto_router as sar

RESULTS = {}


def t_github_parse():
    print("== T1: parse_github ==")
    cases = [
        ("https://github.com/anthropics/skills", ("anthropics", "skills")),
        ("https://github.com/vercel-labs/agent-skills.git", ("vercel-labs", "agent-skills")),
        ("github.com/obra/superpowers", ("obra", "superpowers")),
        ("anthropics/skills", ("anthropics", "skills")),
        ("https://example.com/not/github", None),
    ]
    ok = True
    for url, exp in cases:
        got = si.parse_github(url)
        if got != exp: ok = False
        print(f"  {'OK ' if got==exp else 'FAIL'} {url} -> {got}")
    RESULTS["T1"] = ok; assert ok


def t_candidates_and_name():
    print("== T2: raw_candidates + sanitize_name ==")
    urls = si.raw_candidates("anthropics", "skills", "pdf", ref=None)
    checks = {
        "tries anthropics skills/ layout": any("/skills/pdf/SKILL.md" in u for u in urls),
        "tries flat layout": any(u.endswith("/pdf/SKILL.md") for u in urls),
        "tries both main and master": any("/main/" in u for u in urls) and any("/master/" in u for u in urls),
        "sanitize strips path traversal": si.sanitize_name("../../etc/passwd") == "etc-passwd",
        "sanitize lowercases": si.sanitize_name("Frontend Design") == "frontend-design",
    }
    for k, v in checks.items():
        print(f"  {'OK ' if v else 'FAIL'} {k}")
    RESULTS["T2"] = all(checks.values()); assert RESULTS["T2"]


def t_triggers():
    print("== T3: gen_triggers (salient, deterministic, name-inclusive) ==")
    trg = si.gen_triggers("systematic-debugging",
                          "Systematically debug failures by forming and testing hypotheses about the root cause.")
    trg2 = si.gen_triggers("systematic-debugging",
                           "Systematically debug failures by forming and testing hypotheses about the root cause.")
    checks = {
        "includes name words": "systematic" in trg and "debugging" in trg,
        "includes name phrase": "systematic debugging" in trg,
        "extracts salient keyword": ("hypotheses" in trg or "root" in trg or "failures" in trg),
        "drops stopwords": not ({"the", "and", "by", "about"} & set(trg)),
        "deterministic": trg == trg2,
        "non-empty, capped": 0 < len(trg) <= 16,
    }
    for k, v in checks.items():
        print(f"  {'OK ' if v else 'FAIL'} {k}")
    RESULTS["T3"] = all(checks.values()); assert RESULTS["T3"], str(trg)


def t_frontmatter_and_roundtrip():
    print("== T4: Claude frontmatter parse + round-trip through the router ==")
    claude = ("---\n"
              "name: pdf\n"
              "description: Fill PDF forms and extract text from PDF documents.\n"
              "---\n\n"
              "# PDF skill\nRun scripts/fill_form.py to fill a form.\n")
    meta, body = si.frontmatter_and_body(claude)
    # compose SkynetClaw md + re-parse it exactly as the auto-router would
    trg = si.gen_triggers(meta.get("name"), meta.get("description"))
    md = si.compose_skill_md(meta["name"], meta["description"], body,
                             "https://raw.githubusercontent.com/anthropics/skills/main/skills/pdf/SKILL.md", trg)
    reparsed = sar._parse_frontmatter(md)
    checks = {
        "claude name parsed": meta.get("name") == "pdf",
        "claude description parsed": "extract text" in (meta.get("description") or ""),
        "body preserved": "fill_form.py" in body,
        "composed md re-parses in router": bool(reparsed),
        "router sees triggers (list)": isinstance(reparsed.get("triggers"), list) and len(reparsed["triggers"]) > 0,
        "router sees description": "pdf" in (reparsed.get("description", "").lower()),
        "provenance source recorded": reparsed.get("source", "").startswith("https://raw.githubusercontent.com/"),
    }
    for k, v in checks.items():
        print(f"  {'OK ' if v else 'FAIL'} {k}")
    RESULTS["T4"] = all(checks.values()); assert RESULTS["T4"], json.dumps(reparsed, ensure_ascii=False)[:300]


def t_f1_create_fix():
    print("== T5: F1 fix — skills_create works on the co-owned 10-col schema ==")
    import main as m
    tmp = tempfile.mktemp(suffix=".db"); old = m.DB_PATH
    ok = True
    try:
        m.DB_PATH = tmp
        con = sqlite3.connect(tmp)
        # main.py's original schema ...
        con.execute("CREATE TABLE skills(id TEXT PRIMARY KEY, name TEXT, description TEXT, "
                    "system_prompt TEXT, tools TEXT DEFAULT '[]', created_at REAL, updated_at REAL)")
        # ... then skills_loader ALTERs in version/triggers/folder (the drift that broke it)
        for col, typ in (("version", "TEXT"), ("triggers", "TEXT"), ("folder", "TEXT")):
            con.execute(f"ALTER TABLE skills ADD COLUMN {col} {typ}")
        con.commit(); con.close()
        # the FIXED create must succeed against 10 columns
        res = asyncio.run(m.skills_create(m.SkillReq(
            name="t", description="d", system_prompt="p", tools=[], triggers=["x"])))
        con = sqlite3.connect(tmp)
        row = con.execute("SELECT name, triggers FROM skills WHERE id=?", (res["id"],)).fetchone()
        con.close()
        checks = {
            "create returned id": bool(res.get("id")),
            "row persisted": row is not None and row[0] == "t",
            "triggers stored": row and json.loads(row[1]) == ["x"],
        }
        for k, v in checks.items():
            if not v: ok = False
            print(f"  {'OK ' if v else 'FAIL'} {k}")
    except Exception as e:
        ok = False; print(f"  FAIL exception: {type(e).__name__}: {e}")
    finally:
        m.DB_PATH = old
        try: os.remove(tmp)
        except Exception: pass
    RESULTS["T5"] = ok; assert ok


def t_live_fetch():
    print("== T6: LIVE fetch a real Agent Skill (auto-skip offline) ==")
    import httpx
    async def go():
        async with httpx.AsyncClient() as c:
            # probe connectivity first
            try:
                await c.get("https://raw.githubusercontent.com", timeout=8)
            except Exception:
                return None
            return await si.resolve_and_fetch("https://github.com/anthropics/skills",
                                              "skill-creator", None, c)
    prev = asyncio.run(go())
    if prev is None:
        print("  SKIP (offline / GitHub unreachable)"); RESULTS["T6"] = None; return
    if not prev.get("ok"):
        # not a hard fail — repo layout/name may have moved; report honestly
        print(f"  SKIP (fetch not ok: {prev.get('error')}; tried {len(prev.get('tried',[]))} urls)")
        RESULTS["T6"] = None; return
    checks = {
        "fetched a real skill": prev["ok"],
        "name resolved": bool(prev["name"]),
        "triggers auto-generated (fixes F9)": len(prev["triggers"]) > 0,
        "provenance source set": prev["source"].startswith("https://raw.githubusercontent.com/"),
        "body non-trivial": prev["body_len"] > 100,
    }
    for k, v in checks.items():
        print(f"  {'OK ' if v else 'FAIL'} {k}")
    print(f"  -> name={prev['name']} triggers={prev['triggers'][:6]}")
    RESULTS["T6"] = all(checks.values()); assert RESULTS["T6"]


def main():
    t_github_parse(); t_candidates_and_name(); t_triggers()
    t_frontmatter_and_roundtrip(); t_f1_create_fix(); t_live_fetch()
    print("\n== SUMMARY ==")
    core = ("T1", "T2", "T3", "T4", "T5")
    for k in core + ("T6",):
        v = RESULTS.get(k)
        print(f"  {k}: {'PASS' if v else ('SKIP' if v is None else 'FAIL')}")
    allok = all(RESULTS.get(k) for k in core)
    print("\n  " + ("ALL CORE SKILL-INSTALLER TESTS PASS" if allok else "FAILURES PRESENT"))
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
