"""Asynchronous, tenant-scoped bridge from hosted reviews to outbound Ollama workers."""

from __future__ import annotations

import os
import json
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .artifact_store import artifact_store
from .coordinator import build_evidence_pack, run_specialists
from .llm_catalog import LlmJobCreate, WorkerResult, canonical_hash, catalog
from .models import AuditEvent, DecisionPacket, SpecialistAgentOutput
from .operations import current_principal, record_domain_event, record_domain_measurement
from .providers import resolve_provider
from .selective_integration import invalidate_integration
from .store import store

router = APIRouter(tags=["ollama-review-bridge"])
TERMINAL = {"completed", "failed", "dead_letter", "expired", "canceled", "superseded"}


class ProposalStaleError(RuntimeError):
    pass


def now():
    return datetime.now(UTC).isoformat()


def enabled(tenant: str | None = None):
    if os.getenv("OLLAMA_REVIEW_BRIDGE_ENABLED", "true").lower() not in {"1", "true", "yes", "on"}:
        return False
    allowlist = {
        item.strip()
        for item in os.getenv("OLLAMA_REVIEW_BRIDGE_ORGANIZATIONS", "").split(",")
        if item.strip()
    }
    protected = os.getenv("ENVIRONMENT", "development").lower() in {"staging", "production"}
    return bool(tenant and tenant in allowlist) if protected or allowlist else True


def traceparent():
    return f"00-{uuid4().hex}-{uuid4().hex[:16]}-01"


class OperationCreate(BaseModel):
    providerMode: Literal["ollama"] = "ollama"
    requestedModel: str | None = Field(default=None, max_length=200)
    requestedModelDigest: str | None = Field(default=None, max_length=256)
    traceparent: str | None = Field(default=None, pattern="^00-[a-f0-9]{32}-[a-f0-9]{16}-[0-9a-f]{2}$")


class OperationView(BaseModel):
    id: str
    packetId: str
    expectedPacketVersion: int
    state: str
    stage: str
    progress: int
    requestedProvider: str = "ollama"
    actualProvider: str | None = None
    jobId: str | None = None
    workerId: str | None = None
    modelName: str | None = None
    modelDigest: str | None = None
    workerName: str | None = None
    verificationStatus: str | None = None
    proposalId: str | None = None
    admissionState: str | None = None
    resultPacketVersion: int | None = None
    fallbackOperationId: str | None = None
    error: dict | None = None
    createdAt: str
    updatedAt: str
    deadlineAt: str | None = None
    operationId: str
    statusUrl: str
    cancelUrl: str
    traceparent: str


class ClaimDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claimId: str = Field(min_length=1, max_length=200)
    decision: Literal["accept_as_proposed", "accept_with_human_correction", "reject"]
    correctedText: str | None = Field(default=None, min_length=1, max_length=10_000)
    supportingEvidenceIds: list[str] | None = Field(default=None, max_length=100)
    falsifier: str | None = Field(default=None, max_length=5_000)

    @model_validator(mode="after")
    def require_correction(self):
        if self.decision == "accept_with_human_correction":
            if not self.correctedText:
                raise ValueError("correctedText is required for a corrected claim")
            if not self.supportingEvidenceIds:
                raise ValueError("A corrected claim must cite supplied evidence")
        elif self.correctedText is not None:
            raise ValueError("correctedText is allowed only for a corrected claim")
        return self


class AdmissionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposalId: str
    expectedPacketVersion: int = Field(ge=1)
    expectedProposalHash: str = Field(pattern="^[a-f0-9]{64}$")
    disposition: Literal["accepted", "corrected", "rejected"]
    claimDecisions: list[ClaimDecision] = Field(default_factory=list, max_length=40)
    rationale: str = Field(min_length=3, max_length=10_000)
    unsupportedClaimCount: int = Field(default=0, ge=0)
    citationIssueCount: int = Field(default=0, ge=0)
    usefulnessScore: int | None = Field(default=None, ge=1, le=5)

    @model_validator(mode="after")
    def disposition_matches_claim_decisions(self):
        correction_count = sum(
            item.decision == "accept_with_human_correction" for item in self.claimDecisions
        )
        accepted_count = sum(item.decision != "reject" for item in self.claimDecisions)
        if self.disposition == "corrected" and correction_count == 0:
            raise ValueError("Corrected disposition requires a corrected claim")
        if self.disposition == "accepted" and correction_count:
            raise ValueError("Accepted disposition cannot contain corrected claims")
        if self.disposition == "rejected" and accepted_count:
            raise ValueError("Rejected disposition cannot contain accepted claims")
        if self.disposition != "rejected" and self.claimDecisions and accepted_count == 0:
            raise ValueError("Admission must select at least one claim")
        return self


class RollbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expectedPacketVersion: int = Field(ge=2)
    rationale: str = Field(min_length=3, max_length=10_000)


class ProposalView(BaseModel):
    id: str
    operationId: str
    runId: str
    packetId: str
    basePacketVersion: int
    basePacketHash: str
    evidencePackHash: str
    modelName: str
    modelDigest: str
    workerId: str | None = None
    originalOutputHash: str
    proposedPatchHash: str
    originalOutput: dict
    proposedPatch: dict
    deterministicFindings: list[dict]
    admissionState: str
    resultPacketVersion: int | None = None
    rollbackPacketVersion: int | None = None
    reviewerDecisionHash: str | None = None
    evidenceSnapshot: list[dict] = Field(default_factory=list)
    reviewImpact: list[dict] = Field(default_factory=list)
    claimDecisions: list[dict] = Field(default_factory=list)
    proposalEvents: list[dict] = Field(default_factory=list)
    createdAt: str


class Bridge:
    def __init__(self):
        self.lock = RLock()
        self.operations = {}
        self.idempotency = {}
        self.proposals = {}
        self.admissions = {}
        self.proposal_events = {}
        self.rollbacks = {}

    def tenant(self):
        p = current_principal()
        return (
            p.organization_id
            if p and p.organization_id
            else os.getenv(
                "AMBROSIA_DEFAULT_ORGANIZATION_ID", "00000000-0000-0000-0000-000000000001"
            )
        )

    def public(self, row):
        value = {k: v for k, v in row.items() if k not in {"tenant", "semantic", "resultHash"}}
        value.update(
            operationId=row["id"],
            statusUrl=f"/operations/{row['id']}",
            cancelUrl=f"/operations/{row['id']}/cancel",
            traceparent=row["traceId"],
        )
        return value

    @staticmethod
    def approved_digest(tenant: str, requested: str | None) -> str:
        policies = catalog.active_model_policies(tenant)
        available = {str(item["digest"]) for item in policies}
        default = os.getenv("OLLAMA_DEFAULT_MODEL_DIGEST", "").strip()
        selected = requested or default or (next(iter(available)) if len(available) == 1 else "")
        if not selected:
            raise HTTPException(503, "No unambiguous active tenant Ollama model policy is available")
        if selected not in available:
            raise HTTPException(503, "No active tenant worker provides the approved model digest")
        return selected

    def persist(self, row, connection=None):
        """Upsert operation state before jobs reference it and after every transition."""
        if not catalog.durable:
            return
        owns_connection = connection is None
        connection = connection or catalog._connect(tenant=False)
        try:
            catalog._set_worker_tenant(connection, {"organization_id": row["tenant"]})
            connection.execute(
                """INSERT INTO ollama_review_operations
                (id,organization_id,packet_id,expected_packet_version,semantic_key_hash,idempotency_key_hash,state,stage,
                 progress,provider_requested,provider_used,input_hash,input_artifact_id,
                 requested_model_digest,model_name,model_digest,
                 worker_id,job_id,fallback_operation_id,result_packet_version,result_hash,verification_status,
                 deadline_at,trace_id,created_by,error,proposal_id,admission_state,created_at,updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)
                ON CONFLICT(id) DO UPDATE SET state=EXCLUDED.state,stage=EXCLUDED.stage,progress=EXCLUDED.progress,
                 provider_used=EXCLUDED.provider_used,model_name=EXCLUDED.model_name,model_digest=EXCLUDED.model_digest,
                 worker_id=EXCLUDED.worker_id,job_id=EXCLUDED.job_id,fallback_operation_id=EXCLUDED.fallback_operation_id,
                 result_packet_version=EXCLUDED.result_packet_version,result_hash=EXCLUDED.result_hash,
                 verification_status=EXCLUDED.verification_status,error=EXCLUDED.error,
                 proposal_id=EXCLUDED.proposal_id,admission_state=EXCLUDED.admission_state,
                 deadline_at=EXCLUDED.deadline_at,updated_at=EXCLUDED.updated_at""",
                (
                    row["id"],
                    row["tenant"],
                    row["packetId"],
                    row["expectedPacketVersion"],
                    row["semantic"],
                    canonical_hash([row["tenant"], row["createdBy"], row["idempotencyKey"]])
                    if row.get("idempotencyKey")
                    else None,
                    row["state"],
                    row["stage"],
                    row["progress"],
                    row["requestedProvider"],
                    row.get("actualProvider"),
                    row["inputHash"],
                    row.get("inputArtifactId"),
                    row.get("modelDigest"),
                    row.get("modelName"),
                    row.get("modelDigest"),
                    row.get("workerId"),
                    row.get("jobId"),
                    row.get("fallbackOperationId"),
                    row.get("resultPacketVersion"),
                    row.get("resultHash"),
                    row.get("verificationStatus"),
                    row["deadlineAt"],
                    row["traceId"],
                    row["createdBy"],
                    json.dumps(row.get("error")),
                    row.get("proposalId"),
                    row.get("admissionState"),
                    row["createdAt"],
                    row["updatedAt"],
                ),
            )
            if owns_connection:
                connection.commit()
        finally:
            if owns_connection:
                connection.close()

    def _operation_from_db(self, value, tenant):
        row = {
            "id": str(value["id"]),
            "packetId": value["packet_id"],
            "expectedPacketVersion": value["expected_packet_version"],
            "state": value["state"],
            "stage": value["stage"],
            "progress": value["progress"],
            "requestedProvider": value["provider_requested"],
            "actualProvider": value["provider_used"],
            "jobId": str(value["job_id"]) if value["job_id"] else None,
            "workerId": str(value["worker_id"]) if value["worker_id"] else None,
            "modelName": value["model_name"],
            "modelDigest": value["model_digest"],
            "workerName": value["worker_name"],
            "verificationStatus": value["verification_status"],
            "proposalId": str(value["proposal_id"]) if value.get("proposal_id") else None,
            "admissionState": value.get("admission_state"),
            "resultPacketVersion": value["result_packet_version"],
            "fallbackOperationId": str(value["fallback_operation_id"])
            if value["fallback_operation_id"]
            else None,
            "error": value["error"],
            "createdAt": value["created_at"].isoformat(),
            "updatedAt": value["updated_at"].isoformat(),
            "tenant": str(tenant),
            "semantic": value["semantic_key_hash"],
            "resultHash": value["result_hash"],
            "idempotencyKey": None,
            "inputHash": value["input_hash"],
            "inputArtifactId": str(value["input_artifact_id"])
            if value["input_artifact_id"]
            else None,
            "deadlineAt": value["deadline_at"].isoformat(),
            "traceId": value["trace_id"],
            "createdBy": value["created_by"],
        }
        with self.lock:
            self.operations[row["id"]] = row
        return row

    def hydrate(self, operation_id, tenant):
        if not catalog.durable:
            with self.lock:
                return self.operations.get(str(operation_id))
        with catalog._connect(tenant=False) as connection:
            catalog._set_worker_tenant(connection, {"organization_id": tenant})
            value = connection.execute(
                """SELECT o.*,w.name AS worker_name FROM ollama_review_operations o
                LEFT JOIN local_worker_credentials w ON w.id=o.worker_id WHERE o.id=%s""",
                (operation_id,),
            ).fetchone()
        return self._operation_from_db(value, tenant) if value else None

    def create(self, packet: DecisionPacket, body: OperationCreate, key: str | None):
        tenant = self.tenant()
        if not enabled(tenant):
            raise HTTPException(503, "Ollama review bridge is disabled for this organization")
        readiness = catalog.worker_readiness(tenant, body.requestedModelDigest)
        if not readiness["ready"]:
            raise HTTPException(
                503,
                {
                    "code": readiness["reasonCode"],
                    "message": "No active preflighted Ollama worker can claim this operation.",
                    "remediation": "Start or enroll the canary worker and complete model preflight.",
                },
            )
        principal = current_principal()
        requested_digest = self.approved_digest(tenant, body.requestedModelDigest)
        created_by = principal.subject if principal else "system"
        pack = build_evidence_pack(packet)
        pack_size = len(json.dumps(pack, default=str).encode())
        artifact_id = None
        semantic = canonical_hash(
            [
                tenant,
                packet.id,
                packet.packetVersion,
                requested_digest,
                pack["contentHash"],
                "v2",
            ]
        )
        if catalog.durable:
            with catalog._connect(tenant=False) as connection:
                catalog._set_worker_tenant(connection, {"organization_id": tenant})
                existing = connection.execute(
                    """SELECT id FROM ollama_review_operations
                    WHERE (semantic_key_hash=%s AND state NOT IN ('failed','expired','canceled','superseded'))
                       OR (%s::text IS NOT NULL AND idempotency_key_hash=%s)
                    ORDER BY created_at DESC LIMIT 1""",
                    (
                        semantic,
                        canonical_hash([tenant, created_by, key]) if key else None,
                        canonical_hash([tenant, created_by, key]) if key else None,
                    ),
                ).fetchone()
            if existing:
                record_domain_event("ollama_operation_replay", "durable")
                return self.public(self.hydrate(str(existing["id"]), tenant))
        with self.lock:
            memory_key = (tenant, created_by, key)
            if key and memory_key in self.idempotency:
                record_domain_event("ollama_operation_replay", "memory")
                return self.public(self.operations[self.idempotency[memory_key]])
            old = next(
                (
                    x
                    for x in self.operations.values()
                    if x["semantic"] == semantic
                    and x["state"] not in {"failed", "expired", "canceled"}
                ),
                None,
            )
            if old:
                return self.public(old)
            if pack_size > 512_000 and catalog.durable:
                artifact_id = artifact_store.persist_json(
                    "llm", packet.id, f"ollama-input-{packet.packetVersion}.json", pack
                ).get("artifactId")
            if pack_size > 2_000_000 and not artifact_id:
                raise HTTPException(
                    413, "Governed evidence snapshot requires durable artifact storage"
                )
            oid = str(uuid4())
            row = {
                "id": oid,
                "packetId": packet.id,
                "expectedPacketVersion": packet.packetVersion,
                "state": "queued",
                "stage": "queued",
                "progress": 0,
                "requestedProvider": "ollama",
                "actualProvider": None,
                "jobId": None,
                "workerId": None,
                "modelName": body.requestedModel,
                "modelDigest": requested_digest,
                "workerName": None,
                "verificationStatus": None,
                "proposalId": None,
                "admissionState": None,
                "resultPacketVersion": None,
                "fallbackOperationId": None,
                "error": None,
                "createdAt": now(),
                "updatedAt": now(),
                "tenant": tenant,
                "semantic": semantic,
                "resultHash": None,
                "idempotencyKey": key,
                "inputHash": pack["contentHash"],
                "inputArtifactId": artifact_id,
                "deadlineAt": (datetime.now(UTC) + timedelta(minutes=15)).isoformat(),
                "traceId": body.traceparent or traceparent(),
                "createdBy": created_by,
            }
            self.operations[oid] = row
            if key:
                self.idempotency[memory_key] = oid
        job_body = LlmJobCreate(
            packetId=packet.id,
            thesis=packet.thesis,
            claims=[c.text for c in packet.claims],
            evidence=[] if artifact_id else pack["evidence"],
            observationCutoff=pack["observationCutoff"],
            role="pmSynthesis",
            tickerIdentity=pack["tickerIdentity"],
            operationId=oid,
            expectedPacketVersion=packet.packetVersion,
            requestedModel=body.requestedModel,
            requestedModelDigest=requested_digest,
            traceparent=row["traceId"],
            inputArtifactId=artifact_id,
            inputArtifactHash=canonical_hash(pack) if artifact_id else None,
        )
        if catalog.durable:
            try:
                with catalog._connect(tenant=False) as connection:
                    with connection.transaction():
                        catalog._set_worker_tenant(connection, {"organization_id": tenant})
                        self.persist(row, connection)
                        q = catalog.enqueue(tenant, job_body, connection=connection)
                        row["jobId"] = q["id"]
                        row["updatedAt"] = now()
                        self.persist(row, connection)
                        connection.execute(
                            """INSERT INTO llm_operation_events
                            (organization_id,operation_id,actor_type,actor_id,to_state,reason_code,trace_id)
                            VALUES (%s,%s,'user',%s,'queued','provider_requested',%s)""",
                            (tenant, oid, row["createdBy"], row["traceId"]),
                        )
            except Exception:
                if artifact_id:
                    artifact_store.discard(artifact_id)
                raise
        else:
            q = catalog.enqueue(tenant, job_body)
            with self.lock:
                row["jobId"] = q["id"]
                row["updatedAt"] = now()
        record_domain_event("ollama_operation_created", "queued")
        record_domain_event(
            "ollama_evidence_disclosed", "artifact" if artifact_id else "inline"
        )
        record_domain_measurement("ollama_evidence_bytes", pack_size)
        return self.public(row)

    def get(self, oid):
        tenant = self.tenant()
        row = self.hydrate(oid, tenant)
        if (
            row
            and row["state"] not in TERMINAL
            and datetime.fromisoformat(row["deadlineAt"]) <= datetime.now(UTC)
        ):
            previous_state = row["state"]
            row.update(
                state="expired",
                stage="expired",
                error={
                    "code": "deadline_exceeded",
                    "message": "No completion arrived before the operation deadline.",
                },
                updatedAt=now(),
            )
            if catalog.durable:
                with catalog._connect(tenant=False) as connection:
                    with connection.transaction():
                        catalog._set_worker_tenant(
                            connection, {"organization_id": row["tenant"]}
                        )
                        operation = connection.execute(
                            "SELECT * FROM ollama_review_operations WHERE id=%s FOR UPDATE",
                            (oid,),
                        ).fetchone()
                        connection.execute(
                            """UPDATE llm_jobs SET state='expired',lease_expires_at=NULL,
                            last_error=jsonb_build_object('code','deadline_exceeded','retryable',false)
                            WHERE id=%s AND state NOT IN ('completed','failed','canceled','expired')""",
                            (row["jobId"],),
                        )
                        self.persist(row, connection)
                        self.event(
                            connection,
                            operation,
                            "server",
                            None,
                            previous_state,
                            "expired",
                            "deadline_exceeded",
                        )
            else:
                if row.get("jobId") in catalog.jobs:
                    catalog.jobs[row["jobId"]]["state"] = "expired"
                self.persist(row)
        return self.public(row) if row and row["tenant"] == tenant else None

    def continue_waiting(self, oid):
        row = self.hydrate(oid, self.tenant())
        if not row or row["state"] not in {"expired", "failed", "retry_wait"}:
            return None
        previous_state = row["state"]
        row.update(
            state="queued",
            stage="queued",
            progress=0,
            deadlineAt=(datetime.now(UTC) + timedelta(minutes=15)).isoformat(),
            error=None,
            updatedAt=now(),
        )
        if catalog.durable:
            with catalog._connect(tenant=False) as connection:
                with connection.transaction():
                    catalog._set_worker_tenant(connection, {"organization_id": row["tenant"]})
                    operation = connection.execute(
                        "SELECT * FROM ollama_review_operations WHERE id=%s FOR UPDATE", (oid,)
                    ).fetchone()
                    connection.execute(
                        """UPDATE llm_jobs SET state='queued',next_attempt_at=NULL,attempt_count=0,
                        claimed_by=NULL,claimed_at=NULL,lease_id=NULL,lease_expires_at=NULL,last_error=NULL
                        WHERE id=%s AND state IN ('expired','failed','retry_wait')""",
                        (row["jobId"],),
                    )
                    self.persist(row, connection)
                    self.event(
                        connection,
                        operation,
                        "user",
                        row["createdBy"],
                        previous_state,
                        "queued",
                        "continue_waiting",
                    )
        else:
            catalog.jobs[row["jobId"]]["state"] = "queued"
            catalog.jobs[row["jobId"]]["attempt_count"] = 0
            self.persist(row)
        return self.public(row)

    def list(self, pid):
        t = self.tenant()
        if catalog.durable:
            with catalog._connect(tenant=False) as connection:
                catalog._set_worker_tenant(connection, {"organization_id": t})
                ids = connection.execute(
                    "SELECT id FROM ollama_review_operations WHERE packet_id=%s ORDER BY created_at DESC",
                    (pid,),
                ).fetchall()
            return [self.public(self.hydrate(str(item["id"]), t)) for item in ids]
        with self.lock:
            return [
                self.public(x)
                for x in self.operations.values()
                if x["tenant"] == t and x["packetId"] == pid
            ]

    @staticmethod
    def _proposal_patch(output: dict) -> dict:
        """Return the allowlisted semantic patch; never accept arbitrary JSON Patch."""
        return {
            "role": output.get("role") or "pmSynthesis",
            "summary": output.get("summary") or output.get("roleConclusion") or "",
            "materialClaims": output.get("materialClaims", []),
            "verificationFindings": output.get("verificationFindings", []),
            "rejectedClaims": output.get("rejectedClaims", []),
            "missingEvidence": output.get("missingEvidence", []),
            "falsifiableConditions": output.get("falsifiableConditions", []),
            "alternativeHypotheses": output.get("alternativeHypotheses")
            or output.get("alternativeExplanations", []),
            "abstained": bool(output.get("abstained")),
            "abstentionReason": output.get("abstentionReason"),
        }

    def create_proposal(
        self, row, packet, worker, body: WorkerResult, verification, run_id, connection=None
    ) -> dict:
        output = body.output.model_dump(mode="json", exclude_unset=True)
        patch = self._proposal_patch(output)
        proposal_id = str(uuid4())
        state = "proposed" if verification == "passed" else "awaiting_human_review"
        proposal = {
            "id": proposal_id,
            "operationId": str(row["id"]),
            "runId": str(run_id),
            "packetId": packet.id,
            "basePacketVersion": packet.packetVersion,
            "basePacketHash": canonical_hash(packet.model_dump(mode="json")),
            "evidencePackHash": row["inputHash"],
            "modelName": body.modelName,
            "modelDigest": body.modelDigest or "unknown",
            "workerId": str(worker["id"]) if worker.get("id") else None,
            "pipelineVersion": "evidence-grounded-adversarial.v2",
            "promptTemplateId": "specialist.generate-verify-repair.v2",
            "outputSchemaVersion": output.get("schemaVersion", "specialist-output.v2"),
            "originalOutputHash": canonical_hash(output),
            "proposedPatchHash": canonical_hash(patch),
            "originalOutput": output,
            "proposedPatch": patch,
            "deterministicFindings": output.get("verificationFindings", []),
            "admissionState": state,
            "resultPacketVersion": None,
            "rollbackPacketVersion": None,
            "reviewerDecisionHash": None,
            "createdAt": now(),
            "tenant": str(row["tenant"]),
        }
        if connection is not None:
            connection.execute(
                """INSERT INTO llm_packet_proposals
                (id,organization_id,operation_id,run_id,packet_id,base_packet_version,
                 base_packet_hash,evidence_pack_hash,model_name,model_digest,worker_id,
                 pipeline_version,prompt_template_id,output_schema_version,original_output_hash,
                 proposed_patch_hash,original_output,proposed_patch,deterministic_findings,
                 admission_state,created_at,updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,
                        %s::jsonb,%s,%s,%s)""",
                (
                    proposal_id,
                    row["tenant"],
                    row["id"],
                    run_id,
                    packet.id,
                    packet.packetVersion,
                    proposal["basePacketHash"],
                    proposal["evidencePackHash"],
                    proposal["modelName"],
                    proposal["modelDigest"],
                    worker.get("id"),
                    proposal["pipelineVersion"],
                    proposal["promptTemplateId"],
                    proposal["outputSchemaVersion"],
                    proposal["originalOutputHash"],
                    proposal["proposedPatchHash"],
                    json.dumps(output),
                    json.dumps(patch),
                    json.dumps(proposal["deterministicFindings"]),
                    state,
                    proposal["createdAt"],
                    proposal["createdAt"],
                ),
            )
            self._proposal_event(
                proposal,
                "proposal.created",
                "server:deterministic-verifier",
                {"admissionState": state, "verification": verification},
                connection,
            )
        else:
            self._proposal_event(
                proposal,
                "proposal.created",
                "server:deterministic-verifier",
                {"admissionState": state, "verification": verification},
            )
        with self.lock:
            self.proposals[proposal_id] = proposal
        row.update(proposalId=proposal_id, admissionState=state)
        return proposal

    def get_proposal(self, operation_id: str) -> dict | None:
        tenant = self.tenant()
        if catalog.durable:
            with catalog._connect(tenant=False) as connection:
                catalog._set_worker_tenant(connection, {"organization_id": tenant})
                value = connection.execute(
                    """SELECT * FROM llm_packet_proposals
                    WHERE operation_id=%s AND organization_id=%s""",
                    (operation_id, tenant),
                ).fetchone()
            if not value:
                return None
            proposal = {
                "id": str(value["id"]),
                "operationId": str(value["operation_id"]),
                "runId": str(value["run_id"]),
                "packetId": value["packet_id"],
                "basePacketVersion": value["base_packet_version"],
                "basePacketHash": value["base_packet_hash"],
                "evidencePackHash": value["evidence_pack_hash"],
                "modelName": value["model_name"],
                "modelDigest": value["model_digest"],
                "workerId": str(value["worker_id"]) if value["worker_id"] else None,
                "pipelineVersion": value["pipeline_version"],
                "promptTemplateId": value["prompt_template_id"],
                "outputSchemaVersion": value["output_schema_version"],
                "originalOutputHash": value["original_output_hash"],
                "proposedPatchHash": value["proposed_patch_hash"],
                "originalOutput": value["original_output"],
                "proposedPatch": value["proposed_patch"],
                "deterministicFindings": value["deterministic_findings"],
                "admissionState": value["admission_state"],
                "resultPacketVersion": value["result_packet_version"],
                "rollbackPacketVersion": value.get("rollback_packet_version"),
                "reviewerDecisionHash": value.get("reviewer_decision_hash"),
                "createdAt": value["created_at"].isoformat(),
                "tenant": str(tenant),
            }
            with self.lock:
                self.proposals[proposal["id"]] = proposal
            return proposal
        operation = self.hydrate(operation_id, tenant)
        if not operation or operation["tenant"] != tenant or not operation.get("proposalId"):
            return None
        proposal = self.proposals.get(operation["proposalId"])
        return proposal if proposal and proposal["tenant"] == tenant else None

    def _proposal_event(
        self,
        proposal: dict,
        event_type: str,
        actor: str,
        payload: dict,
        connection=None,
    ) -> dict:
        events = self.proposal_events.setdefault(proposal["id"], [])
        previous_hash = events[-1]["eventHash"] if events else "0" * 64
        payload_hash = canonical_hash(payload)
        event_hash = canonical_hash(
            [proposal["id"], event_type, actor, payload_hash, previous_hash]
        )
        event = {
            "eventType": event_type,
            "actor": actor,
            "payload": payload,
            "payloadHash": payload_hash,
            "previousHash": previous_hash,
            "eventHash": event_hash,
            "createdAt": now(),
        }
        if connection is not None:
            prior = connection.execute(
                """SELECT event_hash FROM llm_proposal_events
                WHERE proposal_id=%s ORDER BY id DESC LIMIT 1 FOR UPDATE""",
                (proposal["id"],),
            ).fetchone()
            event["previousHash"] = prior["event_hash"] if prior else "0" * 64
            event["eventHash"] = canonical_hash(
                [
                    proposal["id"],
                    event_type,
                    actor,
                    payload_hash,
                    event["previousHash"],
                ]
            )
            connection.execute(
                """INSERT INTO llm_proposal_events
                (organization_id,proposal_id,event_type,actor,payload,payload_hash,
                 previous_hash,event_hash,created_at)
                VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)""",
                (
                    proposal["tenant"],
                    proposal["id"],
                    event_type,
                    actor,
                    json.dumps(payload),
                    payload_hash,
                    event["previousHash"],
                    event["eventHash"],
                    event["createdAt"],
                ),
            )
        events.append(event)
        return event

    def _proposal_review_data(self, proposal: dict) -> tuple[list[dict], list[dict], list[dict]]:
        operation = self.hydrate(proposal["operationId"], proposal["tenant"])
        evidence: list[dict] = []
        decisions: list[dict] = []
        events = list(self.proposal_events.get(proposal["id"], []))
        if catalog.durable:
            with catalog._connect(tenant=False) as connection:
                catalog._set_worker_tenant(connection, {"organization_id": proposal["tenant"]})
                job = connection.execute(
                    """SELECT j.input_payload FROM llm_jobs j
                    JOIN ollama_review_operations o ON o.job_id=j.id WHERE o.id=%s""",
                    (proposal["operationId"],),
                ).fetchone()
                decision_rows = connection.execute(
                    """SELECT claim_id,decision,original_claim_hash,corrected_claim_hash,
                    corrected_text,supporting_evidence_ids,falsifier,rationale,created_at
                    FROM llm_proposal_claim_decisions WHERE proposal_id=%s ORDER BY created_at""",
                    (proposal["id"],),
                ).fetchall()
                event_rows = connection.execute(
                    """SELECT event_type,actor,payload,payload_hash,previous_hash,event_hash,created_at
                    FROM llm_proposal_events WHERE proposal_id=%s ORDER BY id""",
                    (proposal["id"],),
                ).fetchall()
            if job:
                evidence = catalog.resolved_input(job["input_payload"]).get("evidence", [])
            decisions = [
                {
                    "claimId": row["claim_id"],
                    "decision": row["decision"],
                    "originalClaimHash": row["original_claim_hash"],
                    "correctedClaimHash": row["corrected_claim_hash"],
                    "correctedText": row["corrected_text"],
                    "supportingEvidenceIds": row["supporting_evidence_ids"],
                    "falsifier": row["falsifier"],
                    "rationale": row["rationale"],
                    "createdAt": row["created_at"].isoformat(),
                }
                for row in decision_rows
            ]
            events = [
                {
                    "eventType": row["event_type"],
                    "actor": row["actor"],
                    "payload": row["payload"],
                    "payloadHash": row["payload_hash"],
                    "previousHash": row["previous_hash"],
                    "eventHash": row["event_hash"],
                    "createdAt": row["created_at"].isoformat(),
                }
                for row in event_rows
            ]
        elif operation:
            evidence = self._memory_resolved_input(operation).get("evidence", [])
            decisions = list(proposal.get("claimDecisions", []))
        return evidence, decisions, events

    def public_proposal(self, proposal: dict) -> dict:
        value = {key: item for key, item in proposal.items() if key != "tenant"}
        evidence, decisions, events = self._proposal_review_data(proposal)
        role = str(proposal.get("proposedPatch", {}).get("role") or "pmSynthesis")
        value.update(
            evidenceSnapshot=evidence,
            claimDecisions=decisions,
            proposalEvents=events,
            reviewImpact=[
                {"claimId": claim.get("claimId"), "reportSection": role}
                for claim in proposal.get("proposedPatch", {}).get("materialClaims", [])
            ],
        )
        return value

    @staticmethod
    def _reviewed_output(proposal: dict, body: AdmissionRequest, reviewer_id: str) -> dict:
        output = json.loads(json.dumps(proposal["originalOutput"]))
        claims = {str(item.get("claimId")): item for item in output.get("materialClaims", [])}
        decisions = {item.claimId: item for item in body.claimDecisions}
        if len(decisions) != len(body.claimDecisions):
            raise HTTPException(422, "Each claim may be reviewed only once")
        unknown = set(decisions) - set(claims)
        if unknown:
            raise HTTPException(422, f"Unknown proposal claim IDs: {', '.join(sorted(unknown))}")
        if not decisions and body.disposition in {"accepted", "corrected"}:
            decisions = {
                claim_id: ClaimDecision(claimId=claim_id, decision="accept_as_proposed")
                for claim_id in claims
            }
        admitted = []
        rejected = list(output.get("rejectedClaims", []))
        findings = {
            str(item.get("claimId")): item
            for item in output.get("verificationFindings", [])
        }
        lineage = []
        human_corrected = []
        human_rejected = []
        corrected = False
        for claim_id, claim in claims.items():
            decision = decisions.get(claim_id)
            if not decision or decision.decision == "reject":
                rejected.append({**claim, "admissionStatus": "rejected"})
                human_rejected.append(
                    {
                        "claimId": claim_id,
                        "proposalId": proposal["id"],
                        "reviewerId": reviewer_id,
                        "originalClaimHash": canonical_hash(claim),
                        "originalText": claim.get("text", ""),
                        "supportingEvidenceIds": claim.get("supportingEvidenceIds", []),
                        "reason": body.rationale,
                    }
                )
                lineage.append(
                    {
                        "claimId": claim_id,
                        "decision": "reject",
                        "originalClaimHash": canonical_hash(claim),
                        "rationale": body.rationale,
                    }
                )
                continue
            item = dict(claim)
            if decision.decision == "accept_with_human_correction":
                corrected = True
                item["text"] = decision.correctedText
                if decision.supportingEvidenceIds is not None:
                    item["supportingEvidenceIds"] = decision.supportingEvidenceIds
                if decision.falsifier is not None:
                    item["falsifier"] = decision.falsifier
                item["admissionStatus"] = "human_review"
                findings[claim_id] = {
                    "claimId": claim_id,
                    "status": "entailed",
                    "evidenceIds": item.get("supportingEvidenceIds", []),
                    "reasons": [
                        "Human correction passed closed-world deterministic revalidation; "
                        "authorship remains human."
                    ],
                    "deterministicChecksPassed": True,
                    "verifier": "ambrosia-human-correction-gate.v1",
                }
                human_corrected.append(
                    {
                        "claimId": claim_id,
                        "proposalId": proposal["id"],
                        "reviewerId": reviewer_id,
                        "originalClaimHash": canonical_hash(claim),
                        "correctedClaimHash": canonical_hash(item),
                        "correctedText": item.get("text", ""),
                        "supportingEvidenceIds": item.get("supportingEvidenceIds", []),
                        "reason": body.rationale,
                    }
                )
            else:
                item["admissionStatus"] = "admitted"
            admitted.append(item)
            lineage.append(
                {
                    "claimId": claim_id,
                    "decision": decision.decision,
                    "originalClaimHash": canonical_hash(claim),
                    "correctedClaimHash": canonical_hash(item)
                    if decision.decision == "accept_with_human_correction"
                    else None,
                    "supportingEvidenceIds": item.get("supportingEvidenceIds", []),
                    "rationale": body.rationale,
                }
            )
        output["materialClaims"] = admitted
        output["rejectedClaims"] = rejected
        output["verificationFindings"] = list(findings.values())
        output["humanReviewLineage"] = lineage
        output["humanCorrectedClaims"] = human_corrected
        output["humanRejectedClaims"] = human_rejected
        if body.disposition != "rejected" and not admitted:
            raise HTTPException(422, "Admission must select at least one material claim")
        references = {
            str(reference)
            for claim in admitted
            for reference in (
                list(claim.get("supportingEvidenceIds", []))
                + list(claim.get("contradictingEvidenceIds", []))
            )
        }
        output["evidenceReferences"] = sorted(references)
        output["abstained"] = not admitted
        if not admitted:
            output["abstentionReason"] = "No model claim was admitted by the human reviewer."
        output["humanCorrectionApplied"] = corrected
        return output

    @staticmethod
    def _worker_result_from_proposal(proposal: dict, output: dict) -> WorkerResult:
        timestamp = datetime.now(UTC)
        return WorkerResult(
            modelName=proposal["modelName"],
            modelDigest=proposal["modelDigest"],
            startedAt=timestamp,
            completedAt=timestamp,
            parameters={"admissionReplay": True},
            output=output,
            resultHash=canonical_hash(output),
            finishReason="human_admission",
        )

    @staticmethod
    def _effective_decisions(proposal: dict, body: AdmissionRequest) -> list[dict]:
        supplied = {item.claimId: item.model_dump(mode="json") for item in body.claimDecisions}
        default_decision = "reject" if body.disposition == "rejected" else "accept_as_proposed"
        return [
            supplied.get(
                str(claim.get("claimId")),
                {"claimId": str(claim.get("claimId")), "decision": default_decision},
            )
            for claim in proposal.get("originalOutput", {}).get("materialClaims", [])
        ]

    def _persist_claim_decisions(
        self, connection, admission_id: str, proposal: dict, body: AdmissionRequest
    ) -> list[dict]:
        original = {
            str(item.get("claimId")): item
            for item in proposal.get("originalOutput", {}).get("materialClaims", [])
        }
        decisions = self._effective_decisions(proposal, body)
        for decision in decisions:
            claim = original[decision["claimId"]]
            corrected = (
                {
                    **claim,
                    "text": decision.get("correctedText"),
                    "supportingEvidenceIds": decision.get("supportingEvidenceIds")
                    or claim.get("supportingEvidenceIds", []),
                    "falsifier": decision.get("falsifier") or claim.get("falsifier"),
                }
                if decision["decision"] == "accept_with_human_correction"
                else None
            )
            connection.execute(
                """INSERT INTO llm_proposal_claim_decisions
                (organization_id,admission_id,proposal_id,claim_id,decision,
                 original_claim_hash,corrected_claim_hash,corrected_text,
                 supporting_evidence_ids,falsifier,rationale)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
                (
                    proposal["tenant"],
                    admission_id,
                    proposal["id"],
                    decision["claimId"],
                    decision["decision"],
                    canonical_hash(claim),
                    canonical_hash(corrected) if corrected else None,
                    decision.get("correctedText"),
                    json.dumps(
                        decision.get("supportingEvidenceIds")
                        or claim.get("supportingEvidenceIds", [])
                    ),
                    decision.get("falsifier") or claim.get("falsifier"),
                    body.rationale,
                ),
            )
        return decisions

    def _memory_resolved_input(self, operation: dict) -> dict:
        job = catalog.jobs.get(operation.get("jobId"))
        if not job:
            raise HTTPException(409, "Immutable job input is unavailable")
        return catalog.resolved_input(job["input_payload"])

    def admit(self, operation_id: str, body: AdmissionRequest, key: str | None) -> dict:
        principal = current_principal()
        if not principal or not principal.organization_id:
            raise HTTPException(401, "Tenant-bound account required")
        if principal.role not in {"analyst", "admin", "owner"}:
            raise HTTPException(403, "Analyst, admin, or owner role required")
        if body.proposalId != str(body.proposalId):
            raise HTTPException(422, "Invalid proposal ID")
        proposal = self.get_proposal(operation_id)
        if not proposal or proposal["id"] != body.proposalId:
            raise HTTPException(404, "LLM packet proposal not found")
        if body.expectedProposalHash != proposal["proposedPatchHash"]:
            raise HTTPException(409, {"code": "proposal_hash_changed"})
        if not key:
            raise HTTPException(400, "Idempotency-Key is required for proposal admission")
        request_hash = canonical_hash(body.model_dump(mode="json"))
        idempotency = (str(principal.organization_id), str(principal.subject), key)
        with self.lock:
            previous = self.admissions.get(idempotency)
            if previous:
                if previous["requestHash"] != request_hash:
                    raise HTTPException(409, {"code": "idempotency_key_reused"})
                return previous["result"]
        if body.disposition == "rejected":
            return self._reject_proposal(proposal, body, key, request_hash, principal)
        reviewed_output = self._reviewed_output(proposal, body, str(principal.subject))
        if catalog.durable:
            result = self._admit_durable(
                proposal, reviewed_output, body, key, request_hash, principal
            )
        else:
            operation = self.hydrate(operation_id, str(principal.organization_id))
            packet = store.get_packet(proposal["packetId"])
            if not operation or not packet:
                raise HTTPException(404, "Operation or packet not found")
            if (
                packet.packetVersion != body.expectedPacketVersion
                or packet.packetVersion != proposal["basePacketVersion"]
                or canonical_hash(packet.model_dump(mode="json")) != proposal["basePacketHash"]
            ):
                proposal["admissionState"] = "stale"
                operation["admissionState"] = "stale"
                self._proposal_event(
                    proposal,
                    "proposal.stale",
                    f"user:{principal.subject}",
                    {
                        "expectedPacketVersion": body.expectedPacketVersion,
                        "actualPacketVersion": packet.packetVersion,
                    },
                )
                raise HTTPException(409, {"code": "proposal_stale"})
            verification, _ = catalog._verify_output(
                self._memory_resolved_input(operation), reviewed_output
            )
            if verification != "passed":
                raise HTTPException(
                    422,
                    {
                        "code": "admission_validation_failed",
                        "verification": verification,
                    },
                )
            worker = {"id": proposal["workerId"] or "human-review"}
            worker_result = self._worker_result_from_proposal(proposal, reviewed_output)
            updated = self.result_packet(
                packet,
                worker,
                worker_result,
                "passed",
                proposal["runId"],
                operation_id,
                operation["traceId"],
                proposal_id=proposal["id"],
                admission_actor=str(principal.subject),
                admission_decisions=reviewed_output.get("humanReviewLineage", []),
            )
            saved = store.commit_packet_transition(
                updated,
                event_type="agents.human_admission.completed",
                detail=f"Human-reviewed Ollama proposal {proposal['id']} admitted exactly once.",
                actor=f"user:{principal.subject}",
            )
            state = (
                "corrected_and_admitted"
                if body.disposition == "corrected"
                else "human_admitted"
            )
            decision_hash = canonical_hash(
                [proposal["proposedPatchHash"], principal.subject, body.model_dump(mode="json")]
            )
            proposal.update(
                admissionState=state,
                resultPacketVersion=saved.packetVersion,
                reviewerDecisionHash=decision_hash,
                claimDecisions=self._effective_decisions(proposal, body),
            )
            operation.update(admissionState=state, resultPacketVersion=saved.packetVersion)
            self._proposal_event(
                proposal,
                "proposal.admitted",
                f"user:{principal.subject}",
                {
                    "decisionHash": decision_hash,
                    "resultPacketVersion": saved.packetVersion,
                    "state": state,
                },
            )
            result = self.public(operation)
        with self.lock:
            self.admissions[idempotency] = {
                "requestHash": request_hash,
                "result": result,
            }
        return result

    def _reject_proposal(self, proposal, body, key, request_hash, principal):
        state = proposal["admissionState"]
        if state in {"auto_admitted", "human_admitted", "corrected_and_admitted"}:
            raise HTTPException(409, {"code": "proposal_already_admitted"})
        if catalog.durable:
            with catalog._connect(tenant=False) as connection:
                with connection.transaction():
                    catalog._set_worker_tenant(
                        connection, {"organization_id": principal.organization_id}
                    )
                    decision_hash = canonical_hash(
                        [proposal["proposedPatchHash"], principal.subject, body.model_dump(mode="json")]
                    )
                    connection.execute(
                        """UPDATE llm_packet_proposals SET admission_state='rejected',
                        admitted_at=now(),admitted_by=%s,reviewer_decision_hash=%s,
                        updated_at=now() WHERE id=%s""",
                        (principal.subject, decision_hash, proposal["id"]),
                    )
                    admission = connection.execute(
                        """INSERT INTO llm_proposal_admissions
                        (organization_id,proposal_id,reviewer_user_id,idempotency_key_hash,
                         request_hash,disposition,claim_decisions,rationale,decision_hash,
                         unsupported_claim_count,citation_issue_count,usefulness_score)
                        VALUES (%s,%s,%s,%s,%s,'rejected',%s::jsonb,%s,%s,%s,%s,%s)
                        RETURNING id""",
                        (
                            principal.organization_id,
                            proposal["id"],
                            principal.subject,
                            canonical_hash(key),
                            request_hash,
                            json.dumps([item.model_dump() for item in body.claimDecisions]),
                            body.rationale,
                            decision_hash,
                            body.unsupportedClaimCount,
                            body.citationIssueCount,
                            body.usefulnessScore,
                        ),
                    ).fetchone()
                    self._persist_claim_decisions(
                        connection, str(admission["id"]), proposal, body
                    )
                    connection.execute(
                        """UPDATE ollama_review_operations SET admission_state='rejected',
                        updated_at=now() WHERE id=%s""",
                        (proposal["operationId"],),
                    )
                    self._proposal_event(
                        proposal,
                        "proposal.stale",
                        f"user:{principal.subject}",
                        {"expectedPacketVersion": body.expectedPacketVersion},
                        connection,
                    )
                    self._proposal_event(
                        proposal,
                        "proposal.rejected",
                        f"user:{principal.subject}",
                        {"decisionHash": decision_hash, "rationale": body.rationale},
                        connection,
                    )
        proposal["admissionState"] = "rejected"
        proposal["reviewerDecisionHash"] = canonical_hash(
            [proposal["proposedPatchHash"], principal.subject, body.model_dump(mode="json")]
        )
        proposal["claimDecisions"] = self._effective_decisions(proposal, body)
        if not catalog.durable:
            self._proposal_event(
                proposal,
                "proposal.rejected",
                f"user:{principal.subject}",
                {"decisionHash": proposal["reviewerDecisionHash"], "rationale": body.rationale},
            )
        operation = self.hydrate(proposal["operationId"], str(principal.organization_id))
        if operation:
            operation["admissionState"] = "rejected"
            self.persist(operation)
        result = self.public(operation) if operation else {"admissionState": "rejected"}
        with self.lock:
            self.admissions[(str(principal.organization_id), str(principal.subject), key)] = {
                "requestHash": request_hash,
                "result": result,
            }
        return result

    def _admit_durable(self, proposal, reviewed_output, body, key, request_hash, principal):
        try:
            return self._admit_durable_transaction(
                proposal, reviewed_output, body, key, request_hash, principal
            )
        except ProposalStaleError as exc:
            # Persist the terminal stale state in a fresh transaction; the failed
            # admission transaction must roll back every other write.
            with catalog._connect(tenant=False) as connection:
                with connection.transaction():
                    catalog._set_worker_tenant(
                        connection, {"organization_id": principal.organization_id}
                    )
                    connection.execute(
                        """UPDATE llm_packet_proposals SET admission_state='stale',
                        updated_at=now() WHERE id=%s""",
                        (proposal["id"],),
                    )
                    connection.execute(
                        """UPDATE ollama_review_operations SET admission_state='stale',
                        updated_at=now() WHERE id=%s""",
                        (proposal["operationId"],),
                    )
            raise HTTPException(409, {"code": "proposal_stale"}) from exc

    def _admit_durable_transaction(
        self, proposal, reviewed_output, body, key, request_hash, principal
    ):
        with catalog._connect(tenant=False) as connection:
            with connection.transaction():
                catalog._set_worker_tenant(
                    connection, {"organization_id": principal.organization_id}
                )
                locked = connection.execute(
                    "SELECT * FROM llm_packet_proposals WHERE id=%s FOR UPDATE",
                    (proposal["id"],),
                ).fetchone()
                existing = connection.execute(
                    """SELECT request_hash,result_packet_version FROM llm_proposal_admissions
                    WHERE organization_id=%s AND reviewer_user_id=%s AND idempotency_key_hash=%s""",
                    (principal.organization_id, principal.subject, canonical_hash(key)),
                ).fetchone()
                if existing:
                    if existing["request_hash"] != request_hash:
                        raise HTTPException(409, {"code": "idempotency_key_reused"})
                    operation_value = connection.execute(
                        """SELECT o.*,w.name AS worker_name FROM ollama_review_operations o
                        LEFT JOIN local_worker_credentials w ON w.id=o.worker_id WHERE o.id=%s""",
                        (proposal["operationId"],),
                    ).fetchone()
                    return self.public(
                        self._operation_from_db(operation_value, str(principal.organization_id))
                    )
                if not locked or locked["admission_state"] not in {
                    "proposed",
                    "awaiting_human_review",
                }:
                    raise HTTPException(409, {"code": "proposal_not_admissible"})
                packet_row = connection.execute(
                    "SELECT artifact FROM review_packet WHERE packet_id=%s FOR UPDATE",
                    (proposal["packetId"],),
                ).fetchone()
                if not packet_row:
                    raise HTTPException(404, "Packet not found")
                packet = DecisionPacket.model_validate(packet_row["artifact"])
                if (
                    packet.packetVersion != body.expectedPacketVersion
                    or packet.packetVersion != proposal["basePacketVersion"]
                    or canonical_hash(packet.model_dump(mode="json")) != proposal["basePacketHash"]
                ):
                    connection.execute(
                        """UPDATE llm_packet_proposals SET admission_state='stale',
                        updated_at=now() WHERE id=%s""",
                        (proposal["id"],),
                    )
                    connection.execute(
                        """UPDATE ollama_review_operations SET admission_state='stale',
                        updated_at=now() WHERE id=%s""",
                        (proposal["operationId"],),
                    )
                    raise ProposalStaleError
                job = connection.execute(
                    """SELECT j.* FROM llm_jobs j JOIN ollama_review_operations o ON o.job_id=j.id
                    WHERE o.id=%s""",
                    (proposal["operationId"],),
                ).fetchone()
                if not job:
                    raise HTTPException(409, "Immutable job input is unavailable")
                verification, _ = catalog._verify_output(
                    catalog.resolved_input(job["input_payload"]), reviewed_output
                )
                if verification != "passed":
                    raise HTTPException(
                        422,
                        {"code": "admission_validation_failed", "verification": verification},
                    )
                operation = connection.execute(
                    "SELECT * FROM ollama_review_operations WHERE id=%s FOR UPDATE",
                    (proposal["operationId"],),
                ).fetchone()
                worker = {"id": proposal["workerId"] or "human-review"}
                worker_result = self._worker_result_from_proposal(proposal, reviewed_output)
                updated = self.result_packet(
                    packet,
                    worker,
                    worker_result,
                    "passed",
                    proposal["runId"],
                    proposal["operationId"],
                    operation["trace_id"],
                    proposal_id=proposal["id"],
                    admission_actor=str(principal.subject),
                    admission_decisions=reviewed_output.get("humanReviewLineage", []),
                )
                packet_store = store._packet_db
                if packet_store is None:
                    raise RuntimeError("Durable packet store is unavailable")
                with connection.cursor() as cursor:
                    packet_store._save_packet_with_cursor(cursor, updated)
                    packet_store._append_packet_audit_chain_event_with_cursor(
                        cursor,
                        updated,
                        event_type="agents.human_admission.completed",
                        detail=f"Human-reviewed Ollama proposal {proposal['id']} admitted exactly once.",
                        actor=f"user:{principal.subject}",
                    )
                state = (
                    "corrected_and_admitted"
                    if body.disposition == "corrected"
                    else "human_admitted"
                )
                decision_hash = canonical_hash(
                    [
                        proposal["proposedPatchHash"],
                        principal.subject,
                        body.model_dump(mode="json"),
                    ]
                )
                connection.execute(
                    """UPDATE llm_packet_proposals SET admission_state=%s,
                    result_packet_version=%s,admitted_at=now(),admitted_by=%s,
                    reviewer_decision_hash=%s,updated_at=now()
                    WHERE id=%s""",
                    (
                        state,
                        updated.packetVersion,
                        principal.subject,
                        decision_hash,
                        proposal["id"],
                    ),
                )
                connection.execute(
                    """UPDATE ollama_review_operations SET admission_state=%s,
                    result_packet_version=%s,updated_at=now() WHERE id=%s""",
                    (state, updated.packetVersion, proposal["operationId"]),
                )
                admission = connection.execute(
                    """INSERT INTO llm_proposal_admissions
                    (organization_id,proposal_id,reviewer_user_id,idempotency_key_hash,
                     request_hash,disposition,claim_decisions,rationale,result_packet_version,
                     decision_hash,unsupported_claim_count,citation_issue_count,usefulness_score)
                    VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s,%s,%s)
                    RETURNING id""",
                    (
                        principal.organization_id,
                        proposal["id"],
                        principal.subject,
                        canonical_hash(key),
                        request_hash,
                        body.disposition,
                        json.dumps([item.model_dump() for item in body.claimDecisions]),
                        body.rationale,
                        updated.packetVersion,
                        decision_hash,
                        body.unsupportedClaimCount,
                        body.citationIssueCount,
                        body.usefulnessScore,
                    ),
                ).fetchone()
                decisions = self._persist_claim_decisions(
                    connection, str(admission["id"]), proposal, body
                )
                self._proposal_event(
                    proposal,
                    "proposal.admitted",
                    f"user:{principal.subject}",
                    {
                        "decisionHash": decision_hash,
                        "resultPacketVersion": updated.packetVersion,
                        "state": state,
                    },
                    connection,
                )
        proposal.update(
            admissionState=state,
            resultPacketVersion=updated.packetVersion,
            reviewerDecisionHash=decision_hash,
            claimDecisions=decisions,
        )
        operation_row = self.hydrate(proposal["operationId"], str(principal.organization_id))
        return self.public(operation_row)

    @staticmethod
    def _rollback_candidate(
        base: DecisionPacket,
        current: DecisionPacket,
        proposal_id: str,
        actor: str,
        rationale: str,
    ) -> DecisionPacket:
        return base.model_copy(
            deep=True,
            update={
                "packetVersion": current.packetVersion + 1,
                "audit": [
                    *current.audit,
                    AuditEvent(
                        id=f"packet-audit-{len(current.audit) + 1}",
                        timestamp=now(),
                        eventType="agents.proposal.rollback",
                        detail=(
                            f"Compensating rollback of proposal {proposal_id} by {actor}: "
                            f"{rationale}"
                        ),
                    ),
                ],
                "providerInfo": {
                    **(base.providerInfo or {}),
                    "rollbackOfProposalId": proposal_id,
                    "rollbackActor": actor,
                    "rollbackRationale": rationale,
                },
            },
        )

    def rollback(
        self, operation_id: str, body: RollbackRequest, key: str | None
    ) -> dict:
        principal = current_principal()
        if not principal or not principal.organization_id:
            raise HTTPException(401, "Tenant-bound account required")
        if principal.role not in {"admin", "owner"}:
            raise HTTPException(403, "Admin or owner role required for proposal rollback")
        if not key:
            raise HTTPException(400, "Idempotency-Key is required for proposal rollback")
        proposal = self.get_proposal(operation_id)
        if not proposal:
            raise HTTPException(404, "LLM packet proposal not found")
        request_hash = canonical_hash(body.model_dump(mode="json"))
        replay_key = (str(principal.organization_id), str(principal.subject), f"rollback:{key}")
        with self.lock:
            replay = self.rollbacks.get(replay_key)
            if replay:
                if replay["requestHash"] != request_hash:
                    raise HTTPException(409, {"code": "idempotency_key_reused"})
                return replay["result"]
        if catalog.durable:
            result = self._rollback_durable(proposal, body, key, request_hash, principal)
        else:
            if proposal["admissionState"] == "rolled_back":
                operation = self.hydrate(operation_id, str(principal.organization_id))
                return self.public(operation)
            if proposal["admissionState"] not in {
                "auto_admitted",
                "human_admitted",
                "corrected_and_admitted",
            }:
                raise HTTPException(409, {"code": "proposal_not_admitted"})
            current = store.get_packet(proposal["packetId"])
            versions = store.list_packet_versions(proposal["packetId"])
            base = next(
                (item for item in versions if item.packetVersion == proposal["basePacketVersion"]),
                None,
            )
            if not current or not base:
                raise HTTPException(409, {"code": "rollback_base_unavailable"})
            if (
                current.packetVersion != body.expectedPacketVersion
                or current.packetVersion != proposal["resultPacketVersion"]
            ):
                raise HTTPException(409, {"code": "rollback_packet_changed"})
            candidate = self._rollback_candidate(
                base, current, proposal["id"], str(principal.subject), body.rationale
            )
            saved = store.commit_packet_transition(
                candidate,
                event_type="agents.proposal.rollback",
                detail=f"Proposal {proposal['id']} compensated by packet v{candidate.packetVersion}.",
                actor=f"user:{principal.subject}",
            )
            proposal.update(
                admissionState="rolled_back", rollbackPacketVersion=saved.packetVersion
            )
            operation = self.hydrate(operation_id, str(principal.organization_id))
            operation.update(
                admissionState="rolled_back", resultPacketVersion=saved.packetVersion
            )
            self._proposal_event(
                proposal,
                "proposal.rolled_back",
                f"user:{principal.subject}",
                {
                    "revertedPacketVersion": current.packetVersion,
                    "rollbackPacketVersion": saved.packetVersion,
                    "rationale": body.rationale,
                },
            )
            result = self.public(operation)
        with self.lock:
            self.rollbacks[replay_key] = {"requestHash": request_hash, "result": result}
        return result

    def _rollback_durable(self, proposal, body, key, request_hash, principal) -> dict:
        with catalog._connect(tenant=False) as connection:
            with connection.transaction():
                catalog._set_worker_tenant(
                    connection, {"organization_id": principal.organization_id}
                )
                existing = connection.execute(
                    """SELECT request_hash,rollback_packet_version FROM llm_proposal_rollbacks
                    WHERE organization_id=%s AND reviewer_user_id=%s
                    AND idempotency_key_hash=%s""",
                    (principal.organization_id, principal.subject, canonical_hash(key)),
                ).fetchone()
                if existing:
                    if existing["request_hash"] != request_hash:
                        raise HTTPException(409, {"code": "idempotency_key_reused"})
                    operation_value = connection.execute(
                        """SELECT o.*,w.name AS worker_name FROM ollama_review_operations o
                        LEFT JOIN local_worker_credentials w ON w.id=o.worker_id WHERE o.id=%s""",
                        (proposal["operationId"],),
                    ).fetchone()
                    return self.public(
                        self._operation_from_db(operation_value, str(principal.organization_id))
                    )
                locked = connection.execute(
                    "SELECT * FROM llm_packet_proposals WHERE id=%s FOR UPDATE",
                    (proposal["id"],),
                ).fetchone()
                if not locked or locked["admission_state"] not in {
                    "auto_admitted",
                    "human_admitted",
                    "corrected_and_admitted",
                }:
                    raise HTTPException(409, {"code": "proposal_not_admitted"})
                current_row = connection.execute(
                    "SELECT artifact FROM review_packet WHERE packet_id=%s FOR UPDATE",
                    (proposal["packetId"],),
                ).fetchone()
                base_row = connection.execute(
                    """SELECT artifact FROM packet_version
                    WHERE packet_id=%s AND packet_version=%s""",
                    (proposal["packetId"], proposal["basePacketVersion"]),
                ).fetchone()
                if not current_row or not base_row:
                    raise HTTPException(409, {"code": "rollback_base_unavailable"})
                current = DecisionPacket.model_validate(current_row["artifact"])
                base = DecisionPacket.model_validate(base_row["artifact"])
                if (
                    current.packetVersion != body.expectedPacketVersion
                    or current.packetVersion != locked["result_packet_version"]
                ):
                    raise HTTPException(409, {"code": "rollback_packet_changed"})
                candidate = self._rollback_candidate(
                    base,
                    current,
                    proposal["id"],
                    str(principal.subject),
                    body.rationale,
                )
                packet_store = store._packet_db
                if packet_store is None:
                    raise RuntimeError("Durable packet store is unavailable")
                with connection.cursor() as cursor:
                    packet_store._save_packet_with_cursor(cursor, candidate)
                    packet_store._append_packet_audit_chain_event_with_cursor(
                        cursor,
                        candidate,
                        event_type="agents.proposal.rollback",
                        detail=(
                            f"Proposal {proposal['id']} compensated by packet "
                            f"v{candidate.packetVersion}."
                        ),
                        actor=f"user:{principal.subject}",
                    )
                connection.execute(
                    """INSERT INTO llm_proposal_rollbacks
                    (organization_id,proposal_id,reviewer_user_id,idempotency_key_hash,
                     request_hash,reverted_packet_version,rollback_packet_version,rationale)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (
                        principal.organization_id,
                        proposal["id"],
                        principal.subject,
                        canonical_hash(key),
                        request_hash,
                        current.packetVersion,
                        candidate.packetVersion,
                        body.rationale,
                    ),
                )
                connection.execute(
                    """UPDATE llm_packet_proposals SET admission_state='rolled_back',
                    rollback_packet_version=%s,updated_at=now() WHERE id=%s""",
                    (candidate.packetVersion, proposal["id"]),
                )
                connection.execute(
                    """UPDATE ollama_review_operations SET admission_state='rolled_back',
                    result_packet_version=%s,updated_at=now() WHERE id=%s""",
                    (candidate.packetVersion, proposal["operationId"]),
                )
                self._proposal_event(
                    proposal,
                    "proposal.rolled_back",
                    f"user:{principal.subject}",
                    {
                        "revertedPacketVersion": current.packetVersion,
                        "rollbackPacketVersion": candidate.packetVersion,
                        "rationale": body.rationale,
                    },
                    connection,
                )
        proposal.update(
            admissionState="rolled_back", rollbackPacketVersion=candidate.packetVersion
        )
        operation = self.hydrate(proposal["operationId"], str(principal.organization_id))
        return self.public(operation)

    def progress(self, oid, state, stage, progress, worker_id=None):
        if not oid:
            return
        with self.lock:
            row = self.hydrate(oid, self.tenant())
            if row and row["state"] not in TERMINAL:
                row.update(
                    state=state,
                    stage=stage,
                    progress=max(row["progress"], progress),
                    workerId=worker_id or row["workerId"],
                    updatedAt=now(),
                )
                self.persist(row)

    def fail(self, oid, error):
        if not oid:
            return
        with self.lock:
            row = self.operations.get(oid)
            if row and row["state"] not in TERMINAL:
                row.update(state="failed", stage="failed", error=error, updatedAt=now())
                self.persist(row)

    def cancel(self, oid):
        with self.lock:
            row = self.hydrate(oid, self.tenant())
            if not row or row["tenant"] != self.tenant():
                return None
            if row["state"] not in TERMINAL:
                previous_state = row["state"]
                row.update(state="canceled", stage="canceled", updatedAt=now())
                if catalog.durable:
                    with catalog._connect(tenant=False) as connection:
                        with connection.transaction():
                            catalog._set_worker_tenant(
                                connection, {"organization_id": row["tenant"]}
                            )
                            operation = connection.execute(
                                "SELECT * FROM ollama_review_operations WHERE id=%s FOR UPDATE",
                                (oid,),
                            ).fetchone()
                            connection.execute(
                                """UPDATE llm_jobs SET state='canceled',lease_expires_at=NULL
                                WHERE id=%s AND state NOT IN ('completed','failed','canceled')""",
                                (row["jobId"],),
                            )
                            self.persist(row, connection)
                            self.event(
                                connection,
                                operation,
                                "user",
                                row["createdBy"],
                                previous_state,
                                "canceled",
                                "user_canceled",
                            )
                else:
                    catalog.cancel_job(row["jobId"])
                    self.persist(row)
                record_domain_event("ollama_operation_canceled", previous_state)
            return self.public(row)

    def complete(self, worker, job, body: WorkerResult, verification, run_id):
        oid = job.get("operation_id") or job.get("input_payload", {}).get("operationId")
        if not oid:
            return
        output = body.output.model_dump(mode="json", exclude_unset=True)
        digest = canonical_hash(output)
        with self.lock:
            row = self.hydrate(str(oid), str(worker["organization_id"]))
            if not row or row["state"] in TERMINAL:
                return
            if row["resultHash"]:
                if row["resultHash"] != digest:
                    raise ValueError("conflicting duplicate completion")
                return
            row.update(
                state="verifying",
                stage="server_verification",
                progress=90,
                workerId=str(worker["id"]),
                updatedAt=now(),
            )
            self.persist(row)
        packet = store.get_packet(row["packetId"])
        if not packet:
            self.fail(str(oid), {"code": "packet_not_found", "message": "Packet no longer exists"})
            return
        if packet.packetVersion != row["expectedPacketVersion"]:
            with self.lock:
                row.update(
                    state="superseded",
                    stage="superseded",
                    error={
                        "code": "packet_version_changed",
                        "message": "Packet changed while review ran",
                    },
                    updatedAt=now(),
                )
                self.persist(row)
            record_domain_event("ollama_packet_superseded", "memory")
            return
        proposal = self.create_proposal(row, packet, worker, body, verification, run_id)
        if verification != "passed":
            row.update(
                state="completed",
                stage="completed",
                progress=100,
                actualProvider="ollama-local-worker",
                modelName=body.modelName,
                modelDigest=body.modelDigest,
                verificationStatus="abstained" if body.output.abstained else "human_review",
                resultHash=digest,
                error={
                    "code": verification,
                    "message": "Output was retained but not admitted to the packet.",
                },
                updatedAt=now(),
            )
            self.persist(row)
            return
        updated = self.result_packet(
            packet, worker, body, verification, run_id, str(oid), row["traceId"]
        )
        saved = store.commit_packet_transition(
            updated,
            event_type="agents.completed",
            detail=f"Verified Ollama operation {oid} applied exactly once.",
            actor=f"local-worker:{worker['id']}",
        )
        with self.lock:
            proposal.update(
                admissionState="auto_admitted", resultPacketVersion=saved.packetVersion
            )
            self._proposal_event(
                proposal,
                "proposal.auto_admitted",
                "server:automatic-verifier",
                {"resultPacketVersion": saved.packetVersion},
            )
            row.update(
                state="completed",
                stage="completed",
                progress=100,
                actualProvider="ollama-local-worker",
                verificationStatus=verification,
                modelName=body.modelName,
                modelDigest=body.modelDigest,
                resultPacketVersion=saved.packetVersion,
                resultHash=digest,
                admissionState="auto_admitted",
                updatedAt=now(),
            )
            self.persist(row)

    @staticmethod
    def result_packet(
        packet,
        worker,
        body: WorkerResult,
        verification,
        run_id,
        operation_id,
        trace_id=None,
        *,
        proposal_id=None,
        admission_actor=None,
        admission_decisions=None,
    ):
        output = body.output.model_dump(mode="json", exclude_unset=True)
        role = output.get("role") or "pmSynthesis"
        specialist = SpecialistAgentOutput(
            role=role,
            summary=output.get("summary")
            or output.get("roleConclusion")
            or "Verified Ollama review.",
            keyPoints=[
                c.get("text", "") for c in output.get("materialClaims", []) if c.get("text")
            ],
            timestamp=now(),
            provider="ollama-local",
            fallbackUsed=False,
            schemaVersion=output.get("schemaVersion", "specialist-output.v2"),
            direction="insufficient" if output.get("abstained") else "mixed",
            verificationStatus="abstained"
            if output.get("abstained")
            else ("repaired" if output.get("repairLineage") else "passed"),
            materialClaims=output.get("materialClaims", []),
            verificationFindings=output.get("verificationFindings", []),
            rejectedClaims=output.get("rejectedClaims", []),
            humanCorrectedClaims=output.get("humanCorrectedClaims", []),
            humanRejectedClaims=output.get("humanRejectedClaims", []),
            calculationArtifacts=output.get("calculationArtifacts", []),
            missingEvidence=output.get("missingEvidence", []),
            falsifiableConditions=output.get("falsifiableConditions", []),
            alternativeHypotheses=output.get("alternativeExplanations", []),
            abstained=output.get("abstained", False),
            abstentionReason=output.get("abstentionReason"),
            modelDigest=body.modelDigest,
            finishReason=body.finishReason,
            truncationDetected=body.truncationDetected,
        )
        base = invalidate_integration(packet, reason="Verified Ollama output changed.")
        outputs = dict(base.agentOutputs or {})
        outputs[role] = specialist
        updated = base.model_copy(
            update={
                "agentOutputs": outputs,
                "coordinatorVersion": "coordinator.v2",
                "providerInfo": {
                    "name": "Ollama Local Worker",
                    "type": "ollama",
                    "requestedProvider": "ollama",
                    "actualProvider": "ollama-local-worker",
                    "fallbackChain": [],
                    "fallbackUsed": False,
                    "reason": "Human-reviewed proposal admitted after deterministic revalidation."
                    if admission_actor
                    else "Verified outbound local worker completion.",
                    "pipelineVersion": "evidence-grounded-adversarial.v2",
                    "operationId": operation_id,
                    "workerId": str(worker["id"]),
                    "modelName": body.modelName,
                    "modelDigest": body.modelDigest,
                    "verificationStatus": verification,
                    "verifiedRoleCount": 1 if verification == "passed" and not output.get("repairLineage") and not output.get("abstained") else 0,
                    "repairedRoleCount": 1 if output.get("repairLineage") else 0,
                    "abstainedRoleCount": 1 if output.get("abstained") else 0,
                    "humanReviewRoleCount": 1 if admission_actor else 0,
                    "runId": run_id,
                    "proposalId": proposal_id,
                    "admissionActor": admission_actor,
                    "humanReviewLineage": admission_decisions or [],
                    "traceparent": trace_id,
                },
                "audit": [
                    *base.audit,
                    AuditEvent(
                        id=f"packet-audit-{len(base.audit) + 1}",
                        timestamp=now(),
                        eventType="agents.human_admission.completed"
                        if admission_actor
                        else "agents.completed",
                        detail=(
                            f"Human-reviewed proposal {proposal_id} from Ollama operation "
                            f"{operation_id} applied by {admission_actor}"
                            if admission_actor
                            else f"Verified Ollama operation {operation_id} applied"
                        ),
                    ),
                ],
            }
        )
        return updated

    def complete_durable(self, connection, worker, job, body, verification, run_id):
        """Apply packet, operation, audit, and job changes in the caller's transaction."""
        operation_id = str(job["operation_id"])
        operation = connection.execute(
            "SELECT * FROM ollama_review_operations WHERE id=%s FOR UPDATE", (operation_id,)
        ).fetchone()
        if not operation:
            raise ValueError("Ollama operation is missing")
        result_hash = canonical_hash(body.output.model_dump(mode="json", exclude_unset=True))
        if operation["state"] == "completed":
            if operation["result_hash"] != result_hash:
                raise ValueError("conflicting duplicate completion")
            return {"duplicate": True, "superseded": False}
        packet_row = connection.execute(
            "SELECT artifact FROM review_packet WHERE packet_id=%s FOR UPDATE", (job["packet_id"],)
        ).fetchone()
        if not packet_row:
            raise ValueError("Originating packet is missing")
        packet = DecisionPacket.model_validate(packet_row["artifact"])
        if packet.packetVersion != operation["expected_packet_version"]:
            connection.execute(
                """UPDATE ollama_review_operations SET state='superseded',stage='superseded',
                reason_code='packet_superseded',result_hash=%s,updated_at=now(),completed_at=now()
                WHERE id=%s""",
                (result_hash, operation_id),
            )
            self.event(
                connection,
                operation,
                "worker",
                str(worker["id"]),
                operation["state"],
                "superseded",
                "packet_superseded",
                job.get("attempt_id"),
            )
            record_domain_event("ollama_packet_superseded", "durable")
            return {"duplicate": False, "superseded": True}
        row = {
            "id": operation_id,
            "tenant": str(worker["organization_id"]),
            "inputHash": operation["input_hash"],
        }
        proposal = self.create_proposal(
            row, packet, worker, body, verification, run_id, connection=connection
        )
        if verification != "passed":
            status = "abstained" if body.output.abstained else "human_review"
            connection.execute(
                """UPDATE ollama_review_operations SET state='completed',stage='completed',progress=100,
                provider_used='ollama-local-worker',model_name=%s,model_digest=%s,worker_id=%s,
                verification_status=%s,reason_code=%s,result_hash=%s,
                proposal_id=%s,admission_state='awaiting_human_review',
                updated_at=now(),completed_at=now()
                WHERE id=%s""",
                (
                    body.modelName,
                    body.modelDigest,
                    worker["id"],
                    status,
                    verification,
                    result_hash,
                    proposal["id"],
                    operation_id,
                ),
            )
            self.event(
                connection,
                operation,
                "server",
                None,
                operation["state"],
                "completed",
                verification,
                job.get("attempt_id"),
            )
            return {"duplicate": False, "superseded": False, "rejected": True}
        updated = self.result_packet(
            packet, worker, body, verification, run_id, operation_id, operation["trace_id"]
        )
        packet_store = store._packet_db
        if packet_store is None:
            raise RuntimeError("Durable packet store is unavailable")
        with connection.cursor() as cursor:
            packet_store._save_packet_with_cursor(cursor, updated)
            packet_store._append_packet_audit_chain_event_with_cursor(
                cursor,
                updated,
                event_type="agents.completed",
                detail=f"Verified Ollama operation {operation_id} applied exactly once.",
                actor=f"local-worker:{worker['id']}",
            )
        connection.execute(
            """UPDATE ollama_review_operations SET state='completed',stage='completed',progress=100,
            provider_used='ollama-local-worker',model_name=%s,model_digest=%s,worker_id=%s,
            verification_status=%s,
            result_packet_version=%s,result_hash=%s,proposal_id=%s,
            admission_state='auto_admitted',updated_at=now(),completed_at=now()
            WHERE id=%s""",
            (
                body.modelName,
                body.modelDigest,
                worker["id"],
                "repaired" if body.output.repairLineage else ("abstained" if body.output.abstained else "passed"),
                updated.packetVersion,
                result_hash,
                proposal["id"],
                operation_id,
            ),
        )
        connection.execute(
            """UPDATE llm_packet_proposals SET admission_state='auto_admitted',
            result_packet_version=%s,admitted_at=now(),admitted_by='automatic-verifier',
            updated_at=now() WHERE id=%s""",
            (updated.packetVersion, proposal["id"]),
        )
        proposal.update(
            admissionState="auto_admitted", resultPacketVersion=updated.packetVersion
        )
        self._proposal_event(
            proposal,
            "proposal.auto_admitted",
            "server:automatic-verifier",
            {"resultPacketVersion": updated.packetVersion},
            connection,
        )
        self.event(
            connection,
            operation,
            "worker",
            str(worker["id"]),
            operation["state"],
            "completed",
            "verified_result_applied",
            job.get("attempt_id"),
        )
        return {"duplicate": False, "superseded": False}

    @staticmethod
    def event(
        connection, operation, actor_type, actor_id, from_state, to_state, reason, attempt_id=None
    ):
        connection.execute(
            """INSERT INTO llm_operation_events
            (organization_id,operation_id,actor_type,actor_id,from_state,to_state,reason_code,attempt_id,trace_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                operation["organization_id"],
                operation["id"],
                actor_type,
                actor_id,
                from_state,
                to_state,
                reason,
                attempt_id,
                operation.get("trace_id"),
            ),
        )

    def fallback(self, oid):
        with self.lock:
            original = self.hydrate(oid, self.tenant())
            if not original or original["tenant"] != self.tenant():
                return None
            if original["state"] not in {"failed", "dead_letter", "expired", "superseded"}:
                raise HTTPException(
                    409, "Deterministic fallback is available only after Ollama stops or expires"
                )
            fid = str(uuid4())
            row = {
                **original,
                "id": fid,
                "state": "running",
                "stage": "deterministic_fallback",
                "progress": 25,
                "jobId": None,
                "actualProvider": "deterministic",
                "fallbackOperationId": None,
                "createdAt": now(),
                "updatedAt": now(),
                "semantic": "fallback:" + oid,
                "resultHash": None,
            }
            self.operations[fid] = row
            original["fallbackOperationId"] = fid
        record_domain_event("ollama_explicit_fallback", original["state"])
        if catalog.durable:
            with catalog._connect(tenant=False) as connection:
                with connection.transaction():
                    catalog._set_worker_tenant(
                        connection, {"organization_id": original["tenant"]}
                    )
                    packet_row = connection.execute(
                        "SELECT artifact FROM review_packet WHERE packet_id=%s FOR UPDATE",
                        (row["packetId"],),
                    ).fetchone()
                    if not packet_row:
                        return None
                    packet = DecisionPacket.model_validate(packet_row["artifact"])
                    row["expectedPacketVersion"] = packet.packetVersion
                    selected = resolve_provider("deterministic")
                    outputs, _ = run_specialists(packet, selected)
                    base = invalidate_integration(
                        packet, reason="Explicit deterministic fallback changed."
                    )
                    updated = base.model_copy(
                        update={
                            "agentOutputs": outputs,
                            "providerInfo": {
                                "name": selected.name,
                                "type": "deterministic",
                                "requestedProvider": "ollama",
                                "actualProvider": "deterministic",
                                "fallbackChain": [],
                                "fallbackUsed": True,
                                "reason": "User explicitly requested fallback.",
                                "fallbackOperationId": fid,
                            },
                        }
                    )
                    packet_store = store._packet_db
                    if packet_store is None:
                        raise RuntimeError("Durable packet store is unavailable")
                    with connection.cursor() as cursor:
                        packet_store._save_packet_with_cursor(cursor, updated)
                        packet_store._append_packet_audit_chain_event_with_cursor(
                            cursor,
                            updated,
                            event_type="agents.fallback.completed",
                            detail=f"Explicit fallback {fid} completed",
                            actor=original["createdBy"],
                        )
                    row.update(
                        state="completed",
                        stage="completed",
                        progress=100,
                        resultPacketVersion=updated.packetVersion,
                        resultHash=canonical_hash(updated.model_dump(mode="json")),
                        updatedAt=now(),
                    )
                    self.persist(row, connection)
                    self.persist(original, connection)
                    operation = connection.execute(
                        "SELECT * FROM ollama_review_operations WHERE id=%s", (fid,)
                    ).fetchone()
                    self.event(
                        connection,
                        operation,
                        "user",
                        original["createdBy"],
                        "running",
                        "completed",
                        "explicit_deterministic_fallback",
                    )
            return self.public(row)
        with self.lock:
            self.persist(row)
            self.persist(original)
        packet = store.get_packet(row["packetId"])
        selected = resolve_provider("deterministic")
        outputs, _ = run_specialists(packet, selected)
        base = invalidate_integration(packet, reason="Explicit deterministic fallback changed.")
        saved = store.commit_packet_transition(
            base.model_copy(
                update={
                    "agentOutputs": outputs,
                    "providerInfo": {
                        "name": selected.name,
                        "type": "deterministic",
                        "requestedProvider": "ollama",
                        "actualProvider": "deterministic",
                        "fallbackChain": [],
                        "fallbackUsed": True,
                        "reason": "User explicitly requested fallback.",
                        "fallbackOperationId": fid,
                    },
                }
            ),
            event_type="agents.fallback.completed",
            detail=f"Explicit fallback {fid} completed",
        )
        with self.lock:
            row.update(
                state="completed",
                stage="completed",
                progress=100,
                resultPacketVersion=saved.packetVersion,
                resultHash=canonical_hash(saved.model_dump(mode="json")),
                updatedAt=now(),
            )
            self.persist(row)
        return self.public(row)


bridge = Bridge()


@router.post("/packets/{packet_id}/agent-operations", response_model=OperationView, status_code=202)
def create_operation(
    packet_id: str,
    body: OperationCreate,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    packet = store.get_packet(packet_id)
    if not packet:
        raise HTTPException(404, "Packet not found")
    result = bridge.create(packet, body, idempotency_key)
    response.headers["Location"] = f"/operations/{result['id']}"
    response.headers["Retry-After"] = "2"
    return result


@router.get("/agent-operations/{operation_id}", response_model=OperationView)
@router.get("/operations/{operation_id}", response_model=OperationView)
def get_operation(operation_id: str):
    result = bridge.get(operation_id)
    if not result:
        raise HTTPException(404, "Operation not found")
    return result


@router.get("/packets/{packet_id}/agent-operations")
def list_operations(packet_id: str):
    return {"operations": bridge.list(packet_id)}


@router.get("/agent-operations/{operation_id}/proposal", response_model=ProposalView)
@router.get("/operations/{operation_id}/proposal", response_model=ProposalView)
def get_operation_proposal(operation_id: str):
    proposal = bridge.get_proposal(operation_id)
    if not proposal:
        raise HTTPException(404, "LLM packet proposal not found")
    return bridge.public_proposal(proposal)


@router.post("/agent-operations/{operation_id}/admission", response_model=OperationView)
@router.post("/operations/{operation_id}/admission", response_model=OperationView)
def admit_operation_proposal(
    operation_id: str,
    body: AdmissionRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    return bridge.admit(operation_id, body, idempotency_key)


@router.post("/agent-operations/{operation_id}/rollback", response_model=OperationView)
@router.post("/operations/{operation_id}/rollback", response_model=OperationView)
def rollback_operation_proposal(
    operation_id: str,
    body: RollbackRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    return bridge.rollback(operation_id, body, idempotency_key)


@router.post("/agent-operations/{operation_id}/cancel", response_model=OperationView)
@router.post("/operations/{operation_id}/cancel", response_model=OperationView)
def cancel_operation(operation_id: str):
    result = bridge.cancel(operation_id)
    if not result:
        raise HTTPException(404, "Operation not found")
    return result


@router.post(
    "/agent-operations/{operation_id}/fallback", response_model=OperationView, status_code=202
)
@router.post("/operations/{operation_id}/fallback", response_model=OperationView, status_code=202)
def fallback_operation(operation_id: str):
    result = bridge.fallback(operation_id)
    if not result:
        raise HTTPException(404, "Operation not found")
    return result


@router.post("/operations/{operation_id}/continue", response_model=OperationView, status_code=202)
def continue_operation(operation_id: str):
    result = bridge.continue_waiting(operation_id)
    if not result:
        raise HTTPException(409, "Completed operation cannot be extended")
    return result
