"""
services/learning_service.py — LearningService
==============================================
Owns the Learning Engine and an append-only history ledger. After a mission, it turns the
recorded decision/outcome history into a structured LearningReport. The analysis is a pure
function of the history (deterministic replay); only the ledger's on-disk persistence has
side effects, and it is optional (in-memory by default).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..contracts import LearningReport
from ..engines.learning_engine import LearningEngine


class LearningService:
    def __init__(self, engine=None, ledger_path: Optional[str] = None):
        self._engine = engine or LearningEngine()
        self._history: List[Dict[str, Any]] = []
        self._ledger = Path(ledger_path) if ledger_path else None
        if self._ledger and self._ledger.exists():
            self._load()

    def record(self, item: Dict[str, Any]) -> None:
        self._history.append(dict(item))
        if self._ledger:
            self._append(item)

    def history(self) -> List[Dict[str, Any]]:
        return list(self._history)

    def learn(self, history: Optional[List[Dict[str, Any]]] = None) -> LearningReport:
        return self._engine.learn(self._history if history is None else history)

    # — ledger persistence (optional side effect; core stays pure) —
    def _append(self, item: Dict[str, Any]) -> None:
        try:
            with self._ledger.open("a", encoding="utf-8") as f:
                f.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
        except Exception:
            pass

    def _load(self) -> None:
        try:
            for line in self._ledger.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    self._history.append(json.loads(line))
        except Exception:
            pass
