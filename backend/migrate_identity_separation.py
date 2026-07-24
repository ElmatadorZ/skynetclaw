"""
migrate_identity_separation.py — OX-H1 repair migration (non-destructive)
=========================================================================
Repairs MISSION IDENTITY fields polluted by execution-prompt text, WITHOUT
destroying history. For every polluted row it:

  1. archives the original prompt text into a *_raw debug column (once), then
  2. rewrites the identity field to the clean USER DIRECTIVE
     (via mission_identity.clean_identity — the SAME extractor the runtime uses).

Tables repaired:
  * house_state.question   (archive → question_raw)
  * agent_runs.task        (archive → task_raw)

Idempotent: re-running only touches rows that are still polluted. Original
prompt text is preserved verbatim in the *_raw column for debug/audit.

Usage:  python migrate_identity_separation.py [--dry-run] [--db PATH]
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mission_identity as MI

_DEFAULT_DB = os.environ.get("INSTITUTIONAL_DB") or str(Path(__file__).resolve().parent / "skynerclaw.db")

# A row is polluted if its identity field carries any execution-prompt sigil.
_POLLUTION_LIKE = (
    "%WORKFLOW CONTEXT%",
    "%YOU UNDERSTAND THE TASK%",
    "%### YOUR PLAN%",
    "%MID-EXECUTION CHECKPOINTS%",
)


def _has_column(c: sqlite3.Connection, table: str, col: str) -> bool:
    return any(r[1] == col for r in c.execute(f"PRAGMA table_info({table})").fetchall())


def _ensure_archive_col(c: sqlite3.Connection, table: str, raw_col: str, dry: bool) -> None:
    if not _has_column(c, table, raw_col):
        if dry:
            print(f"  [dry-run] would ALTER {table} ADD COLUMN {raw_col} TEXT")
        else:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {raw_col} TEXT")
            print(f"  + archive column {table}.{raw_col} created")


def _repair_table(c: sqlite3.Connection, table: str, id_col: str, field: str,
                  raw_col: str, dry: bool) -> dict:
    try:
        _has = _has_column(c, table, field)
    except sqlite3.OperationalError:
        return {"table": table, "skipped": "no such table"}
    if not _has:
        return {"table": table, "skipped": f"no column {field}"}
    _ensure_archive_col(c, table, raw_col, dry)

    where = " OR ".join(f"{field} LIKE ?" for _ in _POLLUTION_LIKE)
    rows = c.execute(
        f"SELECT {id_col} AS id, {field} AS val FROM {table} WHERE {where}",
        _POLLUTION_LIKE,
    ).fetchall()

    repaired, samples = 0, []
    for r in rows:
        rid, original = r["id"], r["val"] or ""
        clean = MI.clean_identity(original)
        if not clean:
            clean = "(unrecoverable directive — see %s)" % raw_col
        if dry:
            if len(samples) < 3:
                samples.append({"id": rid, "before": original[:60], "after": clean[:60]})
            repaired += 1
            continue
        # archive original ONCE (don't overwrite a prior archive), then repair
        c.execute(
            f"UPDATE {table} SET {raw_col}=COALESCE({raw_col}, ?), {field}=? WHERE {id_col}=?",
            (original, clean, rid),
        )
        if len(samples) < 3:
            samples.append({"id": rid, "before": original[:60], "after": clean[:60]})
        repaired += 1
    return {"table": table, "field": field, "polluted_found": len(rows),
            "repaired": repaired, "samples": samples}


def migrate(db_path: str = _DEFAULT_DB, dry_run: bool = False) -> dict:
    print(f"OX-H1 identity migration · db={db_path} · {'DRY-RUN' if dry_run else 'APPLY'}")
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    try:
        res = {
            "house_state": _repair_table(c, "house_state", "id", "question", "question_raw", dry_run),
            "agent_runs": _repair_table(c, "agent_runs", "id", "task", "task_raw", dry_run),
        }
        if not dry_run:
            c.commit()
    finally:
        c.close()
    for t, r in res.items():
        print(f"  {t}: found={r.get('polluted_found','-')} repaired={r.get('repaired','-')}"
              + (f" · {r.get('skipped')}" if r.get("skipped") else ""))
        for s in r.get("samples", []):
            print(f"      {s['id']}: '{s['before']}…' → '{s['after']}'")
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--db", default=_DEFAULT_DB)
    a = ap.parse_args()
    migrate(a.db, a.dry_run)
