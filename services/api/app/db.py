from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

import psycopg
from psycopg.rows import dict_row

from .models import (
    AuditEvent,
    AuditEventCreate,
    DecisionPacket,
    DecisionState,
    ReviewStatus,
    RoadmapDecisionRecord,
    RoadmapOutcomeRecord,
    RoadmapPlanRecord,
    TradeReview,
)
from .feedback import FeedbackRecord


@dataclass
class PacketQuery:
    search: str | None = None
    ticker: str | None = None
    decision_state: DecisionState | None = None


class PostgresReviewStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _review_pk(self, review_id: str) -> str:
        return str(uuid5(NAMESPACE_URL, f"ambrosia-review:{review_id}"))

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def healthcheck(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")

    def save_review(self, review: TradeReview) -> TradeReview:
        payload = review.model_dump(mode="json")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO reviews (
                        id,
                        schema_version,
                        workflow_version,
                        title,
                        thesis,
                        ticker,
                        asset_class,
                        time_horizon,
                        intended_expression,
                        decision_state,
                        confidence,
                        trial_count_impact,
                        follow_up_date,
                        artifact,
                        created_at
                    )
                    VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT (id)
                    DO UPDATE SET
                        schema_version = EXCLUDED.schema_version,
                        workflow_version = EXCLUDED.workflow_version,
                        title = EXCLUDED.title,
                        thesis = EXCLUDED.thesis,
                        ticker = EXCLUDED.ticker,
                        asset_class = EXCLUDED.asset_class,
                        time_horizon = EXCLUDED.time_horizon,
                        intended_expression = EXCLUDED.intended_expression,
                        decision_state = EXCLUDED.decision_state,
                        confidence = EXCLUDED.confidence,
                        trial_count_impact = EXCLUDED.trial_count_impact,
                        follow_up_date = EXCLUDED.follow_up_date,
                        artifact = EXCLUDED.artifact,
                        updated_at = now()
                    """,
                    (
                        self._review_pk(review.id),
                        review.schemaVersion,
                        review.workflowVersion,
                        review.title,
                        review.thesis,
                        review.ticker,
                        review.assetClass,
                        review.timeHorizon,
                        review.intendedExpression,
                        review.decisionState.value if review.decisionState else None,
                        review.confidence,
                        review.trialCountImpact,
                        review.followUpDate,
                        json.dumps(payload),
                        review.createdAt,
                    ),
                )
        return review

    def get_review(self, review_id: str) -> TradeReview | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT artifact FROM reviews WHERE id = %s::uuid", (self._review_pk(review_id),))
                row = cursor.fetchone()
        if row is None:
            return None
        return TradeReview.model_validate(row["artifact"])

    def list_reviews(self) -> list[TradeReview]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT artifact FROM reviews ORDER BY created_at DESC")
                rows = cursor.fetchall()
        return [TradeReview.model_validate(row["artifact"]) for row in rows]

    def count_reviews(self) -> int:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) AS count FROM reviews")
                row = cursor.fetchone()
        return int(row["count"] if row is not None else 0)

    def record_decision(self, review_id: str, decision_state: DecisionState) -> TradeReview | None:
        review = self.get_review(review_id)
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

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO audit_events (review_id, event_type, detail, payload)
                    VALUES (%s::uuid, %s, %s, %s::jsonb)
                    """,
                    (
                        self._review_pk(review_id),
                        "decision.recorded",
                        f"Human decision captured: {decision_state.value}",
                        json.dumps({"source": "api"}),
                    ),
                )
        return self.save_review(updated)

    def record_outcome(self, review_id: str, outcome: str, outcome_date: str) -> TradeReview | None:
        review = self.get_review(review_id)
        if review is None:
            return None

        detail = f"{outcome_date}: {outcome}"
        updated = review.model_copy(
            update={
                "audit": [
                    *review.audit,
                    AuditEvent(
                        id=f"audit-{len(review.audit) + 1}",
                        timestamp=datetime.now().strftime("%H:%M:%S"),
                        eventType="outcome.recorded",
                        detail=detail,
                    ),
                ]
            }
        )

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO audit_events (review_id, event_type, detail, payload)
                    VALUES (%s::uuid, %s, %s, %s::jsonb)
                    """,
                    (
                        self._review_pk(review_id),
                        "outcome.recorded",
                        detail,
                        json.dumps({"source": "api"}),
                    ),
                )
        return self.save_review(updated)

    def add_workflow_run(
        self,
        review_id: str,
        idempotency_key: str,
        status: str,
        workflow_version: str,
        error: str | None = None,
    ) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO workflow_runs (review_id, idempotency_key, status, workflow_version, completed_at, error)
                    VALUES (%s::uuid, %s, %s, %s, now(), %s)
                    ON CONFLICT (idempotency_key)
                    DO UPDATE SET
                        status = EXCLUDED.status,
                        workflow_version = EXCLUDED.workflow_version,
                        completed_at = EXCLUDED.completed_at,
                        error = EXCLUDED.error
                    """,
                    (
                        self._review_pk(review_id),
                        idempotency_key,
                        status,
                        workflow_version,
                        error,
                    ),
                )

    def save_roadmap_plan(self, plan: RoadmapPlanRecord) -> RoadmapPlanRecord:
        payload = plan.model_dump(mode="json")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO roadmap_plan (
                        plan_id,
                        title,
                        workstream,
                        owner,
                        quality,
                        status,
                        target_milestone,
                        artifact
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (plan_id)
                    DO UPDATE SET
                        title = EXCLUDED.title,
                        workstream = EXCLUDED.workstream,
                        owner = EXCLUDED.owner,
                        quality = EXCLUDED.quality,
                        status = EXCLUDED.status,
                        target_milestone = EXCLUDED.target_milestone,
                        artifact = EXCLUDED.artifact,
                        updated_at = now()
                    """,
                    (
                        plan.plan_id,
                        plan.title,
                        plan.workstream,
                        plan.owner,
                        plan.quality,
                        plan.status,
                        plan.target_milestone,
                        json.dumps(payload),
                    ),
                )
        return plan

    def list_roadmap_plans(self) -> list[RoadmapPlanRecord]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT artifact FROM roadmap_plan ORDER BY plan_id")
                rows = cursor.fetchall()
        return [RoadmapPlanRecord.model_validate(row["artifact"]) for row in rows]

    def get_roadmap_plan(self, plan_id: str) -> RoadmapPlanRecord | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT artifact FROM roadmap_plan WHERE plan_id = %s", (plan_id,))
                row = cursor.fetchone()
        if row is None:
            return None
        return RoadmapPlanRecord.model_validate(row["artifact"])

    def save_roadmap_decision(
        self,
        plan_id: str,
        decision: RoadmapDecisionRecord,
    ) -> RoadmapPlanRecord | None:
        plan = self.get_roadmap_plan(plan_id)
        if plan is None:
            return None

        decisions = [item for item in plan.decisions if item.decision_id != decision.decision_id]
        updated = plan.model_copy(update={"decisions": [*decisions, decision]})
        payload = decision.model_dump(mode="json")

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO roadmap_decision (decision_id, plan_id, decision_type, quality, artifact)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (decision_id)
                    DO UPDATE SET
                        plan_id = EXCLUDED.plan_id,
                        decision_type = EXCLUDED.decision_type,
                        quality = EXCLUDED.quality,
                        artifact = EXCLUDED.artifact
                    """,
                    (
                        decision.decision_id,
                        plan_id,
                        decision.decision_type,
                        decision.quality,
                        json.dumps(payload),
                    ),
                )
        return self.save_roadmap_plan(updated)

    def save_roadmap_outcome(
        self,
        decision_id: str,
        outcome: RoadmapOutcomeRecord,
    ) -> RoadmapPlanRecord | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT plan_id FROM roadmap_decision WHERE decision_id = %s",
                    (decision_id,),
                )
                row = cursor.fetchone()
        if row is None:
            return None

        plan_id = row["plan_id"]
        plan = self.get_roadmap_plan(plan_id)
        if plan is None:
            return None

        outcomes = [item for item in plan.outcomes if item.outcome_id != outcome.outcome_id]
        updated = plan.model_copy(update={"outcomes": [*outcomes, outcome]})
        payload = outcome.model_dump(mode="json")

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO roadmap_outcome (outcome_id, decision_id, quality, artifact)
                    VALUES (%s, %s, %s, %s::jsonb)
                    ON CONFLICT (outcome_id)
                    DO UPDATE SET
                        decision_id = EXCLUDED.decision_id,
                        quality = EXCLUDED.quality,
                        artifact = EXCLUDED.artifact
                    """,
                    (
                        outcome.outcome_id,
                        decision_id,
                        outcome.quality,
                        json.dumps(payload),
                    ),
                )
        return self.save_roadmap_plan(updated)

    def save_feedback_record(self, feedback: FeedbackRecord) -> FeedbackRecord:
        payload = feedback.model_dump(mode="json")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO feedback_record_store (
                        feedback_id,
                        packet_id,
                        ticker,
                        asset_class,
                        time_horizon,
                        decision_state,
                        confidence,
                        outcome,
                        outcome_date,
                        pnl,
                        artifact
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (feedback_id)
                    DO UPDATE SET
                        decision_state = EXCLUDED.decision_state,
                        confidence = EXCLUDED.confidence,
                        outcome = EXCLUDED.outcome,
                        outcome_date = EXCLUDED.outcome_date,
                        pnl = EXCLUDED.pnl,
                        artifact = EXCLUDED.artifact,
                        updated_at = now()
                    """,
                    (
                        feedback.id,
                        feedback.packet_id,
                        feedback.ticker,
                        feedback.asset_class,
                        feedback.time_horizon,
                        feedback.decision_state,
                        feedback.confidence,
                        feedback.outcome.value,
                        feedback.outcome_date,
                        feedback.pnl,
                        json.dumps(payload),
                    ),
                )
        return feedback

    def get_feedback_record(self, feedback_id: str) -> FeedbackRecord | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT artifact FROM feedback_record_store WHERE feedback_id = %s",
                    (feedback_id,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return FeedbackRecord.model_validate(row["artifact"])

    def list_feedback_records(
        self,
        ticker: str | None = None,
        decision_state: str | None = None,
        outcome: str | None = None,
        limit: int = 100,
    ) -> list[FeedbackRecord]:
        where_clauses: list[str] = []
        params: list[object] = []
        if ticker:
            where_clauses.append("LOWER(ticker) = LOWER(%s)")
            params.append(ticker)
        if decision_state:
            where_clauses.append("LOWER(decision_state) = LOWER(%s)")
            params.append(decision_state)
        if outcome:
            where_clauses.append("LOWER(outcome) = LOWER(%s)")
            params.append(outcome)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        sql = f"""
            SELECT artifact
            FROM feedback_record_store
            {where_sql}
            ORDER BY created_at DESC
            LIMIT %s
        """
        params.append(limit)

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()
        return [FeedbackRecord.model_validate(row["artifact"]) for row in rows]

    def save_signal_lifecycle_snapshot(self, snapshot: dict) -> None:
        payload = json.dumps(snapshot)
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO signal_lifecycle_snapshot (snapshot_key, artifact)
                    VALUES ('default', %s::jsonb)
                    ON CONFLICT (snapshot_key)
                    DO UPDATE SET artifact = EXCLUDED.artifact, updated_at = now()
                    """,
                    (payload,),
                )

    def load_signal_lifecycle_snapshot(self) -> dict | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT artifact FROM signal_lifecycle_snapshot WHERE snapshot_key = 'default'"
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return row["artifact"]

    def save_relay_run(self, run: dict) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO relay_run (relay_run_id, benchmark, question, route, trace)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (relay_run_id)
                    DO UPDATE SET trace = EXCLUDED.trace, route = EXCLUDED.route
                    """,
                    (
                        run.get("runId"),
                        run.get("benchmark", "unknown"),
                        run.get("question", ""),
                        run.get("route", "unknown"),
                        json.dumps(run),
                    ),
                )

    def get_relay_run(self, run_id: str) -> dict | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT trace FROM relay_run WHERE relay_run_id = %s", (run_id,))
                row = cursor.fetchone()
        if row is None:
            return None
        return row["trace"]

    def list_relay_runs(self, limit: int = 250) -> list[dict]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT trace FROM relay_run ORDER BY created_at DESC LIMIT %s",
                    (limit,),
                )
                rows = cursor.fetchall()
        return [row["trace"] for row in rows]

    def save_idempotency_response(self, key: str, endpoint: str, response_payload: dict) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO api_idempotency_record (idempotency_key, endpoint, response_payload)
                    VALUES (%s, %s, %s::jsonb)
                    ON CONFLICT (idempotency_key)
                    DO UPDATE SET endpoint = EXCLUDED.endpoint, response_payload = EXCLUDED.response_payload, updated_at = now()
                    """,
                    (key, endpoint, json.dumps(response_payload)),
                )

    def get_idempotency_response(self, key: str, endpoint: str) -> dict | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT response_payload FROM api_idempotency_record WHERE idempotency_key = %s AND endpoint = %s",
                    (key, endpoint),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return row["response_payload"]


class PostgresPacketStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self.database_url, row_factory=dict_row)

    def healthcheck(self) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")

    def save_packet(self, packet: DecisionPacket) -> DecisionPacket:
        payload = packet.model_dump(mode="json")
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO review_packet (
                        packet_id,
                        schema_version,
                        workflow_version,
                        ticker,
                        decision_state,
                        confidence,
                        created_at,
                        artifact
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (packet_id)
                    DO UPDATE SET
                        schema_version = EXCLUDED.schema_version,
                        workflow_version = EXCLUDED.workflow_version,
                        ticker = EXCLUDED.ticker,
                        decision_state = EXCLUDED.decision_state,
                        confidence = EXCLUDED.confidence,
                        artifact = EXCLUDED.artifact,
                        updated_at = now()
                    """,
                    (
                        packet.id,
                        packet.schemaVersion,
                        packet.workflowVersion,
                        packet.ticker,
                        packet.decisionState.value if packet.decisionState else None,
                        packet.confidence,
                        packet.createdAt,
                        json.dumps(payload),
                    ),
                )
        return packet

    def get_packet(self, packet_id: str) -> DecisionPacket | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT artifact FROM review_packet WHERE packet_id = %s",
                    (packet_id,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return DecisionPacket.model_validate(row["artifact"])

    def list_packets(self, query: PacketQuery) -> list[DecisionPacket]:
        where_clauses: list[str] = []
        params: list[object] = []

        if query.search:
            where_clauses.append("(artifact->>'title' ILIKE %s OR artifact->>'thesis' ILIKE %s)")
            search_like = f"%{query.search}%"
            params.extend([search_like, search_like])
        if query.ticker:
            where_clauses.append("LOWER(ticker) = LOWER(%s)")
            params.append(query.ticker)
        if query.decision_state is not None:
            where_clauses.append("decision_state = %s")
            params.append(query.decision_state.value)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        sql = f"""
            SELECT artifact
            FROM review_packet
            {where_sql}
            ORDER BY created_at DESC
        """

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(sql, params)
                rows = cursor.fetchall()

        return [DecisionPacket.model_validate(row["artifact"]) for row in rows]

    def add_packet_audit_event(self, packet_id: str, event: AuditEventCreate) -> DecisionPacket | None:
        packet = self.get_packet(packet_id)
        if packet is None:
            return None

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO decision_audit (packet_id, event_type, detail, payload)
                    VALUES (%s, %s, %s, %s::jsonb)
                    """,
                    (
                        packet_id,
                        event.eventType,
                        event.detail,
                        json.dumps({"source": "api"}),
                    ),
                )

        packet.audit.append(
            AuditEvent(
                id=f"packet-audit-{len(packet.audit) + 1}",
                timestamp="db_event",
                eventType=event.eventType,
                detail=event.detail,
            )
        )
        return self.save_packet(packet)

    def get_packet_audit(self, packet_id: str) -> list[AuditEvent] | None:
        packet = self.get_packet(packet_id)
        if packet is None:
            return None
        return packet.audit

    def add_metric_snapshot(self, packet_id: str, metric_type: str, metric_payload: dict) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO metric_snapshot (packet_id, metric_type, metric_payload)
                    VALUES (%s, %s, %s::jsonb)
                    """,
                    (packet_id, metric_type, json.dumps(metric_payload)),
                )

    def add_outcome_record(self, packet_id: str, outcome: str, outcome_date: str, payload: dict) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO outcome_record (packet_id, outcome, outcome_date, payload)
                    VALUES (%s, %s, %s, %s::jsonb)
                    """,
                    (packet_id, outcome, outcome_date, json.dumps(payload)),
                )

    def add_retrieval_event(self, packet_id: str, query_text: str, result_count: int, payload: dict) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO retrieval_event (packet_id, source_type, source_ref, confidence, payload)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        packet_id,
                        "hybrid_query",
                        query_text,
                        float(result_count),
                        json.dumps({"query": query_text, "resultCount": result_count, **payload}),
                    ),
                )
