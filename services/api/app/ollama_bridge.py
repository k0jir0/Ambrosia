"""Asynchronous, tenant-scoped bridge from hosted reviews to outbound Ollama workers."""

from __future__ import annotations

import os
import json
from datetime import UTC, datetime
from threading import RLock
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Response
from pydantic import BaseModel, Field

from .coordinator import build_evidence_pack, run_specialists
from .llm_catalog import LlmJobCreate, WorkerResult, canonical_hash, catalog
from .models import AuditEvent, DecisionPacket, SpecialistAgentOutput
from .operations import current_principal
from .providers import resolve_provider
from .selective_integration import invalidate_integration
from .store import store

router = APIRouter(tags=["ollama-review-bridge"])
TERMINAL = {"completed", "failed", "expired", "canceled", "superseded"}


def now():
    return datetime.now(UTC).isoformat()


def enabled():
    return os.getenv("OLLAMA_REVIEW_BRIDGE_ENABLED", "true").lower() in {"1", "true", "yes", "on"}


class OperationCreate(BaseModel):
    providerMode: Literal["ollama"] = "ollama"
    requestedModel: str | None = Field(default=None, max_length=200)
    requestedModelDigest: str | None = Field(default=None, max_length=256)


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
    resultPacketVersion: int | None = None
    fallbackOperationId: str | None = None
    error: dict | None = None
    createdAt: str
    updatedAt: str


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
        return {k: v for k, v in row.items() if k not in {"tenant", "semantic", "resultHash"}}

    def persist(self, row):
        """Upsert operation state before jobs reference it and after every transition."""
        if not catalog.durable:
            return
        with catalog._connect(tenant=False) as connection:
            catalog._set_worker_tenant(connection, {"organization_id": row["tenant"]})
            connection.execute(
                """INSERT INTO ollama_review_operations
                (id,organization_id,packet_id,expected_packet_version,semantic_key,idempotency_key,state,stage,
                 progress,requested_provider,actual_provider,requested_model_digest,model_name,model_digest,
                 worker_id,job_id,fallback_operation_id,result_packet_version,result_hash,error,created_at,updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)
                ON CONFLICT(id) DO UPDATE SET state=EXCLUDED.state,stage=EXCLUDED.stage,progress=EXCLUDED.progress,
                 actual_provider=EXCLUDED.actual_provider,model_name=EXCLUDED.model_name,model_digest=EXCLUDED.model_digest,
                 worker_id=EXCLUDED.worker_id,job_id=EXCLUDED.job_id,fallback_operation_id=EXCLUDED.fallback_operation_id,
                 result_packet_version=EXCLUDED.result_packet_version,result_hash=EXCLUDED.result_hash,error=EXCLUDED.error,
                 updated_at=EXCLUDED.updated_at""",
                (
                    row["id"],
                    row["tenant"],
                    row["packetId"],
                    row["expectedPacketVersion"],
                    row["semantic"],
                    row.get("idempotencyKey"),
                    row["state"],
                    row["stage"],
                    row["progress"],
                    row["requestedProvider"],
                    row.get("actualProvider"),
                    row.get("modelDigest"),
                    row.get("modelName"),
                    row.get("modelDigest"),
                    row.get("workerId"),
                    row.get("jobId"),
                    row.get("fallbackOperationId"),
                    row.get("resultPacketVersion"),
                    row.get("resultHash"),
                    json.dumps(row.get("error")),
                    row["createdAt"],
                    row["updatedAt"],
                ),
            )

    def hydrate(self, operation_id, tenant):
        with self.lock:
            cached = self.operations.get(str(operation_id))
            if cached:
                return cached
        if not catalog.durable:
            return None
        with catalog._connect(tenant=False) as connection:
            catalog._set_worker_tenant(connection, {"organization_id": tenant})
            value = connection.execute(
                "SELECT * FROM ollama_review_operations WHERE id=%s", (operation_id,)
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
            "requestedProvider": value["requested_provider"],
            "actualProvider": value["actual_provider"],
            "jobId": str(value["job_id"]) if value["job_id"] else None,
            "workerId": str(value["worker_id"]) if value["worker_id"] else None,
            "modelName": value["model_name"],
            "modelDigest": value["model_digest"],
            "resultPacketVersion": value["result_packet_version"],
            "fallbackOperationId": str(value["fallback_operation_id"])
            if value["fallback_operation_id"]
            else None,
            "error": value["error"],
            "createdAt": value["created_at"].isoformat(),
            "updatedAt": value["updated_at"].isoformat(),
            "tenant": str(tenant),
            "semantic": value["semantic_key"],
            "resultHash": value["result_hash"],
            "idempotencyKey": value["idempotency_key"],
        }
        with self.lock:
            self.operations[row["id"]] = row
        return row

    def create(self, packet: DecisionPacket, body: OperationCreate, key: str | None):
        if not enabled():
            raise HTTPException(503, "Ollama review bridge is disabled")
        tenant = self.tenant()
        pack = build_evidence_pack(packet)
        semantic = canonical_hash(
            [
                tenant,
                packet.id,
                packet.packetVersion,
                body.requestedModelDigest,
                pack["contentHash"],
                "v2",
            ]
        )
        with self.lock:
            if key and (tenant, key) in self.idempotency:
                return self.public(self.operations[self.idempotency[tenant, key]])
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
                "modelDigest": body.requestedModelDigest,
                "resultPacketVersion": None,
                "fallbackOperationId": None,
                "error": None,
                "createdAt": now(),
                "updatedAt": now(),
                "tenant": tenant,
                "semantic": semantic,
                "resultHash": None,
                "idempotencyKey": key,
            }
            self.operations[oid] = row
            if key:
                self.idempotency[tenant, key] = oid
        self.persist(row)
        q = catalog.enqueue(
            tenant,
            LlmJobCreate(
                packetId=packet.id,
                thesis=packet.thesis,
                claims=[c.text for c in packet.claims],
                evidence=pack["evidence"],
                observationCutoff=pack["observationCutoff"],
                role="pmSynthesis",
                tickerIdentity=pack["tickerIdentity"],
                operationId=oid,
                expectedPacketVersion=packet.packetVersion,
                requestedModel=body.requestedModel,
                requestedModelDigest=body.requestedModelDigest,
            ),
        )
        with self.lock:
            row["jobId"] = q["id"]
            row["updatedAt"] = now()
            self.persist(row)
        return self.public(row)

    def get(self, oid):
        tenant = self.tenant()
        row = self.hydrate(oid, tenant)
        return self.public(row) if row and row["tenant"] == tenant else None

    def list(self, pid):
        t = self.tenant()
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
            row = self.operations.get(oid)
            if not row or row["tenant"] != self.tenant():
                return None
            if row["state"] not in TERMINAL:
                row.update(state="canceled", stage="canceled", updatedAt=now())
                catalog.cancel_job(row["jobId"])
                self.persist(row)
            return self.public(row)

    def complete(self, worker, job, body: WorkerResult, verification, run_id):
        oid = job.get("operation_id") or job.get("input_payload", {}).get("operationId")
        if not oid:
            return
        output = body.output.model_dump(mode="json")
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
            return
        if verification != "passed":
            self.fail(
                str(oid), {"code": "verification_failed", "message": "Output requires human review"}
            )
            return
        role = output.get("role") or "pmSynthesis"
        specialist = SpecialistAgentOutput(
            role=role,
            summary=output.get("summary")
            or output.get("roleConclusion")
            or "Verified Ollama review.",
            keyPoints=[
                c.get("claimText", "")
                for c in output.get("materialClaims", [])
                if c.get("claimText")
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
                    "actualProvider": "ollama-local",
                    "fallbackChain": [],
                    "fallbackUsed": False,
                    "reason": "Verified outbound local worker completion.",
                    "pipelineVersion": "evidence-grounded-adversarial.v2",
                    "operationId": str(oid),
                    "workerId": str(worker["id"]),
                    "modelName": body.modelName,
                    "modelDigest": body.modelDigest,
                    "verificationStatus": verification,
                    "runId": run_id,
                },
                "audit": [
                    *base.audit,
                    AuditEvent(
                        id=f"packet-audit-{len(base.audit) + 1}",
                        timestamp=now(),
                        eventType="agents.completed",
                        detail=f"Verified Ollama operation {oid} applied",
                    ),
                ],
            }
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
                actualProvider="ollama-local",
                modelName=body.modelName,
                modelDigest=body.modelDigest,
                resultPacketVersion=saved.packetVersion,
                resultHash=digest,
                updatedAt=now(),
            )
            self.persist(row)

    def fallback(self, oid):
        with self.lock:
            original = self.operations.get(oid)
            if not original or original["tenant"] != self.tenant():
                return None
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
    response.headers["Location"] = f"/agent-operations/{result['id']}"
    response.headers["Retry-After"] = "2"
    return result


@router.get("/agent-operations/{operation_id}", response_model=OperationView)
def get_operation(operation_id: str):
    result = bridge.get(operation_id)
    if not result:
        raise HTTPException(404, "Operation not found")
    return result


@router.get("/packets/{packet_id}/agent-operations")
def list_operations(packet_id: str):
    return {"operations": bridge.list(packet_id)}


@router.post("/agent-operations/{operation_id}/cancel", response_model=OperationView)
def cancel_operation(operation_id: str):
    result = bridge.cancel(operation_id)
    if not result:
        raise HTTPException(404, "Operation not found")
    return result


@router.post(
    "/agent-operations/{operation_id}/fallback", response_model=OperationView, status_code=202
)
def fallback_operation(operation_id: str):
    result = bridge.fallback(operation_id)
    if not result:
        raise HTTPException(404, "Operation not found")
    return result
