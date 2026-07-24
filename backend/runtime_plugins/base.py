"""
runtime_plugins/base.py — OX-RUNTIME-KERNEL-1
=============================================
The Runtime Driver interface. EVERY runtime is reached only through a driver;
no runtime-specific logic lives outside backend/runtime_plugins/. A plugin module
exports `DRIVER = SomeDriver()` and the kernel discovers it — adding a runtime
requires zero kernel changes.

Contract (all drivers implement):
  matches(probe) connect() health() list_models() capabilities()
  benchmark() infer() embeddings() shutdown()

Dependency-free (stdlib only).
License: Apache-2.0 — ElmatadorZ / THE HOUSE
"""
from __future__ import annotations

import abc
from typing import Any, Dict, Iterable, List, Optional


class RuntimeDriver(abc.ABC):
    """Stateless adapter for one runtime *family* (url passed per call)."""

    name: str = "base"          # driver id (also the plugin's identity)
    api_types: tuple = ()       # api_type values this driver claims

    def matches(self, probe: Dict[str, Any]) -> bool:
        """Does this driver own the given probe/connection?"""
        return probe.get("api_type") in self.api_types

    @abc.abstractmethod
    def connect(self, url: str) -> bool:
        """Lightweight reachability check (used at pool join)."""

    @abc.abstractmethod
    def health(self, url: str) -> Dict[str, Any]:
        """{alive, latency_s, healthy, ...}."""

    @abc.abstractmethod
    def list_models(self, url: str) -> List[Dict[str, Any]]:
        """Discover models with declared metadata (no hardcoded names)."""

    @abc.abstractmethod
    def capabilities(self, url: str, model: str) -> Dict[str, Any]:
        """Per-model capability record (tool_calling/vision/thinking/embedding/...)."""

    @abc.abstractmethod
    def benchmark(self, url: str, model: str) -> Dict[str, Any]:
        """Measure ttft/tok-s/tool latency/VRAM for one model."""

    @abc.abstractmethod
    def infer(self, url: str, model: str, messages: List[Dict[str, Any]],
              tools: Optional[list] = None, stream: bool = False,
              options: Optional[dict] = None) -> Iterable[str]:
        """Yield normalized event JSON strings (same contract as _llm_stream)."""

    @abc.abstractmethod
    def embeddings(self, url: str, model: str, texts: List[str]) -> List[List[float]]:
        """Return embedding vectors for texts (empty if unsupported)."""

    def shutdown(self, url: str) -> None:
        """Release any runtime-side residency (best-effort, optional)."""
        return None

    def describe(self) -> Dict[str, Any]:
        return {"driver": self.name, "api_types": list(self.api_types)}
