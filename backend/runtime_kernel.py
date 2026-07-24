"""
runtime_kernel.py — OX-RUNTIME-KERNEL-1
=======================================
The Runtime Kernel: the single execution entry point. It loads Runtime Drivers
(plugins), discovers runtime instances into capability POOLS, negotiates the
best runtime by CAPABILITY (never by model name), manages persistent SESSIONS
(keep_alive / residency reuse), load-balances, monitors health, and fails over.

The House talks to the Kernel; the Kernel talks to Drivers; Drivers talk to
runtimes. No runtime-specific logic here — only driver calls.

Pure pieces (negotiate / pool grouping / session reuse) are unit-tested with
injected fake drivers; discover()/infer() hit the network via drivers.

License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

import runtime_registry as registry
import runtime_router as router
from runtime_plugins import load_drivers
from runtime_scanner import DEFAULT_PROBES


# ── data model ────────────────────────────────────────────────────────────────
@dataclass
class RuntimeInstance:
    name: str
    url: str
    api_type: str
    driver: Any                      # RuntimeDriver
    models: List[Dict[str, Any]] = field(default_factory=list)
    online: bool = True
    healthy: bool = True


@dataclass
class RuntimeSession:
    url: str
    model: str
    api_type: str
    runtime: str
    keep_alive: str = "30m"
    created: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    requests: int = 0

    @property
    def key(self): return (self.url, self.model)

    def touch(self):
        self.last_used = time.time(); self.requests += 1


# ── kernel ────────────────────────────────────────────────────────────────────
class RuntimeKernel:
    def __init__(self, drivers: Optional[list] = None):
        self.drivers = drivers if drivers is not None else load_drivers()
        self.instances: List[RuntimeInstance] = []
        self.sessions: Dict[tuple, RuntimeSession] = {}
        self._rr: Dict[str, int] = {}        # round-robin cursors per role

    # — driver lifecycle / discovery —
    def _driver_for(self, api_type: str):
        for d in self.drivers:
            if d.matches({"api_type": api_type}):
                return d
        return None

    def discover(self, extra_probes: Optional[List[dict]] = None) -> "RuntimeKernel":
        self.instances = []
        for p in list(DEFAULT_PROBES) + list(extra_probes or []):
            drv = self._driver_for(p.get("api_type", "openai"))
            if not drv:
                continue
            if not drv.connect(p["url"]):
                continue
            inst = RuntimeInstance(name=p["runtime"], url=p["url"].rstrip("/"),
                                   api_type=p.get("api_type", "openai"), driver=drv,
                                   models=drv.list_models(p["url"]), online=True,
                                   healthy=drv.health(p["url"]).get("healthy", True))
            # annotate roles per model (capability classification, no names)
            try:
                import vision_probe as _vp
            except Exception:
                _vp = None
            for m in inst.models:
                m["runtime"], m["url"], m["api_type"] = inst.name, inst.url, inst.api_type
                m["online"] = inst.online
                # Trust-but-verify vision: a model may DECLARE vision yet reject
                # images. If a probe definitively showed it broken, drop the claim
                # so it never enters the Vision pool (Intel stops over-claiming).
                if m.get("vision") and _vp is not None and _vp.is_broken(m.get("id", "")):
                    m["vision"] = False
                    m["vision_verified"] = False
                elif m.get("vision"):
                    m["vision_verified"] = _vp.cache().get(m.get("id", "")) if _vp else None
                m["roles"] = registry.classify(m)
            self.instances.append(inst)
        return self

    # — capability negotiation —
    def required_for_task(self, task: str) -> Dict[str, Any]:
        role = router.task_to_role(task)
        req = {"role": role}
        if role == "Execution":
            req["tool_calling"] = True
        if role == "Vision":
            req["vision"] = True
        if role == "Embedding":
            req["embedding"] = True
        return req

    def _all_models(self) -> List[Dict[str, Any]]:
        out = []
        for inst in self.instances:
            for m in inst.models:
                if inst.healthy:
                    out.append(m)
        return out

    def negotiate(self, required: Dict[str, Any],
                  metrics: Optional[dict] = None) -> List[Dict[str, Any]]:
        """Match runtimes by capability, return ranked selections (best first)."""
        role = required.get("role", "Execution")
        cands = []
        for m in self._all_models():
            if role not in m.get("roles", []):
                continue
            # hard capability filters (None = unknown/eligible, not a reject)
            if required.get("tool_calling") and m.get("tool_calling") is False:
                continue
            if required.get("vision") and not m.get("vision"):
                continue
            if required.get("embedding") and not m.get("embedding"):
                continue
            if required.get("min_context") and (m.get("context") or 0) < required["min_context"]:
                continue
            cands.append(m)
        ranked = registry.rank_for_role(cands, role, metrics or {})
        return [{"runtime": m["runtime"], "url": m["url"], "api_type": m["api_type"],
                 "model": m["id"], "role": role,
                 "score": registry._score(m, role, metrics or {})} for m in ranked]

    def select(self, task: Optional[str] = None,
               required: Optional[dict] = None,
               metrics: Optional[dict] = None) -> Optional[Dict[str, Any]]:
        req = required or self.required_for_task(task or "")
        ranked = self.negotiate(req, metrics)
        if not ranked:
            return None
        # load-balance across equally-top candidates (round-robin per role)
        top = ranked[0]["score"]
        tier = [r for r in ranked if r["score"] == top]
        i = self._rr.get(req["role"], 0) % len(tier)
        self._rr[req["role"]] = i + 1
        sel = tier[i]
        sel["alternatives"] = [r for r in ranked if r is not sel]
        return sel

    # — sessions —
    def acquire_session(self, sel: Dict[str, Any], keep_alive: str = "30m") -> RuntimeSession:
        key = (sel["url"], sel["model"])
        s = self.sessions.get(key)
        if s is None:
            s = RuntimeSession(url=sel["url"], model=sel["model"], api_type=sel["api_type"],
                               runtime=sel["runtime"], keep_alive=keep_alive)
            self.sessions[key] = s
        s.touch()
        return s

    def prune_sessions(self, max_idle_s: float = 1800.0) -> int:
        now = time.time()
        dead = [k for k, s in self.sessions.items() if now - s.last_used > max_idle_s]
        for k in dead:
            try: self.sessions[k]  # noop; drivers are stateless/keep_alive on runtime
            finally: self.sessions.pop(k, None)
        return len(dead)

    # — execution (single entry point) with failover —
    def infer(self, task: Optional[str] = None, required: Optional[dict] = None,
              messages: Optional[list] = None, tools: Optional[list] = None,
              stream: bool = False, options: Optional[dict] = None,
              metrics: Optional[dict] = None) -> Iterable[str]:
        req = required or self.required_for_task(task or "")
        candidates = self.negotiate(req, metrics)
        if not candidates:
            yield '{"type":"error","msg":"no runtime satisfies required capabilities"}'
            return
        last_err = None
        for sel in candidates:                       # FAILOVER across ranked runtimes
            drv = self._driver_for(sel["api_type"])
            if not drv:
                continue
            self.acquire_session(sel, (options or {}).get("keep_alive", "30m"))
            try:
                produced = False
                for ev in drv.infer(sel["url"], sel["model"], messages or [],
                                    tools=tools, stream=stream, options=options or {}):
                    produced = True
                    yield ev
                if produced:
                    return
            except Exception as e:
                last_err = f"{sel['runtime']}/{sel['model']}: {str(e)[:80]}"
                self._mark_unhealthy(sel["url"])
                continue
        yield '{"type":"error","msg":"all runtimes failed: %s"}' % (last_err or "unknown")

    def embeddings(self, texts: List[str], metrics: Optional[dict] = None) -> List[List[float]]:
        sel = self.select(required={"role": "Embedding", "embedding": True}, metrics=metrics)
        if not sel:
            return [[] for _ in texts]
        drv = self._driver_for(sel["api_type"])
        return drv.embeddings(sel["url"], sel["model"], texts) if drv else [[] for _ in texts]

    def _mark_unhealthy(self, url: str):
        for inst in self.instances:
            if inst.url == url:
                inst.healthy = False

    # — introspection / pools / health —
    def pools(self) -> Dict[str, Any]:
        pools: Dict[str, list] = {r: [] for r in registry.ROLES}
        for inst in self.instances:
            for m in inst.models:
                for role in m.get("roles", []):
                    pools[role].append({"runtime": inst.name, "model": m["id"],
                                        "url": inst.url, "healthy": inst.healthy})
        return {role: members for role, members in pools.items() if members}

    def health(self) -> Dict[str, Any]:
        out = []
        for inst in self.instances:
            h = inst.driver.health(inst.url)
            inst.healthy = h.get("healthy", False)
            out.append({"runtime": inst.name, "url": inst.url, **h,
                        "models": len(inst.models)})
        return {"runtimes": out,
                "healthy": [o["runtime"] for o in out if o.get("healthy")],
                "unhealthy": [o["runtime"] for o in out if not o.get("healthy")]}

    def drivers_info(self) -> List[Dict[str, Any]]:
        return [d.describe() for d in self.drivers]

    def sessions_info(self) -> List[Dict[str, Any]]:
        return [{"runtime": s.runtime, "model": s.model, "url": s.url,
                 "requests": s.requests, "idle_s": round(time.time() - s.last_used, 1),
                 "keep_alive": s.keep_alive} for s in self.sessions.values()]

    def snapshot(self) -> Dict[str, Any]:
        return {"drivers": self.drivers_info(),
                "instances": [{"runtime": i.name, "url": i.url, "api_type": i.api_type,
                               "models": len(i.models), "healthy": i.healthy}
                              for i in self.instances],
                "pools": {k: len(v) for k, v in self.pools().items()},
                "sessions": len(self.sessions)}


# module-level singleton (lazy) so the API and the agent share one kernel
_KERNEL: Optional[RuntimeKernel] = None
_KERNEL_DISCOVERED_AT: float = 0.0
_DISCOVERY_TTL_S = 60.0      # discovery is networked (offline probes) → cache it


def get_kernel(extra_probes: Optional[List[dict]] = None,
               rediscover: bool = False, ttl: float = _DISCOVERY_TTL_S) -> RuntimeKernel:
    """Shared kernel. Discovery is cached for `ttl` seconds — re-scanning every
    request would add seconds of offline-probe latency to each agent step."""
    global _KERNEL, _KERNEL_DISCOVERED_AT
    now = time.time()
    if _KERNEL is None:
        _KERNEL = RuntimeKernel()
        _KERNEL.discover(extra_probes)
        _KERNEL_DISCOVERED_AT = now
    elif rediscover and (now - _KERNEL_DISCOVERED_AT) > ttl:
        _KERNEL.discover(extra_probes)
        _KERNEL_DISCOVERED_AT = now
    return _KERNEL
