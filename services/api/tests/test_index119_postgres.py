from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.db import PostgresReviewStore
from app.models import JobRecord, JobState


DATABASE_URL = os.getenv("INDEX119_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="INDEX119_TEST_DATABASE_URL not configured")


def test_durable_job_claim_idempotency_completion_and_recovery() -> None:
    database = PostgresReviewStore(DATABASE_URL or "")
    suffix = uuid4().hex
    job = JobRecord(
        id=f"job-{suffix}", jobType="index119.test", state=JobState.queued,
        queuedAt=datetime.now(UTC).isoformat(), inputSummary="durability probe",
        idempotencyKey=f"idem-{suffix}", timeoutSeconds=30,
    )
    try:
        saved = database.enqueue_job(job)
        duplicate = database.enqueue_job(job.model_copy(update={"id": f"job-other-{suffix}"}))
        assert duplicate.id == saved.id
        assert database.claim_job(saved.id, "worker-a", 30) is not None
        assert database.claim_job(saved.id, "worker-b", 30) is None
        completed = database.finish_job(saved.id, result={"verified": True})
        assert completed is not None
        assert completed.state == JobState.completed
        assert completed.result == {"verified": True}
    finally:
        with database._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM durable_job WHERE idempotency_key = %s", (job.idempotencyKey,))


def test_security_audit_is_globally_hash_chained() -> None:
    database = PostgresReviewStore(DATABASE_URL or "")
    request_id = f"index119-{uuid4().hex}"
    database.append_security_audit(
        request_id=request_id, actor="integration-test", role="service",
        action="POST", resource="/integration", status=200,
    )
    with database._connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT previous_hash, event_hash FROM security_audit_event WHERE request_id = %s",
                (request_id,),
            )
            row = cursor.fetchone()
            assert row is not None
            assert len(row["previous_hash"]) == 64
            assert len(row["event_hash"]) == 64
