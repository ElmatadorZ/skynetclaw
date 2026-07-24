"""
test_execution_confidence.py — OX-1.3 validation (model-free)
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from execution_confidence import ExecutionConfidence


def test_rise_on_success_drop_on_failure():
    ec = ExecutionConfidence()
    base = ec.value()
    ec.on_success()
    assert ec.value() > base, "success must raise confidence"
    after_succ = ec.value()
    ec.on_failure()
    assert ec.value() < after_succ, "failure must drop confidence"
    print(f"  OK  success raises, failure drops (start {base} → succ → fail {ec.value()})")


def test_bounds_and_failure_multiplier():
    ec = ExecutionConfidence(start=0.6)
    ec.on_failure()
    assert abs(ec.value() - round(0.6 * 0.6, 3)) < 1e-9, "failure is multiplicative ×0.6"
    # repeated failures drive toward critical but never below 0
    for _ in range(20):
        ec.on_failure()
    assert 0.0 <= ec.value() <= 1.0
    assert ec.is_low() and ec.level() == "critical"
    print(f"  OK  failure ×0.6, bounded [0,1], sustained failure → critical ({ec.value()})")


def test_levels():
    ec = ExecutionConfidence(start=0.9); assert ec.level() == "high"
    ec = ExecutionConfidence(start=0.5); assert ec.level() == "medium"
    ec = ExecutionConfidence(start=0.3); assert ec.level() == "low"
    ec = ExecutionConfidence(start=0.1); assert ec.level() == "critical" and ec.is_low()
    print("  OK  level thresholds high/medium/low/critical")


def test_distinct_scalar():
    # it is its OWN scalar — must not IMPORT/couple to the other confidence owners
    # (the docstring may NAME them to document the boundary; coupling = an import)
    import execution_confidence as mod, inspect
    src = inspect.getsource(mod)
    assert "import house_state" not in src and "import agent_reputation" not in src, \
        "must not couple to other confidence owners"
    print("  OK  execution confidence is an independent scalar (no belief/reputation import)")


def main():
    print("=" * 56 + "\nOX-1.3 EXECUTION CONFIDENCE\n" + "=" * 56)
    test_rise_on_success_drop_on_failure()
    test_bounds_and_failure_multiplier()
    test_levels()
    test_distinct_scalar()
    print("\n  ALL EXECUTION-CONFIDENCE TESTS PASS — measure execution quality")
    return 0


if __name__ == "__main__":
    sys.exit(main())
