from __future__ import annotations

import logging
import os
from datetime import datetime
from uuid import uuid4

from .models import (
    AuditEvent,
    AuditEventCreate,
    DecisionPacket,
    DecisionState,
    OutcomeUpdate,
    ReviewStatus,
    TradeReview,
    AlertQueueRecord,
)
from .db import PacketQuery, PostgresPacketStore, PostgresReviewStore

logger = logging.getLogger(__name__)


class ReviewStore:
    def __init__(self) -> None:
        self._reviews: dict[str, TradeReview] = {}
        self._packets: dict[str, DecisionPacket] = {}
        self._alerts: list[AlertQueueRecord] = []
        self._trial_count = 0
        self._db_enabled = False
        self._review_db: PostgresReviewStore | None = None
        self._packet_db: PostgresPacketStore | None = None

        database_url = os.getenv("DATABASE_URL")
        if database_url:
            try:
                review_db = PostgresReviewStore(database_url)
                packet_db = PostgresPacketStore(database_url)
                review_db.healthcheck()
                packet_db.healthcheck()
                self._review_db = review_db
                self._packet_db = packet_db
                self._db_enabled = True
            except Exception as exc:  # pragma: no cover - environment dependent
                logger.warning("Falling back to in-memory review/packet store: %s", exc)

    def _disable_db(self, exc: Exception) -> None:
        if self._db_enabled:
            logger.warning("Disabling Postgres review/packet stores and using in-memory fallback: %s", exc)
        self._db_enabled = False
        self._review_db = None
        self._packet_db = None

    @property
    def next_trial_count(self) -> int:
        if self._db_enabled and self._review_db is not None:
            try:
                return self._review_db.count_reviews() + 1
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)
        self._trial_count += 1
        return self._trial_count

    def list_reviews(self) -> list[TradeReview]:
        if self._db_enabled and self._review_db is not None:
            try:
                return self._review_db.list_reviews()
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)
        return sorted(self._reviews.values(), key=lambda review: review.createdAt, reverse=True)

    def get_review(self, review_id: str) -> TradeReview | None:
        if self._db_enabled and self._review_db is not None:
            try:
                return self._review_db.get_review(review_id)
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)
        return self._reviews.get(review_id)

    def save_review(self, review: TradeReview) -> TradeReview:
        if self._db_enabled and self._review_db is not None:
            try:
                return self._review_db.save_review(review)
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)
        self._reviews[review.id] = review
        return review

    def record_decision(self, review_id: str, decision_state: DecisionState) -> TradeReview | None:
        if self._db_enabled and self._review_db is not None:
            try:
                return self._review_db.record_decision(review_id, decision_state)
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)

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
        if self._db_enabled and self._review_db is not None:
            try:
                return self._review_db.record_outcome(review_id, outcome.outcome, outcome.outcome_date)
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)

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

    def list_packets(
        self,
        search: str | None = None,
        ticker: str | None = None,
        decision_state: DecisionState | None = None,
    ) -> list[DecisionPacket]:
        if self._db_enabled and self._packet_db is not None:
            try:
                return self._packet_db.list_packets(
                    PacketQuery(search=search, ticker=ticker, decision_state=decision_state)
                )
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)

        packets = list(self._packets.values())
        if search:
            search_lower = search.lower()
            packets = [
                packet
                for packet in packets
                if search_lower in packet.title.lower() or search_lower in packet.thesis.lower()
            ]
        if ticker:
            ticker_lower = ticker.lower()
            packets = [packet for packet in packets if packet.ticker.lower() == ticker_lower]
        if decision_state is not None:
            packets = [packet for packet in packets if packet.decisionState == decision_state]
        return sorted(packets, key=lambda packet: packet.createdAt, reverse=True)

    def get_packet(self, packet_id: str) -> DecisionPacket | None:
        if self._db_enabled and self._packet_db is not None:
            try:
                return self._packet_db.get_packet(packet_id)
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)
        return self._packets.get(packet_id)

    def save_packet(self, packet: DecisionPacket) -> DecisionPacket:
        if self._db_enabled and self._packet_db is not None:
            try:
                return self._packet_db.save_packet(packet)
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)
        self._packets[packet.id] = packet
        return packet

    def add_packet_audit_event(
        self,
        packet_id: str,
        event: AuditEventCreate,
    ) -> DecisionPacket | None:
        if self._db_enabled and self._packet_db is not None:
            try:
                return self._packet_db.add_packet_audit_event(packet_id, event)
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)

        packet = self._packets.get(packet_id)
        if packet is None:
            return None
        updated = packet.model_copy(
            update={
                "audit": [
                    *packet.audit,
                    AuditEvent(
                        id=f"packet-audit-{len(packet.audit) + 1}",
                        timestamp=datetime.now().strftime("%H:%M:%S"),
                        eventType=event.eventType,
                        detail=event.detail,
                    ),
                ]
            }
        )
        self._packets[packet_id] = updated
        return updated

    def get_packet_audit(self, packet_id: str) -> list[AuditEvent] | None:
        if self._db_enabled and self._packet_db is not None:
            try:
                return self._packet_db.get_packet_audit(packet_id)
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)

        packet = self._packets.get(packet_id)
        if packet is None:
            return None
        return packet.audit

    def record_metric_snapshot(self, packet_id: str, metric_type: str, metric_payload: dict) -> None:
        if self._db_enabled and self._packet_db is not None:
            try:
                self._packet_db.add_metric_snapshot(packet_id, metric_type, metric_payload)
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)

    def record_packet_outcome(self, packet_id: str, outcome: str, outcome_date: str, payload: dict) -> None:
        if self._db_enabled and self._packet_db is not None:
            try:
                self._packet_db.add_outcome_record(packet_id, outcome, outcome_date, payload)
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)

    def record_retrieval_event(self, packet_id: str, query_text: str, result_count: int, payload: dict) -> None:
        if self._db_enabled and self._packet_db is not None:
            try:
                self._packet_db.add_retrieval_event(packet_id, query_text, result_count, payload)
            except Exception as exc:  # pragma: no cover - environment dependent
                self._disable_db(exc)

    def enqueue_alert(
        self,
        source: str,
        symbol: str,
        message: str,
        payload: dict[str, object],
        signature_verified: bool,
        prompt_injection_detected: bool,
    ) -> AlertQueueRecord:
        alert = AlertQueueRecord(
            id=f"alert-{uuid4().hex[:10]}",
            source=source,
            symbol=symbol,
            message=message,
            receivedAt=datetime.now().isoformat(),
            signatureVerified=signature_verified,
            promptInjectionDetected=prompt_injection_detected,
            payload=payload,
        )
        self._alerts.insert(0, alert)
        self._alerts = self._alerts[:200]
        return alert

    def list_alerts(self) -> list[AlertQueueRecord]:
        return list(self._alerts)

    def record_workflow_run(
        self,
        review_id: str | None,
        idempotency_key: str,
        status: str,
        workflow_version: str,
        error: str | None = None,
    ) -> None:
        if review_id is None or not self._db_enabled or self._review_db is None:
            return
        try:
            self._review_db.add_workflow_run(review_id, idempotency_key, status, workflow_version, error)
        except Exception as exc:  # pragma: no cover - environment dependent
            self._disable_db(exc)


store = ReviewStore()