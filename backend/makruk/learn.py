"""
makruk/learn.py — genuine self-improvement for the Makruk engine
================================================================
The engine's strength lives in its evaluation Weights (ai.Weights). This module
LEARNS better weights by self-play, honestly:

  champion ── perturb one weight ──▶ candidate
      ▲                                  │
      │  promote ONLY if the candidate   ▼
      │  (a) beats the champion head-to-head across seeded openings, AND
      └──(b) does NOT regress on a FROZEN anchor suite (fixed puzzles with
             known answers — mate + win-material positions).

(b) is the guard against circular self-deception: "improvement" that only beats
your own past self is not enough — you must still solve the objective anchors.
Everything is deterministic (seeded) and every step is written to a ledger, so a
gain is auditable evidence, not a vibe.

This is also the REFERENCE self-improvement loop for SkynetClaw: parameterise a
capability → self-play/self-measure → gate against a frozen anchor → promote →
persist. Other cognitive capabilities can follow the same shape. See ADR-0010.

Run:  python -m makruk.learn --generations 40
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .board import Board, parse_alg, alg
from .game import Game
from .ai import (Weights, DEFAULT_WEIGHTS, best_move, save_weights, load_weights,
                 _WEIGHTS_FILE, _MATE)

_LEDGER_FILE = Path(__file__).with_name("training_ledger.json")


# ── the FROZEN anchor suite: fixed positions with known correct play ──────────
# verdict: ("mate",) → engine must see a forced mate; ("to", sq) → best move must
# land on sq (win the hanging piece / promote). These never change — they are the
# non-circular floor every candidate must still clear.
ANCHORS: List[Tuple[str, Dict[str, str], str, Tuple]] = [
    ("mate_in_1",   {"a8": "bK", "h7": "wR", "g7": "wR", "e1": "wK"}, "w", ("mate",)),
    ("win_rook",    {"e1": "wK", "e8": "bK", "d1": "wR", "d5": "bR"}, "w", ("to", "d5")),
    ("win_knight",  {"e1": "wK", "e8": "bK", "a1": "wR", "a5": "bN"}, "w", ("to", "a5")),
    ("promote_bia", {"h1": "wK", "h8": "bK", "a5": "wP"},             "w", ("to", "a6")),
]


def _setup(pieces: Dict[str, str], turn: str) -> Game:
    b = Board()
    for a, p in pieces.items():
        b.set(parse_alg(a), p)
    return Game(board=b, turn=turn)


def anchor_score(w: Weights, depth: int = 2) -> float:
    """Fraction of the frozen anchor suite the weights get right. Non-circular."""
    ok = 0
    for _name, pieces, turn, verdict in ANCHORS:
        g = _setup(pieces, turn)
        res = best_move(g, depth=depth, w=w, extend=False)
        if res.move is None:
            continue
        if verdict[0] == "mate":
            ok += res.score >= _MATE - 1000
        else:
            ok += alg(res.move.to) == verdict[1]
    return ok / len(ANCHORS)


# ── self-play ─────────────────────────────────────────────────────────────────
def random_opening(rng: random.Random, plies: int = 4) -> List[Tuple[str, str]]:
    """A short seeded random opening so self-play games are diverse (the engine is
    deterministic, so without this every game would be identical)."""
    g = Game()
    seq: List[Tuple[str, str]] = []
    for _ in range(plies):
        moves = g.legal_moves()
        if not moves:
            break
        m = rng.choice(moves)
        g.push(m)
        seq.append((alg(m.frm), alg(m.to)))
    return seq


def _material(board: Board, color: str) -> float:
    """Neutral material count — judged by the FIXED default values, never the
    candidate's own weights (so a candidate can't 'win' by inflating its values)."""
    return sum(DEFAULT_WEIGHTS.value(k) for _s, k in board.pieces(color))


def _play_outcome(w_white: Weights, w_black: Weights, depth: int,
                  opening: Tuple, max_plies: int) -> float:
    """Play a game; return a dense outcome from White's view: a big number for a
    checkmate, otherwise the final material difference (so even unfinished short
    games carry signal — essential when shallow games rarely mate)."""
    g = Game()
    for frm, to in opening:
        try:
            g.push_algebraic(frm, to)
        except ValueError:
            break
    while not g.is_over() and len(g.history) < max_plies:
        w = w_white if g.turn == "w" else w_black
        res = best_move(g, depth=depth, w=w, extend=False)
        if res.move is None:
            break
        g.push(res.move)
    if g.result == "checkmate":
        return 100.0 if g.winner == "w" else -100.0
    return _material(g.board, "w") - _material(g.board, "b")


def play_game(w_white: Weights, w_black: Weights, depth: int = 2,
              opening: Tuple = (), max_plies: int = 60) -> Optional[str]:
    """Convenience: winning colour ('w'/'b') if the game was decided by mate, else None."""
    g = Game()
    for frm, to in opening:
        try:
            g.push_algebraic(frm, to)
        except ValueError:
            break
    while not g.is_over() and len(g.history) < max_plies:
        w = w_white if g.turn == "w" else w_black
        res = best_move(g, depth=depth, w=w, extend=False)
        if res.move is None:
            break
        g.push(res.move)
    return g.winner if g.result == "checkmate" else None


def match(w_a: Weights, w_b: Weights, openings: List, depth: int = 2,
          max_plies: int = 40) -> float:
    """Net dense score of A vs B, each opening played from both colours.
    Positive ⇒ A is stronger. Uses the neutral material judge."""
    score = 0.0
    for opening in openings:
        score += _play_outcome(w_a, w_b, depth, opening, max_plies)   # A White
        score -= _play_outcome(w_b, w_a, depth, opening, max_plies)   # A Black
    return score


def perturb(w: Weights, rng: random.Random, scale: float = 0.18) -> Weights:
    """Mutate one weight multiplicatively (a (1+1) coordinate step)."""
    d = w.as_dict()
    key = rng.choice(list(d.keys()))
    d[key] = round(max(0.0, d[key] * (1 + rng.uniform(-scale, scale))), 4)
    return Weights.from_dict(d)


@dataclass
class TuneResult:
    champion: Weights
    base: Weights
    ledger: List[Dict] = field(default_factory=list)
    promotions: int = 0
    base_anchor: float = 0.0
    champion_anchor: float = 0.0


def tune(generations: int = 30, depth: int = 2, n_openings: int = 3,
         seed: int = 1, start: Optional[Weights] = None, max_plies: int = 40) -> TuneResult:
    """(1+1) self-play hill-climb with a frozen-anchor gate. Deterministic per seed."""
    rng = random.Random(seed)
    champion = start or DEFAULT_WEIGHTS
    champ_anchor = anchor_score(champion, depth)
    base_anchor = champ_anchor
    ledger: List[Dict] = []
    promotions = 0

    for gen in range(generations):
        openings = [random_opening(rng, 4) for _ in range(n_openings)]
        cand = perturb(champion, rng)
        cand_anchor = anchor_score(cand, depth)
        m = match(cand, champion, openings, depth, max_plies)   # >0 ⇒ candidate is stronger
        # gate: must not regress on the frozen anchor AND must beat the champion
        promote = (cand_anchor >= champ_anchor - 1e-9) and (m > 0)
        changed = [k for k in cand.as_dict() if cand.as_dict()[k] != champion.as_dict()[k]]
        ledger.append({"gen": gen, "changed": changed, "match": m,
                       "cand_anchor": round(cand_anchor, 3),
                       "champ_anchor": round(champ_anchor, 3), "promoted": promote})
        if promote:
            champion, champ_anchor = cand, cand_anchor
            promotions += 1

    return TuneResult(champion, champion if start is None else start, ledger,
                      promotions, base_anchor, champ_anchor)


def run_and_save(generations: int = 40, depth: int = 2, n_openings: int = 3,
                 seed: int = 1) -> TuneResult:
    """Tune from the currently-active weights and persist champion + ledger."""
    res = tune(generations, depth, n_openings, seed, start=load_weights())
    # only overwrite the shipped weights if the champion is at least as good on
    # the frozen anchor (never ship a regression)
    if res.champion_anchor >= res.base_anchor - 1e-9 and res.promotions > 0:
        save_weights(res.champion)
    _LEDGER_FILE.write_text(json.dumps({
        "generations": generations, "seed": seed, "promotions": res.promotions,
        "base_anchor": res.base_anchor, "champion_anchor": res.champion_anchor,
        "champion": res.champion.as_dict(), "ledger": res.ledger,
    }, indent=2), "utf-8")
    return res


if __name__ == "__main__":
    import argparse
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Self-play weight tuning for Makruk")
    ap.add_argument("--generations", type=int, default=40)
    ap.add_argument("--depth", type=int, default=2)
    ap.add_argument("--openings", type=int, default=3)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    r = run_and_save(a.generations, a.depth, a.openings, a.seed)
    print(f"promotions: {r.promotions}/{a.generations}")
    print(f"anchor: {r.base_anchor:.3f} -> {r.champion_anchor:.3f} (frozen floor held)")
    print("champion weights:", json.dumps(r.champion.as_dict()))
    print(f"ledger -> {_LEDGER_FILE.name}; weights -> {_WEIGHTS_FILE.name if r.promotions else '(unchanged)'}")
