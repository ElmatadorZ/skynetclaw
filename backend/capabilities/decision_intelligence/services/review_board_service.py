"""
services/review_board_service.py — ReviewBoardService
=====================================================
Owns the Decision Review Engine AND the Counter Example Engine, and composes them (this is
the legitimate place two engines meet — at the service layer, never engine→engine). It
searches for a counter-example, feeds it to the review engine, and returns a verdict that
can REJECT a weak decision.
"""
from __future__ import annotations

from typing import Dict, List

from ..contracts import Decision, Goal, ReviewVerdict, SimOutcome, WorldVars
from ..engines.decision_review_engine import DecisionReviewEngine
from ..engines.counter_example_engine import DIFCounterExampleEngine


class ReviewBoardService:
    def __init__(self, review_engine=None, counter_example_engine=None):
        self._review = review_engine or DecisionReviewEngine()
        self._ce = counter_example_engine or DIFCounterExampleEngine()

    def review(self, decision: Decision, world: WorldVars, goals: List[Goal],
               outcomes: Dict[str, SimOutcome], constraints_text: str,
               confidence_threshold: float) -> ReviewVerdict:
        counterexample = self._ce.find(world, constraints_text, goals)
        return self._review.review(
            decision, world, goals, outcomes, constraints_text, confidence_threshold,
            counterexample=counterexample)
