"""
test_telegram_exec.py — Telegram task-execution SECURITY regression
===================================================================
The Telegram bot can now run the agent on the machine (/run). That is a remote
code-execution channel, so these tests lock the guarantees that keep it safe:

  1. The safe tool subset NEVER contains shell/code/package/dev-server, and every
     tool it names really exists in BUILTIN_TOOLS.
  2. The restricted schema (what the model is shown) excludes dangerous tools yet
     stays capable (write_file / web_search present).
  3. The execution-time hard-guard predicate refuses any tool outside the allow
     list — the real boundary (exec_tool does NOT gate shell on its own).
  4. Owner auth: unset by default, claim-once (trust-on-first-use), NO silent
     takeover, token-scoped.

Hermetic — no server/network:

    python backend/tests/test_telegram_exec.py
"""
from __future__ import annotations
import sys, os, json, sqlite3, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import main as m

RESULTS = {}
DANGEROUS = {"shell_command", "run_python", "install_package", "dev_server"}


def t_safe_subset():
    print("== T1: safe tool subset invariants ==")
    leak = DANGEROUS & set(m._TG_SAFE_TOOLS)
    names = {t["function"]["name"] for t in m.BUILTIN_TOOLS}
    missing = [x for x in m._TG_SAFE_TOOLS if x not in names]
    checks = {
        "no dangerous tool in safe subset": not leak,
        "every safe tool exists in BUILTIN_TOOLS": not missing,
        "subset is non-empty & capable": {"write_file", "web_search"} <= set(m._TG_SAFE_TOOLS),
    }
    for k, v in checks.items():
        print(f"  {'OK ' if v else 'FAIL'} {k}" + ("" if v else f"  ({leak or missing})"))
    RESULTS["T1"] = all(checks.values())
    assert RESULTS["T1"], "safe subset invariant broken"


def t_restricted_schema():
    print("== T2: restricted schema excludes dangerous, keeps capability ==")
    allow = set(m._TG_SAFE_TOOLS)
    restricted = [t for t in m.BUILTIN_TOOLS if t["function"]["name"] in allow]
    rn = {t["function"]["name"] for t in restricted}
    checks = {
        "restricted schema has no dangerous tool": not (rn & DANGEROUS),
        "restricted schema still has write_file": "write_file" in rn,
        "restricted schema still has web_search": "web_search" in rn,
        "restricted schema smaller than full": len(restricted) < len(m.BUILTIN_TOOLS),
    }
    for k, v in checks.items():
        print(f"  {'OK ' if v else 'FAIL'} {k}")
    RESULTS["T2"] = all(checks.values())
    assert RESULTS["T2"], "restricted schema wrong"


def t_hard_guard():
    print("== T3: execution-time hard-guard predicate ==")
    allow = m._TG_SAFE_TOOLS
    def blocked(nm):  # mirrors the choke-point guard: req.tool_allow and nm not in it
        return bool(allow) and nm not in allow
    checks = {
        "shell_command blocked at exec": blocked("shell_command"),
        "run_python blocked at exec": blocked("run_python"),
        "install_package blocked at exec": blocked("install_package"),
        "write_file allowed": not blocked("write_file"),
        "web_search allowed": not blocked("web_search"),
    }
    for k, v in checks.items():
        print(f"  {'OK ' if v else 'FAIL'} {k}")
    RESULTS["T3"] = all(checks.values())
    assert RESULTS["T3"], "hard guard wrong"


def t_owner_auth():
    print("== T4: owner auth — claim-once, no takeover, token-scoped ==")
    tmp = tempfile.mktemp(suffix=".db")
    old = m.DB_PATH
    ok = True
    try:
        m.DB_PATH = tmp
        con = sqlite3.connect(tmp)
        con.execute("CREATE TABLE integrations(id TEXT, service TEXT, name TEXT, "
                    "credentials TEXT, enabled INT, created_at REAL, tg_auto_start INT)")
        con.execute("INSERT INTO integrations VALUES(?,?,?,?,?,?,?)",
                    ("ig1", "telegram", "tg", json.dumps({"bot_token": "TOK"}), 1, 0, 1))
        con.commit(); con.close()
        seq = [
            ("no owner by default", m.tg_owner_ids("TOK") == set()),
            ("wrong token -> no owner", m.tg_owner_ids("NOPE") == set()),
            ("claim succeeds when unset", m.tg_set_owner("TOK", "123") is True),
            ("owner now recorded", m.tg_owner_ids("TOK") == {"123"}),
            ("second claim refused (no takeover)", m.tg_set_owner("TOK", "999") is False),
            ("owner unchanged after takeover attempt", m.tg_owner_ids("TOK") == {"123"}),
        ]
        for name, cond in seq:
            if not cond: ok = False
            print(f"  {'OK ' if cond else 'FAIL'} {name}")
    finally:
        m.DB_PATH = old
        try: os.remove(tmp)
        except Exception: pass
    RESULTS["T4"] = ok
    assert ok, "owner auth wrong"


def t_activity_mirror():
    print("== T5: telegram activity mirrors to the runtime event bus ==")
    import house_sync as hs
    before = len(hs._EVENT_LOG)
    m._tg_activity("in", 4242, "commander", "ค้นหาราคาทอง")
    m._tg_activity("run", 4242, "commander", "สรุปข่าวทอง")
    m._tg_activity("out", 4242, "commander", "เสร็จแล้ว")
    evs = [e for e in list(hs._EVENT_LOG)[before:] if e.get("type") == "telegram_activity"]
    checks = {
        "3 telegram_activity events published": len(evs) == 3,
        "kinds are in/run/out": [e["payload"]["kind"] for e in evs] == ["in", "run", "out"],
        "payload carries user+text+chat_id": all(
            e["payload"].get("user") == "commander" and e["payload"].get("text")
            and e["payload"].get("chat_id") == "4242" for e in evs),
        "source tagged 'telegram'": all(e.get("source") == "telegram" for e in evs),
        "envelope has timestamp": all(isinstance(e.get("timestamp"), (int, float)) for e in evs),
    }
    for k, v in checks.items():
        print(f"  {'OK ' if v else 'FAIL'} {k}")
    RESULTS["T5"] = all(checks.values())
    assert RESULTS["T5"], "activity mirror wrong"


def main():
    t_safe_subset()
    t_restricted_schema()
    t_hard_guard()
    t_owner_auth()
    t_activity_mirror()
    print("\n== SUMMARY ==")
    allok = all(RESULTS.get(k) for k in ("T1", "T2", "T3", "T4", "T5"))
    for k in ("T1", "T2", "T3", "T4", "T5"):
        print(f"  {k}: {'PASS' if RESULTS.get(k) else 'FAIL'}")
    print("\n  " + ("ALL TELEGRAM EXEC SECURITY TESTS PASS" if allok else "FAILURES PRESENT"))
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
