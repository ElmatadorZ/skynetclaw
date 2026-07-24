"""
makruk/game.py — Makruk game state (the playable object)
========================================================
Single responsibility: hold a full game (board + side-to-move + history), apply
moves by algebraic squares, report status, and serialize for the UI/API. Rules
live in rules.py; this is the stateful wrapper the API and AI talk to.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .board import Board, WHITE, BLACK, opponent, alg, parse_alg
from . import rules
from .rules import Move


@dataclass
class Game:
    board: Board = field(default_factory=Board.initial)
    turn: str = WHITE
    history: List[str] = field(default_factory=list)     # move UCIs
    winner: Optional[str] = None                          # 'w' | 'b' | None
    result: Optional[str] = None                          # checkmate/stalemate/draw/repetition
    _positions: Dict = field(default_factory=dict, repr=False)   # position → times seen

    def __post_init__(self):
        self._positions = {self._pos_key(): 1}            # seed the starting position

    def _pos_key(self):
        return (tuple(self.board.squares), self.turn)

    # ── queries ──
    def legal_moves(self) -> List[Move]:
        return rules.legal_moves(self.board, self.turn)

    def legal_from(self, frm: int) -> List[Move]:
        return [m for m in self.legal_moves() if m.frm == frm]

    def status(self) -> str:
        return rules.status(self.board, self.turn)

    def is_over(self) -> bool:
        return self.result is not None

    # ── mutation ──
    def push(self, m: Move) -> "Game":
        """Apply a legal Move, flip turn, update terminal state."""
        legal = {(x.frm, x.to, x.promo) for x in self.legal_moves()}
        if (m.frm, m.to, m.promo) not in legal:
            raise ValueError(f"illegal move: {m.uci()}")
        self.board = rules.apply_move(self.board, m)
        self.history.append(m.uci())
        self.turn = opponent(self.turn)
        self._update_terminal()
        if not self.result:                            # threefold repetition → draw
            key = self._pos_key()
            self._positions[key] = self._positions.get(key, 0) + 1
            if self._positions[key] >= 3:
                self.result = "repetition"
                self.winner = None
        return self

    def push_algebraic(self, frm: str, to: str) -> "Game":
        f, t = parse_alg(frm), parse_alg(to)
        # find the matching legal move (resolves promotion automatically)
        for m in self.legal_from(f):
            if m.to == t:
                return self.push(m)
        raise ValueError(f"illegal move: {frm}{to}")

    def _update_terminal(self) -> None:
        st = self.status()
        if st == rules.CHECKMATE:
            self.result = "checkmate"
            self.winner = opponent(self.turn)      # side that just moved
        elif st == rules.STALEMATE:
            self.result = "stalemate"              # draw in Makruk
            self.winner = None
        elif st == rules.DRAW:
            self.result = "draw"                   # insufficient material (e.g. bare kings)
            self.winner = None

    # ── serialization for the API/UI ──
    def to_state(self) -> Dict:
        st = self.status()
        return {
            "board": self.board.to_rows(),
            "turn": self.turn,
            "status": st,
            "in_check": st in (rules.CHECK, rules.CHECKMATE),
            "result": self.result,
            "winner": self.winner,
            "history": list(self.history),
            "legal_moves": [{"from": alg(m.frm), "to": alg(m.to), "promo": m.promo}
                            for m in self.legal_moves()],
        }
