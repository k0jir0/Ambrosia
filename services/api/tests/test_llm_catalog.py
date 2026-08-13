from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.llm_catalog import (
    Catalog,
    HumanReviewCreate,
    LlmJobCreate,
    WorkerResult,
    WorkerClaim,
    LeaseUpdate,
    WorkerFailure,
    canonical_hash,
)


def _job(*, evidence_id: str = "source-1") -> LlmJobCreate:
    return LlmJobCreate(
        thesis="Revenue acceleration supports a re-rating over the next year.",
        claims=["Revenue growth will exceed consensus."],
        evidence=[{"id": evidence_id, "title": "Dated filing"}],
        observationCutoff=datetime(2026, 8, 7, tzinfo=UTC),
    )


def _result(*, reference: str = "source-1", abstained: bool = False) -> WorkerResult:
    started = datetime.now(UTC)
    return WorkerResult(
        modelName="llama3.1:8b",
        modelDigest="sha256:fixed-model",
        ollamaVersion="0.11.4",
        startedAt=started,
        completedAt=started + timedelta(seconds=2),
        parameters={"temperature": 0},
        output={
            "summary": "The supplied evidence does not independently establish the forecast.",
            "claimsTested": ["Revenue growth will exceed consensus."],
            "falsifiableConditions": ["Quarterly growth falls below consensus."],
            "alternativeExplanations": ["Temporary pricing effects."],
            "contradictions": [],
            "missingEvidence": ["Independent demand data."],
            "evidenceReferences": [] if abstained else [reference],
            "abstained": abstained,
        },
    )


def test_governed_input_artifact_is_loaded_and_hash_verified(monkeypatch) -> None:
    pack = {
        "evidence": [{"id": "source-artifact", "title": "Governed filing"}],
        "tickerIdentity": {"canonical": "AAPL"},
        "observationCutoff": "2026-08-07T00:00:00+00:00",
    }
    monkeypatch.setattr("app.llm_catalog.artifact_store.load_json", lambda _: pack)
    payload = {
        "inputArtifactId": "artifact-1",
        "inputArtifactHash": canonical_hash(pack),
        "evidence": [],
    }

    resolved = Catalog.resolved_input(payload)
    assert resolved["evidence"] == pack["evidence"]
    assert resolved["tickerIdentity"] == pack["tickerIdentity"]

    payload["inputArtifactHash"] = "0" * 64
    with pytest.raises(ValueError, match="hash mismatch"):
        Catalog.resolved_input(payload)


def test_worker_result_rejects_excessive_json_depth() -> None:
    result = _result().model_dump(mode="json")
    nested: dict = {}
    cursor = nested
    for _ in range(40):
        cursor["child"] = {}
        cursor = cursor["child"]
    result["output"]["confidence"] = nested

    with pytest.raises(ValidationError, match="maximum JSON depth"):
        WorkerResult.model_validate(result)


def test_worker_queue_is_tenant_scoped_and_credentials_can_be_revoked(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    catalog = Catalog()
    first = catalog.create_worker("org-a", "user-a", "Analyst laptop")
    second = catalog.create_worker("org-b", "user-b", "Research workstation")
    catalog.enqueue("org-a", _job())
    catalog.enqueue("org-b", _job(evidence_id="source-b"))

    worker_a = catalog.authenticate_worker(first["token"])
    worker_b = catalog.authenticate_worker(second["token"])
    assert worker_a and worker_b
    claimed_a = catalog.claim(worker_a, 120)
    claimed_b = catalog.claim(worker_b, 120)
    assert claimed_a and claimed_b
    assert claimed_a["input"]["evidence"][0]["id"] == "source-1"
    assert claimed_b["input"]["evidence"][0]["id"] == "source-b"

    assert not catalog.revoke_worker("org-b", first["id"])
    assert catalog.revoke_worker("org-a", first["id"])
    assert catalog.authenticate_worker(first["token"]) is None


def test_completion_catalogues_reproducibility_and_requires_resolved_citations(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    catalog = Catalog()
    created = catalog.create_worker("org-a", "user-a", "Local Ollama")
    worker = catalog.authenticate_worker(created["token"])
    assert worker

    first_job = catalog.enqueue("org-a", _job())
    assert catalog.claim(worker, 120)["id"] == first_job["id"]
    accepted = catalog.complete(worker, first_job["id"], _result())
    assert accepted
    assert accepted["verificationStatus"] == "passed"
    assert accepted["citationResolution"] == 1.0

    second_job = catalog.enqueue("org-a", _job())
    assert catalog.claim(worker, 120)["id"] == second_job["id"]
    unresolved = catalog.complete(worker, second_job["id"], _result(reference="invented"))
    assert unresolved
    assert unresolved["verificationStatus"] == "needs_human_review"
    assert unresolved["citationResolution"] == 0.0

    runs = catalog.list_runs("org-a")
    assert len(runs) == 2
    assert all(run["model_digest"] == "sha256:fixed-model" for run in runs)
    assert all(len(run["content_hash"]) == 64 for run in runs)


def test_abstention_and_human_review_are_first_class_catalogue_records(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    catalog = Catalog()
    created = catalog.create_worker("org-a", "user-a", "Local Ollama")
    worker = catalog.authenticate_worker(created["token"])
    job = catalog.enqueue("org-a", _job())
    catalog.claim(worker, 120)
    completed = catalog.complete(worker, job["id"], _result(abstained=True))
    assert completed and completed["verificationStatus"] == "passed"

    review = catalog.review_run(
        "org-a",
        "reviewer-a",
        completed["runId"],
        HumanReviewCreate(
            disposition="corrected",
            corrections={"summary": "Explicitly distinguish absence of evidence."},
            unsupportedClaimCount=0,
            citationIssueCount=0,
            usefulnessScore=4,
        ),
    )
    assert review and review["disposition"] == "corrected"
    assert (
        catalog.review_run(
            "org-b", "reviewer-b", completed["runId"], HumanReviewCreate(disposition="accepted")
        )
        is None
    )


def test_operation_jobs_require_compatible_model_and_fenced_lease(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    local = Catalog()
    credential = local.create_worker("org-a", "user-a", "Pinned worker")
    worker = local.authenticate_worker(credential["token"])
    queued = local.enqueue(
        "org-a",
        _job().model_copy(
            update={
                "operationId": "00000000-0000-0000-0000-000000000010",
                "requestedModelDigest": "sha256:approved",
            }
        ),
    )
    assert (
        local.claim(worker, 120, WorkerClaim(models=[{"name": "wrong", "digest": "sha256:wrong"}]))
        is None
    )
    lease = local.claim(
        worker, 120, WorkerClaim(models=[{"name": "approved", "digest": "sha256:approved"}])
    )
    assert lease and lease["generation"] == 1 and lease["leaseId"]
    stale = _result().model_copy(update={"leaseId": "stale", "generation": lease["generation"]})
    assert local.complete(worker, queued["id"], stale) is None


def test_heartbeats_are_fenced_and_retry_attempts_are_bounded(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    local = Catalog()
    credential = local.create_worker("org-a", "user-a", "Recovery worker")
    worker = local.authenticate_worker(credential["token"])
    queued = local.enqueue("org-a", _job())
    lease = local.claim(worker, 30, WorkerClaim(models=[]))
    assert lease
    assert not local.heartbeat(
        worker,
        queued["id"],
        LeaseUpdate(leaseId=lease["leaseId"], generation=lease["generation"] + 1),
    )
    assert local.heartbeat(
        worker,
        queued["id"],
        LeaseUpdate(
            leaseId=lease["leaseId"], generation=lease["generation"], stage="verifier", progress=60
        ),
    )
    assert local.fail_job(
        worker,
        queued["id"],
        WorkerFailure(
            leaseId=lease["leaseId"],
            generation=lease["generation"],
            code="ollama_unreachable",
            message="connection refused",
            retryable=True,
        ),
    )
    assert local.jobs[queued["id"]]["state"] == "retry_wait"
    second = local.claim(worker, 30, WorkerClaim(models=[]))
    assert second and second["generation"] == lease["generation"] + 1
