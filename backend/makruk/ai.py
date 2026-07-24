"""
makruk/ai.py — the Makruk opponent (deterministic search)
=========================================================
Single responsibility: choose a move for a side. Negamax + alpha-beta over the
exact rules engine, with a Makruk-tuned evaluation. Deterministic (given a
position + depth it always plays the same move) and node-budgeted (SkynetClaw is
CPU-bound, so search must stay responsive).

This is the *logic testbed*: the evaluation and search are the knobs to develop.
Every choice is explainable — best_move returns the principal variation + score.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .board import Board, file_of, rank_of, WHITE, BLACK, opponent, forward, promotion_rank
from . import rules
from .rules import Move, legal_moves, in_check, apply_move

# ── tunable evaluation weights — the parameters the self-play loop LEARNS ──────
@dataclass(frozen=True)
class Weights:
    # Makruk relative piece values (Ruea strongest; Met/promoted-pawn weak)
    P: float = 1.0
    M: float = 2.0
    F: float = 2.0
    B: float = 2.5
    N: float = 3.0
    R: float = 5.0
    center: float = 0.04         # activity bonus toward the centre
    pawn_advance: float = 0.5    # extra Bia value approaching promotion
    mop_edge: float = 0.20       # drive the losing king to the edge (mate technique)
    mop_king: float = 0.07       # bring the winning king in

    def value(self, kind: str) -> float:
        return 0.0 if kind == "K" else getattr(self, kind, 0.0)

    def as_dict(self) -> Dict[str, float]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "Weights":
        f = cls.__dataclass_fields__
        return cls(**{k: float(v) for k, v in d.items() if k in f})


DEFAULT_WEIGHTS = Weights()
_MATE = 100_000.0

# A self-tuned weights.json (produced by makruk.learn) ships automatically when
# present — this is how the self-improvement PERSISTS into the deployed engine.
_WEIGHTS_FILE = Path(__file__).with_name("weights.json")


def load_weights(path=None) -> "Weights":
    try:
        return Weights.from_dict(json.loads(Path(path or _WEIGHTS_FILE).read_text("utf-8")))
    except Exception:
        return DEFAULT_WEIGHTS


def save_weights(w: "Weights", path=None) -> None:
    Path(path or _WEIGHTS_FILE).write_text(json.dumps(w.as_dict(), indent=2), "utf-8")


ACTIVE_WEIGHTS = load_weights()

# Back-compat: default piece values as a plain dict (used by move ordering).
VALUE: Dict[str, float] = {k: DEFAULT_WEIGHTS.value(k) for k in ("P", "M", "F", "B", "N", "R", "K")}


def _center_manhattan(s: int) -> int:
    """Distance of a square from the central 2x2 block (0 at centre, 6 at a corner)."""
    f, r = file_of(s), rank_of(s)
    return max(3 - f, f - 4, 0) + max(3 - r, r - 4, 0)


def _manhattan(a: int, b: int) -> int:
    return abs(file_of(a) - file_of(b)) + abs(rank_of(a) - rank_of(b))


def evaluate(board: Board, color: str, w: Optional["Weights"] = None) -> float:
    """Static evaluation from `color`'s perspective (higher = better). `w` are the
    tunable weights; defaults to the active (possibly self-tuned) set."""
    w = w or ACTIVE_WEIGHTS
    score = 0.0
    mat = {WHITE: 0.0, BLACK: 0.0}
    for c in (WHITE, BLACK):
        sign = 1.0 if c == color else -1.0
        for s, kind in board.pieces(c):
            v = w.value(kind)
            if kind == "P":                      # pawns gain value approaching promotion
                promo_r = promotion_rank(c)
                start_r = 2 if c == WHITE else 5
                dist = abs(promo_r - rank_of(s))
                span = abs(promo_r - start_r) or 1
                v += w.pawn_advance * (1 - dist / span)
            mat[c] += w.value(kind)
            f, r = file_of(s), rank_of(s)
            score += sign * (v + w.center * (min(f, 7 - f) + min(r, 7 - r)))

    # ── mop-up: convert a decisive material lead into a mate ──────────────────
    # Once winning overwhelmingly, plain material is flat across moves, so the
    # search shuffles. Drive the losing king to the edge and bring the winning
    # king in (the KR-vs-K technique). Only when the loser is nearly bare.
    for winner in (WHITE, BLACK):
        loser = opponent(winner)
        lead = mat[winner] - mat[loser]
        loser_pieces = sum(1 for _, k in board.pieces(loser) if k != "K")
        if lead >= 4.0 and loser_pieces <= 3:
            wk, lk = board.king_sq(winner), board.king_sq(loser)
            if wk is not None and lk is not None:
                mop = w.mop_edge * _center_manhattan(lk) + w.mop_king * (14 - _manhattan(wk, lk))
                score += mop if winner == color else -mop
    return score


def _order(board: Board, moves: List[Move]) -> List[Move]:
    """Captures first (by victim value) to strengthen alpha-beta pruning. Stable."""
    def key(m: Move) -> Tuple:
        cap = VALUE.get(m.capture[1], 0.0) if m.capture else -1.0
        return (-cap, -1.0 if m.promo else 0.0, m.frm, m.to)
    return sorted(moves, key=key)


@dataclass
class SearchResult:
    move: Optional[Move]
    score: float
    nodes: int
    depth: int
    pv: List[str]           # principal variation (UCIs) — the engine's plan
    reason: str


class _Timeout(Exception):
    """Raised to abort a search that has exceeded its wall-clock deadline."""


def _negamax(board: Board, color: str, depth: int, alpha: float, beta: float,
             budget: List[int], w: "Weights", deadline: Optional[float] = None
             ) -> Tuple[float, List[Move]]:
    if deadline is not None and time.time() > deadline:
        raise _Timeout                       # unwind; the incomplete depth is discarded
    if budget[0] <= 0:
        return evaluate(board, color, w), []
    budget[0] -= 1

    moves = legal_moves(board, color)
    if not moves:
        # no legal move: checkmate (bad, prefer later) or stalemate (draw)
        if in_check(board, color):
            return -_MATE - depth, []       # deeper mate against us scores higher (avoid)
        return 0.0, []                       # stalemate = draw
    if depth == 0:
        return evaluate(board, color, w), []

    best_score = -float("inf")
    best_line: List[Move] = []
    for m in _order(board, moves):
        child = apply_move(board, m)
        score, line = _negamax(child, opponent(color), depth - 1, -beta, -alpha, budget, w, deadline)
        score = -score
        if score > best_score:
            best_score, best_line = score, [m] + line
        alpha = max(alpha, score)
        if alpha >= beta:
            break                            # prune
    return best_score, best_line


def best_move(game, depth: int = 3, node_budget: int = 120_000,
              w: Optional["Weights"] = None, extend: bool = True,
              time_limit: Optional[float] = None) -> SearchResult:
    """Pick a move for the side to move; returns the plan + score.
    `w` selects the evaluation weights (defaults to the active, self-tuned set).
    `extend=False` disables the endgame depth extension.
    `time_limit` (seconds): if set, iterative-deepening search up to `depth`,
    stopping at the deadline and returning the deepest COMPLETED iteration — this
    keeps deep levels responsive (bounded wall-clock). Without it the search is
    fixed-depth and deterministic (used by tests and tuning)."""
    w = w or ACTIVE_WEIGHTS
    board, color = game.board, game.turn
    moves = legal_moves(board, color)
    if not moves:
        return SearchResult(None, 0.0, 0, depth, [], "no legal moves (game over)")
    # Endgame extension: with few pieces the branching factor is tiny, so search
    # deeper to actually see the mating net (converts wins instead of shuffling).
    total = len(board.pieces(WHITE)) + len(board.pieces(BLACK))
    if extend and total <= 5:
        depth = max(depth, 6)
    elif extend and total <= 8:
        depth = max(depth, 5)

    used = 0
    if time_limit:
        # iterative deepening under a wall-clock deadline
        deadline = time.time() + time_limit
        score, line, reached = 0.0, [], 0
        for d in range(1, depth + 1):
            budget = [node_budget]
            try:
                s, ln = _negamax(board, color, d, -float("inf"), float("inf"), budget, w, deadline)
            except _Timeout:
                break                        # keep the last completed depth
            score, line, reached = s, ln, d
            used += node_budget - budget[0]
            if abs(score) >= _MATE - 100:    # found a forced mate — no need to go deeper
                break
        depth = reached or 1
    else:
        budget = [node_budget]
        score, line = _negamax(board, color, depth, -float("inf"), float("inf"), budget, w)
        used = node_budget - budget[0]

    mv = line[0] if line else _order(board, moves)[0]
    if score >= _MATE - 100:
        why = f"forced mate in {(len(line) + 1) // 2} (depth {depth})"
    elif score <= -_MATE + 100:
        why = "position is lost against best play — playing the most resistant move"
    else:
        why = f"eval {score:+.2f} for {color} at depth {depth} ({used} nodes)"
    return SearchResult(mv, score, used, depth, [x.uci() for x in line], why)


def win_prob(score: float) -> float:
    """A calibrated-shape win-expectancy estimate from the evaluation, in [0,1],
    for the side the score belongs to. This is an honest monotonic transform of the
    exact eval (the standard logistic win curve) — NOT a separate probability model.
    A forced mate maps to ~1, being mated to ~0."""
    if score >= _MATE - 1000:
        return 0.999
    if score <= -_MATE + 1000:
        return 0.001
    return round(1.0 / (1.0 + math.exp(-score / 2.5)), 4)


# difficulty presets. Genesis = the deepest (5-ply) search — strongest & slowest.
LEVELS = {"easy": 1, "normal": 2, "hard": 3, "expert": 4, "genesis": 5}

# per-level node budget: Genesis gets a bigger budget so 5-ply search can actually
# complete the critical lines instead of being truncated (still bounded — CPU-safe).
LEVEL_BUDGET = {"genesis": 400_000}
DEFAULT_BUDGET = 120_000

# Genesis uses iterative deepening under a wall-clock limit so a 5-ply search stays
# responsive: it returns the deepest COMPLETED depth within the time budget. ~10s
# reliably completes depth 4 in the midgame (so Genesis ≥ Expert) and reaches the
# full 5 ply in simpler / endgame positions.
LEVEL_TIME = {"genesis": 10.0}
