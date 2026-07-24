"""
test_makruk.py — rules & engine tests for the Thai Chess (Makruk) engine.
Deterministic, model-free. Run: python -m pytest tests/test_makruk.py
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from makruk.board import Board, parse_alg, alg
from makruk import rules
from makruk.rules import Move, pseudo_moves_from, legal_moves, in_check, status, apply_move
from makruk.game import Game


def _empty() -> Board:
    return Board()


def _targets(board: Board, sq_alg: str):
    s = parse_alg(sq_alg)
    return sorted(alg(m.to) for m in pseudo_moves_from(board, s))


# ── SETUP ────────────────────────────────────────────────────────────────────
def test_initial_setup_counts_and_kings():
    g = Game()
    assert len(g.board.pieces("w")) == 16 and len(g.board.pieces("b")) == 16
    # Makruk: White Khun d1 / Met e1; Black Khun e8 / Met d8 (rotational, not mirror)
    assert g.board.piece_at(parse_alg("d1")) == "wK"
    assert g.board.piece_at(parse_alg("e1")) == "wM"
    assert g.board.piece_at(parse_alg("e8")) == "bK"
    assert g.board.piece_at(parse_alg("d8")) == "bM"
    # pawns on the 3rd / 6th ranks
    assert g.board.piece_at(parse_alg("a3")) == "wP"
    assert g.board.piece_at(parse_alg("h6")) == "bP"


# ── PIECE MOVEMENT ───────────────────────────────────────────────────────────
def test_met_moves_diagonally_only():
    b = _empty()
    b.set(parse_alg("d4"), "wM")
    assert _targets(b, "d4") == ["c3", "c5", "e3", "e5"]


def test_khon_moves_diagonals_plus_forward():
    b = _empty()
    b.set(parse_alg("d4"), "wB")          # white khon → 4 diagonals + north
    assert _targets(b, "d4") == ["c3", "c5", "d5", "e3", "e5"]


def test_black_khon_forward_is_south():
    b = _empty()
    b.set(parse_alg("d4"), "bB")          # black khon → 4 diagonals + south
    assert _targets(b, "d4") == ["c3", "c5", "d3", "e3", "e5"]


def test_knight_jumps():
    b = _empty()
    b.set(parse_alg("d4"), "wN")
    assert _targets(b, "d4") == ["b3", "b5", "c2", "c6", "e2", "e6", "f3", "f5"]


def test_rook_slides_and_stops_at_blocker():
    b = _empty()
    b.set(parse_alg("d4"), "wR")
    b.set(parse_alg("d6"), "bP")          # enemy → capturable, blocks beyond
    b.set(parse_alg("f4"), "wP")          # own → blocks, not capturable
    t = _targets(b, "d4")
    assert "d5" in t and "d6" in t and "d7" not in t   # capture d6, stop
    assert "e4" in t and "f4" not in t                 # own piece blocks f4


def test_pawn_pushes_and_captures_diagonally():
    b = _empty()
    b.set(parse_alg("d2"), "wP")
    b.set(parse_alg("e3"), "bP")          # capturable diagonally
    b.set(parse_alg("c3"), "wP")          # own — not a capture target
    t = _targets(b, "d2")
    assert "d3" in t                       # forward push
    assert "e3" in t                       # diagonal capture
    assert "c3" not in t                   # own piece, no capture


def test_pawn_no_forward_capture():
    b = _empty()
    b.set(parse_alg("d2"), "wP")
    b.set(parse_alg("d3"), "bP")          # blocks the push, cannot be captured
    assert "d3" not in _targets(b, "d2")


# ── PROMOTION ────────────────────────────────────────────────────────────────
def test_pawn_promotes_to_met_mover_on_sixth_rank():
    b = _empty()
    b.set(parse_alg("e1"), "wK")
    b.set(parse_alg("d8"), "bK")
    b.set(parse_alg("a5"), "wP")          # rank 5 (0-idx 4) → a6 promotes
    g = Game(board=b, turn="w")
    g.push_algebraic("a5", "a6")
    assert g.board.piece_at(parse_alg("a6")) == "wF"   # promoted (Met-mover)
    # F now moves like Met (diagonally)
    assert sorted(alg(m.to) for m in pseudo_moves_from(g.board, parse_alg("a6"))) == ["b5", "b7"]


# ── CHECK / CHECKMATE / STALEMATE ────────────────────────────────────────────
def test_in_check_detection():
    b = _empty()
    b.set(parse_alg("a8"), "bK")
    b.set(parse_alg("h8"), "wR")          # rook checks along rank 8
    assert in_check(b, "b")
    assert not in_check(b, "w")


def test_two_rook_checkmate():
    b = _empty()
    b.set(parse_alg("a8"), "bK")
    b.set(parse_alg("h8"), "wR")          # check along rank 8
    b.set(parse_alg("g7"), "wR")          # covers rank 7 (a7, b7)
    b.set(parse_alg("e1"), "wK")
    assert status(b, "b") == rules.CHECKMATE
    assert legal_moves(b, "b") == []


def test_stalemate_is_draw():
    b = _empty()
    b.set(parse_alg("a8"), "bK")
    b.set(parse_alg("c7"), "wK")          # covers b7, b8 (not a8)
    b.set(parse_alg("b5"), "wN")          # Ma covers a7 (not a8)
    assert not in_check(b, "b")            # a8 is not attacked
    assert status(b, "b") == rules.STALEMATE   # ...but every king move is


def test_bare_kings_is_a_draw():
    b = _empty()
    b.set(parse_alg("e3"), "wK")
    b.set(parse_alg("g2"), "bK")          # only the two kings left (the screenshot case)
    assert status(b, "b") == rules.DRAW
    assert rules.insufficient_material(b)


def test_king_and_lone_minor_is_a_draw():
    b = _empty()
    b.set(parse_alg("e1"), "wK")
    b.set(parse_alg("c3"), "wN")          # a lone Ma cannot force mate
    b.set(parse_alg("e8"), "bK")
    assert rules.insufficient_material(b) and status(b, "b") == rules.DRAW


def test_rook_or_pawn_is_still_playable():
    b = _empty()
    b.set(parse_alg("e1"), "wK"); b.set(parse_alg("e8"), "bK")
    b.set(parse_alg("a1"), "wR")          # a rook can mate → not a draw
    assert not rules.insufficient_material(b)
    b.set(parse_alg("a1"), None); b.set(parse_alg("d4"), "wP")   # a pawn can promote → not a draw
    assert not rules.insufficient_material(b)


def test_game_declares_draw_when_last_piece_is_captured():
    b = _empty()
    b.set(parse_alg("e3"), "wK")
    b.set(parse_alg("a8"), "bK")          # far away, does not defend e4
    b.set(parse_alg("e4"), "bN")          # White King can capture Black's last Ma...
    g = Game(board=b, turn="w")
    g.push_algebraic("e3", "e4")          # ...leaving bare kings
    assert g.result == "draw" and g.winner is None and g.is_over()


def test_mopup_drives_losing_king_to_the_edge():
    from makruk.ai import evaluate
    # White is winning (K+R vs K). Driving Black's king to a corner should score
    # higher for White than leaving it in the centre — this is what lets the
    # engine make progress toward mate instead of shuffling.
    centre = _empty(); centre.set(parse_alg("e1"), "wK"); centre.set(parse_alg("a1"), "wR"); centre.set(parse_alg("e5"), "bK")
    corner = _empty(); corner.set(parse_alg("e1"), "wK"); corner.set(parse_alg("a1"), "wR"); corner.set(parse_alg("a8"), "bK")
    assert evaluate(corner, "w") > evaluate(centre, "w")


def test_threefold_repetition_is_a_draw():
    b = _empty()
    b.set(parse_alg("e1"), "wK"); b.set(parse_alg("h1"), "wR"); b.set(parse_alg("e8"), "bK")
    g = Game(board=b, turn="w")
    # shuffle rook and king back and forth; the start position recurs every 4 plies
    for _ in range(2):
        g.push_algebraic("h1", "h2"); g.push_algebraic("e8", "e7")
        g.push_algebraic("h2", "h1"); g.push_algebraic("e7", "e8")
    assert g.result == "repetition" and g.winner is None and g.is_over()


def test_game_records_checkmate_result():
    b = _empty()
    b.set(parse_alg("a8"), "bK")
    b.set(parse_alg("h7"), "wR")          # ready to swing to h8
    b.set(parse_alg("g7"), "wR")
    b.set(parse_alg("e1"), "wK")
    g = Game(board=b, turn="w")
    g.push_algebraic("h7", "h8")          # delivers mate
    assert g.result == "checkmate" and g.winner == "w"


# ── LEGALITY (self-check is illegal) ─────────────────────────────────────────
def test_cannot_leave_king_in_check():
    b = _empty()
    b.set(parse_alg("e1"), "wK")
    b.set(parse_alg("e2"), "wR")          # pinned in front of the king
    b.set(parse_alg("e8"), "bR")          # pins along the e-file
    b.set(parse_alg("a8"), "bK")
    moves = legal_moves(b, "w")
    # the pinned rook may move along the e-file but not off it
    rook_dests = sorted(alg(m.to) for m in moves if m.frm == parse_alg("e2"))
    assert all(d[0] == "e" for d in rook_dests)   # stays on e-file, never abandons the pin


def test_initial_position_has_legal_moves():
    g = Game()
    assert len(g.legal_moves()) > 0 and g.status() == rules.ONGOING


# ── AI (deterministic search) ────────────────────────────────────────────────
def test_ai_plays_a_legal_move_from_start():
    from makruk.ai import best_move
    g = Game()
    res = best_move(g, depth=2)
    legal = {(m.frm, m.to, m.promo) for m in g.legal_moves()}
    assert (res.move.frm, res.move.to, res.move.promo) in legal


def test_ai_finds_mate_in_one():
    from makruk.ai import best_move
    b = _empty()
    b.set(parse_alg("a8"), "bK")
    b.set(parse_alg("h7"), "wR")          # h7-h8 is mate (g7 rook covers rank 7)
    b.set(parse_alg("g7"), "wR")
    b.set(parse_alg("e1"), "wK")
    g = Game(board=b, turn="w")
    res = best_move(g, depth=2)
    assert res.score >= 100_000 - 100              # recognized as forced mate
    g.push(res.move)                               # play it...
    assert g.result == "checkmate" and g.winner == "w"   # ...and it is mate


def test_ai_captures_free_material():
    from makruk.ai import best_move
    b = _empty()
    b.set(parse_alg("e1"), "wK")
    b.set(parse_alg("e8"), "bK")
    b.set(parse_alg("d1"), "wR")
    b.set(parse_alg("d5"), "bR")          # undefended, on the rook's file
    g = Game(board=b, turn="w")
    res = best_move(g, depth=3)
    assert res.move.to == parse_alg("d5")          # grabs the hanging rook


def test_genesis_level_is_depth_5():
    from makruk.ai import LEVELS
    assert LEVELS["genesis"] == 5 and LEVELS["genesis"] == max(LEVELS.values())


def test_win_prob_is_monotonic_and_bounded():
    from makruk.ai import win_prob, _MATE
    assert 0.0 <= win_prob(0.0) <= 1.0
    assert win_prob(0.0) == 0.5                        # equal position → 50%
    assert win_prob(5.0) > win_prob(1.0) > win_prob(0.0) > win_prob(-1.0)   # monotonic
    assert win_prob(_MATE) >= 0.99 and win_prob(-_MATE) <= 0.01             # mate ≈ certainty


def test_time_limited_search_is_responsive_and_legal():
    from makruk.ai import best_move
    import time
    g = Game()
    t0 = time.time()
    r = best_move(g, depth=5, time_limit=1.0)          # Genesis-style iterative deepening
    assert (time.time() - t0) < 4.0                    # honours the deadline (with slack)
    legal = {(m.frm, m.to, m.promo) for m in g.legal_moves()}
    assert (r.move.frm, r.move.to, r.move.promo) in legal and r.depth >= 1


def test_time_limited_search_still_finds_mate():
    from makruk.ai import best_move, _MATE
    b = _empty()
    b.set(parse_alg("a8"), "bK"); b.set(parse_alg("h7"), "wR")
    b.set(parse_alg("g7"), "wR"); b.set(parse_alg("e1"), "wK")
    r = best_move(Game(board=b, turn="w"), depth=5, time_limit=3.0)
    assert r.score >= _MATE - 1000                     # deep search still sees the forced mate


def test_ai_is_deterministic():
    from makruk.ai import best_move
    g = Game()
    a = best_move(g, depth=3)
    b = best_move(Game(), depth=3)
    assert (a.move.frm, a.move.to) == (b.move.frm, b.move.to) and a.score == b.score


# ── self-improvement (learn.py) ──────────────────────────────────────────────
def test_evaluate_respects_weights():
    from makruk.ai import evaluate, Weights, DEFAULT_WEIGHTS
    b = _empty(); b.set(parse_alg("e1"), "wK"); b.set(parse_alg("e8"), "bK"); b.set(parse_alg("a1"), "wR")
    hi = Weights.from_dict({**DEFAULT_WEIGHTS.as_dict(), "R": 9.0})
    assert evaluate(b, "w", hi) > evaluate(b, "w", DEFAULT_WEIGHTS)   # weights actually drive eval


def test_anchor_suite_solved_by_default():
    from makruk import learn
    from makruk.ai import DEFAULT_WEIGHTS
    assert learn.anchor_score(DEFAULT_WEIGHTS, depth=2) == 1.0        # the frozen floor is real & met


def test_perturb_changes_one_weight_deterministically():
    import random
    from makruk import learn
    from makruk.ai import DEFAULT_WEIGHTS
    a = learn.perturb(DEFAULT_WEIGHTS, random.Random(1))
    b = learn.perturb(DEFAULT_WEIGHTS, random.Random(1))
    base = DEFAULT_WEIGHTS.as_dict()
    assert a.as_dict() == b.as_dict()                                # deterministic per seed
    assert sum(1 for k in base if a.as_dict()[k] != base[k]) == 1    # exactly one coordinate


def test_weights_save_load_roundtrip(tmp_path):
    from makruk.ai import Weights, save_weights, load_weights, DEFAULT_WEIGHTS
    p = tmp_path / "w.json"
    w = Weights.from_dict({**DEFAULT_WEIGHTS.as_dict(), "R": 6.5})
    save_weights(w, p)
    assert load_weights(p).as_dict() == w.as_dict()


def test_learning_signal_is_real():
    # good weights beat clearly-broken ones head-to-head → the fitness has signal
    # (the necessary condition for the self-play climb to be meaningful, not circular)
    import random
    from makruk import learn
    from makruk.ai import DEFAULT_WEIGHTS, Weights
    rng = random.Random(5)                                    # one rng → two DISTINCT openings
    ops = [learn.random_opening(rng, 6) for _ in range(2)]
    broken = Weights.from_dict({**DEFAULT_WEIGHTS.as_dict(), "R": 1.2, "N": 1.0, "B": 1.0, "M": 0.8})
    assert learn.match(DEFAULT_WEIGHTS, broken, ops, depth=2, max_plies=60) > 0


def test_tune_is_deterministic_and_never_regresses_the_anchor():
    from makruk import learn
    r1 = learn.tune(generations=2, depth=2, n_openings=1, seed=4, max_plies=18)
    r2 = learn.tune(generations=2, depth=2, n_openings=1, seed=4, max_plies=18)
    assert r1.champion.as_dict() == r2.champion.as_dict()            # reproducible
    assert r1.champion_anchor >= r1.base_anchor - 1e-9               # never ships a regression
