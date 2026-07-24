"""
migrate.py — PART 9: migration runner for THE HOUSE institutional memory
========================================================================
Usage:
    python migrate.py up         # apply all pending migrations
    python migrate.py down 001   # rollback a migration
    python migrate.py status     # show applied versions

Migrations live in backend/migrations/NNN_name.up.sql / .down.sql
DB path resolves from INSTITUTIONAL_DB env or backend/skynerclaw.db.
"""
from __future__ import annotations

import sys
from pathlib import Path

import institutional_db as _db

MIG_DIR = Path(__file__).parent / "migrations"


def _ensure_table(c):
    c.execute("CREATE TABLE IF NOT EXISTS schema_migrations "
              "(version INTEGER PRIMARY KEY, name TEXT, applied_at REAL)")


def applied(path=None):
    with _db.connect(path) as c:
        _ensure_table(c)
        return {r["version"] for r in c.execute("SELECT version FROM schema_migrations")}


def up(path=None):
    done = applied(path)
    ran = []
    for f in sorted(MIG_DIR.glob("*.up.sql")):
        ver = int(f.name.split("_", 1)[0])
        if ver in done:
            continue
        with _db.connect(path) as c:
            c.executescript(f.read_text(encoding="utf-8"))
            c.commit()
        ran.append(f.name)
    return ran


def down(version, path=None):
    f = next(MIG_DIR.glob(f"{int(version):03d}_*.down.sql"), None)
    if not f:
        raise FileNotFoundError(f"no down migration for {version}")
    with _db.connect(path) as c:
        c.executescript(f.read_text(encoding="utf-8"))
        c.commit()
    return f.name


def status(path=None):
    return sorted(applied(path))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "up":
        print("applied:", up())
    elif cmd == "down":
        print("rolled back:", down(sys.argv[2]))
    else:
        print("versions:", status())
