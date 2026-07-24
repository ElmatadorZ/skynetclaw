"""
test_task_planner.py — the Planning bridge, deterministically (mock LLM)
=======================================================================
Locks the Vol IV bridge mechanics without the real model: decompose parses a plan,
rounds refine+accumulate the whole artifact, the anti-drop guard rejects a truncated
round, and the planner writes the file itself (so "the model wouldn't save" cannot
happen).

    python backend/tests/test_task_planner.py
"""
from __future__ import annotations
import sys, asyncio, tempfile, json
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception: pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import task_planner as tp

RESULTS = {}


def make_llm(script):
    """script: a function(messages)->str. Async wrapper."""
    async def call_llm(messages):
        return script(messages)
    return call_llm


async def _run(task, workspace, call_llm):
    events = []
    async for ev in tp.plan_and_execute(task, workspace, call_llm):
        events.append(ev)
    return events


def t_decompose_and_build():
    print("== T1: decompose (JSON) + iterative build + deterministic write ==")
    calls = {"n": 0}
    def script(messages):
        sysmsg = messages[0]["content"]
        if "build planner" in sysmsg:  # decompose
            return '[{"title":"Skeleton","instruction":"scaffold"},{"title":"Logic","instruction":"calc"},{"title":"Charts","instruction":"charts"}]'
        calls["n"] += 1
        # each build round returns a growing complete file (realistic ~KB size)
        base = ("<!doctype html><html><head><title>DCA Dashboard</title>"
                "<style>body{font-family:system-ui;background:#0d1117;color:#e6edf3;padding:24px}"
                ".card{border:1px solid #30363d;border-radius:12px;padding:18px;margin:8px}</style>"
                "</head><body>\n")
        parts = [
            "<h1>DCA Dashboard</h1><div class='card'>ผลลัพธ์การลงทุนแบบ Dollar-Cost Averaging</div>\n",
            "<script>const monthly=1000,years=5;const totalInvested=monthly*12*years;const shares=totalInvested/50;const value=shares*55;</script>\n",
            "<canvas id='chartMain'></canvas><canvas id='chartMix'></canvas><script>/* chart.js rendering of totalInvested vs value */</script>\n",
        ]
        body = "".join(parts[:calls["n"]])
        return f"```html\n{base}{body}</body></html>\n```"
    ws = tempfile.mkdtemp()
    events = asyncio.new_event_loop().run_until_complete(_run("สร้าง dashboard DCA เป็น html", ws, make_llm(script)))
    complete = next((e for e in events if e["type"] == "plan_complete"), {})
    decomposed = next((e for e in events if e["type"] == "plan_decomposed"), {})
    fpath = Path(ws) / "dashboard.html"
    checks = {
        "decomposed into 3 sections": decomposed.get("n") == 3,
        "file was written by the planner": fpath.exists(),
        "file is a valid-ish html artifact": fpath.exists() and "<html>" in fpath.read_text(encoding="utf-8") and "</html>" in fpath.read_text(encoding="utf-8"),
        "build reported ok": complete.get("ok") is True,
        "final content grew across rounds": complete.get("chars", 0) > 100,
    }
    for k, v in checks.items(): print(f"  {'OK ' if v else 'FAIL'} {k}")
    RESULTS["T1"] = all(checks.values()); assert RESULTS["T1"]


def t_anti_drop_guard():
    print("== T2: anti-drop guard rejects a round that truncates the artifact ==")
    def script(messages):
        if "build planner" in messages[0]["content"]:
            return '[{"title":"A","instruction":"a"},{"title":"B","instruction":"b"}]'
        usr = messages[1]["content"]
        if "first version" in usr:                # round 1: big valid whole file
            return "```html\n" + "<html><body>" + ("X" * 500) + "</body></html>" + "\n```"
        return "```html\n<html>tiny</html>\n```"   # round 2: shrunken WHOLE file -> anti-drop rejects
    ws = tempfile.mkdtemp()
    events = asyncio.new_event_loop().run_until_complete(_run("build an html page", ws, make_llm(script)))
    complete = next((e for e in events if e["type"] == "plan_complete"), {})
    step2 = [e for e in events if e["type"] == "plan_step_done"][-1]
    content = (Path(ws) / "dashboard.html").read_text(encoding="utf-8")
    checks = {
        "round-2 truncation was rejected": step2.get("accepted") is False,
        "artifact kept the large round-1 content": len(content) > 400 and "tiny" not in content,
    }
    for k, v in checks.items(): print(f"  {'OK ' if v else 'FAIL'} {k}")
    RESULTS["T2"] = all(checks.values()); assert RESULTS["T2"]


def t_build_detection():
    print("== T3: auto-route detector (build task vs question) ==")
    checks = {
        "'สร้าง dashboard DCA เป็น html' -> build": tp.looks_like_build_task("สร้าง dashboard DCA โดยใส่ตัวเลขเงินลงทุน") is True,
        "'build a landing page' -> build": tp.looks_like_build_task("build a landing page with a chart") is True,
        "'ราคาทองวันนี้เท่าไร' -> NOT build": tp.looks_like_build_task("ราคาทองวันนี้เท่าไร") is False,
        "'summarize the news' -> NOT build": tp.looks_like_build_task("summarize the news") is False,
    }
    for k, v in checks.items(): print(f"  {'OK ' if v else 'FAIL'} {k}")
    RESULTS["T3"] = all(checks.values()); assert RESULTS["T3"]


def main():
    t_decompose_and_build(); t_anti_drop_guard(); t_build_detection()
    print("\n== SUMMARY ==")
    ok = all(RESULTS.get(k) for k in ("T1", "T2", "T3"))
    for k in ("T1", "T2", "T3"): print(f"  {k}: {'PASS' if RESULTS.get(k) else 'FAIL'}")
    print("\n  " + ("ALL PLANNER TESTS PASS" if ok else "FAILURES PRESENT"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
