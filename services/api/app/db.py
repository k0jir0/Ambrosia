from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid5

import psycopg
from psycopg.rows import dict_row

from .models import (
    AuditEvent,
    AuditEventCreate,
    DecisionMemoryRecord,
    DecisionPacket,
    DecisionState,
    JobRecord,
    JobState,
    PacketAuditChainEvent,
    ReviewStatus,
    RoadmapDecisionRecord,
    RoadmapOutcomeRecord,
    RoadmapPlanRecord,
    TradeReview,
)
from .feedback import FeedbackRecord
from .selective_integration import create_packet_audit_event, packet_content_hash


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

    @staticmethod
    def _job_from_row(row: dict) -> JobRecord:
        return JobRecord(
            id=row["id"],
            jobType=row["job_type"],
            state=JobState(row["state"]),
            queuedAt=row["queued_at"].isoformat(),
            startedAt=row["started_at"].isoformat() if row.get("started_at") else None,
            completedAt=row["completed_at"].isoformat() if row.get("completed_at") else None,
            inputSummary=row["input_summary"],
            idempotencyKey=row.get("idempotency_key"),
            attempt=row["attempt"],
            maxAttempts=row["max_attempts"],
            timeoutSeconds=row["timeout_seconds"],
            cancelRequested=row["cancel_requested"],
            result=row.get("result"),
            error=row.get("error"),
        )

    def enqueue_job(self, job: JobRecord) -> JobRecord:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                if job.idempotencyKey:
                    cursor.execute(
                        """
                        INSERT INTO durable_job (
                          id, job_type, idempotency_key, state, input_summary,
                          max_attempts, timeout_seconds, queued_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (job_type, idempotency_key)
                        DO UPDATE SET job_type = EXCLUDED.job_type
                        RETURNING *
                        """,
                        (job.id, job.jobType, job.idempotencyKey, job.state.value,
                         job.inputSummary, job.maxAttempts, job.timeoutSeconds, job.queuedAt),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO durable_job (
                          id, job_type, state, input_summary, max_attempts,
                          timeout_seconds, queued_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING *
                        """,
                        (job.id, job.jobType, job.state.value, job.inputSummary,
                         job.maxAttempts, job.timeoutSeconds, job.queuedAt),
                    )
                row = cursor.fetchone()
        return self._job_from_row(row)

    def claim_job(self, job_id: str, worker_id: str, lease_seconds: int = 300) -> JobRecord | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE durable_job
                    SET state = 'running', started_at = COALESCE(started_at, now()),
                        attempt = attempt + 1, lease_owner = %s,
                        lease_expires_at = now() + (%s * interval '1 second')
                    WHERE id = %s AND state = 'queued' AND cancel_requested = FALSE
                      AND attempt < max_attempts
                    RETURNING *
                    """,
                    (worker_id, lease_seconds, job_id),
                )
                row = cursor.fetchone()
        return self._job_from_row(row) if row else None

    def finish_job(self, job_id: str, *, result: dict | None = None,
                   error: str | None = None) -> JobRecord | None:
        state = "completed" if error is None else "failed"
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE durable_job
                    SET state = %s, result = %s::jsonb, error = %s,
                        completed_at = now(), lease_owner = NULL, lease_expires_at = NULL
                    WHERE id = %s AND state = 'running'
                    RETURNING *
                    """,
                    (state, json.dumps(result) if result is not None else None, error, job_id),
                )
                row = cursor.fetchone()
        return self._job_from_row(row) if row else None

    def get_job(self, job_id: str) -> JobRecord | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM durable_job WHERE id = %s", (job_id,))
                row = cursor.fetchone()
        return self._job_from_row(row) if row else None

    def list_jobs(self, job_type: str | None = None) -> list[JobRecord]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                if job_type:
                    cursor.execute(
                        "SELECT * FROM durable_job WHERE job_type = %s ORDER BY queued_at DESC",
                        (job_type,),
                    )
                else:
                    cursor.execute("SELECT * FROM durable_job ORDER BY queued_at DESC LIMIT 1000")
                rows = cursor.fetchall()
        return [self._job_from_row(row) for row in rows]

    def cancel_job(self, job_id: str) -> JobRecord | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE durable_job SET cancel_requested = TRUE,
                      state = CASE WHEN state = 'queued' THEN 'cancelled' ELSE state END,
                      completed_at = CASE WHEN state = 'queued' THEN now() ELSE completed_at END
                    WHERE id = %s RETURNING *
                    """,
                    (job_id,),
                )
                row = cursor.fetchone()
        return self._job_from_row(row) if row else None

    def requeue_expired_jobs(self) -> int:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE durable_job SET state = 'queued', lease_owner = NULL,
                      lease_expires_at = NULL
                    WHERE state = 'running' AND lease_expires_at < now()
                      AND attempt < max_attempts AND cancel_requested = FALSE
                    """
                )
                return cursor.rowcount

    def append_security_audit(
        self,
        *,
        request_id: str,
        actor: str,
        role: str,
        action: str,
        resource: str,
        status: int,
    ) -> None:
        """Append one globally ordered hash-chain event under a DB advisory lock."""
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(hashtext('ambrosia-security-audit'))")
                cursor.execute(
                    "SELECT sequence_id, event_hash FROM security_audit_event "
                    "ORDER BY sequence_id DESC LIMIT 1"
                )
                previous = cursor.fetchone()
                sequence = int(previous["sequence_id"]) + 1 if previous else 1
                previous_hash = previous["event_hash"] if previous else "0" * 64
                timestamp = datetime.now(UTC)
                payload = {
                    "sequence": sequence,
                    "timestamp": timestamp.isoformat(),
                    "request_id": request_id,
                    "actor": actor,
                    "role": role,
                    "action": action,
                    "resource": resource,
                    "status": status,
                    "previous_hash": previous_hash,
                }
                event_hash = hashlib.sha256(
                    json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
                cursor.execute(
                    """
                    INSERT INTO security_audit_event (
                      sequence_id, event_time, request_id, actor_id, actor_role,
                      action, resource, response_status, previous_hash, event_hash
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (sequence, timestamp, request_id, actor, role, action, resource,
                     status, previous_hash, event_hash),
                )

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

    def _save_packet_with_cursor(self, cursor, packet: DecisionPacket) -> None:
        payload = packet.model_dump(mode="json")
        content_hash = packet_content_hash(packet)
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
        cursor.execute(
            """
            INSERT INTO packet_version (
                packet_id,
                packet_version,
                schema_version,
                contract_version,
                content_hash,
                artifact
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (packet_id, packet_version) DO NOTHING
            """,
            (
                packet.id,
                packet.packetVersion,
                packet.schemaVersion,
                packet.contractVersion,
                content_hash,
                json.dumps(payload),
            ),
        )

    def save_packet(self, packet: DecisionPacket) -> DecisionPacket:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                self._save_packet_with_cursor(cursor, packet)
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

    def _add_outcome_record_with_cursor(
        self,
        cursor,
        packet_id: str,
        outcome: str,
        outcome_date: str,
        payload: dict,
    ) -> None:
        cursor.execute(
            """
            INSERT INTO outcome_record (packet_id, outcome, outcome_date, payload)
            VALUES (%s, %s, %s, %s::jsonb)
            """,
            (packet_id, outcome, outcome_date, json.dumps(payload)),
        )

    def add_outcome_record(self, packet_id: str, outcome: str, outcome_date: str, payload: dict) -> None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                self._add_outcome_record_with_cursor(
                    cursor,
                    packet_id,
                    outcome,
                    outcome_date,
                    payload,
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

    def _append_packet_memory_with_cursor(self, cursor, memory: DecisionMemoryRecord) -> None:
        payload = memory.model_dump(mode="json")
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))",
            (f"ambrosia-packet-memory:{memory.packetId}",),
        )
        cursor.execute(
            "SELECT sequence_id, event_hash FROM decision_memory_record "
            "WHERE packet_id = %s ORDER BY sequence_id DESC LIMIT 1",
            (memory.packetId,),
        )
        previous = cursor.fetchone()
        expected_sequence = int(previous["sequence_id"]) + 1 if previous else 1
        expected_previous_hash = previous["event_hash"] if previous else "0" * 64
        if memory.sequence != expected_sequence or memory.previousHash != expected_previous_hash:
            raise ValueError("decision memory hash-chain position is stale")
        cursor.execute(
            """
            INSERT INTO decision_memory_record (
                memory_id,
                packet_id,
                packet_version,
                record_type,
                outcome,
                score,
                sequence_id,
                observed_at,
                previous_hash,
                event_hash,
                artifact
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                memory.memoryId,
                memory.packetId,
                memory.packetVersion,
                memory.recordType,
                memory.outcome,
                memory.score,
                memory.sequence,
                memory.observedAt,
                memory.previousHash,
                memory.eventHash,
                json.dumps(payload),
            ),
        )

    def append_packet_memory(self, memory: DecisionMemoryRecord) -> DecisionMemoryRecord:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                self._append_packet_memory_with_cursor(cursor, memory)
        return memory

    def get_packet_memory(self, packet_id: str) -> list[DecisionMemoryRecord]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT artifact FROM decision_memory_record "
                    "WHERE packet_id = %s ORDER BY sequence_id",
                    (packet_id,),
                )
                rows = cursor.fetchall()
        return [DecisionMemoryRecord.model_validate(row["artifact"]) for row in rows]

    def list_decision_memories(self, limit: int = 500) -> list[DecisionMemoryRecord]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT artifact FROM decision_memory_record "
                    "ORDER BY created_at DESC LIMIT %s",
                    (limit,),
                )
                rows = cursor.fetchall()
        return [DecisionMemoryRecord.model_validate(row["artifact"]) for row in rows]

    def _append_packet_audit_chain_event_with_cursor(
        self,
        cursor,
        packet: DecisionPacket,
        *,
        event_type: str,
        detail: str,
        actor: str = "system",
    ) -> PacketAuditChainEvent:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))",
            (f"ambrosia-packet-audit:{packet.id}",),
        )
        cursor.execute(
            "SELECT * FROM packet_audit_chain WHERE packet_id = %s "
            "ORDER BY sequence_id DESC LIMIT 1",
            (packet.id,),
        )
        row = cursor.fetchone()
        previous = None
        if row is not None:
            previous = PacketAuditChainEvent(
                sequence=row["sequence_id"],
                packetId=row["packet_id"],
                packetVersion=row["packet_version"],
                eventType=row["event_type"],
                detail=row["detail"],
                actor=row["actor_id"],
                createdAt=row["event_time"].isoformat().replace("+00:00", "Z"),
                payloadHash=row["payload_hash"],
                previousHash=row["previous_hash"],
                eventHash=row["event_hash"],
            )
        event = create_packet_audit_event(
            packet,
            event_type=event_type,
            detail=detail,
            actor=actor,
            previous_event=previous,
        )
        cursor.execute(
            """
            INSERT INTO packet_audit_chain (
                packet_id,
                sequence_id,
                packet_version,
                event_type,
                detail,
                actor_id,
                event_time,
                payload_hash,
                previous_hash,
                event_hash
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                event.packetId,
                event.sequence,
                event.packetVersion,
                event.eventType,
                event.detail,
                event.actor,
                event.createdAt,
                event.payloadHash,
                event.previousHash,
                event.eventHash,
            ),
        )
        cursor.execute(
            """
            INSERT INTO packet_audit_head (packet_id, last_sequence, last_event_hash)
            VALUES (%s, %s, %s)
            ON CONFLICT (packet_id)
            DO UPDATE SET
              last_sequence = EXCLUDED.last_sequence,
              last_event_hash = EXCLUDED.last_event_hash,
              updated_at = now()
            """,
            (event.packetId, event.sequence, event.eventHash),
        )
        return event

    def append_packet_audit_chain_event(
        self,
        packet: DecisionPacket,
        *,
        event_type: str,
        detail: str,
        actor: str = "system",
    ) -> PacketAuditChainEvent:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                return self._append_packet_audit_chain_event_with_cursor(
                    cursor,
                    packet,
                    event_type=event_type,
                    detail=detail,
                    actor=actor,
                )

    def commit_packet_transition(
        self,
        packet: DecisionPacket,
        *,
        event_type: str,
        detail: str,
        actor: str = "system",
        outcome_record: tuple[str, str, dict] | None = None,
    ) -> PacketAuditChainEvent:
        """Persist a packet transition, optional outcome, and chain event atomically."""
        with self._connect() as connection:
            with connection.cursor() as cursor:
                self._save_packet_with_cursor(cursor, packet)
                if outcome_record is not None:
                    outcome, outcome_date, payload = outcome_record
                    self._add_outcome_record_with_cursor(
                        cursor,
                        packet.id,
                        outcome,
                        outcome_date,
                        payload,
                    )
                return self._append_packet_audit_chain_event_with_cursor(
                    cursor,
                    packet,
                    event_type=event_type,
                    detail=detail,
                    actor=actor,
                )

    def commit_selective_integration(
        self,
        packet: DecisionPacket,
        memory: DecisionMemoryRecord,
        *,
        event_type: str,
        detail: str,
        actor: str = "system",
        outcome_record: tuple[str, str, dict] | None = None,
    ) -> PacketAuditChainEvent:
        """Persist the packet, memory checkpoint, and audit event atomically."""
        with self._connect() as connection:
            with connection.cursor() as cursor:
                self._save_packet_with_cursor(cursor, packet)
                self._append_packet_memory_with_cursor(cursor, memory)
                if outcome_record is not None:
                    outcome, outcome_date, payload = outcome_record
                    self._add_outcome_record_with_cursor(
                        cursor,
                        packet.id,
                        outcome,
                        outcome_date,
                        payload,
                    )
                return self._append_packet_audit_chain_event_with_cursor(
                    cursor,
                    packet,
                    event_type=event_type,
                    detail=detail,
                    actor=actor,
                )

    def get_packet_audit_chain(self, packet_id: str) -> list[PacketAuditChainEvent]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM packet_audit_chain WHERE packet_id = %s ORDER BY sequence_id",
                    (packet_id,),
                )
                rows = cursor.fetchall()
        return [
            PacketAuditChainEvent(
                sequence=row["sequence_id"],
                packetId=row["packet_id"],
                packetVersion=row["packet_version"],
                eventType=row["event_type"],
                detail=row["detail"],
                actor=row["actor_id"],
                createdAt=row["event_time"].isoformat().replace("+00:00", "Z"),
                payloadHash=row["payload_hash"],
                previousHash=row["previous_hash"],
                eventHash=row["event_hash"],
            )
            for row in rows
        ]

    def get_packet_audit_head(self, packet_id: str) -> tuple[int, str] | None:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT last_sequence, last_event_hash FROM packet_audit_head WHERE packet_id = %s",
                    (packet_id,),
                )
                row = cursor.fetchone()
        if row is None:
            return None
        return int(row["last_sequence"]), str(row["last_event_hash"])

    def list_packet_versions(self, packet_id: str) -> list[DecisionPacket]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT artifact FROM packet_version WHERE packet_id = %s ORDER BY packet_version",
                    (packet_id,),
                )
                rows = cursor.fetchall()
        return [DecisionPacket.model_validate(row["artifact"]) for row in rows]
