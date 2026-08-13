"""Asynchronous, tenant-scoped bridge from hosted reviews to outbound Ollama workers."""

from __future__ import annotations

import os
import json
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, Field

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


class Bridge:
    def __init__(self):
        self.lock = RLock()
        self.operations = {}
        self.idempotency = {}

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
                 deadline_at,trace_id,created_by,error,created_at,updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
                ON CONFLICT(id) DO UPDATE SET state=EXCLUDED.state,stage=EXCLUDED.stage,progress=EXCLUDED.progress,
                 provider_used=EXCLUDED.provider_used,model_name=EXCLUDED.model_name,model_digest=EXCLUDED.model_digest,
                 worker_id=EXCLUDED.worker_id,job_id=EXCLUDED.job_id,fallback_operation_id=EXCLUDED.fallback_operation_id,
                 result_packet_version=EXCLUDED.result_packet_version,result_hash=EXCLUDED.result_hash,
                 verification_status=EXCLUDED.verification_status,error=EXCLUDED.error,
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
                    row["createdAt"],
                    row["updatedAt"],
                ),
            )
            if owns_connection:
                connection.commit()
        finally:
            if owns_connection:
                connection.close()

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
        if not value:
            return None
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

    def create(self, packet: DecisionPacket, body: OperationCreate, key: str | None):
        tenant = self.tenant()
        if not enabled(tenant):
            raise HTTPException(503, "Ollama review bridge is disabled for this organization")
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
                updatedAt=now(),
            )
            self.persist(row)

    @staticmethod
    def result_packet(
        packet, worker, body: WorkerResult, verification, run_id, operation_id, trace_id=None
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
                    "reason": "Verified outbound local worker completion.",
                    "pipelineVersion": "evidence-grounded-adversarial.v2",
                    "operationId": operation_id,
                    "workerId": str(worker["id"]),
                    "modelName": body.modelName,
                    "modelDigest": body.modelDigest,
                    "verificationStatus": verification,
                    "verifiedRoleCount": 1 if verification == "passed" and not output.get("repairLineage") and not output.get("abstained") else 0,
                    "repairedRoleCount": 1 if output.get("repairLineage") else 0,
                    "abstainedRoleCount": 1 if output.get("abstained") else 0,
                    "humanReviewRoleCount": 0,
                    "runId": run_id,
                    "traceparent": trace_id,
                },
                "audit": [
                    *base.audit,
                    AuditEvent(
                        id=f"packet-audit-{len(base.audit) + 1}",
                        timestamp=now(),
                        eventType="agents.completed",
                        detail=f"Verified Ollama operation {operation_id} applied",
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
        if verification != "passed":
            status = "abstained" if body.output.abstained else "human_review"
            connection.execute(
                """UPDATE ollama_review_operations SET state='completed',stage='completed',progress=100,
                provider_used='ollama-local-worker',model_name=%s,model_digest=%s,worker_id=%s,
                verification_status=%s,reason_code=%s,result_hash=%s,
                updated_at=now(),completed_at=now()
                WHERE id=%s""",
                (
                    body.modelName,
                    body.modelDigest,
                    worker["id"],
                    status,
                    verification,
                    result_hash,
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
            result_packet_version=%s,result_hash=%s,updated_at=now(),completed_at=now()
            WHERE id=%s""",
            (
                body.modelName,
                body.modelDigest,
                worker["id"],
                "repaired" if body.output.repairLineage else ("abstained" if body.output.abstained else "passed"),
                updated.packetVersion,
                result_hash,
                operation_id,
            ),
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
