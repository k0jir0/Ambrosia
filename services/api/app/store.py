from __future__ import annotations

from datetime import datetime

from .models import AuditEvent, DecisionState, OutcomeUpdate, ReviewStatus, TradeReview


class ReviewStore:
    def __init__(self) -> None:
        self._reviews: dict[str, TradeReview] = {}
        self._trial_count = 0

    @property
    def next_trial_count(self) -> int:
        self._trial_count += 1
        return self._trial_count

    def list_reviews(self) -> list[TradeReview]:
        return sorted(self._reviews.values(), key=lambda review: review.createdAt, reverse=True)

    def get_review(self, review_id: str) -> TradeReview | None:
        return self._reviews.get(review_id)

    def save_review(self, review: TradeReview) -> TradeReview:
        self._reviews[review.id] = review
        return review

    def record_decision(self, review_id: str, decision_state: DecisionState) -> TradeReview | None:
        review = self._reviews.get(review_id)
        if review is None:
            return None
        updated = review.model_copy(
            update={
                "decisionState": decision_state,
                "status": ReviewStatus.decision_recorded,
                "audit": [
                    *review.audit,
                    AuditEvent(
                        id=f"audit-{len(review.audit) + 1}",
                        timestamp=datetime.now().strftime("%H:%M:%S"),
                        eventType="decision.recorded",
                        detail=f"Human decision captured: {decision_state.value}",
                    ),
                ],
            }
        )
        self._reviews[review_id] = updated
        return updated

    def record_outcome(self, review_id: str, outcome: OutcomeUpdate) -> TradeReview | None:
        review = self._reviews.get(review_id)
        if review is None:
            return None
        updated = review.model_copy(
            update={
                "audit": [
                    *review.audit,
                    AuditEvent(
                        id=f"audit-{len(review.audit) + 1}",
                        timestamp=datetime.now().strftime("%H:%M:%S"),
                        eventType="outcome.recorded",
                        detail=f"{outcome.outcome_date}: {outcome.outcome}",
                    ),
                ]
            }
        )
        self._reviews[review_id] = updated
        return updated


store = ReviewStore()