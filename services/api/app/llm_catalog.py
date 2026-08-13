"""Tenant-scoped local-worker queue and reproducible LLM run catalogue."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Literal
from uuid import uuid4
from uuid import UUID

import psycopg
from fastapi import APIRouter, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator, model_validator
from psycopg.rows import dict_row

from .coordinator import INSTRUCTION_MANIFEST, SPECIALIST_RESPONSE_SCHEMA_V2, _before
from .artifact_store import artifact_store
from .financial_calculations import evaluate_calculation_intent
from .identity import hash_token, ip_prefix
from .models import CalculationArtifact, SpecialistOutputV2, TickerIdentity
from .operations import current_principal, record_domain_event
from .review_engine import detects_prompt_injection
from .tenant_context import apply_tenant_context

router = APIRouter(tags=["local-llm"])

DISCONFIRMATION_SCHEMA_VERSION = "specialist-output.v2"
LEGACY_DISCONFIRMATION_SCHEMA = {
    "type": "object",
    "required": [
        "summary",
        "claimsTested",
        "falsifiableConditions",
        "alternativeExplanations",
        "contradictions",
        "missingEvidence",
        "evidenceReferences",
        "abstained",
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
DISCONFIRMATION_SCHEMA = SPECIALIST_RESPONSE_SCHEMA_V2


class CompletionConflict(ValueError):
    pass


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
    role: str = Field(default="bear", min_length=2, max_length=80)
    tickerIdentity: dict | None = None
    pipelineVersion: str = "evidence-grounded-adversarial.v2"
    operationId: str | None = None
    expectedPacketVersion: int | None = Field(default=None, ge=1)
    requestedModel: str | None = None
    requestedModelDigest: str | None = None
    requiredContextLength: int = Field(default=8192, ge=1024, le=1_000_000)
    inputArtifactId: str | None = None
    inputArtifactHash: str | None = Field(default=None, pattern="^[a-f0-9]{64}$")
    verificationCandidate: dict | None = None
    verificationBindingHash: str | None = Field(default=None, pattern="^[a-f0-9]{64}$")
    traceparent: str | None = Field(
        default=None, pattern="^00-[a-f0-9]{32}-[a-f0-9]{16}-[0-9a-f]{2}$"
    )


class WorkerClaim(BaseModel):
    leaseSeconds: int = Field(default=120, ge=30, le=600)
    workerVersion: str | None = None
    ollamaVersion: str | None = None
    models: list[dict] = Field(default_factory=list)
    maxConcurrentJobs: int = Field(default=1, ge=1, le=16)
    waitSeconds: int = Field(default=0, ge=0, le=25)

    @field_validator("models")
    @classmethod
    def require_hardware_qualified_models(cls, models: list[dict]) -> list[dict]:
        for model in models:
            if not isinstance(model, dict):
                raise ValueError("worker model capability must be an object")
            if (
                not str(model.get("name") or "").strip()
                or not str(model.get("digest") or "").strip()
            ):
                raise ValueError("worker model capability requires name and digest")
            if model.get("readiness") != "preflighted":
                raise ValueError("worker model capability requires a passed hardware preflight")
            if not str(model.get("preflightCompletedAt") or "").strip():
                raise ValueError("worker model capability requires preflightCompletedAt")
            context = int(model.get("contextLength") or 0)
            if not 1024 <= context <= 1_000_000:
                raise ValueError("worker model capability requires a qualified contextLength")
        return models


class WorkerCapabilities(WorkerClaim):
    pass


class LeaseUpdate(BaseModel):
    leaseId: str
    generation: int = Field(ge=1)
    leaseSeconds: int = Field(default=120, ge=30, le=600)
    stage: Literal[
        "claimed",
        "loading_model",
        "analyst",
        "deterministic_checks",
        "verifier",
        "repair",
        "final_verifier",
        "uploading",
        "running",
    ] = "running"
    progress: int = Field(default=0, ge=0, le=99)


class WorkerFailure(BaseModel):
    leaseId: str
    generation: int = Field(ge=1)
    code: Literal[
        "no_worker_available",
        "no_compatible_model",
        "lease_lost",
        "ollama_unreachable",
        "model_load_failed",
        "timeout",
        "truncation",
        "out_of_memory",
        "schema_invalid",
        "verification_rejected",
        "packet_superseded",
        "credential_revoked",
        "prompt_injection_detected",
        "model_digest_changed",
        "worker_failure",
    ]
    message: str
    retryable: bool = True


class DisconfirmationOutput(BaseModel):
    summary: str = Field(default="", max_length=10_000)
    claimsTested: list[str] = Field(default_factory=list, max_length=100)
    falsifiableConditions: list[str] = Field(default_factory=list, max_length=100)
    alternativeExplanations: list[str] = Field(default_factory=list, max_length=100)
    contradictions: list[str] = Field(default_factory=list, max_length=100)
    missingEvidence: list[str] = Field(default_factory=list, max_length=100)
    evidenceReferences: list[str] = Field(default_factory=list, max_length=200)
    abstained: bool = False
    schemaVersion: str = "disconfirmation.local.v1"
    role: str | None = None
    instructionReferences: list[str] = Field(default_factory=list)
    materialClaims: list[dict] = Field(default_factory=list)
    calculationIntents: list[dict] = Field(default_factory=list)
    calculationArtifacts: list[dict] = Field(default_factory=list)
    verificationFindings: list[dict] = Field(default_factory=list)
    rejectedClaims: list[dict] = Field(default_factory=list)
    repairLineage: list[dict] = Field(default_factory=list)
    roleConclusion: str | None = None
    confidence: dict = Field(default_factory=dict)
    abstentionReason: str | None = None
    humanReviewLineage: list[dict] = Field(default_factory=list)
    humanCorrectedClaims: list[dict] = Field(default_factory=list)
    humanRejectedClaims: list[dict] = Field(default_factory=list)


class WorkerResult(BaseModel):
    leaseId: str | None = None
    generation: int | None = Field(default=None, ge=1)
    inputHash: str | None = Field(default=None, pattern="^[a-f0-9]{64}$")
    resultHash: str | None = Field(default=None, pattern="^[a-f0-9]{64}$")
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
    verifierModelName: str | None = None
    verifierModelDigest: str | None = None
    finishReason: str | None = None
    truncationDetected: bool = False
    stageHashes: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def bound_untrusted_json(self):
        payload = self.model_dump(mode="json")
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        if len(encoded) > 1_000_000:
            raise ValueError("Worker result exceeds the one-megabyte protocol limit")

        def check_depth(value: object, depth: int = 0) -> None:
            if depth > 32:
                raise ValueError("Worker result exceeds the maximum JSON depth")
            if isinstance(value, dict):
                for child in value.values():
                    check_depth(child, depth + 1)
            elif isinstance(value, list):
                for child in value:
                    check_depth(child, depth + 1)

        check_depth(payload)
        return self


class HumanReviewCreate(BaseModel):
    disposition: str = Field(pattern="^(accepted|corrected|rejected)$")
    corrections: dict = Field(default_factory=dict)
    unsupportedClaimCount: int = Field(default=0, ge=0)
    citationIssueCount: int = Field(default=0, ge=0)
    usefulnessScore: int | None = Field(default=None, ge=1, le=5)


class WorkerEnrollmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    requestedModelDigest: str | None = None
    requiredContextLength: int = Field(default=8192, ge=1024, le=1_000_000)


class WorkerEnrollmentCanaryCreate(BaseModel):
    requestedModelDigest: str | None = None
    requiredContextLength: int = Field(default=8192, ge=1024, le=1_000_000)


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

    @staticmethod
    def resolved_input(payload: dict) -> dict:
        artifact_id = payload.get("inputArtifactId")
        if not artifact_id:
            return payload
        pack = artifact_store.load_json(artifact_id)
        if canonical_hash(pack) != payload.get("inputArtifactHash"):
            raise ValueError("Immutable evidence artifact hash mismatch")
        return {
            **payload,
            "evidence": pack["evidence"],
            "tickerIdentity": pack["tickerIdentity"],
            "observationCutoff": pack["observationCutoff"],
        }

    def create_worker(self, organization_id: str, user_id: str, name: str) -> dict:
        worker_id = str(uuid4())
        token = secrets.token_urlsafe(40)
        token_digest = hash_token(token)
        if self.durable:
            try:
                database_user_id = str(UUID(user_id))
            except ValueError:
                database_user_id = None
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO local_worker_credentials
                      (id, organization_id, user_id, created_by_subject, name, token_hash)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        worker_id,
                        organization_id,
                        database_user_id,
                        user_id,
                        name,
                        token_digest,
                    ),
                )
        else:
            with self.lock:
                self.devices[token_digest] = {
                    "id": worker_id,
                    "organization_id": organization_id,
                    "user_id": user_id,
                    "name": name,
                    "status": "active",
                }
        return {"id": worker_id, "name": name, "token": token}

    def authenticate_worker(self, token: str, remote_ip: str | None = None) -> dict | None:
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
                        """UPDATE local_worker_credentials SET last_seen_at=now(),last_ip_prefix=%s
                        WHERE id=%s""",
                        (ip_prefix(remote_ip), row["id"]),
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
                    SELECT w.id,w.name,w.status,w.last_seen_at,w.last_ip_prefix,w.worker_version,
                    w.ollama_version,w.capability_digest,w.capabilities,w.max_concurrent_jobs,
                    w.created_at,w.revoked_at,
                    (SELECT count(*) FROM llm_jobs j WHERE j.claimed_by=w.id AND j.state='claimed'
                     AND j.lease_expires_at>now()) AS active_lease_count
                    FROM local_worker_credentials w
                    WHERE organization_id = ambrosia_current_organization_id()
                    ORDER BY created_at DESC
                    """
                ).fetchall()
            return [dict(row) for row in rows]
        with self.lock:
            return [
                {
                    key: value
                    for key, value in row.items()
                    if key not in {"organization_id", "user_id"}
                }
                for row in self.devices.values()
                if row["organization_id"] == organization_id
            ]

    def has_compatible_worker(self, organization_id: str, model_digest: str | None = None) -> bool:
        if self.durable:
            with self._connect() as connection:
                row = connection.execute(
                    """SELECT 1 FROM local_worker_credentials
                    WHERE organization_id=%s AND status='active'
                      AND last_seen_at>now()-interval '2 minutes'
                      AND (%s::text IS NULL OR capabilities->'models' @> %s::jsonb)
                    LIMIT 1""",
                    (
                        organization_id,
                        model_digest,
                        json.dumps([{"digest": model_digest}]) if model_digest else "[]",
                    ),
                ).fetchone()
            return row is not None
        with self.lock:
            for worker in self.devices.values():
                if worker["organization_id"] != organization_id or worker["status"] != "active":
                    continue
                models = worker.get("capabilities", {}).get("models", [])
                if model_digest is None or any(
                    item.get("digest") == model_digest for item in models
                ):
                    return True
        return False

    def worker_readiness(
        self,
        organization_id: str,
        model_digest: str | None = None,
        required_context_length: int | None = None,
        required_prompt_manifest_hash: str | None = None,
        required_output_schema_hash: str | None = None,
        required_worker_version: str | None = None,
    ) -> dict:
        """Explain worker compatibility instead of collapsing it to a boolean."""
        configured = self.configured_model_policies(organization_id)
        default_digest = os.getenv("OLLAMA_DEFAULT_MODEL_DIGEST", "").strip()
        if model_digest is None and len(configured) > 1 and not default_digest:
            return {
                "ready": False,
                "reasonCode": "model_policy_ambiguous",
                "compatibleCount": 0,
            }
        if model_digest is None and default_digest:
            model_digest = default_digest
        required_prompt_manifest_hash = (
            required_prompt_manifest_hash
            or os.getenv("OLLAMA_REQUIRED_PROMPT_MANIFEST_HASH", "").strip()
            or None
        )
        required_output_schema_hash = (
            required_output_schema_hash
            or os.getenv("OLLAMA_REQUIRED_OUTPUT_SCHEMA_HASH", "").strip()
            or None
        )
        required_worker_version = (
            required_worker_version
            or os.getenv("OLLAMA_REQUIRED_WORKER_VERSION", "").strip()
            or None
        )
        workers = self.list_workers(organization_id)
        if not workers:
            return {"ready": False, "reasonCode": "no_enrolled_worker", "compatibleCount": 0}
        active = [worker for worker in workers if worker.get("status") == "active"]
        if not active:
            reason = "worker_revoked" if any(w.get("status") == "revoked" for w in workers) else "worker_offline"
            return {"ready": False, "reasonCode": reason, "compatibleCount": 0}
        cutoff = now() - timedelta(minutes=2)
        fresh = []
        newest_seen = None
        for worker in active:
            seen = worker.get("last_seen_at") or worker.get("lastSeenAt")
            if isinstance(seen, str):
                seen = datetime.fromisoformat(seen.replace("Z", "+00:00"))
            if seen and (newest_seen is None or seen > newest_seen):
                newest_seen = seen
            if not self.durable or (seen and seen > cutoff):
                fresh.append(worker)
        if not fresh:
            return {
                "ready": False,
                "reasonCode": "worker_offline",
                "compatibleCount": 0,
                "lastSeenAt": newest_seen.isoformat() if newest_seen else None,
                "lastHeartbeatAgeSeconds": int((now() - newest_seen).total_seconds())
                if newest_seen
                else None,
            }
        preflight_max_age_seconds = int(os.getenv("OLLAMA_PREFLIGHT_MAX_AGE_SECONDS", "0") or "0")
        qualified = []
        digest_seen = False
        newest_preflight = None
        max_qualified_context_length = 0
        compatibility_failure = False
        policy_mismatch = False
        for worker in fresh:
            models = (worker.get("capabilities") or {}).get("models", [])
            for model in models:
                if model_digest and model.get("digest") != model_digest:
                    continue
                digest_seen = True
                if model.get("readiness") == "preflighted" and model.get("preflightCompletedAt"):
                    preflight_completed = model.get("preflightCompletedAt")
                    if isinstance(preflight_completed, str):
                        try:
                            preflight_completed = datetime.fromisoformat(
                                preflight_completed.replace("Z", "+00:00")
                            )
                        except ValueError:
                            preflight_completed = None
                    context_length = int(model.get("contextLength") or 0)
                    if context_length > max_qualified_context_length:
                        max_qualified_context_length = context_length
                    if preflight_completed and (
                        newest_preflight is None or preflight_completed > newest_preflight
                    ):
                        newest_preflight = preflight_completed
                    if required_context_length and context_length < required_context_length:
                        compatibility_failure = True
                        continue
                    if required_prompt_manifest_hash and model.get("promptManifestHash") != required_prompt_manifest_hash:
                        compatibility_failure = True
                        policy_mismatch = True
                        continue
                    if required_output_schema_hash and model.get("outputSchemaHash") != required_output_schema_hash:
                        compatibility_failure = True
                        policy_mismatch = True
                        continue
                    if required_worker_version and worker.get("worker_version") != required_worker_version:
                        compatibility_failure = True
                        policy_mismatch = True
                        continue
                    if preflight_max_age_seconds > 0 and preflight_completed:
                        if (now() - preflight_completed).total_seconds() > preflight_max_age_seconds:
                            compatibility_failure = True
                            continue
                    qualified.append((worker, model))
        if not digest_seen:
            return {"ready": False, "reasonCode": "digest_mismatch", "compatibleCount": 0}
        if not qualified:
            response = {
                "ready": False,
                "reasonCode": "preflight_incomplete",
                "compatibleCount": 0,
            }
            if required_context_length:
                response["requiredContextLength"] = required_context_length
                response["maxQualifiedContextLength"] = max_qualified_context_length
            if preflight_max_age_seconds > 0:
                response["preflightMaxAgeSeconds"] = preflight_max_age_seconds
                response["preflightExpired"] = bool(compatibility_failure and newest_preflight)
            if required_prompt_manifest_hash:
                response["requiredPromptManifestHash"] = required_prompt_manifest_hash
            if required_output_schema_hash:
                response["requiredOutputSchemaHash"] = required_output_schema_hash
            if required_worker_version:
                response["requiredWorkerVersion"] = required_worker_version
            if policy_mismatch:
                response["policyCompatibilityMismatch"] = True
            return response
        return {
            "ready": True,
            "reasonCode": "ready",
            "compatibleCount": len({str(worker.get("id")) for worker, _ in qualified}),
            "freshnessSeconds": 120,
            "lastSeenAt": newest_seen.isoformat() if newest_seen else None,
            "lastHeartbeatAgeSeconds": int((now() - newest_seen).total_seconds())
            if newest_seen
            else 0,
            "preflightCompletedAt": newest_preflight.isoformat() if newest_preflight else None,
            "preflightAgeSeconds": int((now() - newest_preflight).total_seconds())
            if newest_preflight
            else None,
        }

    def _advertised_models(self, organization_id: str, *, fresh_only: bool) -> list[dict]:
        if self.durable:
            with self._connect() as connection:
                freshness = "AND last_seen_at>now()-interval '2 minutes'" if fresh_only else ""
                rows = connection.execute(
                    f"""SELECT capabilities->'models' AS models FROM local_worker_credentials
                    WHERE organization_id=%s AND status='active'
                    {freshness}""",
                    (organization_id,),
                ).fetchall()
            models = [model for row in rows for model in (row["models"] or [])]
        else:
            models = [
                model
                for worker in self.devices.values()
                if worker["organization_id"] == organization_id and worker["status"] == "active"
                and (not fresh_only or worker.get("last_seen_at"))
                for model in worker.get("capabilities", {}).get("models", [])
            ]
        return models

    def configured_model_policies(self, organization_id: str) -> list[dict]:
        """Return durable policy eligibility independently of worker freshness."""
        advertised = self._advertised_models(organization_id, fresh_only=False)
        metadata = {
            str(model.get("digest")): model for model in advertised if model.get("digest")
        }
        approved = {
            item.strip()
            for item in os.getenv("OLLAMA_APPROVED_MODEL_DIGESTS", "").split(",")
            if item.strip()
        }
        default_digest = os.getenv("OLLAMA_DEFAULT_MODEL_DIGEST", "").strip()
        if default_digest:
            approved.add(default_digest)
        if not approved:
            approved = set(metadata)
        return [
            {
                **metadata.get(digest, {}),
                "name": metadata.get(digest, {}).get("name") or "Approved Ollama model",
                "digest": digest,
                "approved": True,
                "default": digest == default_digest,
            }
            for digest in sorted(approved)
        ]

    def active_model_policies(self, organization_id: str) -> list[dict]:
        """Backward-compatible name: configured policies, not liveness-derived policies."""
        return self.configured_model_policies(organization_id)

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

    def rotate_worker(self, organization_id: str, worker_id: str) -> dict | None:
        token = secrets.token_urlsafe(40)
        digest = hash_token(token)
        if self.durable:
            with self._connect() as connection:
                result = connection.execute(
                    """UPDATE local_worker_credentials SET token_hash=%s,last_seen_at=NULL
                    WHERE id=%s AND organization_id=%s AND status='active' RETURNING id,name""",
                    (digest, worker_id, organization_id),
                ).fetchone()
            return (
                {"id": str(result["id"]), "name": result["name"], "token": token}
                if result
                else None
            )
        with self.lock:
            old_key = next(
                (
                    key
                    for key, value in self.devices.items()
                    if value["id"] == worker_id
                    and value["organization_id"] == organization_id
                    and value["status"] == "active"
                ),
                None,
            )
            if not old_key:
                return None
            worker = self.devices.pop(old_key)
            self.devices[digest] = worker
            return {"id": worker_id, "name": worker["name"], "token": token}

    def register_capabilities(self, worker: dict, body: WorkerCapabilities) -> dict:
        payload = body.model_dump(mode="json", exclude={"leaseSeconds"})
        digest = canonical_hash(payload)
        if self.durable:
            with self._connect(tenant=False) as connection:
                self._set_worker_tenant(connection, worker)
                connection.execute(
                    """UPDATE local_worker_credentials SET capabilities=%s::jsonb,
                    capability_digest=%s,worker_version=%s,ollama_version=%s,
                    max_concurrent_jobs=%s,last_seen_at=now() WHERE id=%s""",
                    (
                        json.dumps(payload),
                        digest,
                        body.workerVersion,
                        body.ollamaVersion,
                        body.maxConcurrentJobs,
                        worker["id"],
                    ),
                )
        else:
            with self.lock:
                worker.update(
                    capabilities=payload,
                    capability_digest=digest,
                    worker_version=body.workerVersion,
                    ollama_version=body.ollamaVersion,
                    max_concurrent_jobs=body.maxConcurrentJobs,
                    last_seen_at=now(),
                )
        return {"workerId": str(worker["id"]), "capabilityDigest": digest, "accepted": True}

    def enqueue(self, organization_id: str, body: LlmJobCreate, connection=None) -> dict:
        job_id = str(uuid4())
        cutoff = body.observationCutoff or now()
        identity = body.tickerIdentity or {
            "instrumentId": "unresolved",
            "canonicalTicker": "UNRESOLVED",
            "resolutionStatus": "ambiguous",
        }
        evidence = []
        for index, raw in enumerate(body.evidence):
            item = dict(raw)
            item.setdefault("evidenceId", item.get("id") or f"evidence-{index + 1}")
            item.setdefault("evidenceType", item.get("type") or "source")
            item.setdefault("subjectInstrumentId", identity.get("instrumentId", "unresolved"))
            item.setdefault("canonicalTicker", identity.get("canonicalTicker", "UNRESOLVED"))
            item.setdefault("observedAt", cutoff.isoformat())
            item.setdefault("retrievedAt", now().isoformat())
            item.setdefault("observationCutoff", cutoff.isoformat())
            item.setdefault("dataMode", "user_asserted")
            item.setdefault("contentHash", canonical_hash(item))
            evidence.append(item)
        payload = {
            "thesis": body.thesis,
            "claims": body.claims,
            "evidence": evidence,
            "tickerIdentity": identity,
            "observationCutoff": cutoff.isoformat(),
            "role": body.role,
            "pipelineVersion": body.pipelineVersion,
            "instructionManifest": INSTRUCTION_MANIFEST,
            "outputSchema": DISCONFIRMATION_SCHEMA,
            "outputSchemaVersion": DISCONFIRMATION_SCHEMA_VERSION,
            "promptTemplateId": "specialist.generate-verify-repair.v2",
            "operationId": body.operationId,
            "expectedPacketVersion": body.expectedPacketVersion,
            "requestedModel": body.requestedModel,
            "requestedModelDigest": body.requestedModelDigest,
            "requiredContextLength": body.requiredContextLength,
            "traceparent": body.traceparent,
            "inputArtifactId": body.inputArtifactId,
            "inputArtifactHash": body.inputArtifactHash,
            "verificationCandidate": body.verificationCandidate,
            "verificationBindingHash": body.verificationBindingHash,
        }
        task_type = (
            "correction_verification_v1"
            if body.verificationCandidate is not None
            else "adversarial_specialist_v2"
        )
        row = {
            "id": job_id,
            "organization_id": organization_id,
            "workspace_id": body.workspaceId,
            "packet_id": body.packetId,
            "task_type": task_type,
            "state": "queued",
            "input_payload": payload,
            "observation_cutoff": cutoff,
            "created_at": now(),
            "operation_id": body.operationId,
            "requested_model_digest": body.requestedModelDigest,
            "required_context_length": body.requiredContextLength,
            "lease_id": None,
            "lease_generation": 0,
            "attempt_count": 0,
            "max_attempts": 3,
            "next_attempt_at": None,
        }
        if self.durable:
            owns_connection = connection is None
            connection = connection or self._connect()
            try:
                connection.execute(
                    """
                    INSERT INTO llm_jobs (
                      id, organization_id, workspace_id, packet_id, task_type,
                      input_payload, observation_cutoff, operation_id, requested_model,
                      requested_model_digest, required_context_length
                    ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)
                    """,
                    (
                        job_id,
                        organization_id,
                        body.workspaceId,
                        body.packetId,
                        task_type,
                        json.dumps(payload),
                        cutoff,
                        body.operationId,
                        body.requestedModel,
                        body.requestedModelDigest,
                        body.requiredContextLength,
                    ),
                )
                if owns_connection:
                    connection.commit()
            finally:
                if owns_connection:
                    connection.close()
        else:
            with self.lock:
                self.jobs[job_id] = row
        return {"id": job_id, "state": "queued", "taskType": task_type}

    @staticmethod
    def _set_worker_tenant(connection, worker: dict) -> None:
        connection.execute(
            "SELECT set_config('app.current_organization_id', %s, false)",
            (str(worker["organization_id"]),),
        )

    def claim(
        self, worker: dict, lease_seconds: int, capabilities: WorkerClaim | None = None
    ) -> dict | None:
        lease_until = now() + timedelta(seconds=lease_seconds)
        lease_id = str(uuid4())
        digests = {
            str(x.get("digest"))
            for x in (capabilities.models if capabilities else [])
            if x.get("digest")
        }
        maximum_context = max(
            (
                int(x.get("contextLength") or 1_000_000)
                for x in (capabilities.models if capabilities else [])
            ),
            default=1_000_000,
        )
        if self.durable:
            with self._connect(tenant=False) as connection:
                with connection.transaction():
                    self._set_worker_tenant(connection, worker)
                    if capabilities:
                        payload = capabilities.model_dump(mode="json", exclude={"leaseSeconds"})
                        connection.execute(
                            """UPDATE local_worker_credentials SET capabilities=%s::jsonb,
                            capability_digest=%s,worker_version=%s,ollama_version=%s,
                            max_concurrent_jobs=%s,last_seen_at=now() WHERE id=%s""",
                            (
                                json.dumps(payload),
                                canonical_hash(payload),
                                capabilities.workerVersion,
                                capabilities.ollamaVersion,
                                capabilities.maxConcurrentJobs,
                                worker["id"],
                            ),
                        )
                    connection.execute(
                        """
                        UPDATE llm_jobs SET
                          state=CASE WHEN attempt_count>=max_attempts THEN 'dead_letter' ELSE 'queued' END,
                          claimed_by=NULL,claimed_at=NULL,lease_expires_at=NULL,
                          last_error=jsonb_build_object('code','lease_lost','retryable',attempt_count<max_attempts)
                        WHERE state='claimed' AND lease_expires_at<=now()
                        """
                    )
                    connection.execute(
                        """UPDATE ollama_review_operations o SET
                        state=CASE WHEN j.state='dead_letter' THEN 'dead_letter' ELSE 'retry_wait' END,
                        stage=CASE WHEN j.state='dead_letter' THEN 'dead_letter' ELSE 'retry_wait' END,
                        reason_code='lease_lost',updated_at=now()
                        FROM llm_jobs j WHERE j.operation_id=o.id
                        AND j.last_error->>'code'='lease_lost'
                        AND o.state IN ('leased','running','verifying','repairing')"""
                    )
                    row = connection.execute(
                        """
                        SELECT id FROM llm_jobs
                        WHERE state IN ('queued','retry_wait')
                          AND (next_attempt_at IS NULL OR next_attempt_at<=now())
                          AND attempt_count<max_attempts
                          AND (requested_model_digest IS NULL OR requested_model_digest = ANY(%s))
                          AND required_context_length<=%s
                          AND (SELECT count(*) FROM llm_jobs active
                               WHERE active.claimed_by=%s AND active.state='claimed'
                               AND active.lease_expires_at>now())<%s
                        ORDER BY created_at
                        FOR UPDATE SKIP LOCKED LIMIT 1
                        """,
                        (
                            list(digests),
                            maximum_context,
                            worker["id"],
                            capabilities.maxConcurrentJobs if capabilities else 1,
                        ),
                    ).fetchone()
                    if not row:
                        return None
                    job = connection.execute(
                        """
                        UPDATE llm_jobs SET state = 'claimed', claimed_by = %s,
                          claimed_at = now(), lease_expires_at = %s, lease_id=%s,
                          lease_generation=lease_generation+1, attempt_count=attempt_count+1
                        WHERE id = %s
                        RETURNING id, task_type, input_payload, operation_id, lease_generation,
                          attempt_count, requested_model, requested_model_digest
                        """,
                        (worker["id"], lease_until, lease_id, row["id"]),
                    ).fetchone()
                    operation = None
                    if job.get("operation_id"):
                        operation = connection.execute(
                            """UPDATE ollama_review_operations SET state='leased',stage='claimed',
                            progress=5,worker_id=%s,updated_at=now()
                            WHERE id=%s AND state IN ('queued','retry_wait')
                            RETURNING trace_id,deadline_at""",
                            (worker["id"], job["operation_id"]),
                        ).fetchone()
                    attempt = connection.execute(
                        """INSERT INTO llm_job_attempts
                        (organization_id,job_id,attempt_number,worker_id,lease_id,lease_generation,
                         lease_expires_at,model_name,model_digest,worker_version,ollama_version)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (
                            worker["organization_id"],
                            job["id"],
                            job["attempt_count"],
                            worker["id"],
                            lease_id,
                            job["lease_generation"],
                            lease_until,
                            job["requested_model"],
                            job["requested_model_digest"],
                            capabilities.workerVersion if capabilities else None,
                            capabilities.ollamaVersion if capabilities else None,
                        ),
                    ).fetchone()
                    if operation:
                        connection.execute(
                            """INSERT INTO llm_operation_events
                            (organization_id,operation_id,actor_type,actor_id,from_state,to_state,
                             reason_code,attempt_id,trace_id)
                            VALUES (%s,%s,'worker',%s,'queued','leased','compatible_worker_claimed',%s,%s)""",
                            (
                                worker["organization_id"],
                                job["operation_id"],
                                worker["id"],
                                attempt["id"],
                                operation["trace_id"],
                            ),
                        )
            record_domain_event("ollama_job_claimed", str(job["attempt_count"]))
            return {
                "id": str(job["id"]),
                "taskType": job["task_type"],
                "input": self.resolved_input(job["input_payload"]),
                "leaseExpiresAt": lease_until.isoformat(),
                "leaseId": lease_id,
                "generation": job["lease_generation"],
                "attempt": job["attempt_count"],
                "attemptId": str(attempt["id"]),
                "traceparent": operation["trace_id"] if operation else None,
                "inputHash": canonical_hash(self.resolved_input(job["input_payload"])),
                "allowedModelDigests": [job["requested_model_digest"]]
                if job["requested_model_digest"]
                else sorted(digests),
                "stageBudgets": {
                    "analystSeconds": 300,
                    "verifierSeconds": 180,
                    "repairSeconds": 180,
                },
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
                if job["organization_id"] == worker["organization_id"] and job["state"] in {
                    "queued",
                    "retry_wait",
                }:
                    if (
                        job.get("requested_model_digest")
                        and job["requested_model_digest"] not in digests
                    ):
                        continue
                    if job.get("required_context_length", 8192) > maximum_context:
                        continue
                    job.update(
                        {
                            "state": "claimed",
                            "claimed_by": worker["id"],
                            "lease_expires_at": lease_until,
                            "lease_id": lease_id,
                            "lease_generation": job.get("lease_generation", 0) + 1,
                            "attempt_count": job.get("attempt_count", 0) + 1,
                        }
                    )
                    return {
                        "id": job["id"],
                        "taskType": job["task_type"],
                        "input": self.resolved_input(job["input_payload"]),
                        "leaseExpiresAt": lease_until.isoformat(),
                        "leaseId": lease_id,
                        "generation": job["lease_generation"],
                        "attempt": job["attempt_count"],
                        "attemptId": f"attempt:{job['id']}:{job['attempt_count']}",
                        "traceparent": job["input_payload"].get("traceparent"),
                        "inputHash": canonical_hash(self.resolved_input(job["input_payload"])),
                        "allowedModelDigests": [job["requested_model_digest"]]
                        if job.get("requested_model_digest")
                        else sorted(digests),
                        "stageBudgets": {
                            "analystSeconds": 300,
                            "verifierSeconds": 180,
                            "repairSeconds": 180,
                        },
                    }
        return None

    def heartbeat(self, worker: dict, job_id: str, body: LeaseUpdate) -> bool:
        until = now() + timedelta(seconds=body.leaseSeconds)
        if self.durable:
            with self._connect(tenant=False) as connection:
                with connection.transaction():
                    self._set_worker_tenant(connection, worker)
                    result = connection.execute(
                        """UPDATE llm_jobs j SET lease_expires_at=LEAST(%s,
                        COALESCE((SELECT deadline_at FROM ollama_review_operations o WHERE o.id=j.operation_id),%s)),
                        workflow_stage=%s WHERE j.id=%s AND j.state='claimed' AND j.claimed_by=%s
                        AND j.lease_id=%s AND j.lease_generation=%s AND j.lease_expires_at>now()
                        RETURNING j.operation_id""",
                        (
                            until,
                            until,
                            body.stage,
                            job_id,
                            worker["id"],
                            body.leaseId,
                            body.generation,
                        ),
                    ).fetchone()
                    if result:
                        connection.execute(
                            """UPDATE llm_job_attempts SET last_heartbeat_at=now(),stage=%s,
                            stage_started_at=CASE WHEN stage<>%s THEN now() ELSE stage_started_at END,
                            lease_expires_at=LEAST(%s,lease_expires_at + interval '10 minutes')
                            WHERE job_id=%s AND lease_id=%s AND lease_generation=%s""",
                            (body.stage, body.stage, until, job_id, body.leaseId, body.generation),
                        )
                        if result["operation_id"]:
                            connection.execute(
                                """UPDATE ollama_review_operations SET state='running',stage=%s,
                                progress=GREATEST(progress,%s),updated_at=now()
                                WHERE id=%s AND state NOT IN ('completed','failed','expired','canceled','superseded')""",
                                (body.stage, body.progress, result["operation_id"]),
                            )
                            connection.execute(
                                """INSERT INTO llm_operation_events
                                (organization_id,operation_id,actor_type,actor_id,from_state,to_state,reason_code)
                                VALUES (%s,%s,'worker',%s,'running','running',%s)""",
                                (
                                    worker["organization_id"],
                                    result["operation_id"],
                                    worker["id"],
                                    f"progress:{body.stage}",
                                ),
                            )
            if result is None:
                record_domain_event("ollama_stale_fence_rejected", "heartbeat")
            return result is not None
        with self.lock:
            job = self.jobs.get(job_id)
            if (
                not job
                or job.get("claimed_by") != worker["id"]
                or job.get("lease_id") != body.leaseId
                or job.get("lease_generation") != body.generation
                or job.get("lease_expires_at") <= now()
            ):
                return False
            job.update(lease_expires_at=until, workflow_stage=body.stage)
            from .ollama_bridge import bridge

            bridge.progress(
                job["input_payload"].get("operationId"),
                "running",
                body.stage,
                body.progress,
                worker["id"],
            )
            return True

    def fail_job(self, worker: dict, job_id: str, body: WorkerFailure) -> bool:
        if self.durable:
            with self._connect(tenant=False) as connection:
                with connection.transaction():
                    self._set_worker_tenant(connection, worker)
                    job = connection.execute(
                        """SELECT * FROM llm_jobs WHERE id=%s AND state='claimed' AND claimed_by=%s
                        AND lease_id=%s AND lease_generation=%s FOR UPDATE""",
                        (job_id, worker["id"], body.leaseId, body.generation),
                    ).fetchone()
                    if not job:
                        return False
                    retry = body.retryable and job["attempt_count"] < job["max_attempts"]
                    base_delay = min(240, 2 ** max(1, job["attempt_count"]))
                    delay = base_delay + secrets.randbelow(max(1, base_delay))
                    terminal_state = "failed" if not body.retryable else "dead_letter"
                    connection.execute(
                        """UPDATE llm_jobs SET state=%s,last_error=%s::jsonb,claimed_by=NULL,
                        lease_expires_at=NULL,next_attempt_at=CASE WHEN %s THEN now()+(%s * interval '1 second') ELSE NULL END
                        WHERE id=%s""",
                        (
                            "retry_wait" if retry else terminal_state,
                            json.dumps(body.model_dump(mode="json")),
                            retry,
                            delay,
                            job_id,
                        ),
                    )
                    connection.execute(
                        """UPDATE llm_job_attempts SET completed_at=now(),failure_code=%s,stage='failed'
                        WHERE job_id=%s AND lease_id=%s AND lease_generation=%s""",
                        (body.code, job_id, body.leaseId, body.generation),
                    )
                    if job["operation_id"]:
                        connection.execute(
                            """UPDATE ollama_review_operations SET state=%s,stage=%s,reason_code=%s,
                            error=%s::jsonb,updated_at=now(),completed_at=CASE WHEN %s THEN NULL ELSE now() END
                            WHERE id=%s""",
                            (
                                "retry_wait" if retry else terminal_state,
                                "retry_wait" if retry else terminal_state,
                                body.code,
                                json.dumps({"code": body.code, "message": body.message}),
                                retry,
                                job["operation_id"],
                            ),
                        )
                        connection.execute(
                            """INSERT INTO llm_operation_events
                            (organization_id,operation_id,actor_type,actor_id,from_state,to_state,reason_code)
                            VALUES (%s,%s,'worker',%s,'running',%s,%s)""",
                            (
                                worker["organization_id"],
                                job["operation_id"],
                                worker["id"],
                                "retry_wait" if retry else terminal_state,
                                body.code,
                            ),
                        )
            if not retry:
                record_domain_event("ollama_job_terminal", terminal_state)
            record_domain_event("ollama_job_failure", body.code)
            return True
        with self.lock:
            job = self.jobs.get(job_id)
            if (
                not job
                or job.get("claimed_by") != worker["id"]
                or job.get("lease_id") != body.leaseId
                or job.get("lease_generation") != body.generation
            ):
                return False
            retry = body.retryable and job.get("attempt_count", 0) < job.get("max_attempts", 3)
            job.update(
                state="retry_wait" if retry else ("dead_letter" if body.retryable else "failed"),
                claimed_by=None,
                lease_expires_at=None,
                last_error=body.model_dump(mode="json"),
            )
            from .ollama_bridge import bridge

            (
                bridge.progress(
                    job["input_payload"].get("operationId"), "retry_wait", "retry_wait", 0
                )
                if retry
                else bridge.fail(
                    job["input_payload"].get("operationId"),
                    {"code": body.code, "message": body.message},
                )
            )
            if not retry:
                record_domain_event(
                    "ollama_job_terminal",
                    "dead_letter" if body.retryable else "failed",
                )
            record_domain_event("ollama_job_failure", body.code)
            return True

    def cancel_job(self, job_id: str | None):
        if not job_id:
            return
        if self.durable:
            with self._connect() as connection:
                connection.execute(
                    "UPDATE llm_jobs SET state='canceled' WHERE id=%s AND state IN ('queued','claimed')",
                    (job_id,),
                )
        else:
            with self.lock:
                if job_id in self.jobs:
                    self.jobs[job_id]["state"] = "canceled"

    @staticmethod
    def _verify_output(input_payload: dict, output: dict) -> tuple[str, float]:
        parsed = (
            SpecialistOutputV2.model_validate(output)
            if output.get("schemaVersion") == "specialist-output.v2"
            else None
        )
        cutoff = str(input_payload.get("observationCutoff") or "")
        evidence = input_payload.get("evidence", [])
        if parsed:
            identity_data = dict(input_payload.get("tickerIdentity") or {})
            identity_data.setdefault("ticker", identity_data.get("canonicalTicker", "UNRESOLVED"))
            identity = TickerIdentity.model_validate(identity_data)
            if any(detects_prompt_injection(json.dumps(item, sort_keys=True)) for item in evidence):
                return "prompt_injection_detected", 0.0
            for item in evidence:
                if item.get("subjectInstrumentId") != identity.instrumentId:
                    return "needs_human_review", 0.0
                if not _before(str(item.get("observedAt", "")), cutoff):
                    return "needs_human_review", 0.0
        computed = {}
        for raw in parsed.calculationIntents if parsed else []:
            artifact = evaluate_calculation_intent(raw, evidence)
            computed[artifact.calculationId] = artifact
        supplied = {
            item.calculationId: item
            for item in map(
                CalculationArtifact.model_validate, output.get("calculationArtifacts", [])
            )
        }
        for calculation_id, artifact in computed.items():
            if (
                calculation_id not in supplied
                or supplied[calculation_id].model_dump() != artifact.model_dump()
            ):
                return "needs_human_review", 0.0
        allowed = {
            str(item.get("evidenceId") or item.get("id"))
            for item in input_payload.get("evidence", [])
            if isinstance(item, dict) and (item.get("evidenceId") or item.get("id"))
        }
        references = set(output.get("evidenceReferences", []))
        for claim in output.get("materialClaims", []):
            references.update(str(item) for item in claim.get("supportingEvidenceIds", []))
            references.update(str(item) for item in claim.get("contradictingEvidenceIds", []))
        resolved = references.intersection(allowed)
        ratio = len(resolved) / len(references) if references else 0.0
        passed = bool(references) and references.issubset(allowed)
        if output.get("abstained") and not references:
            passed = True
        if output.get("schemaVersion") == "specialist-output.v2":
            instruction_ids = set(output.get("instructionReferences", []))
            passed = (
                passed and bool(instruction_ids) and instruction_ids.issubset(INSTRUCTION_MANIFEST)
            )
            by_id = {
                str(item.get("evidenceId") or item.get("id")): item
                for item in input_payload.get("evidence", [])
                if isinstance(item, dict)
            }
            findings = {
                str(item.get("claimId")): item
                for item in output.get("verificationFindings", [])
                if isinstance(item, dict)
            }
            for claim in output.get("materialClaims", []):
                support = [str(item) for item in claim.get("supportingEvidenceIds", [])]
                if claim.get("claimType") == "observation" and (
                    not support
                    or any(
                        by_id.get(item, {}).get("dataMode") in {"simulated", "user_asserted"}
                        for item in support
                    )
                ):
                    passed = False
                if (
                    claim.get("materiality") in {"medium", "high"}
                    and claim.get("claimType") != "opinion"
                    and not claim.get("falsifier")
                ):
                    passed = False
                if claim.get("calculationId") and claim["calculationId"] not in computed:
                    passed = False
                finding = findings.get(str(claim.get("claimId")))
                expected_status = (
                    "nonfactual_opinion"
                    if claim.get("claimType") == "opinion"
                    else "entailed"
                )
                if (
                    not finding
                    or finding.get("status") != expected_status
                    or not finding.get("deterministicChecksPassed")
                    or not set(claim.get("supportingEvidenceIds", [])).issubset(
                        set(finding.get("evidenceIds", []))
                    )
                ):
                    passed = False
        return ("passed" if passed else "needs_human_review", ratio)

    def complete(self, worker: dict, job_id: str, body: WorkerResult) -> dict | None:
        output = body.output.model_dump(mode="json", exclude_unset=True)
        if len(json.dumps(output).encode()) > 1_000_000:
            raise ValueError("Structured result exceeds the one-megabyte limit")
        output_hash = canonical_hash(output)
        if body.resultHash and body.resultHash != output_hash:
            raise ValueError("resultHash does not match the canonical structured output")
        if body.completedAt < body.startedAt:
            raise ValueError("completedAt cannot precede startedAt")
        if body.truncationDetected or body.finishReason in {"length", "max_tokens"}:
            raise ValueError("Truncated model output cannot be catalogued")
        run_id = str(uuid4())
        if self.durable:
            with self._connect(tenant=False) as connection:
                with connection.transaction():
                    self._set_worker_tenant(connection, worker)
                    job = connection.execute(
                        "SELECT * FROM llm_jobs WHERE id=%s AND claimed_by=%s FOR UPDATE",
                        (job_id, worker["id"]),
                    ).fetchone()
                    if not job:
                        return None
                    if job["state"] == "completed":
                        existing = connection.execute(
                            "SELECT id,content_hash,verification_status FROM llm_runs WHERE job_id=%s",
                            (job_id,),
                        ).fetchone()
                        if existing and existing["content_hash"] == output_hash:
                            record_domain_event("ollama_completion_replay", "identical")
                            return {
                                "runId": str(existing["id"]),
                                "verificationStatus": existing["verification_status"],
                                "citationResolution": 1.0,
                                "duplicate": True,
                            }
                        record_domain_event("ollama_completion_replay", "divergent")
                        raise CompletionConflict("conflicting duplicate completion")
                    if job["state"] != "claimed" or job["lease_expires_at"] <= now():
                        return None
                    if (job.get("operation_id") or job.get("task_type") == "correction_verification_v1") and (
                        body.leaseId != str(job.get("lease_id"))
                        or body.generation != int(job.get("lease_generation") or 0)
                    ):
                        return None
                    if job.get("requested_model_digest") and body.modelDigest != job.get(
                        "requested_model_digest"
                    ):
                        raise ValueError("executed model digest does not match the approved digest")
                    resolved_input = self.resolved_input(job["input_payload"])
                    if body.inputHash and body.inputHash != canonical_hash(resolved_input):
                        raise ValueError("inputHash does not match the immutable job snapshot")
                    verification, citation_ratio = self._verify_output(resolved_input, output)
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
                          %s, %s, %s, %s, %s, 'disconfirmation', 'ollama', 'ollama-local-worker',
                          %s, %s, %s, %s, 'disconfirmation.v1', %s, %s, %s::jsonb,
                          %s, %s, %s, %s, %s, %s, %s, %s, %s, 'valid', %s,
                          %s::jsonb, %s
                        )
                        """,
                        (
                            run_id,
                            worker["organization_id"],
                            job_id,
                            job["workspace_id"],
                            job["packet_id"],
                            body.modelName,
                            body.modelDigest,
                            body.ollamaVersion,
                            worker["id"],
                            canonical_hash(resolved_input),
                            job["observation_cutoff"],
                            json.dumps(body.parameters),
                            body.startedAt,
                            body.completedAt,
                            body.totalDurationNs,
                            body.loadDurationNs,
                            body.promptEvalCount,
                            body.promptEvalDurationNs,
                            body.evalCount,
                            body.evalDurationNs,
                            DISCONFIRMATION_SCHEMA_VERSION,
                            verification,
                            json.dumps(output),
                            output_hash,
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
                        (
                            worker["organization_id"],
                            run_id,
                            worker["organization_id"],
                            run_id,
                            citation_ratio,
                        ),
                    )
                    connection.execute(
                        """UPDATE llm_runs SET pipeline_version='evidence-grounded-adversarial.v2',
                        context_builder_version='evidence-pack-builder.v2', verifier_model_name=%s,
                        verifier_model_digest=%s, verification_findings=%s::jsonb,
                        rejected_claims=%s::jsonb, repair_lineage=%s::jsonb, finish_reason=%s,
                        truncation_detected=%s,stage_hashes=%s::jsonb,trace_id=%s WHERE id=%s""",
                        (
                            body.verifierModelName,
                            body.verifierModelDigest,
                            json.dumps(output.get("verificationFindings", [])),
                            json.dumps(output.get("rejectedClaims", [])),
                            json.dumps(output.get("repairLineage", [])),
                            body.finishReason,
                            body.truncationDetected,
                            json.dumps(body.stageHashes),
                            resolved_input.get("traceparent"),
                            run_id,
                        ),
                    )
                    from .ollama_bridge import bridge

                    completion = (
                        bridge.complete_durable(
                            connection, worker, dict(job), body, verification, run_id
                        )
                        if job.get("operation_id")
                        else {"superseded": False}
                    )
                    connection.execute(
                        """UPDATE llm_jobs SET state = %s, completed_at = now()
                        WHERE id = %s""",
                        ("superseded" if completion.get("superseded") else "completed", job_id),
                    )
        else:
            with self.lock:
                job = self.jobs.get(job_id)
                if not job or job.get("claimed_by") != worker["id"]:
                    return None
                if job["state"] == "completed":
                    existing = next(
                        (run for run in self.runs.values() if run["job_id"] == job_id), None
                    )
                    if existing and existing["content_hash"] == output_hash:
                        record_domain_event("ollama_completion_replay", "identical")
                        return {
                            "runId": existing["id"],
                            "verificationStatus": existing["verification_status"],
                            "citationResolution": existing["citation_resolution"],
                            "duplicate": True,
                        }
                    record_domain_event("ollama_completion_replay", "divergent")
                    raise CompletionConflict("conflicting duplicate completion")
                if job["state"] != "claimed":
                    return None
                if (job.get("operation_id") or job.get("task_type") == "correction_verification_v1") and (
                    body.leaseId != job.get("lease_id")
                    or body.generation != job.get("lease_generation")
                    or job.get("lease_expires_at") <= now()
                ):
                    return None
                if job.get("requested_model_digest") and body.modelDigest != job.get(
                    "requested_model_digest"
                ):
                    raise ValueError("executed model digest does not match the approved digest")
                resolved_input = self.resolved_input(job["input_payload"])
                if body.inputHash and body.inputHash != canonical_hash(resolved_input):
                    raise ValueError("inputHash does not match the immutable job snapshot")
                verification, citation_ratio = self._verify_output(resolved_input, output)
                job["state"] = "completed"
                self.runs[run_id] = {
                    "id": run_id,
                    "organization_id": worker["organization_id"],
                    "job_id": job_id,
                    "model_name": body.modelName,
                    "packet_id": job.get("packet_id"),
                    "model_digest": body.modelDigest,
                    "verification_status": verification,
                    "structured_output": output,
                    "content_hash": output_hash,
                    "citation_resolution": citation_ratio,
                    "created_at": now(),
                    "pipeline_version": "evidence-grounded-adversarial.v2",
                    "verification_findings": output.get("verificationFindings", []),
                    "rejected_claims": output.get("rejectedClaims", []),
                    "repair_lineage": output.get("repairLineage", []),
                    "stage_hashes": body.stageHashes,
                    "trace_id": resolved_input.get("traceparent"),
                }
        if not self.durable:
            from .ollama_bridge import bridge

            bridge.complete(worker, dict(job), body, verification, run_id)
        return {
            "runId": run_id,
            "verificationStatus": verification,
            "citationResolution": citation_ratio,
        }

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
            return [
                {**dict(row), "id": str(row["id"]), "job_id": str(row["job_id"])} for row in rows
            ]
        with self.lock:
            return [row for row in self.runs.values() if row["organization_id"] == organization_id]

    def verified_runs_for_packet(self, organization_id: str, packet_id: str) -> list[dict]:
        if self.durable:
            with self._connect() as connection:
                rows = connection.execute(
                    """SELECT id, packet_id, model_name, model_digest, prompt_template_id,
                    evidence_pack_hash,observation_cutoff,verification_status,structured_output,
                    content_hash,trace_id,created_at FROM llm_runs WHERE packet_id=%s
                    AND output_schema_version='specialist-output.v2' ORDER BY created_at""",
                    (packet_id,),
                ).fetchall()
            return [{**dict(row), "id": str(row["id"])} for row in rows]
        with self.lock:
            return [
                row
                for row in self.runs.values()
                if row["organization_id"] == organization_id
                and row.get("packet_id") == packet_id
                and row.get("structured_output", {}).get("schemaVersion") == "specialist-output.v2"
            ]

    def job_status(self, organization_id: str, job_id: str) -> dict | None:
        """Expose bounded completion evidence for one tenant-owned LLM job."""
        if self.durable:
            with self._connect(tenant=False) as connection:
                self._set_worker_tenant(connection, {"organization_id": organization_id})
                row = connection.execute(
                    """SELECT j.id,j.state,j.task_type,r.id AS run_id,
                    r.verification_status FROM llm_jobs j LEFT JOIN llm_runs r ON r.job_id=j.id
                    WHERE j.id=%s AND j.organization_id=%s""",
                    (job_id, organization_id),
                ).fetchone()
            if not row:
                return None
            return {
                "id": str(row["id"]), "state": row["state"],
                "taskType": row["task_type"],
                "runId": str(row["run_id"]) if row.get("run_id") else None,
                "verificationStatus": row.get("verification_status"),
            }
        job = self.jobs.get(job_id)
        if not job or job["organization_id"] != organization_id:
            return None
        run = next((value for value in self.runs.values() if value["job_id"] == job_id), None)
        return {
            "id": job_id, "state": job["state"], "taskType": job["task_type"],
            "runId": run["id"] if run else None,
            "verificationStatus": run["verification_status"] if run else None,
        }

    def correction_verification(
        self, organization_id: str, run_id: str, binding_hash: str
    ) -> dict | None:
        """Return a worker result only when its immutable input binds this correction."""
        if self.durable:
            with self._connect(tenant=False) as connection:
                self._set_worker_tenant(connection, {"organization_id": organization_id})
                row = connection.execute(
                    """SELECT r.structured_output,r.verification_status,
                    r.verifier_model_name,r.verifier_model_digest,j.input_payload
                    FROM llm_runs r JOIN llm_jobs j ON j.id=r.job_id
                    WHERE r.id=%s AND r.organization_id=%s
                      AND j.task_type='correction_verification_v1'""",
                    (run_id, organization_id),
                ).fetchone()
            if (
                not row or row["verification_status"] != "passed"
                or row["input_payload"].get("verificationBindingHash") != binding_hash
            ):
                return None
            return dict(row)
        run = self.runs.get(run_id)
        if not run or run["organization_id"] != organization_id:
            return None
        job = self.jobs.get(run["job_id"])
        if (
            not job or job["task_type"] != "correction_verification_v1"
            or job["input_payload"].get("verificationBindingHash") != binding_hash
            or run["verification_status"] != "passed"
        ):
            return None
        return {
            "structured_output": run["structured_output"],
            "verification_status": run["verification_status"],
            "verifier_model_name": run.get("model_name"),
            "verifier_model_digest": run.get("model_digest"),
            "input_payload": job["input_payload"],
        }

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
                        review_id,
                        organization_id,
                        run_id,
                        user_id,
                        body.disposition,
                        json.dumps(body.corrections),
                        body.unsupportedClaimCount,
                        body.citationIssueCount,
                        body.usefulnessScore,
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


def _worker(authorization: str | None, request: Request | None = None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Worker credential required")
    worker = catalog.authenticate_worker(
        authorization[7:].strip(), request.client.host if request and request.client else None
    )
    if not worker:
        raise HTTPException(status_code=401, detail="Worker credential is invalid or revoked")
    return worker


@router.post("/llm/workers", status_code=201)
def create_worker(body: WorkerCreate) -> dict:
    principal = _principal()
    if principal.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Owner or admin role required")
    return catalog.create_worker(principal.organization_id, principal.subject, body.name)


@router.post("/llm/worker-enrollments", status_code=201)
def create_worker_enrollment(body: WorkerEnrollmentCreate) -> dict:
    principal = _principal()
    if principal.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Owner or admin role required")
    created = catalog.create_worker(principal.organization_id, principal.subject, body.name)
    readiness = catalog.worker_readiness(
        principal.organization_id,
        body.requestedModelDigest,
        body.requiredContextLength,
    )
    return {
        "enrollmentId": created["id"],
        "workerId": created["id"],
        "workerName": created["name"],
        "token": created["token"],
        "readiness": readiness,
    }


@router.get("/llm/worker-enrollments/{enrollment_id}")
def get_worker_enrollment(
    enrollment_id: str,
    requested_model_digest: str | None = Query(default=None, alias="requestedModelDigest"),
    required_context_length: int = Query(default=8192, alias="requiredContextLength", ge=1024, le=1_000_000),
) -> dict:
    principal = _principal()
    if principal.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Owner or admin role required")
    worker = next(
        (item for item in catalog.list_workers(principal.organization_id) if str(item.get("id")) == enrollment_id),
        None,
    )
    if worker is None:
        raise HTTPException(status_code=404, detail="Worker enrollment not found")
    readiness = catalog.worker_readiness(
        principal.organization_id,
        requested_model_digest,
        required_context_length,
    )
    return {
        "enrollmentId": enrollment_id,
        "worker": worker,
        "readiness": readiness,
    }


@router.post("/llm/worker-enrollments/{enrollment_id}/rotate")
def rotate_worker_enrollment(enrollment_id: str) -> dict:
    principal = _principal()
    if principal.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Owner or admin role required")
    result = catalog.rotate_worker(principal.organization_id, enrollment_id)
    if not result:
        raise HTTPException(status_code=404, detail="Active worker enrollment not found")
    return {
        "enrollmentId": enrollment_id,
        "workerId": result["id"],
        "workerName": result["name"],
        "token": result["token"],
    }


@router.post("/llm/worker-enrollments/{enrollment_id}/canary", status_code=202)
def run_worker_enrollment_canary(enrollment_id: str, body: WorkerEnrollmentCanaryCreate) -> dict:
    principal = _principal()
    if principal.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Owner or admin role required")
    worker = next(
        (item for item in catalog.list_workers(principal.organization_id) if str(item.get("id")) == enrollment_id),
        None,
    )
    if worker is None:
        raise HTTPException(status_code=404, detail="Worker enrollment not found")
    readiness = catalog.worker_readiness(
        principal.organization_id,
        body.requestedModelDigest,
        body.requiredContextLength,
    )
    if not readiness.get("ready"):
        raise HTTPException(status_code=409, detail={"code": readiness.get("reasonCode", "worker_offline")})
    canary = catalog.enqueue(
        principal.organization_id,
        LlmJobCreate(
            workspaceId="worker-enrollment-canary",
            thesis="Canary: verify enrolled local worker can execute the governed adversarial pipeline.",
            claims=["Canary should return structured output under schema constraints."],
            evidence=[
                {
                    "id": "canary-evidence-1",
                    "title": "Synthetic canary evidence",
                    "subjectInstrumentId": "ticker:CANARY",
                    "observedAt": now().isoformat(),
                }
            ],
            observationCutoff=now(),
            role="bear",
            requestedModelDigest=body.requestedModelDigest,
            requiredContextLength=body.requiredContextLength,
        ),
    )
    return {
        "enrollmentId": enrollment_id,
        "job": canary,
        "readiness": readiness,
    }


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


@router.post("/llm/workers/{worker_id}/rotate")
def rotate_worker(worker_id: str) -> dict:
    principal = _principal()
    if principal.role not in {"owner", "admin"}:
        raise HTTPException(status_code=403, detail="Owner or admin role required")
    result = catalog.rotate_worker(principal.organization_id, worker_id)
    if not result:
        raise HTTPException(status_code=404, detail="Active worker not found")
    return result


@router.post("/llm/jobs", status_code=202)
def enqueue_job(body: LlmJobCreate) -> dict:
    principal = _principal()
    return catalog.enqueue(principal.organization_id, body)


@router.get("/llm/jobs/{job_id}")
def get_llm_job(job_id: str) -> dict:
    principal = _principal()
    result = catalog.job_status(principal.organization_id, job_id)
    if not result:
        raise HTTPException(status_code=404, detail="LLM job not found")
    return result


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
def claim_job(
    body: WorkerClaim, request: Request, authorization: str | None = Header(default=None)
) -> dict:
    worker = _worker(authorization, request)
    deadline = time.monotonic() + body.waitSeconds
    while True:
        job = catalog.claim(worker, body.leaseSeconds, body)
        if job or time.monotonic() >= deadline:
            return {"job": job}
        time.sleep(1)


@router.post("/local-worker/capabilities")
def register_worker_capabilities(
    body: WorkerCapabilities, request: Request, authorization: str | None = Header(default=None)
) -> dict:
    return catalog.register_capabilities(_worker(authorization, request), body)


@router.post("/local-worker/jobs/{job_id}/heartbeat")
def heartbeat_job(
    job_id: str,
    body: LeaseUpdate,
    request: Request,
    authorization: str | None = Header(default=None),
):
    if not catalog.heartbeat(_worker(authorization, request), job_id, body):
        raise HTTPException(409, "Job lease is invalid, fenced, or expired")
    return {"accepted": True}


@router.post("/local-worker/jobs/{job_id}/progress")
def progress_job(
    job_id: str,
    body: LeaseUpdate,
    request: Request,
    authorization: str | None = Header(default=None),
):
    return heartbeat_job(job_id, body, request, authorization)


@router.post("/local-worker/jobs/{job_id}/failure")
def failure_job(
    job_id: str,
    body: WorkerFailure,
    request: Request,
    authorization: str | None = Header(default=None),
):
    if not catalog.fail_job(_worker(authorization, request), job_id, body):
        raise HTTPException(409, "Job lease is invalid or fenced")
    return {"accepted": True, "retrying": body.retryable}


@router.post("/local-worker/jobs/{job_id}/result")
def complete_job(
    job_id: str,
    body: WorkerResult,
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict:
    worker = _worker(authorization, request)
    try:
        result = catalog.complete(worker, job_id, body)
    except CompletionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not result:
        raise HTTPException(status_code=409, detail="Job lease is invalid or expired")
    return result
