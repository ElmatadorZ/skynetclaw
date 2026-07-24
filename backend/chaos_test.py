"""
chaos_test.py — Chaos Engineering regression suite for THE HOUSE reliability.

Philosophy: do not prove the system reliable — try to break it. Every reproducible
failure becomes a permanent assertion here, so the same failure cannot recur without a
red test. Evidence, not opinions: each experiment prints measured numbers.

Run:  python chaos_test.py
Exit: non-zero if any RELIABILITY REGRESSION assertion fails (informational controls
      never fail the run).
"""
from __future__ import annotations
import json, os, sqlite3, sys, tempfile, threading, time, shutil
from pathlib import Path

HERE = Path(__file__).parent
REAL_DB = HERE / "skynerclaw.db"
_fail = []
_evidence = []


def rec(msg): _evidence.append(msg); print("   " + msg)
def assert_(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    print(f"  [{tag}] {name}" + (f" — {detail}" if detail else ""))
    if not cond: _fail.append(name)


# ── EXP-1: config corruption → auto-recovery ─────────────────────────────────
def exp_config_recovery():
    print("EXP-1  Config corruption recovery (real SettingsBackupChain)")
    try:
        import openclaw_port_tier2 as ocp
    except Exception as e:
        assert_("EXP-1 chain importable", False, str(e)); return
    d = Path(tempfile.mkdtemp(prefix="chaos_cfg_"))
    chain = ocp.SettingsBackupChain(d / "settings.json")
    chain.safe_save({"model": "A", "n": 1})
    chain.safe_save({"model": "B", "n": 2})            # creates .bak
    # CHAOS: corrupt the primary file (truncated / garbage)
    (d / "settings.json").write_text('{"model": "B", "n":', encoding="utf-8")
    recovered = chain.safe_load(default={"model": "?"})
    assert_("EXP-1 recovers a valid dict after corruption", isinstance(recovered, dict) and recovered.get("model") in ("A", "B"),
            f"recovered={recovered}")
    # primary should be rewritten to a parseable file
    try: json.loads((d / "settings.json").read_text(encoding="utf-8")); ok = True
    except Exception: ok = False
    assert_("EXP-1 primary is valid JSON again after recovery", ok)
    shutil.rmtree(d, ignore_errors=True)


# ── EXP-2: atomic save survives an interrupted write ─────────────────────────
def exp_atomic_save():
    print("EXP-2  Atomic save — interrupted replace must not corrupt the good file")
    try:
        import openclaw_port_tier2 as ocp
    except Exception as e:
        assert_("EXP-2 chain importable", False, str(e)); return
    d = Path(tempfile.mkdtemp(prefix="chaos_atom_"))
    p = d / "settings.json"
    chain = ocp.SettingsBackupChain(p)
    chain.safe_save({"good": True, "v": 1})
    good_before = p.read_text(encoding="utf-8")
    # CHAOS: make the tmp->primary replace raise mid-save (simulates crash/kill)
    orig_replace = Path.replace
    def boom(self, *a, **k):
        if self.suffix == ".tmp": raise OSError("simulated crash during replace")
        return orig_replace(self, *a, **k)
    Path.replace = boom
    try:
        chain.safe_save({"good": False, "v": 999})     # should fail cleanly
    except Exception:
        pass
    finally:
        Path.replace = orig_replace
    good_after = p.read_text(encoding="utf-8") if p.exists() else ""
    try: parsed = json.loads(good_after)
    except Exception: parsed = None
    assert_("EXP-2 original file still valid after interrupted save", parsed is not None and parsed.get("v") == 1,
            f"after={good_after[:60]!r}")
    assert_("EXP-2 no stray .tmp left behind", not (p.with_suffix(p.suffix + ".tmp")).exists())
    shutil.rmtree(d, ignore_errors=True)


# ── EXP-3: concurrent writers — plain (control) vs hardened (regression) ──────
def _hammer(db_path, connect_fn, threads=24, iters=25):
    errs = {"locked": 0, "other": 0}
    def worker(wid):
        for i in range(iters):
            try:
                c = connect_fn(db_path)
                c.execute("INSERT INTO t(w,i,ts) VALUES(?,?,?)", (wid, i, time.time()))
                c.commit(); c.close()
            except sqlite3.OperationalError as e:
                errs["locked" if "lock" in str(e).lower() else "other"] += 1
            except Exception:
                errs["other"] += 1
    ts = [threading.Thread(target=worker, args=(w,)) for w in range(threads)]
    t0 = time.time(); [t.start() for t in ts]; [t.join() for t in ts]
    return errs, round(time.time() - t0, 2)

def exp_concurrency():
    print("EXP-3  Concurrent writers (24 threads x 25 writes)")
    import db_reliability as dbr
    # control: the CURRENT app pattern (plain connect, stdlib 5s default timeout, no WAL)
    d1 = Path(tempfile.mkdtemp(prefix="chaos_plain_")); p1 = d1 / "x.db"
    sqlite3.connect(p1).execute("CREATE TABLE t(w,i,ts)").connection.commit()
    e1, t1 = _hammer(p1, lambda p: sqlite3.connect(p))
    rec(f"CONTROL (plain, no WAL): locked={e1['locked']} other={e1['other']} time={t1}s")
    # regression: the hardened path (WAL + explicit busy_timeout)
    d2 = Path(tempfile.mkdtemp(prefix="chaos_wal_")); p2 = d2 / "x.db"
    sqlite3.connect(p2).execute("CREATE TABLE t(w,i,ts)").connection.commit()
    dbr.ensure_wal(p2)
    e2, t2 = _hammer(p2, dbr.connect)
    rec(f"HARDENED (WAL + busy_timeout): locked={e2['locked']} other={e2['other']} time={t2}s")
    # REGRESSION assertions: the hardened path must not lock and must be no slower
    assert_("EXP-3 hardened path has ZERO lock errors", e2["locked"] == 0, f"locked={e2['locked']}")
    assert_("EXP-3 hardened path has no other errors", e2["other"] == 0, f"other={e2['other']}")
    assert_("EXP-3 WAL not slower than plain", t2 <= t1 + 0.5, f"wal={t2}s plain={t1}s")
    shutil.rmtree(d1, ignore_errors=True); shutil.rmtree(d2, ignore_errors=True)


# ── EXP-4: SQLite integrity after a hard-killed writer (ACID crash-safety) ────
def exp_crash_integrity():
    print("EXP-4  Data integrity after an aborted transaction (kill-mid-write proxy)")
    import db_reliability as dbr
    d = Path(tempfile.mkdtemp(prefix="chaos_kill_")); p = d / "x.db"
    dbr.ensure_wal(p)
    c = dbr.connect(p); c.execute("CREATE TABLE t(k INTEGER PRIMARY KEY, v)")
    c.executemany("INSERT INTO t(v) VALUES(?)", [(i,) for i in range(100)]); c.commit(); c.close()
    # CHAOS: open a write txn and abandon it WITHOUT commit (proxy for kill -9)
    c2 = dbr.connect(p); c2.execute("BEGIN"); c2.execute("INSERT INTO t(v) VALUES(999999)")
    del c2                                             # drop without commit → rollback
    c3 = dbr.connect(p)
    integrity = c3.execute("PRAGMA integrity_check").fetchone()[0]
    count = c3.execute("SELECT COUNT(*) FROM t").fetchone()[0]
    c3.close()
    assert_("EXP-4 DB integrity_check == ok after aborted write", integrity == "ok", integrity)
    assert_("EXP-4 uncommitted row did NOT persist (ACID)", count == 100, f"count={count}")
    shutil.rmtree(d, ignore_errors=True)


# ── EXP-5: real DB can be put in WAL (the shipped fix) ────────────────────────
def exp_real_db_wal():
    print("EXP-5  Real skynerclaw.db reliability mode")
    import db_reliability as dbr
    if not REAL_DB.exists():
        rec("skynerclaw.db not present in this checkout — skipping real-DB assertion")
        return
    mode = dbr.ensure_wal(REAL_DB)
    assert_("EXP-5 real DB journal_mode == wal after ensure_wal", mode == "wal", f"mode={mode}")


# ── EXP-6: locked DB — busy_timeout must WAIT, not instantly fail ─────────────
def exp_locked_db_waits():
    print("EXP-6  Locked DB — hardened connect must wait out a held write lock")
    import db_reliability as dbr
    d = Path(tempfile.mkdtemp(prefix="chaos_lock_")); p = d / "x.db"
    dbr.ensure_wal(p)
    c0 = dbr.connect(p); c0.execute("CREATE TABLE t(v)"); c0.commit(); c0.close()
    holder = dbr.connect(p); holder.isolation_level = None
    holder.execute("BEGIN IMMEDIATE"); holder.execute("INSERT INTO t(v) VALUES(1)")  # holds write lock
    result = {}
    def writer():
        try:
            c = dbr.connect(p, timeout=3.0)
            c.execute("INSERT INTO t(v) VALUES(2)"); c.commit(); c.close()
            result["ok"] = True
        except Exception as e:
            result["ok"] = False; result["err"] = str(e)
    th = threading.Thread(target=writer); th.start()
    time.sleep(0.4)                       # hold the lock briefly (< the 3s timeout)
    holder.execute("COMMIT"); holder.close()
    th.join(timeout=6)
    assert_("EXP-6 blocked writer waited then succeeded (busy_timeout mitigates lock)",
            result.get("ok") is True, result.get("err", ""))
    shutil.rmtree(d, ignore_errors=True)


# ── EXP-7: every settings source corrupt → safe default, no crash ────────────
def exp_all_backups_corrupt():
    print("EXP-7  All settings sources corrupt → falls back to default (no crash)")
    import openclaw_port_tier2 as ocp
    d = Path(tempfile.mkdtemp(prefix="chaos_allcorrupt_")); p = d / "settings.json"
    chain = ocp.SettingsBackupChain(p)
    chain.safe_save({"v": 1}); chain.safe_save({"v": 2})       # create backups
    for f in list(d.glob("settings.json*")):
        try: f.write_text("<<<not json>>>", encoding="utf-8")
        except Exception: pass
    out = chain.safe_load(default={"defaulted": True})
    assert_("EXP-7 returns provided default when all sources corrupt",
            isinstance(out, dict) and out.get("defaulted") is True, f"out={out}")
    shutil.rmtree(d, ignore_errors=True)


# ── EXP-8: write failure (disk-full / permission-denied) must not corrupt ─────
def exp_write_failure():
    print("EXP-8  Write failure (disk full / permission denied proxy)")
    import openclaw_port_tier2 as ocp
    d = Path(tempfile.mkdtemp(prefix="chaos_wfail_")); p = d / "settings.json"
    chain = ocp.SettingsBackupChain(p); chain.safe_save({"v": 1})
    orig = Path.write_text
    def boom(self, *a, **k):
        if self.suffix == ".tmp": raise PermissionError("simulated permission denied / disk full")
        return orig(self, *a, **k)
    Path.write_text = boom
    try: ok = chain.safe_save({"v": 999})
    finally: Path.write_text = orig
    good = json.loads(p.read_text(encoding="utf-8"))
    assert_("EXP-8 safe_save returns False on write failure", ok is False)
    assert_("EXP-8 good file unchanged after write failure", good.get("v") == 1, f"good={good}")
    assert_("EXP-8 no stray .tmp after write failure", not p.with_suffix(p.suffix + ".tmp").exists())
    shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    os.chdir(HERE)
    sys.path.insert(0, str(HERE))
    print("=" * 60); print("  CHAOS ENGINEERING — reliability regression suite"); print("=" * 60)
    for exp in (exp_config_recovery, exp_atomic_save, exp_concurrency, exp_crash_integrity,
                exp_real_db_wal, exp_locked_db_waits, exp_all_backups_corrupt, exp_write_failure):
        try: exp()
        except Exception as e:
            assert_(exp.__name__ + " ran without harness error", False, repr(e))
        print()
    print("-" * 60)
    if _fail:
        print(f"RESULT: {len(_fail)} RELIABILITY REGRESSION(S) FAILED — {_fail}")
        sys.exit(1)
    print("RESULT: ALL RELIABILITY REGRESSIONS PASS")
