"""Tenant-scoped local-worker queue and reproducible LLM run catalogue."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import UTC, datetime, timedelta
from threading import RLock
from uuid import uuid4

import psycopg
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from psycopg.rows import dict_row

from .identity import hash_token
from .operations import current_principal
from .tenant_context import apply_tenant_context

router = APIRouter(tags=["local-llm"])

DISCONFIRMATION_SCHEMA_VERSION = "disconfirmation.local.v1"
DISCONFIRMATION_SCHEMA = {
    "type": "object",
    "required": [
        "summary", "claimsTested", "falsifiableConditions", "alternativeExplanations",
        "contradictions", "missingEvidence", "evidenceReferences", "abstained",
    ],
    "properties": {
        "summary": {"type": "string"},
        "claimsTested": {"type": "array", "items": {"type": "string"}},
        "falsifiableConditions": {"type": "array", "items": {"type": "string"}},
        "alternativeExplanations": {"type": "array", "items": {"type": "string"}},
        "contradictions": {"type": "array", "items": {"type": "string"}},
        "missingEvidence": {"type": "array", "items": {"type": "string"}},
        "evidenceReferences": {"type": "array", "items": {"type": "string"}},
        "abstained": {"type": "boolean"},
    },
    "additionalProperties": False,
}


def now() -> datetime:
    return datetime.now(UTC)


def canonical_hash(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class WorkerCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class LlmJobCreate(BaseModel):
    packetId: str | None = None
    workspaceId: str | None = None
    thesis: str = Field(min_length=10, max_length=20_000)
    claims: list[str] = Field(default_factory=list, max_length=50)
    evidence: list[dict] = Field(default_factory=list, max_length=100)
    observationCutoff: datetime | None = None


class WorkerClaim(BaseModel):
    leaseSeconds: int = Field(default=120, ge=30, le=600)


class DisconfirmationOutput(BaseModel):
    summary: str = Field(min_length=1, max_length=10_000)
    claimsTested: list[str] = Field(default_factory=list, max_length=100)
    falsifiableConditions: list[str] = Field(default_factory=list, max_length=100)
    alternativeExplanations: list[str] = Field(default_factory=list, max_length=100)
    contradictions: list[str] = Field(default_factory=list, max_length=100)
    missingEvidence: list[str] = Field(default_factory=list, max_length=100)
    evidenceReferences: list[str] = Field(default_factory=list, max_length=200)
    abstained: bool = False


class WorkerResult(BaseModel):
    modelName: str = Field(min_length=1, max_length=200)
    modelDigest: str | None = Field(default=None, max_length=256)
    ollamaVersion: str | None = Field(default=None, max_length=100)
    startedAt: datetime
    completedAt: datetime
    totalDurationNs: int | None = Field(default=None, ge=0)
    loadDurationNs: int | None = Field(default=None, ge=0)
    promptEvalCount: int | None = Field(default=None, ge=0)
    promptEvalDurationNs: int | None = Field(default=None, ge=0)
    evalCount: int | None = Field(default=None, ge=0)
    evalDurationNs: int | None = Field(default=None, ge=0)
    parameters: dict = Field(default_factory=dict)
    output: DisconfirmationOutput


class HumanReviewCreate(BaseModel):
    disposition: str = Field(pattern="^(accepted|corrected|rejected)$")
    corrections: dict = Field(default_factory=dict)
    unsupportedClaimCount: int = Field(default=0, ge=0)
    citationIssueCount: int = Field(default=0, ge=0)
    usefulnessScore: int | None = Field(default=None, ge=1, le=5)


class Catalog:
    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL", "").strip()
        self.lock = RLock()
        self.devices: dict[str, dict] = {}
        self.jobs: dict[str, dict] = {}
        self.runs: dict[str, dict] = {}

    def _connect(self, *, tenant: bool = True):
        connection = psycopg.connect(self.database_url, row_factory=dict_row)
        if tenant:
            apply_tenant_context(connection)
        return connection

    @property
    def durable(self) -> bool:
        return bool(self.database_url)

    def create_worker(self, organization_id: str, user_id: str, name: str) -> dict:
        worker_id = str(uuid4())
        token = secrets.token_urlsafe(40)
        token_digest = hash_token(token)
        if self.durable:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO local_worker_credentials
                      (id, organization_id, user_id, name, token_hash)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (worker_id, organization_id, user_id, name, token_digest),
                )
        else:
            with self.lock:
                self.devices[token_digest] = {
                    "id": worker_id, "organization_id": organization_id,
                    "user_id": user_id, "name": name, "status": "active",
                }
        return {"id": worker_id, "name": name, "token": token}

    def authenticate_worker(self, token: str) -> dict | None:
        digest = hash_token(token)
        if self.durable:
            with self._connect(tenant=False) as connection:
                row = connection.execute(
                    """
                    SELECT id, organization_id, user_id, name
                    FROM local_worker_credentials
                    WHERE token_hash = %s AND status = 'active'
                    """,
                    (digest,),
                ).fetchone()
                if row:
                    connection.execute(
                        "UPDATE local_worker_credentials SET last_seen_at = now() WHERE id = %s",
                        (row["id"],),
                    )
            return dict(row) if row else None
        with self.lock:
            worker = self.devices.get(digest)
            return worker if worker and worker["status"] == "active" else None

    def list_workers(self, organization_id: str) -> list[dict]:
        if self.durable:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT id, name, status, last_seen_at, created_at, revoked_at
                    FROM local_worker_credentials
                    WHERE organization_id = ambrosia_current_organization_id()
                    ORDER BY created_at DESC
                    """
                ).fetchall()
            return [dict(row) for row in rows]
        with self.lock:
            return [
                {key: value for key, value in row.items() if key not in {"organization_id", "user_id"}}
                for row in self.devices.values()
                if row["organization_id"] == organization_id
            ]

    def revoke_worker(self, organization_id: str, worker_id: str) -> bool:
        if self.durable:
            with self._connect() as connection:
                result = connection.execute(
                    """
                    UPDATE local_worker_credentials SET status = 'revoked', revoked_at = now()
                    WHERE id = %s AND organization_id = ambrosia_current_organization_id()
                      AND status = 'active'
                    """,
                    (worker_id,),
                )
            return result.rowcount == 1
        with self.lock:
            for worker in self.devices.values():
                if worker["id"] == worker_id and worker["organization_id"] == organization_id:
                    worker["status"] = "revoked"
                    return True
        return False

    def enqueue(self, organization_id: str, body: LlmJobCreate) -> dict:
        job_id = str(uuid4())
        payload = {
            "thesis": body.thesis,
            "claims": body.claims,
            "evidence": body.evidence,
            "outputSchema": DISCONFIRMATION_SCHEMA,
            "outputSchemaVersion": DISCONFIRMATION_SCHEMA_VERSION,
            "promptTemplateId": "disconfirmation.v1",
        }
        row = {
            "id": job_id,
            "organization_id": organization_id,
            "workspace_id": body.workspaceId,
            "packet_id": body.packetId,
            "task_type": "disconfirmation",
            "state": "queued",
            "input_payload": payload,
            "observation_cutoff": body.observationCutoff,
            "created_at": now(),
        }
        if self.durable:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO llm_jobs (
                      id, organization_id, workspace_id, packet_id, task_type,
                      input_payload, observation_cutoff
                    ) VALUES (%s, %s, %s, %s, 'disconfirmation', %s::jsonb, %s)
                    """,
                    (
                        job_id, organization_id, body.workspaceId, body.packetId,
                        json.dumps(payload), body.observationCutoff,
                    ),
                )
        else:
            with self.lock:
                self.jobs[job_id] = row
        return {"id": job_id, "state": "queued", "taskType": "disconfirmation"}

    @staticmethod
    def _set_worker_tenant(connection, worker: dict) -> None:
        connection.execute(
            "SELECT set_config('app.current_organization_id', %s, false)",
            (str(worker["organization_id"]),),
        )

    def claim(self, worker: dict, lease_seconds: int) -> dict | None:
        lease_until = now() + timedelta(seconds=lease_seconds)
        if self.durable:
            with self._connect(tenant=False) as connection:
                with connection.transaction():
                    self._set_worker_tenant(connection, worker)
                    connection.execute(
                        """
                        UPDATE llm_jobs SET state = 'queued', claimed_by = NULL,
                          claimed_at = NULL, lease_expires_at = NULL
                        WHERE state = 'claimed' AND lease_expires_at <= now()
                        """
                    )
                    row = connection.execute(
                        """
                        SELECT id FROM llm_jobs
                        WHERE state = 'queued' ORDER BY created_at
                        FOR UPDATE SKIP LOCKED LIMIT 1
                        """
                    ).fetchone()
                    if not row:
                        return None
                    job = connection.execute(
                        """
                        UPDATE llm_jobs SET state = 'claimed', claimed_by = %s,
                          claimed_at = now(), lease_expires_at = %s
                        WHERE id = %s
                        RETURNING id, task_type, input_payload
                        """,
                        (worker["id"], lease_until, row["id"]),
                    ).fetchone()
            return {
                "id": str(job["id"]), "taskType": job["task_type"],
                "input": job["input_payload"], "leaseExpiresAt": lease_until.isoformat(),
            }
        with self.lock:
            for job in sorted(self.jobs.values(), key=lambda item: item["created_at"]):
                expired = (
                    job["state"] == "claimed"
                    and job.get("lease_expires_at")
                    and job["lease_expires_at"] <= now()
                )
                if expired:
                    job.update({"state": "queued", "claimed_by": None, "lease_expires_at": None})
                if job["organization_id"] == worker["organization_id"] and job["state"] == "queued":
                    job.update({
                        "state": "claimed", "claimed_by": worker["id"],
                        "lease_expires_at": lease_until,
                    })
                    return {"id": job["id"], "taskType": job["task_type"], "input": job["input_payload"], "leaseExpiresAt": lease_until.isoformat()}
        return None

    @staticmethod
    def _verify_output(input_payload: dict, output: dict) -> tuple[str, float]:
        allowed = {
            str(item.get("id")) for item in input_payload.get("evidence", [])
            if isinstance(item, dict) and item.get("id")
        }
        references = set(output.get("evidenceReferences", []))
        resolved = references.intersection(allowed)
        ratio = len(resolved) / len(references) if references else 0.0
        passed = bool(references) and references.issubset(allowed)
        if output.get("abstained") and not references:
            passed = True
        return ("passed" if passed else "needs_human_review", ratio)

    def complete(self, worker: dict, job_id: str, body: WorkerResult) -> dict | None:
        output = body.output.model_dump(mode="json")
        if body.completedAt < body.startedAt:
            raise ValueError("completedAt cannot precede startedAt")
        run_id = str(uuid4())
        if self.durable:
            with self._connect(tenant=False) as connection:
                with connection.transaction():
                    self._set_worker_tenant(connection, worker)
                    job = connection.execute(
                        """
                        SELECT * FROM llm_jobs WHERE id = %s AND state = 'claimed'
                          AND claimed_by = %s AND lease_expires_at > now() FOR UPDATE
                        """,
                        (job_id, worker["id"]),
                    ).fetchone()
                    if not job:
                        return None
                    verification, citation_ratio = self._verify_output(job["input_payload"], output)
                    connection.execute(
                        """
                        INSERT INTO llm_runs (
                          id, organization_id, job_id, workspace_id, packet_id,
                          workflow_stage, provider_mode_requested, provider_used,
                          model_name, model_digest, ollama_version, worker_id,
                          prompt_template_id, evidence_pack_hash, observation_cutoff,
                          parameters_json, started_at, completed_at, total_duration_ns,
                          load_duration_ns, prompt_eval_count, prompt_eval_duration_ns,
                          eval_count, eval_duration_ns, output_schema_version,
                          parse_status, verification_status, structured_output, content_hash
                        ) VALUES (
                          %s, %s, %s, %s, %s, 'disconfirmation', 'ollama', 'ollama-local',
                          %s, %s, %s, %s, 'disconfirmation.v1', %s, %s, %s::jsonb,
                          %s, %s, %s, %s, %s, %s, %s, %s, %s, 'valid', %s,
                          %s::jsonb, %s
                        )
                        """,
                        (
                            run_id, worker["organization_id"], job_id, job["workspace_id"],
                            job["packet_id"], body.modelName, body.modelDigest,
                            body.ollamaVersion, worker["id"], canonical_hash(job["input_payload"]),
                            job["observation_cutoff"], json.dumps(body.parameters),
                            body.startedAt, body.completedAt,
                            body.totalDurationNs, body.loadDurationNs, body.promptEvalCount,
                            body.promptEvalDurationNs, body.evalCount, body.evalDurationNs,
                            DISCONFIRMATION_SCHEMA_VERSION, verification, json.dumps(output),
                            canonical_hash(output),
                        ),
                    )
                    connection.execute(
                        """
                        INSERT INTO llm_evaluations (
                          organization_id, run_id, suite_id, suite_version,
                          evaluator_type, metric_name, metric_value, notes
                        ) VALUES
                          (%s, %s, 'runtime-verification', 'v1', 'deterministic', 'schema_valid', 1, NULL),
                          (%s, %s, 'runtime-verification', 'v1', 'deterministic', 'citation_resolution', %s, NULL)
                        """,
                        (worker["organization_id"], run_id, worker["organization_id"], run_id, citation_ratio),
                    )
                    connection.execute(
                        "UPDATE llm_jobs SET state = 'completed', completed_at = now() WHERE id = %s",
                        (job_id,),
                    )
        else:
            with self.lock:
                job = self.jobs.get(job_id)
                if not job or job.get("claimed_by") != worker["id"] or job["state"] != "claimed":
                    return None
                verification, citation_ratio = self._verify_output(job["input_payload"], output)
                job["state"] = "completed"
                self.runs[run_id] = {
                    "id": run_id, "organization_id": worker["organization_id"],
                    "job_id": job_id, "model_name": body.modelName,
                    "model_digest": body.modelDigest, "verification_status": verification,
                    "structured_output": output, "content_hash": canonical_hash(output),
                    "citation_resolution": citation_ratio, "created_at": now(),
                }
        return {"runId": run_id, "verificationStatus": verification, "citationResolution": citation_ratio}

    def list_runs(self, organization_id: str) -> list[dict]:
        if self.durable:
            with self._connect() as connection:
                rows = connection.execute(
                    """
                    SELECT id, job_id, packet_id, model_name, model_digest,
                      verification_status, output_schema_version, content_hash, created_at
                    FROM llm_runs ORDER BY created_at DESC LIMIT 200
                    """
                ).fetchall()
            return [{**dict(row), "id": str(row["id"]), "job_id": str(row["job_id"])} for row in rows]
        with self.lock:
            return [row for row in self.runs.values() if row["organization_id"] == organization_id]

    def review_run(
        self, organization_id: str, user_id: str, run_id: str, body: HumanReviewCreate
    ) -> dict | None:
        review_id = str(uuid4())
        row = {
            "id": review_id,
            "run_id": run_id,
            "reviewer_user_id": user_id,
            "disposition": body.disposition,
            "corrections": body.corrections,
            "unsupported_claim_count": body.unsupportedClaimCount,
            "citation_issue_count": body.citationIssueCount,
            "usefulness_score": body.usefulnessScore,
            "created_at": now(),
        }
        if self.durable:
            with self._connect() as connection:
                exists = connection.execute(
                    "SELECT 1 FROM llm_runs WHERE id = %s", (run_id,)
                ).fetchone()
                if not exists:
                    return None
                connection.execute(
                    """
                    INSERT INTO llm_human_reviews (
                      id, organization_id, run_id, reviewer_user_id, disposition,
                      corrections, unsupported_claim_count, citation_issue_count,
                      usefulness_score
                    ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                    """,
                    (
                        review_id, organization_id, run_id, user_id, body.disposition,
                        json.dumps(body.corrections), body.unsupportedClaimCount,
                        body.citationIssueCount, body.usefulnessScore,
                    ),
                )
        else:
            with self.lock:
                run = self.runs.get(run_id)
                if not run or run["organization_id"] != organization_id:
                    return None
                run.setdefault("human_reviews", []).append(row)
        return row


catalog = Catalog()


def _principal():
    principal = current_principal()
    if not principal or not principal.organization_id:
        raise HTTPException(status_code=401, detail="Tenant-bound account required")
    return principal


def _worker(authorization: str | None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Worker credential required")
    worker = catalog.authenticate_worker(authorization[7:].strip())
    if not worker:
        raise HTTPException(status_code=401, detail="Worker credential is invalid or revoked")
    return worker


@router.post("/llm/workers", status_code=201)
def create_worker(body: WorkerCreate) -> dict:
    principal = _principal()
    if principal.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Owner or admin role required")
    return catalog.create_worker(principal.organization_id, principal.subject, body.name)


@router.get("/llm/workers")
def list_workers() -> dict:
    principal = _principal()
    if principal.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Owner or admin role required")
    return {"workers": catalog.list_workers(principal.organization_id)}


@router.delete("/llm/workers/{worker_id}")
def revoke_worker(worker_id: str) -> dict:
    principal = _principal()
    if principal.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Owner or admin role required")
    if not catalog.revoke_worker(principal.organization_id, worker_id):
        raise HTTPException(status_code=404, detail="Worker not found")
    return {"revoked": True, "workerId": worker_id}


@router.post("/llm/jobs", status_code=202)
def enqueue_job(body: LlmJobCreate) -> dict:
    principal = _principal()
    return catalog.enqueue(principal.organization_id, body)


@router.get("/llm/runs")
def list_runs() -> dict:
    principal = _principal()
    return {"runs": catalog.list_runs(principal.organization_id)}


@router.post("/llm/runs/{run_id}/reviews", status_code=201)
def review_run(run_id: str, body: HumanReviewCreate) -> dict:
    principal = _principal()
    result = catalog.review_run(principal.organization_id, principal.subject, run_id, body)
    if not result:
        raise HTTPException(status_code=404, detail="LLM run not found")
    return result


@router.post("/local-worker/claim")
def claim_job(body: WorkerClaim, authorization: str | None = Header(default=None)) -> dict:
    worker = _worker(authorization)
    job = catalog.claim(worker, body.leaseSeconds)
    return {"job": job}


@router.post("/local-worker/jobs/{job_id}/result")
def complete_job(
    job_id: str,
    body: WorkerResult,
    authorization: str | None = Header(default=None),
) -> dict:
    worker = _worker(authorization)
    try:
        result = catalog.complete(worker, job_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not result:
        raise HTTPException(status_code=409, detail="Job lease is invalid or expired")
    return result
