from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.llm_catalog import Catalog, LlmJobCreate, WorkerResult
from app.db import PostgresReviewStore
from app.models import JobRecord, JobState
from app.tenant_context import (
    LEGACY_QUARANTINE_ORGANIZATION_ID,
    reset_organization_id,
    set_organization_id,
)


DATABASE_URL = os.getenv("INDEX119_TEST_DATABASE_URL")
if DATABASE_URL:
    os.environ.setdefault("DATABASE_URL", DATABASE_URL)
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="INDEX119_TEST_DATABASE_URL not configured")


def _llm_job() -> LlmJobCreate:
    return LlmJobCreate(
        thesis="Revenue acceleration supports a re-rating over the next year.",
        claims=["Revenue growth will exceed consensus."],
        evidence=[{"id": "source-1", "title": "Dated filing"}],
        observationCutoff=datetime(2026, 8, 7, tzinfo=UTC),
    )


def _llm_result(*, lease_id: str, generation: int) -> WorkerResult:
    started = datetime.now(UTC)
    return WorkerResult(
        leaseId=lease_id,
        generation=generation,
        modelName="llama3.1:8b",
        modelDigest="sha256:fixed-model",
        ollamaVersion="0.11.4",
        startedAt=started,
        completedAt=started,
        parameters={"temperature": 0},
        output={
            "summary": "The supplied evidence does not independently establish the forecast.",
            "claimsTested": ["Revenue growth will exceed consensus."],
            "falsifiableConditions": ["Quarterly growth falls below consensus."],
            "alternativeExplanations": ["Temporary pricing effects."],
            "contradictions": [],
            "missingEvidence": ["Independent demand data."],
            "evidenceReferences": ["source-1"],
            "abstained": False,
        },
    )


def test_durable_job_claim_idempotency_completion_and_recovery() -> None:
    tenant_token = set_organization_id(LEGACY_QUARANTINE_ORGANIZATION_ID)
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
        try:
            with database._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "DELETE FROM durable_job WHERE idempotency_key = %s",
                        (job.idempotencyKey,),
                    )
        finally:
            reset_organization_id(tenant_token)


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


def test_durable_llm_completion_rejects_stale_reclaimed_lease() -> None:
    tenant_token = set_organization_id(LEGACY_QUARANTINE_ORGANIZATION_ID)
    catalog = Catalog()
    worker_id = None
    job_id = None
    user_id = str(uuid4())
    try:
        with catalog._connect(tenant=False) as connection:
            connection.execute(
                """
                INSERT INTO users (
                  id, email, email_canonical, display_name, password_hash,
                  status, terms_version, privacy_version, terms_accepted_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    f"index119-{user_id}@example.com",
                    f"index119-{user_id}@example.com",
                    "Index119 durable user",
                    "password-hash",
                    "active",
                    "v1",
                    "v1",
                    datetime.now(UTC),
                ),
            )
        credential = catalog.create_worker(
            LEGACY_QUARANTINE_ORGANIZATION_ID,
            user_id,
            f"Index119 worker {uuid4().hex[:8]}",
        )
        worker_id = credential["id"]
        worker = catalog.authenticate_worker(credential["token"])
        assert worker is not None

        queued = catalog.enqueue(LEGACY_QUARANTINE_ORGANIZATION_ID, _llm_job())
        job_id = queued["id"]
        first = catalog.claim(worker, 30)
        assert first is not None
        assert first["generation"] == 1

        with catalog._connect(tenant=False) as connection:
            catalog._set_worker_tenant(connection, worker)
            connection.execute(
                "UPDATE llm_jobs SET lease_expires_at=now()-interval '1 second' WHERE id=%s",
                (job_id,),
            )

        second = catalog.claim(worker, 30)
        assert second is not None
        assert second["id"] == job_id
        assert second["generation"] == 2
        assert second["leaseId"] != first["leaseId"]

        stale = catalog.complete(
            worker,
            job_id,
            _llm_result(lease_id=first["leaseId"], generation=first["generation"]),
        )
        assert stale is None

        accepted = catalog.complete(
            worker,
            job_id,
            _llm_result(lease_id=second["leaseId"], generation=second["generation"]),
        )
        assert accepted is not None
        assert accepted["verificationStatus"] == "passed"

        with catalog._connect(tenant=False) as connection:
            catalog._set_worker_tenant(connection, worker)
            attempts = connection.execute(
                "SELECT lease_generation FROM llm_job_attempts WHERE job_id=%s ORDER BY attempt_number",
                (job_id,),
            ).fetchall()
            assert [row["lease_generation"] for row in attempts] == [1, 2]
    finally:
        try:
            with catalog._connect(tenant=False) as connection:
                connection.execute(
                    "DELETE FROM llm_evaluations WHERE run_id IN (SELECT id FROM llm_runs WHERE job_id=%s)",
                    (job_id,),
                )
                connection.execute("DELETE FROM llm_runs WHERE job_id=%s", (job_id,))
                connection.execute("DELETE FROM llm_job_attempts WHERE job_id=%s", (job_id,))
                connection.execute("DELETE FROM llm_jobs WHERE id=%s", (job_id,))
                connection.execute(
                    "DELETE FROM local_worker_credentials WHERE id=%s",
                    (worker_id,),
                )
                connection.execute("DELETE FROM users WHERE id=%s", (user_id,))
        finally:
            reset_organization_id(tenant_token)
