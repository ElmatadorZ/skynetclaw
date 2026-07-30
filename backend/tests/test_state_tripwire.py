"""
test_state_tripwire.py — ADR-0014 guard rail: no new state store without an ADR
===============================================================================
The drift that produced 6 databases and 27 root-level JSON state files must be
STRUCTURALLY impossible to repeat silently. This test is the CI tripwire:

  * backend/*.db must be exactly the chartered set (institutional + transcript).
  * backend/*.json must be within the allowlist recorded here.

Adding a store REQUIRES editing this file — and this file requires the ADR that
charters the store (that edit-with-citation IS the gate). See
docs/adr/ADR-0014-state-consolidation.md and docs/state/EVIDENCE_INVENTORY.md.

    python backend/tests/test_state_tripwire.py
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

BACKEND = Path(__file__).resolve().parent.parent

# ── Chartered databases (ADR-0014 §Decision + §Mechanical appendix) ───────────
CHARTERED_DBS = {
    "skynerclaw.db",      # THE institutional truth (House Bible)
    "chat_history.db",    # chartered transcript store — dialogue is evidence
                          # ABOUT cognition, not cognition itself (ADR-0014)
}

# ── Allowlisted root-level JSON state (EVIDENCE_INVENTORY 2026-07-19) ─────────
# Classification lives in the inventory; this list only guards against NEW stores.
ALLOWED_JSON = {
    # module-owned state (single owner per file — D3 narrows writers)
    "acquisitions.json", "agent_memory.json", "atlas_genome.json",
    "attribution.json", "capabilities.json", "capability_weights.json",
    "causal_hypotheses.json", "compliance.json", "control_history.json",
    "exec_approvals.json", "exploration.json", "governance_config.json",
    # ADR-0015 (Tool Provider Layer): operator-authored MCP server declarations.
    # Same class as settings.json — the House reads it and never writes it, and
    # it is gitignored because it may carry API tokens. Registered here
    # deliberately: the tripwire asked for a decision and this is it.
    "mcp_servers.json",
    "learning_strategies.json", "lessons.json", "model_costs.json",
    "pending_gates.json", "router_config.json", "settings.json",
    "tool_memory.json",
    # derived caches / projections (rebuildable — never truth)
    "skills_index.json", "skills_capability_index.json",
    "vision_probe_cache.json", "runtime_inventory.json",
    "runtime_rankings.json", "driver_inventory.json",
    # templates — shipped for the operator to copy, never written by the House.
    # A template is not a state store: it has no runtime writer, and deleting it
    # loses documentation, not state. Anything the House *writes* still needs an
    # ADR (ADR-0014), which is what this tripwire exists to enforce.
    "settings.example.json",
    "mcp_servers.example.json",
}

FAILED = []
def check(name, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok: FAILED.append(name)


def test_no_uncnartered_databases():
    dbs = {p.name for p in BACKEND.glob("*.db")}
    extra = dbs - CHARTERED_DBS
    missing_core = "skynerclaw.db" not in dbs
    check("no unchartered .db store (new store requires an ADR)", not extra,
          f"extras: {sorted(extra)}" if extra else "")
    check("institutional DB present", not missing_core)
    assert not extra and not missing_core


def test_no_new_root_json_state():
    js = {p.name for p in BACKEND.glob("*.json")}
    extra = js - ALLOWED_JSON
    check("no new root-level JSON state store (new store requires an ADR)",
          not extra, f"extras: {sorted(extra)}" if extra else "")
    assert not extra


def test_retired_stores_stay_retired():
    retired = ["data.db", "openclaw.db", "_house_archive_backup.json",
               "runtime_registry.db", "runtime_metrics.db"]
    back = [f for f in retired if (BACKEND / f).exists()]
    check("ADR-0014 P0 retirements stay retired", not back,
          f"returned: {back}" if back else "")
    assert not back





# ── D3 / P1: one authoritative writer per state file ────────────────────────
# ADR-0014 line 172 specified a "single-writer guard for D3 files" and it had
# never been built, so the property held by luck rather than by design. An
# invariant that holds by luck reads exactly like one that holds by design, up
# until someone adds a convenient json.dump. This is the guard.
#
# It earned its keep on the first run: obsidian_tools.py wrote settings.json
# directly, bypassing the backup chain that rotates .bak/.last-good — a crash
# mid-write would have left the file truncated with no recoverable copy. Manual
# grep had missed it.
def test_one_authoritative_writer_per_state_file():
    import state_ownership
    r = state_ownership.verify()
    detail = "; ".join(
        f"{v['module']}:{v['line']} writes {v['file']} (owner {v['owner']})"
        for v in r["violations"])
    check("one authoritative writer per declared state file (ADR-0014 D3)",
          r["ok"], detail)
    assert r["ok"], (
        "State Ownership Principle violated — every mutable state SHALL have "
        f"exactly one authoritative writer: {detail}")


def test_every_declared_owner_module_exists():
    """A declaration pointing at a module that is gone is worse than none: the
    guard would pass while nothing owned the file."""
    import state_ownership
    missing = [s["owner"] for s in state_ownership.OWNERS.values()
               if not (BACKEND / s["owner"]).exists()]
    check("every declared owner module exists", not missing,
          f"missing: {missing}" if missing else "")
    assert not missing


def test_every_exemption_states_a_reason():
    """An exemption is a hole in the principle. It may exist; it may not be silent."""
    import state_ownership
    bare = [k for k, v in state_ownership.EXEMPT.items() if len(str(v).strip()) < 20]
    check("every ownership exemption carries a reason", not bare,
          f"unexplained: {bare}" if bare else "")
    assert not bare

def main():
    for fn in (test_no_uncnartered_databases, test_no_new_root_json_state,
               test_retired_stores_stay_retired,
               test_one_authoritative_writer_per_state_file,
               test_every_declared_owner_module_exists,
               test_every_exemption_states_a_reason):
        try:
            fn()
        except AssertionError:
            pass
        except Exception as e:
            check(fn.__name__, False, f"harness error: {type(e).__name__}: {e}")
    print()
    print("ALL PASS" if not FAILED else "FAILED: " + ", ".join(FAILED))
    return 0 if not FAILED else 1


if __name__ == "__main__":
    raise SystemExit(main())
