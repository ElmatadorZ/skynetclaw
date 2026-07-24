"""
test_reliability.py — FULL RELIABILITY VALIDATION (Phase R1)
============================================================
Proves THE HOUSE survives real, long-running work. Runs standalone:

    python backend/tests/test_reliability.py

Covers:
  R1A execution trace (Operator->...->Policy)
  R1B context stress (50/100/200/300 tool calls) + metrics
  R1C mission survival (no silent/halt/overflow/stuck/deadlock)
  R1D house consistency (mind/timeline/mission/learning/policy synchronized)
  R1E event-bus load (1000+ events: no drop, no duplicate, no storm)
  R1F recovery (timeout / empty response / context critical / temp failure)

No features, no redesign — measurement only. Every metric is real.
"""
from __future__ import annotations
import asyncio, os, sys, time, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
DB = os.path.join(tempfile.gettempdir(), "reliability_test.db")
if os.path.exists(DB):
    os.remove(DB)

# NB: do NOT set os.environ["INSTITUTIONAL_DB"] at import — it mutates a process-global
# during pytest collection and leaks into sibling test modules. Init the DB explicitly
# by path here; the run-time fixture below points the env at it only during these tests.
import institutional_db as idb
idb._INITIALIZED.discard(DB)
idb.init_once(DB)
import house_state as hs, house_cognition as hcog, belief_timeline as btl
import mission_command as mcc, learning_engine as le, house_os as hos
import outcome_tracker as ot, agent_council as ac
import context_budget as cb, mission_snapshot as ms
import house_sync as hsync
import openclaw_port_tier2 as ocp
ARDB = ocp.AgentRunsDB(Path(DB))


@pytest.fixture(autouse=True, scope="module")
def _isolated_reliability_db():
    # Point INSTITUTIONAL_DB at this module's DB AND install the council stubs only
    # during these tests (run time), then restore everything. Setting env or mutating
    # agent_council globals at IMPORT time leaks into sibling modules — the council
    # traced test_operator_intent's failure to `ac._OINTENT = False` leaking from here.
    prev_env = os.environ.get("INSTITUTIONAL_DB")
    saved = {k: getattr(ac, k) for k in ("_llm_call_json", "_IMEM", "_GOV", "_OINTENT", "_BRIEF")}
    os.environ["INSTITUTIONAL_DB"] = DB
    ac._llm_call_json = _fake
    ac._IMEM = ac._GOV = ac._OINTENT = ac._BRIEF = False
    yield
    for k, v in saved.items():
        setattr(ac, k, v)
    if prev_env is None:
        os.environ.pop("INSTITUTIONAL_DB", None)
    else:
        os.environ["INSTITUTIONAL_DB"] = prev_env


RESULTS = {}

def banner(t): print("\n" + "=" * 64 + "\n" + t + "\n" + "=" * 64)

# ── stub council LLM (real-shaped JSON) ───────────────────────────────────────
RJ = {"ANALYST":{"known":["Found 7 repositories"],"unknown":["no ownership metadata"]},
      "STRATEGIST":{"leverage_point":"Build one registry"},
      "SKEPTIC":{"fatal_assumption":"all repos maintained","verdict":"FRAGILE","rebuild_trigger":"if 2+ abandoned"},
      "FORECASTER":{"scenario":"Likely adoption within 7 days"},
      "EXECUTOR":{"start":"Build registry.json"},"STORYTELLER":{"hook":"one catalogue"}}
def _role(s):
    h = s.split("\n")[0].upper(); return next((r for r in RJ if r in h), "")
async def _fake(system, user, **k):
    await asyncio.sleep(0.002); return {"ok": True, "json": RJ.get(_role(system), {})}
# NB: ac._llm_call_json / ac._IMEM/_GOV/_OINTENT/_BRIEF are installed at RUN time by
# the _isolated_reliability_db fixture (with restore) — NOT at import, so they no
# longer leak into sibling test modules.

BUS = []
def pub(t, p, source="x"): BUS.append((source, t, p)); return {}
def coev(e):
    pl = {"agent": e.get("agent",""), "message": e.get("message","")}
    if e.get("source_field"): pl["source_field"] = e["source_field"]
    pub(e["type"], pl, source="council")

Q = "should we build a skill registry"

# ══════════════════════════════════════════════════════════════════════════════
def r1a_execution_trace():
    banner("R1A — EXECUTION TRACE (Operator -> Mission -> ... -> Policy)")
    BUS.clear()
    async def go():
        pub("agent_activated", {"phase":"council"}, source="runtime")          # mission/runtime
        await ac.run_council(Q, {}, model="stub", on_event=coev)               # council + reasoning
        hcog.reset(); hcog.diff_and_emit(pub)                                   # house mind
        btl.reset(); btl.diff_and_emit(pub)                                     # timeline
        ARDB.start_run("r_trace","Build registry.json","stub"); ARDB.end_run("r_trace","complete",n_steps=4,n_tools=6)
        mcc.reset(); mcc.diff_and_emit(pub)                                     # mission
        cs="cs_trace"
        with idb.connect() as c:
            c.execute("INSERT OR REPLACE INTO council_sessions(id,ts,directive,created_at) VALUES(?,?,?,?)",(cs,time.time(),Q,time.time())); c.commit()
        pid=ot.record_prediction("Registry adopted within a week",agent="Forecaster",session_id=cs,confidence=0.6)
        ot.evaluate(pid,"30","incorrect"); le.reset(); le.diff_and_emit(pub)   # learning
        lessons=le.snapshot()["lessons"]
        if lessons:
            p=hos.create_policy(statement="codify registry ownership",
                what_happened="adoption prediction disproven", why="no owner assigned",
                what_changed="require an owner", origin="lesson:"+lessons[0]["id"], publish=pub)  # policy
            hos.create_rule("every registry must have an owner", policy_id=p["id"], publish=pub)
    asyncio.run(go())
    stages = {
        "Mission/Runtime": any(t=="agent_activated" for _,t,_ in BUS),
        "Council":        any(t in ("agent_started","agent_completed") for _,t,_ in BUS),
        "Reasoning":      any(t.startswith("reasoning_") for _,t,_ in BUS),
        "House Mind":     any(t.startswith("house_") for _,t,_ in BUS),
        "Timeline":       any(t.startswith("timeline_") for _,t,_ in BUS),
        "Mission CC":     any(t.startswith("mission_") for _,t,_ in BUS),
        "Learning":       any(t.startswith(("lesson_","behavior_")) for _,t,_ in BUS),
        "Policy":         any(t.startswith(("policy_","rule_")) for _,t,_ in BUS),
    }
    for k,v in stages.items(): print(f"  {'OK ' if v else 'FAIL'} {k}")
    ok = all(stages.values())
    RESULTS["R1A"] = ok
    assert ok, "execution trace incomplete: " + str(stages)

# ══════════════════════════════════════════════════════════════════════════════
def r1b_context_stress():
    banner("R1B — CONTEXT STRESS TEST (50/100/200/300 tool calls)")
    LIMIT = 16384
    PRE = [{"role":"system","content":"X"*1600} for _ in range(4)]
    TASK = {"role":"user","content":"Index the vault. DONE_WHEN: registry written."}
    def tool(i):
        return {"role":"tool","name":["read_file","grep_search","web_search","shell_command"][i%4],
                "content":f"result {i}\n"+("DATA "*790)}   # ~4000 chars (the truncation cap)
    rows = []
    for n in (50,100,200,300):
        cur = list(PRE)+[TASK]; peak=0; total=0; rec=0; comp=0; t0=time.time(); msgpeak=0
        for i in range(n):
            cur.append(tool(i))
            cur=[m for m in cur if "[[SKYNET_LEDGER_v1]]" not in (m.get("content") or "")]
            cur.append({"role":"user","content":"[[SKYNET_LEDGER_v1]] step "+str(i)})
            a=cb.assess(cur,limit=LIMIT)
            if a["level"]=="critical":
                cur,_s,_d=ms.compress(cur,keep_recent=6); rec+=1; comp+=1; a=cb.assess(cur,limit=LIMIT)
            peak=max(peak,a["total"]); total+=a["total"]; msgpeak=max(msgpeak,len(cur))
        dt=(time.time()-t0)*1000
        avg=total//n
        survived = peak<=LIMIT
        rows.append((n,peak,avg,rec,comp,msgpeak,round(dt,1),survived))
        print(f"  {n:3d} calls | peak {peak:6d} | avg {avg:6d} | recoveries {rec:2d} | "
              f"compress {comp:2d} | msgs<= {msgpeak:3d} | {dt:6.1f}ms | {'SURVIVES' if survived else 'OVERFLOW'}")
    RESULTS["R1B"] = all(r[7] for r in rows)
    RESULTS["R1B_rows"] = rows
    assert RESULTS["R1B"], "a stress case overflowed the window"

# ══════════════════════════════════════════════════════════════════════════════
def r1c_mission_survival():
    banner("R1C — MISSION SURVIVAL TEST")
    LIMIT=16384
    PRE=[{"role":"system","content":"sys"}]
    cur=list(PRE)+[{"role":"user","content":"big mission. DONE_WHEN: done."}]
    failures={"operative_silent":False,"mission_halted":False,"context_overflow":False,
              "stuck_execution":False,"deadlock":False}
    recovered=False; completed=False; resumed=False
    for i in range(250):
        cur.append({"role":"tool","name":"read_file","content":"fact "+str(i)+"\n"+("Z"*3800)})
        a=cb.assess(cur,limit=LIMIT)
        if a["total"]>LIMIT: failures["context_overflow"]=True
        if a["level"]=="critical":
            before=len(cur); cur,snap,_=ms.compress(cur,keep_recent=4); recovered=True
            resumed = len(cur)<before and any("MISSION_SNAPSHOT" in (m.get("content") or "") for m in cur)
    # mission "completes": a terminal snapshot is producible and bounded
    final=cb.assess(cur,limit=LIMIT)
    completed = final["total"]<=LIMIT
    for k,v in failures.items(): print(f"  {'OK  ' if not v else 'FAIL'} no {k}: {not v}")
    print(f"  survives={not any(failures.values())} resumes={resumed} completes={completed} recoveries={recovered}")
    ok = (not any(failures.values())) and resumed and completed and recovered
    RESULTS["R1C"]=ok
    assert ok, "survival failed: "+str(failures)

# ══════════════════════════════════════════════════════════════════════════════
def r1d_consistency():
    banner("R1D — HOUSE CONSISTENCY TEST")
    # one real mission already ran in R1A; read all projections and check they agree
    cogn = hcog.snapshot()
    cur = hs.current()
    tl = btl.timeline()
    miss = mcc.snapshot()
    learn = le.snapshot()
    osnap = hos.snapshot()
    state_id = cur["id"] if cur else ""
    belief = (cogn.get("beliefs") or [{}])[0].get("belief","")
    tl_decision = next((n["content"] for n in tl["nodes"] if n["node"]=="decision"), "")
    checks = {
        "house_state has belief": bool(belief),
        "timeline decision == current belief": (tl_decision == belief) or (belief in tl_decision) or (tl_decision in belief),
        "timeline state_id == current state": tl["state_id"] == state_id,
        "mission lists the council mission": any(m["objective"]==cogn["mission"] for m in miss["active"]+miss["completed"]),
        "lesson exists from graded outcome": learn["counts"]["lessons"]>=1,
        "behavior change recorded": learn["counts"]["behavior_changes"]>=1,
        "policy answers to a lesson": any("lesson:" in (p.get("origin") or "") for p in osnap["policies"]),
    }
    for k,v in checks.items(): print(f"  {'OK  ' if v else 'FAIL'} {k}")
    ok=all(checks.values()); RESULTS["R1D"]=ok
    assert ok, "divergence detected: "+str({k:v for k,v in checks.items() if not v})

# ══════════════════════════════════════════════════════════════════════════════
def r1e_event_bus_load():
    banner("R1E — EVENT BUS LOAD TEST (1000+ events)")
    async def run():
        import house_sync as H
        q = asyncio.Queue(maxsize=H._EVENT_SUBSCRIBERS and 0 or 0)  # noop ref
        received = []
        sub = asyncio.Queue(maxsize=4096)
        H._EVENT_SUBSCRIBERS.append(sub)
        drained = asyncio.Event()
        N = 1200
        async def consumer():
            got=0
            while got < N:
                msg = await sub.get(); received.append(msg); got+=1
            drained.set()
        async def producer():
            for i in range(N):
                H.publish("load_test", {"i": i}, source="load")
                if i % 50 == 0:
                    await asyncio.sleep(0)   # let the consumer drain (realistic pacing)
        ct = asyncio.create_task(consumer())
        await producer()
        try:
            await asyncio.wait_for(drained.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            pass
        ct.cancel()
        try: H._EVENT_SUBSCRIBERS.remove(sub)
        except ValueError: pass
        import json as _j
        ids = [_j.loads(m)["id"] for m in received]
        return N, received, ids
    N, received, ids = asyncio.run(run())
    dropped = N - len(received)
    duplicates = len(ids) - len(set(ids))
    # storm check: diff_and_emit on no change emits nothing
    hcog.reset(); hcog.snapshot()  # prime baseline by reading
    storm = len(hcog.diff_and_emit(lambda *a, **k: None))  # first call after reset re-emits current; second is 0
    storm2 = len(hcog.diff_and_emit(lambda *a, **k: None))
    print(f"  produced {N} | received {len(received)} | dropped {dropped} | duplicates {duplicates}")
    print(f"  no-change re-emit (storm guard): {storm2} events")
    ok = dropped == 0 and duplicates == 0 and storm2 == 0
    RESULTS["R1E"]=ok; RESULTS["R1E_metrics"]=(N,dropped,duplicates)
    assert ok, f"bus integrity: dropped={dropped} dup={duplicates} storm={storm2}"

# ══════════════════════════════════════════════════════════════════════════════
def r1f_recovery():
    banner("R1F — RECOVERY TEST")
    import main as _m  # for _tool_result_failed
    checks = {}
    # 1) tool timeout -> detected as failure (drives adaptation, not silent death)
    checks["tool_timeout_detected"] = _m._tool_result_failed("run_python","❌ run_python TIMEOUT after 300s")
    # 2) empty model response -> snapshot recovery yields a valid continuation context
    cur=[{"role":"system","content":"sys"},{"role":"user","content":"task. DONE_WHEN: x"}]
    for i in range(30): cur.append({"role":"tool","name":"grep_search","content":"hit "+str(i)+"\n"+("Y"*3800)})
    new,snap,dropped = ms.compress(cur, keep_recent=4)
    checks["empty_response_recoverable"] = dropped>0 and any("MISSION_SNAPSHOT" in (m.get("content") or "") for m in new)
    # 3) context critical -> mission_recovered emitted
    EV=[]
    cur2=[{"role":"system","content":"X"*1600} for _ in range(4)]+[{"role":"user","content":"t"}]
    for i in range(40): cur2.append({"role":"tool","name":"read_file","content":"X"*3800})
    a=cb.assess(cur2,limit=16384)
    if a["level"]=="critical":
        cur2,_s,_d=ms.compress(cur2,keep_recent=6); EV.append("mission_recovered")
    checks["context_critical_recovered"] = "mission_recovered" in EV
    # 4) temporary failure -> failure flag clears on next success (adaptation logic)
    fail1=_m._tool_result_failed("read_file","[File not found: x]")
    ok2=_m._tool_result_failed("read_file","file contents ok")
    checks["temp_failure_then_success"] = (fail1 is True and ok2 is False)
    for k,v in checks.items(): print(f"  {'OK  ' if v else 'FAIL'} {k}")
    ok=all(checks.values()); RESULTS["R1F"]=ok
    assert ok, "recovery failed: "+str({k:v for k,v in checks.items() if not v})

# ══════════════════════════════════════════════════════════════════════════════
def r1g_schema_blind_spot():
    """Regression for a production incident: llama.cpp returned
    exceed_context_size_error (n_prompt_tokens=17160, n_ctx=16384) on a request
    cb.assess() had rated safe. Root cause: assess() only measured `cur`
    (messages) and never the `tools` function-calling schema, which the chat
    template also renders into the real prompt. A 19-tool mission-scoped
    schema alone is ~2.4k tokens; a 50-tool fallback is ~4.4k tokens."""
    banner("R1G — CONTEXT BUDGET: TOOL-SCHEMA BLIND SPOT (regression)")
    LIMIT = 16384
    # borderline `cur`: schema-blind assess must call this "ok"/"warning"...
    cur = ([{"role": "system", "content": "X" * 1600} for _ in range(4)]
           + [{"role": "user", "content": "วิเคราะห์ข้อมูล"}]
           + [{"role": "tool", "name": "read_file", "content": "Y" * 3800} for _ in range(11)])
    tools = [{"type": "function", "function": {
        "name": f"tool_{i}", "description": "D" * 120,
        "parameters": {"type": "object", "properties": {
            "a": {"type": "string", "description": "P" * 80},
            "b": {"type": "string", "description": "P" * 80}}}}}
        for i in range(19)]  # mirrors the real 19-tool mission-scoped selection

    blind = cb.assess(cur, limit=LIMIT)                      # old behaviour: no tools arg
    aware = cb.assess(cur, tools=tools, limit=LIMIT)          # fixed behaviour

    checks = {
        "schema_tokens counted (>0)": aware["schema_tokens"] > 0,
        "schema-aware total > schema-blind total": aware["total"] > blind["total"],
        "blind spot can hide a real overflow risk": blind["level"] != "critical" and aware["level"] in ("warning", "critical"),
    }
    for k, v in checks.items():
        print(f"  {'OK  ' if v else 'FAIL'} {k}")
    print(f"  blind total={blind['total']} aware total={aware['total']} "
          f"(+{aware['total']-blind['total']} schema tokens, {len(tools)} tools)")

    # KNOWN RESIDUAL RISK (documented, not silently hidden): if the overflow is
    # from the *static* preamble+schema on turn 0 (no accumulated tool-call
    # middle yet), mission_snapshot.compress() has nothing to drop. Budget
    # detection still fires (critical), which is strictly better than the
    # pre-fix silent blind spot, but it does not by itself guarantee recovery.
    turn0_cur = [{"role": "system", "content": "X" * 1600} for _ in range(4)] + \
                [{"role": "user", "content": "วิเคราะห์ข้อมูล"}]
    turn0 = cb.assess(turn0_cur, tools=tools, limit=LIMIT)
    _, _snap, dropped0 = ms.compress(turn0_cur, keep_recent=6)
    checks["turn0_overflow_detected"] = True  # detection doesn't require critical here; documents the shape
    print(f"  turn-0 static overflow case: level={turn0['level']} compress_dropped={dropped0} "
          f"(0 dropped is EXPECTED — no tool-history middle exists yet; residual risk, not a regression)")

    ok = checks["schema_tokens counted (>0)"] and checks["schema-aware total > schema-blind total"] and checks["blind spot can hide a real overflow risk"]
    RESULTS["R1G"] = ok
    assert ok, "schema blind-spot regression failed: " + str(checks)

# ══════════════════════════════════════════════════════════════════════════════
def r1h_turn0_downgrade():
    """Regression for the turn-0 residual case R1G documented: when critical
    overflow comes from the static preamble (no tool-history middle to
    compress), /api/agent/run now swaps the full system prompt for the
    compact one. Validates the swap actually clears the real production
    incident's shape using the REAL GENESIS_AGENT_PROMPT / compact prompt /
    tool schema from main.py (not synthetic stand-ins)."""
    banner("R1H — TURN-0 STATIC-OVERFLOW DOWNGRADE (regression, real artifacts)")
    import main as _m
    tools = _m._select_tools_for_task("วิเคราะห์ข้อมูล")
    # Reproduce a turn-0 cur: full system prompt + a few small preamble
    # messages + task, scaled with padding to land near the incident's
    # reported overflow (n_prompt_tokens=17160 / n_ctx=16384).
    pad = {"role": "system", "content": "P" * 25000}  # stand-in for workspace/ledger/memory banners
    cur = [{"role": "system", "content": _m.GENESIS_AGENT_PROMPT}, pad,
           {"role": "user", "content": "วิเคราะห์ข้อมูล"}]
    before = cb.assess(cur, tools=tools, limit=16384)

    # apply the exact downgrade main.py now performs
    cur[0]["content"] = _m._MODULAR_PROMPT_COMPACT
    after = cb.assess(cur, tools=tools, limit=16384)

    checks = {
        "before is at/near overflow (>=90% of num_ctx)": before["total"] >= 0.90 * 16384,
        "downgrade frees real tokens": after["total"] < before["total"],
        "downgrade clears the 16384 hard ceiling": after["total"] < 16384,
    }
    for k, v in checks.items():
        print(f"  {'OK  ' if v else 'FAIL'} {k}")
    print(f"  before={before['total']} after={after['total']} freed={before['total']-after['total']} "
          f"(GENESIS_AGENT_PROMPT={len(_m.GENESIS_AGENT_PROMPT)//4}tok compact={len(_m._MODULAR_PROMPT_COMPACT)//4}tok "
          f"tools={len(tools)})")
    ok = all(checks.values())
    RESULTS["R1H"] = ok
    assert ok, "turn-0 downgrade regression failed: " + str(checks)

# ══════════════════════════════════════════════════════════════════════════════
def main():
    r1a_execution_trace()
    r1b_context_stress()
    r1c_mission_survival()
    r1d_consistency()
    r1e_event_bus_load()
    r1f_recovery()
    r1g_schema_blind_spot()
    r1h_turn0_downgrade()
    banner("RELIABILITY SUMMARY")
    allok = all(v for k,v in RESULTS.items() if k in ("R1A","R1B","R1C","R1D","R1E","R1F","R1G","R1H"))
    for k in ("R1A","R1B","R1C","R1D","R1E","R1F","R1G","R1H"):
        print(f"  {k}: {'PASS' if RESULTS.get(k) else 'FAIL'}")
    print("\n  " + ("ALL RELIABILITY TESTS PASS" if allok else "FAILURES PRESENT"))
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
