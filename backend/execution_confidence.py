"""
execution_confidence.py — OX-1.3 EXECUTION CONFIDENCE (per-run scalar)
=====================================================================
A live, per-run measure of EXECUTION quality: "am I making reliable progress?"
Updated after every tool call — rises on success, drops on failure.

This is DISTINCT from the two existing confidence owners and must never be
confused with them:
  * house_state.confidence  → BELIEF confidence (do we believe the answer?)
  * agent_reputation        → AGENT skill / calibration (track record)
  * execution_confidence    → THIS: live per-run execution reliability (transient)

In-memory, per agent run. No persistence, no DB, no duplicate truth.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

from typing import Dict

_START = 0.7
_SUCCESS_GAIN = 0.05     # asymptotic toward 1.0
_FAILURE_MULT = 0.6      # multiplicative drop
_NOINFO_DECAY = 0.03     # a step that adds no new information


class ExecutionConfidence:
    def __init__(self, start: float = _START) -> None:
        self.c = max(0.0, min(1.0, start))
        self.successes = 0
        self.failures = 0
        self.steps = 0

    def on_success(self) -> float:
        self.c = self.c + _SUCCESS_GAIN * (1.0 - self.c)
        self.successes += 1
        self.steps += 1
        return self.value()

    def on_failure(self) -> float:
        self.c = self.c * _FAILURE_MULT
        self.failures += 1
        self.steps += 1
        return self.value()

    def on_no_info(self) -> float:
        self.c = max(0.0, self.c - _NOINFO_DECAY)
        return self.value()

    def on_recovery(self) -> float:
        # a successful recovery partially restores confidence (same as a success)
        return self.on_success()

    def value(self) -> float:
        return round(self.c, 3)

    def level(self) -> str:
        c = self.c
        if c >= 0.70:
            return "high"
        if c >= 0.45:
            return "medium"
        if c >= 0.25:
            return "low"
        return "critical"

    def is_low(self) -> bool:
        return self.c < 0.25

    def snapshot(self) -> Dict[str, float]:
        return {"value": self.value(), "level": self.level(),
                "successes": self.successes, "failures": self.failures, "steps": self.steps}
