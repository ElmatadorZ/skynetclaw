"""
makruk/rules.py — Makruk move generation & legality
===================================================
Single responsibility: given a Board and a side to move, produce the LEGAL moves,
and answer check / checkmate / stalemate. Deterministic and exhaustive — this is
the "logic" the engine reasons over.

Move rules (Makruk):
    Khun (K)  — 1 step, 8 directions (like a chess king).
    Met  (M)  — 1 step diagonally (4 directions).       [weak counselor]
    Khon (B)  — 1 step diagonally (4) + 1 step straight FORWARD.  [silver-general]
    Ma   (N)  — knight L-jumps (8), the only jumper.
    Ruea (R)  — slides orthogonally any distance.
    Bia  (P)  — 1 step straight forward (non-capture); captures 1 step diagonally
                forward; promotes to Met-mover (F) on the promotion rank.
    F         — promoted pawn: moves like Met.

License: Apache-2.0 — ElmatadorZ
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .board import (Board, file_of, rank_of, in_bounds, sq, alg,
                    opponent, forward, promotion_rank, WHITE, BLACK)

# direction sets (df, dr)
_DIAG = [(-1, -1), (-1, 1), (1, -1), (1, 1)]
_ORTHO = [(-1, 0), (1, 0), (0, -1), (0, 1)]
_ALL8 = _DIAG + _ORTHO
_KNIGHT = [(-1, -2), (1, -2), (-1, 2), (1, 2), (-2, -1), (-2, 1), (2, -1), (2, 1)]


@dataclass(frozen=True)
class Move:
    frm: int
    to: int
    promo: bool = False
    capture: Optional[str] = None   # captured piece code, for display/undo

    def uci(self) -> str:
        return alg(self.frm) + alg(self.to) + ("=M" if self.promo else "")

    def __repr__(self) -> str:
        return self.uci()


def _step_targets(board: Board, s: int, deltas, color: str) -> List[int]:
    """One-step moves in each delta that land on empty or enemy squares."""
    out = []
    f, r = file_of(s), rank_of(s)
    for df, dr in deltas:
        nf, nr = f + df, r + dr
        if not in_bounds(nf, nr):
            continue
        t = sq(nf, nr)
        if board.color_at(t) != color:      # empty or enemy
            out.append(t)
    return out


def _slide_targets(board: Board, s: int, deltas, color: str) -> List[int]:
    """Sliding moves (rook) — stop at first blocker, may capture enemy."""
    out = []
    f, r = file_of(s), rank_of(s)
    for df, dr in deltas:
        nf, nr = f + df, r + dr
        while in_bounds(nf, nr):
            t = sq(nf, nr)
            occ = board.color_at(t)
            if occ is None:
                out.append(t)
            else:
                if occ != color:
                    out.append(t)          # capture
                break
            nf += df
            nr += dr
    return out


def _khon_deltas(color: str):
    """Bishop = 4 diagonals + 1 straight forward."""
    return _DIAG + [(0, forward(color))]


def pseudo_moves_from(board: Board, s: int) -> List[Move]:
    """All pseudo-legal moves (ignoring self-check) for the piece on `s`."""
    piece = board.piece_at(s)
    if not piece:
        return []
    color, kind = piece[0], piece[1]
    moves: List[Move] = []

    def emit(targets):
        for t in targets:
            moves.append(Move(s, t, capture=board.piece_at(t)))

    if kind == "K":
        emit(_step_targets(board, s, _ALL8, color))
    elif kind == "M" or kind == "F":
        emit(_step_targets(board, s, _DIAG, color))
    elif kind == "B":
        emit(_step_targets(board, s, _khon_deltas(color), color))
    elif kind == "N":
        emit(_step_targets(board, s, _KNIGHT, color))
    elif kind == "R":
        emit(_slide_targets(board, s, _ORTHO, color))
    elif kind == "P":
        moves.extend(_pawn_moves(board, s, color))
    return moves


def _pawn_moves(board: Board, s: int, color: str) -> List[Move]:
    out: List[Move] = []
    f, r = file_of(s), rank_of(s)
    dr = forward(color)
    promo_r = promotion_rank(color)
    # forward one (non-capturing) — only if empty
    nr = r + dr
    if in_bounds(f, nr) and board.piece_at(sq(f, nr)) is None:
        out.append(Move(s, sq(f, nr), promo=(nr == promo_r)))
    # diagonal captures
    for df in (-1, 1):
        nf = f + df
        if in_bounds(nf, nr):
            t = sq(nf, nr)
            occ = board.color_at(t)
            if occ is not None and occ != color:
                out.append(Move(s, t, promo=(nr == promo_r), capture=board.piece_at(t)))
    return out


def _attacks_of_kind(board: Board, s: int, color: str, kind: str) -> List[int]:
    """Squares a piece ATTACKS (pawns attack only diagonally, unlike their pushes)."""
    if kind == "K":
        return _step_targets(board, s, _ALL8, color)
    if kind in ("M", "F"):
        return _step_targets(board, s, _DIAG, color)
    if kind == "B":
        return _step_targets(board, s, _khon_deltas(color), color)
    if kind == "N":
        return _step_targets(board, s, _KNIGHT, color)
    if kind == "R":
        return _slide_targets(board, s, _ORTHO, color)
    if kind == "P":
        f, r = file_of(s), rank_of(s)
        dr = forward(color)
        out = []
        for df in (-1, 1):
            nf, nr = f + df, r + dr
            if in_bounds(nf, nr):
                out.append(sq(nf, nr))
        return out
    return []


def is_attacked(board: Board, target: int, by_color: str) -> bool:
    """Is `target` attacked by any piece of `by_color`?

    King-centric (look OUTWARD from the target) — O(1) square probes plus 4 rook
    rays, instead of generating every enemy piece's move list. This is the search
    hot path, so speed here dominates engine strength."""
    sq_at = board.squares
    f, r = file_of(target), rank_of(target)
    fwd = forward(by_color)

    # Bia (pawn): an enemy pawn one step "back" on either file attacks diagonally in
    for df in (-1, 1):
        nf, nr = f + df, r - fwd
        if in_bounds(nf, nr) and sq_at[sq(nf, nr)] == by_color + "P":
            return True
    # Ma (knight)
    for df, dr in _KNIGHT:
        nf, nr = f + df, r + dr
        if in_bounds(nf, nr) and sq_at[sq(nf, nr)] == by_color + "N":
            return True
    # Khun (king) — adjacent
    for df, dr in _ALL8:
        nf, nr = f + df, r + dr
        if in_bounds(nf, nr) and sq_at[sq(nf, nr)] == by_color + "K":
            return True
    # diagonal attackers: Met, promoted Bia (F), and Khon (all move 1 diagonally)
    for df, dr in _DIAG:
        nf, nr = f + df, r + dr
        if in_bounds(nf, nr):
            p = sq_at[sq(nf, nr)]
            if p == by_color + "M" or p == by_color + "F" or p == by_color + "B":
                return True
    # Khon straight-forward: a khon one step "back" attacks its forward square
    nf, nr = f, r - fwd
    if in_bounds(nf, nr) and sq_at[sq(nf, nr)] == by_color + "B":
        return True
    # Ruea (rook): first blocker along each orthogonal ray
    for df, dr in _ORTHO:
        nf, nr = f + df, r + dr
        while in_bounds(nf, nr):
            p = sq_at[sq(nf, nr)]
            if p:
                if p == by_color + "R":
                    return True
                break
            nf += df
            nr += dr
    return False


def in_check(board: Board, color: str) -> bool:
    ks = board.king_sq(color)
    if ks is None:
        return False
    return is_attacked(board, ks, opponent(color))


def apply_move(board: Board, m: Move) -> Board:
    """Return a NEW board with the move applied (promotion handled)."""
    nb = board.clone()
    piece = nb.piece_at(m.frm)
    nb.set(m.frm, None)
    if m.promo and piece and piece[1] == "P":
        nb.set(m.to, piece[0] + "F")     # promote Bia → Met-mover
    else:
        nb.set(m.to, piece)
    return nb


def legal_moves(board: Board, color: str) -> List[Move]:
    """Pseudo-legal moves filtered so the mover's own king is not left in check.

    Uses in-place make/unmake (no board clone per candidate) — the other search
    hot path. Correctness is guarded by the test-suite (checks, pins, mate)."""
    out: List[Move] = []
    sqs = board.squares
    for s, _kind in board.pieces(color):
        for m in pseudo_moves_from(board, s):
            moved = sqs[m.frm]
            captured = sqs[m.to]
            sqs[m.frm] = None
            sqs[m.to] = (color + "F") if (m.promo and moved and moved[1] == "P") else moved
            legal = not in_check(board, color)
            sqs[m.frm] = moved                 # unmake (exact restore)
            sqs[m.to] = captured
            if legal:
                out.append(m)
    # deterministic ordering
    out.sort(key=lambda mv: (mv.frm, mv.to, mv.promo))
    return out


# ── game status ───────────────────────────────────────────────────────────────
CHECKMATE = "checkmate"
STALEMATE = "stalemate"
DRAW = "draw"
CHECK = "check"
ONGOING = "ongoing"


def insufficient_material(board: Board) -> bool:
    """True when neither side can possibly force checkmate → an immediate draw.

    In Makruk a lone king, or a king with a single weak piece (Met, promoted Bia,
    Khon or Ma), cannot deliver mate. So with no pawns and no rooks anywhere, and
    at most one such piece per side, the game is drawn — this is the bare-king case
    that ends a game the moment the last mating material is gone.
    (Full Makruk piece/board *counting* rules for still-winnable endings are not
    modelled here; only positions that are definitely drawn are declared.)"""
    w = [k for _, k in board.pieces("w") if k != "K"]
    b = [k for _, k in board.pieces("b") if k != "K"]
    if any(k in ("P", "R") for k in w + b):     # a pawn (can promote) or rook → mate is possible
        return False
    return len(w) <= 1 and len(b) <= 1


def status(board: Board, color: str) -> str:
    """Status for the side `color` to move."""
    has_move = bool(legal_moves(board, color))
    checked = in_check(board, color)
    if checked and not has_move:
        return CHECKMATE
    if not checked and not has_move:
        return STALEMATE
    if insufficient_material(board):
        return DRAW
    if checked:
        return CHECK
    return ONGOING
