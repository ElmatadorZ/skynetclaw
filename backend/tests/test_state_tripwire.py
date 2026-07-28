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
    "learning_strategies.json", "lessons.json", "model_costs.json",
    "pending_gates.json", "router_config.json", "settings.json",
    "tool_memory.json",
    # derived caches / projections (rebuildable — never truth)
    "skills_index.json", "skills_capability_index.json",
    "vision_probe_cache.json", "runtime_inventory.json",
    "runtime_rankings.json", "driver_inventory.json",
    # templates — shipped for the operator to copy, never written by the House
    "settings.example.json", "mcp_servers.example.json",
    # ADR-0015 (Tool Provider Layer): operator-authored MCP server declarations.
    # Same class as settings.json — read by the House, never written by it, and
    # gitignored because it may carry API tokens. It does not exist in a fresh
    # clone; it appears once the operator copies the template.
    "mcp_servers.json",
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


def main():
    for fn in (test_no_uncnartered_databases, test_no_new_root_json_state,
               test_retired_stores_stay_retired):
        try:
            fn()
        except AssertionError:
            pass
        except Exception as e:
            check(fn.__name__, False, f"harness error: {type(e).__name__}: {e}")
    print(f"\n{'ALL PASS' if not FAILED else 'FAILED: ' + ', '.join(FAILED)}")
    return 0 if not FAILED else 1

if __name__ == "__main__":
    raise SystemExit(main())
