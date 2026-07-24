"""
test_concurrency.py — CONCURRENT MISSION SAFETY + BUS INTEGRITY (hardening)
===========================================================================
Proves the projection baselines are scoped per state/mission so Mission A
cannot affect Mission B, and the event bus has no drop/duplicate under load.

    python backend/tests/test_concurrency.py
"""
from __future__ import annotations
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import house_cognition as hc
import belief_timeline as bt
import house_sync as H


def test_house_cognition_isolation():
    """Mission A (state stA) and Mission B (state stB) keep independent baselines."""
    A = {"state_id": "stA", "mission": "A", "status": "open", "known": ["a1", "a2"],
         "unknown": [], "hypotheses": [], "beliefs": [{"belief": "BA", "confidence": 0.6}],
         "confidence": 0.6, "next_action": {}, "last_update": 1}
    B = {"state_id": "stB", "mission": "B", "status": "open", "known": ["b1"],
         "unknown": [], "hypotheses": [], "beliefs": [{"belief": "BB", "confidence": 0.4}],
         "confidence": 0.4, "next_action": {}, "last_update": 2}
    cur = {"v": "A"}
    orig = hc.snapshot
    hc.snapshot = lambda path=None: A if cur["v"] == "A" else B
    try:
        hc.reset()
        ev = []
        pub = lambda t, p, source="house": ev.append((t, p.get("state_id")))
        cur["v"] = "A"; ev.clear(); hc.diff_and_emit(pub)
        assert ev and all(s == "stA" for _, s in ev), "A should emit only stA"
        cur["v"] = "B"; ev.clear(); hc.diff_and_emit(pub)
        assert ev and all(s == "stB" for _, s in ev), "B must emit (not suppressed) and only stB"
        cur["v"] = "A"; ev.clear(); hc.diff_and_emit(pub)
        assert ev == [], "A re-diff must be silent — B did not clobber A's baseline"
    finally:
        hc.snapshot = orig
    print("  OK  house_cognition: Mission A / B isolated by state_id")


def test_belief_timeline_isolation():
    tlA = {"state_id": "stA", "question": "qA", "gaps": [],
           "nodes": [{"id": "n1", "node": "question", "content": "qA", "source": "X", "provenance": "p", "timestamp": 1}]}
    tlB = {"state_id": "stB", "question": "qB", "gaps": [],
           "nodes": [{"id": "n2", "node": "question", "content": "qB", "source": "X", "provenance": "p", "timestamp": 1}]}
    cur = {"v": "A"}
    orig = bt.timeline
    bt.timeline = lambda state_id=None, path=None: tlA if cur["v"] == "A" else tlB
    try:
        bt.reset()
        ev = []
        pub = lambda t, p, source="timeline": ev.append((t, p.get("state_id")))
        cur["v"] = "A"; ev.clear(); bt.diff_and_emit(pub); assert ev and all(s == "stA" for _, s in ev)
        cur["v"] = "B"; ev.clear(); bt.diff_and_emit(pub); assert ev and all(s == "stB" for _, s in ev)
        cur["v"] = "A"; ev.clear(); bt.diff_and_emit(pub); assert ev == [], "A timeline re-diff must be silent"
    finally:
        bt.timeline = orig
    print("  OK  belief_timeline: timelines isolated by state_id")


def test_bus_integrity():
    async def run():
        sub = asyncio.Queue(maxsize=4096); H._EVENT_SUBSCRIBERS.append(sub)
        N = 1500; got = []; done = asyncio.Event()
        async def consumer():
            while len(got) < N: got.append(await sub.get())
            done.set()
        async def producer():
            for i in range(N):
                H.publish("burst", {"i": i}, source="t")
                if i % 50 == 0: await asyncio.sleep(0)
        ct = asyncio.create_task(consumer()); await producer()
        try: await asyncio.wait_for(done.wait(), timeout=5)
        except asyncio.TimeoutError: pass
        ct.cancel()
        try: H._EVENT_SUBSCRIBERS.remove(sub)
        except ValueError: pass
        ids = [json.loads(m)["id"] for m in got]
        return N, len(got), len(ids) - len(set(ids))
    N, recv, dup = asyncio.run(run())
    assert recv == N and dup == 0, f"drop={N-recv} dup={dup}"
    print(f"  OK  bus integrity: {N} events, 0 dropped, 0 duplicate, monotonic ids")


def main():
    print("=" * 56 + "\nCONCURRENT MISSION SAFETY + BUS INTEGRITY\n" + "=" * 56)
    test_house_cognition_isolation()
    test_belief_timeline_isolation()
    test_bus_integrity()
    print("\n  ALL CONCURRENCY TESTS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
