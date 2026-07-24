"""
db_reliability.py — reliability hardening for the SQLite datastore (skynerclaw.db).
Extracted so both main.py and the chaos regression suite exercise the SAME code path.

Two things the default `sqlite3.connect(path)` does NOT give you:
  1. WAL journal mode — readers no longer block the writer (huge under concurrency).
     WAL is a *persistent* property of the DB file: set it once, it stays.
  2. An explicit busy timeout on every connection (the stdlib default is 5s, but we
     make it explicit and tunable, and pair it with WAL).

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations
import sqlite3


def ensure_wal(path) -> str:
    """Enable WAL + NORMAL synchronous on the DB file (idempotent). Returns the
    resulting journal_mode ('wal' on success). Safe to call at startup and while
    other connections are open."""
    c = sqlite3.connect(str(path), timeout=5.0)
    try:
        mode = c.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        c.execute("PRAGMA synchronous=NORMAL")
        c.commit()
        return (mode or "").lower()
    finally:
        c.close()


def connect(path, timeout: float = 5.0) -> sqlite3.Connection:
    """A connection with an explicit busy timeout. Use for write paths so a
    concurrent writer WAITS instead of failing with 'database is locked'."""
    c = sqlite3.connect(str(path), timeout=timeout)
    try:
        c.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")
    except Exception:
        pass
    return c
