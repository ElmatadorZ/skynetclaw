"""
runtime_plugins — OX-RUNTIME-KERNEL-1 Plugin SDK
================================================
Drop a module in this package that exports `DRIVER = <RuntimeDriver instance>`
and the kernel discovers it automatically — ZERO kernel changes to add a runtime.
"""
from __future__ import annotations

import importlib
import pkgutil
from typing import Dict, List

from runtime_plugins.base import RuntimeDriver


def load_drivers() -> List[RuntimeDriver]:
    """Discover every plugin module exporting a `DRIVER` RuntimeDriver."""
    drivers: List[RuntimeDriver] = []
    for mod in pkgutil.iter_modules(__path__):
        if mod.name in ("base",) or mod.name.startswith("_"):
            continue
        try:
            m = importlib.import_module(f"{__name__}.{mod.name}")
            drv = getattr(m, "DRIVER", None)
            if isinstance(drv, RuntimeDriver):
                drivers.append(drv)
        except Exception:
            continue
    return drivers


def driver_for(probe: dict, drivers: List[RuntimeDriver] = None) -> RuntimeDriver:
    """Pick the driver that claims a probe/connection (by api_type)."""
    for d in (drivers if drivers is not None else load_drivers()):
        if d.matches(probe):
            return d
    return None
