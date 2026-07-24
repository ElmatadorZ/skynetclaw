"""
blocked_detector.py — OX-1.4 BLOCKED STATE (per-run dead-end detector)
======================================================================
The cycle breaker already catches the IDENTICAL-action loop (same tool, same
args, 3×). It does NOT catch the subtler failure: the agent takes VARIED
actions step after step yet learns NOTHING NEW — a genuine dead end.

This detector measures INFORMATION GAIN per step from real signals only:
  * did the WORLD MODEL grow?  (a new verified/absent entity was learned)
  * did any tool return a result we have NOT seen before this run?

If a step takes real actions but gains no information, the streak grows. When
the streak reaches K AND recovery is exhausted (the loop already tried
alternates / reliability collapsed), the run terminates as BLOCKED — a new
canonical terminal state, distinct from FAILED (a hard error) and LIMIT
(ran out of steps). BLOCKED means: "I tried varied moves and hit a wall."

Stateless except for the per-run streak; no DB, no persistence, no model call.
Ownership: extends the agent loop's progress vocabulary. It OWNS the info-gain
streak; it does NOT own failure counting or execution confidence — those are
fed in (recovery_exhausted) by the loop, which already owns them.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict

_DEFAULT_K = 4   # varied-but-empty steps tolerated before declaring BLOCKED


class BlockedDetector:
    def __init__(self, k: int = _DEFAULT_K) -> None:
        self.k = max(2, int(k))
        self.streak = 0
        self.prev_world_size = 0
        self.step_novel = False
        self._seen: set[str] = set()

    def begin_step(self) -> None:
        """Call at the start of every step that may run tools."""
        self.step_novel = False

    def observe_result(self, name: str, result: str) -> bool:
        """Record a real tool result; flag step-level novelty. Returns True if new."""
        key = hashlib.sha1(f"{name}:{(result or '')[:300]}".encode("utf-8", "replace")).hexdigest()
        novel = key not in self._seen
        if novel:
            self._seen.add(key)
            self.step_novel = True
        return novel

    def end_step(self, world_size: int, acted: bool) -> int:
        """Evaluate information gain for the step just finished.

        world_size — current count of verified facts in the world model.
        acted      — did the step actually run at least one tool?

        Returns the current no-information streak.
        """
        world_grew = world_size > self.prev_world_size
        self.prev_world_size = max(self.prev_world_size, world_size)
        gained = world_grew or self.step_novel
        # Only VARIED-but-empty steps count toward BLOCKED. A step with no action
        # is stagnation (handled elsewhere); a step that learned something resets.
        if acted and not gained:
            self.streak += 1
        else:
            self.streak = 0
        return self.streak

    def is_blocked(self, recovery_exhausted: bool) -> bool:
        """True when varied actions have yielded no information for K steps AND
        the loop reports recovery is exhausted (failures mounting / reliability
        collapsed). Both conditions are required — a long, productive-but-not-
        world-changing task must never be falsely declared BLOCKED."""
        return self.streak >= self.k and bool(recovery_exhausted)

    def snapshot(self) -> Dict[str, Any]:
        return {"streak": self.streak, "k": self.k, "facts_seen": len(self._seen)}
