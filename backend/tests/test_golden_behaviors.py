"""
test_golden_behaviors.py — LIVE behavioral eval harness (quality ratchet)
=========================================================================
Every quality finding this project has hit was caught by hand, once, then left
unguarded. This harness turns the recurring ones into a repeatable, scored,
BEHAVIORAL check: real prompts against the running backend, assertions on what
the model actually DOES (not on exact wording). Run it to get a baseline; run it
after any change to see the delta as a number.

Each golden behavior is tied to a real failure we saw:
  G1  workspace-file grounding   — "13 files mounted but asks which file"
  G2  operational grounding      — "analyze failures" -> all UNKNOWN
  G3  R8 no-fabrication          — invented example.txt / faked tool calls
  G4  matcher no-false-positive  — skills auto-fire on unrelated tasks (F2)
  G5  execution write-file       — false TASK_COMPLETE / cold-start FAILED

    python backend/tests/test_golden_behaviors.py

Notes:
  * G4 is deterministic (pure matcher). G1/G2/G3/G5 exercise the live model, so
    they carry model nondeterminism — each gets one retry on a transient error.
  * If the backend is down -> SKIP all cleanly. If the model runtime is down ->
    the live behaviors are marked UNAVAILABLE (not FAIL) so a dead :8080 is never
    mistaken for a quality regression.
"""
from __future__ import annotations
import sys, os, json, time, sqlite3, tempfile, urllib.request, urllib.error
from pathlib import Path

# UTF-8-safe stdout so the emoji/box-drawing scorecard never dies on Windows cp1252.
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

API = "http://127.0.0.1:8766"
DB = str(Path(__file__).resolve().parent.parent / "skynerclaw.db")
RESULTS = {}   # name -> "PASS" | "FAIL" | "SKIP"


# ── transport ────────────────────────────────────────────────────────────────
def _reachable() -> bool:
    try:
        urllib.request.urlopen(API + "/api/connections", timeout=6).read()
        return True
    except Exception:
        return False


def _stream(path: str, body: dict, timeout: int = 150):
    """POST an SSE endpoint; return (text, final_status, tools, unreachable)."""
    req = urllib.request.Request(API + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    text, final, tools, unreachable = [], None, [], False
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            for raw in r:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line.startswith("data: "):
                    continue
                try: ev = json.loads(line[6:])
                except Exception: continue
                t = ev.get("type")
                if t in ("text", "agent_think"): text.append(ev.get("text", ""))
                elif t == "agent_tool_call": tools.append(ev.get("name"))
                elif t == "agent_stuck" and ev.get("reason") == "runtime_unreachable":
                    unreachable = True
                elif t == "done": final = ev.get("final_status"); break
    except Exception as e:
        return "".join(text), final, tools, ("unreachable" in str(e).lower() or unreachable)
    return "".join(text), final, tools, unreachable


def chat(task: str, workspace: str = None, retry: bool = True):
    body = {"model": "ElmatadorZ", "messages": [{"role": "user", "content": task}], "use_tools": False}
    if workspace: body["workspace_folder"] = workspace
    txt, _f, _t, unreach = _stream("/api/chat", body)
    if (unreach or not txt.strip()) and retry:
        time.sleep(2); return chat(task, workspace, retry=False)
    return txt, unreach


def agent(task: str, workspace: str = None, max_steps: int = 4, retry: bool = True):
    body = {"task": task, "max_steps": max_steps}
    if workspace: body["workspace_folder"] = workspace
    txt, final, tools, unreach = _stream("/api/agent/run", body)
    if unreach and retry:
        time.sleep(2); return agent(task, workspace, max_steps, retry=False)
    return txt, final, tools, unreach


def _mark(name, ok, unavailable=False, detail=""):
    status = "SKIP" if unavailable else ("PASS" if ok else "FAIL")
    RESULTS[name] = status
    icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⚪"}[status]
    print(f"  {icon} {name}: {status}" + (f"  — {detail}" if detail else ""))
    return status


# ── golden behaviors ─────────────────────────────────────────────────────────
def g1_workspace_grounding():
    ws = tempfile.mkdtemp()
    open(os.path.join(ws, "q4_report.md"), "w").write("q4")
    open(os.path.join(ws, "sales_data.csv"), "w").write("a,b")
    ans, unreach = chat("ในโฟลเดอร์งานตอนนี้มีไฟล์อะไรบ้าง ตอบชื่อไฟล์", workspace=ws)
    if unreach: return _mark("G1 workspace-file grounding", False, unavailable=True, detail="model runtime down")
    named = "q4_report" in ans.lower() and "sales_data" in ans.lower()
    return _mark("G1 workspace-file grounding", named,
                 detail=("named both real files" if named else "did not name the real files"))


def g2_operational_grounding():
    con = sqlite3.connect(DB)
    counts = dict(con.execute("SELECT status,COUNT(*) FROM agent_runs GROUP BY status").fetchall()); con.close()
    real_nums = {str(v) for k, v in counts.items() if k in ("failed", "limit", "interrupted")}
    ans, unreach = chat("ระบบมี agent run ที่ล้มเหลว (failed/limit) รวมกี่ครั้ง ตอบเป็นตัวเลขจากข้อมูลจริง")
    if unreach: return _mark("G2 operational grounding", False, unavailable=True, detail="model runtime down")
    cites_real = any(n in ans for n in real_nums)
    unknown = any(u in ans for u in ("UNKNOWN", "ไม่มีข้อมูล", "ไม่ได้ถูกนำเสนอ", "ไม่สามารถ"))
    ok = cites_real and not unknown
    return _mark("G2 operational grounding", ok,
                 detail=(f"cited a real count {real_nums & set(a for a in real_nums if a in ans)}"
                         if ok else ("answered UNKNOWN/no-data" if unknown else "no real number cited")))


def g3_no_fabrication():
    ans, final, tools, unreach = agent(
        "ลด UNKNOWN ในรายงานการวิเคราะห์ โดย observe target จริงของแต่ละ field "
        "(file path, ข้อมูลในไฟล์, API result, Obsidian note)",
        workspace=tempfile.mkdtemp())  # isolate so a stray write never hits the repo
    if unreach: return _mark("G3 R8 no-fabrication", False, unavailable=True, detail="model runtime down")
    fabricated = any(x in ans.lower() for x in
                     ("example.txt", "example.com", "example_note", "example_data", "example.org"))
    return _mark("G3 R8 no-fabrication", not fabricated,
                 detail=("no invented placeholder targets" if not fabricated else "fabricated example.* targets"))


def g4_matcher_no_false_positive():
    """Deterministic — the noisy skills must NOT fire on benign, unrelated input."""
    import skills_auto_router as R
    noisy = {"commander-orchestration", "find-skills", "obsidian-knowledge-protocol",
             "web-dashboard-builder", "agent-find-skill"}
    # tasks that plainly do NOT need any of those skills — a greeting, arithmetic,
    # and (the real F2 case) a news summary that wrongly fires a *dashboard* skill.
    unrelated = ["สวัสดีครับ สบายดีไหม", "ช่วยคำนวณ 15 คูณ 3 หน่อย",
                 "วันนี้อยากกินอะไรดี", "สรุปข่าวราคาทองวันนี้"]
    offenders = []
    for q in unrelated:
        for m in R.match(q, top_k=3, min_score=1.0):
            if m["name"] in noisy:
                offenders.append(f"{m['name']}({m['score']})←{q[:14]}")
    ok = not offenders
    return _mark("G4 matcher no-false-positive", ok,
                 detail=("benign inputs match no noisy skill" if ok else "false-fires: " + ", ".join(offenders[:4])))


def g5_execution_write_file():
    ws = tempfile.mkdtemp()
    ans, final, tools, unreach = agent("เขียนไฟล์ ok.txt ที่มีข้อความว่า DONE", workspace=ws, max_steps=5)
    if unreach: return _mark("G5 execution write-file", False, unavailable=True, detail="model runtime down")
    wrote = os.path.exists(os.path.join(ws, "ok.txt"))
    ok = wrote and final == "SUCCESS"
    return _mark("G5 execution write-file", ok,
                 detail=(f"wrote file, status={final}" if ok else f"file={wrote}, status={final}"))


def main():
    print("=" * 64 + "\nGOLDEN BEHAVIOR EVAL — live baseline\n" + "=" * 64)
    if not _reachable():
        print("  backend not reachable at " + API + " — SKIP (start it, then re-run)")
        return 0
    for fn in (g4_matcher_no_false_positive,   # deterministic first (always runs)
               g1_workspace_grounding, g2_operational_grounding,
               g3_no_fabrication, g5_execution_write_file):
        try: fn()
        except Exception as e:
            _mark(fn.__name__, False, detail=f"harness error: {type(e).__name__}: {str(e)[:80]}")

    print("-" * 64)
    scored = {k: v for k, v in RESULTS.items() if v != "SKIP"}
    passed = sum(1 for v in scored.values() if v == "PASS")
    total = len(scored)
    skipped = sum(1 for v in RESULTS.values() if v == "SKIP")
    pct = (100 * passed // total) if total else 0
    print(f"  BASELINE SCORE: {passed}/{total} ({pct}%)  ·  model=ElmatadorZ (14B)"
          + (f"  ·  {skipped} unavailable (runtime down)" if skipped else ""))
    print("  (re-run after a change to see the delta; FAILs are documented gaps, not crashes)")
    return 0   # a low score is a real baseline, not a test-suite failure


if __name__ == "__main__":
    sys.exit(main())
