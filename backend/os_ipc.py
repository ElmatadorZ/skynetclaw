"""
os_ipc.py — OX-HOUSE-OS-1 Phase 4
=================================
The OS IPC Event Bus. Applications and services communicate by publishing and
subscribing to topics — never by holding direct references to each other. This
is the only sanctioned channel for inter-app messaging.

Topics are dotted strings; subscribe to an exact topic or to a prefix wildcard
("runtime.*" / "*"). Delivery is synchronous and isolated (a failing handler
never breaks the publisher or other handlers). A bounded history supports
observability (/api/os/ipc).

Dependency-free (stdlib only).
License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Tuple

Handler = Callable[[str, Any], None]


class EventBus:
    def __init__(self, history_limit: int = 500):
        self._subs: List[Tuple[str, Handler, str]] = []   # (pattern, handler, owner)
        self._history: List[Dict[str, Any]] = []
        self._limit = history_limit

    def subscribe(self, pattern: str, handler: Handler, owner: str = "") -> Callable[[], None]:
        entry = (pattern, handler, owner)
        self._subs.append(entry)
        return lambda: self._subs.remove(entry) if entry in self._subs else None

    def unsubscribe_owner(self, owner: str) -> int:
        before = len(self._subs)
        self._subs = [s for s in self._subs if s[2] != owner]
        return before - len(self._subs)

    @staticmethod
    def _matches(pattern: str, topic: str) -> bool:
        if pattern == "*" or pattern == topic:
            return True
        if pattern.endswith(".*"):
            return topic.startswith(pattern[:-1])   # "runtime." prefix
        return False

    def publish(self, topic: str, payload: Any = None, source: str = "") -> int:
        rec = {"topic": topic, "payload": payload, "source": source, "ts": time.time()}
        self._history.append(rec)
        if len(self._history) > self._limit:
            self._history = self._history[-self._limit:]
        delivered = 0
        for pattern, handler, _ in list(self._subs):
            if self._matches(pattern, topic):
                try:
                    handler(topic, payload)
                    delivered += 1
                except Exception:
                    # isolation: a bad subscriber must not break the bus
                    pass
        return delivered

    def history(self, topic_prefix: str = "", limit: int = 100) -> List[Dict[str, Any]]:
        items = [h for h in self._history
                 if not topic_prefix or h["topic"].startswith(topic_prefix)]
        return items[-limit:]

    def topics(self) -> List[str]:
        return sorted({h["topic"] for h in self._history})

    def subscriptions(self) -> List[Dict[str, str]]:
        return [{"pattern": p, "owner": o} for p, _, o in self._subs]
