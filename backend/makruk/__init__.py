"""
makruk — Thai Chess (Makruk) engine + AI for SkynetClaw.

A deterministic rules engine (board · rules · game) plus a searching AI (ai),
built as an isolated package (no main.py coupling). Serves as a live logic
testbed: exact move legality, check/checkmate, and a minimax opponent.

A self-play learning loop (learn) tunes the engine's evaluation weights and
persists the champion, so the engine genuinely improves over time — gated by a
frozen anchor suite so gains are real, not circular. See ADR-0009 / ADR-0010.

Public API:
    from makruk import Game, Board, Move
    from makruk.ai import best_move, Weights, load_weights
    from makruk.learn import tune, anchor_score, run_and_save
"""
from .board import Board, WHITE, BLACK, alg, parse_alg  # noqa: F401
from .rules import (Move, legal_moves, in_check, status, insufficient_material,  # noqa: F401
                    CHECKMATE, STALEMATE, DRAW, CHECK, ONGOING)
from .game import Game  # noqa: F401
from .ai import best_move, evaluate, Weights, DEFAULT_WEIGHTS, load_weights, save_weights  # noqa: F401
