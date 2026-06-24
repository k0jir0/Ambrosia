from __future__ import annotations

import logging
import os
from datetime import datetime

from .models import (
    AuditEvent,
    AuditEventCreate,
    DecisionPacket,
    DecisionState,
    OutcomeUpdate,
    ReviewStatus,
    TradeReview,
)
from .db import PacketQuery, PostgresPacketStore

logger = logging.getLogger(__name__)


class ReviewStore:
    def __init__(self) -> None:
        self._reviews: dict[str, TradeReview] = {}
        self._packets: dict[str, DecisionPacket] = {}
        self._trial_count = 0
        self._db_enabled = False
        self._packet_db: PostgresPacketStore | None = None

        database_url = os.getenv("DATABASE_URL")
        if database_url:
            try:
                packet_db = PostgresPacketStore(database_url)
                packet_db.healthcheck()
                self._packet_db = packet_db
                self._db_enabled = True
            except Exception as exc:  # pragma: no cover - environment dependent
                logger.warning("Falling back to in-memory packet store: %s", exc)

    def _disable_db(self, exc: Exception) -> None:
        if self._db_enabled:
            logger.warning("Disabling Postgres packet store and using in-memory fallback: %s", exc)
        self._db_enabled = False
        self._packet_db = None

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


store = ReviewStore()