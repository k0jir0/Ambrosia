from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from .models import DecisionPacket


class ProvenanceMetadata(BaseModel):
    source: str
    sourceType: str
    timestamp: str
    freshnessSeconds: int | None = None
    dataMode: str = "fallback"
    confidence: str = "verified"
    notes: str | None = None


class DisconfirmationOutcome(BaseModel):
    status: str = Field(default="pass")
    requiresHumanReview: bool = False
    summary: str = ""
    reasons: list[str] = Field(default_factory=list)


class RiskGateOutcome(BaseModel):
    status: str = Field(default="pass")
    reasons: list[str] = Field(default_factory=list)


class DecisionMemoryRecord(BaseModel):
    memoryId: str
    packetId: str
    outcome: str
    notes: str | None = None
    score: int | None = None
    createdAt: str


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def attach_provenance(packet: DecisionPacket, provenance: list[ProvenanceMetadata]) -> DecisionPacket:
    if getattr(packet, "provenance", None) is None:
        packet.__dict__["provenance"] = []
    packet.__dict__["provenance"] = [ProvenanceMetadata.model_validate(item.model_dump(mode="json") if hasattr(item, "model_dump") else item) for item in provenance]
    return packet


def run_disconfirmation(packet: DecisionPacket) -> DisconfirmationOutcome:
    reasons: list[str] = []
    if not packet.thesis or len(packet.thesis.split()) < 4:
        reasons.append("thesis too short")
    if not packet.validation.hypothesis:
        reasons.append("validation hypothesis missing")
    if packet.confidence < 60:
        reasons.append("confidence below threshold")

    if reasons:
        return DisconfirmationOutcome(status="fail", requiresHumanReview=True, summary="Disconfirmation failed", reasons=reasons)

    return DisconfirmationOutcome(status="pass", requiresHumanReview=False, summary="Disconfirmation passed", reasons=[])


def evaluate_risk_gate(packet: DecisionPacket) -> RiskGateOutcome:
    if packet.riskMonitor is None:
        return RiskGateOutcome(status="pass", reasons=[])
    reasons: list[str] = []
    if packet.riskMonitor.concentrationRisk == "high":
        reasons.append("concentration risk is high")
    if packet.riskMonitor.varAtRisk is not None and packet.riskMonitor.varAtRisk > packet.riskMonitor.maxDrawdownThreshold:
        reasons.append("var-at-risk exceeds threshold")
    if reasons:
        return RiskGateOutcome(status="blocked", reasons=reasons)
    return RiskGateOutcome(status="pass", reasons=[])


def create_decision_memory_record(packet: DecisionPacket, *, outcome: str, notes: str | None = None, score: int | None = None) -> DecisionMemoryRecord:
    return DecisionMemoryRecord(
        memoryId=f"mem-{uuid4().hex[:10]}",
        packetId=packet.id,
        outcome=outcome,
        notes=notes,
        score=score,
        createdAt=_utc_now(),
    )


def verify_audit_chain(records: list[dict] | list[DecisionMemoryRecord], packet_id: str) -> bool:
    normalized = []
    for record in records:
        if isinstance(record, DecisionMemoryRecord):
            normalized.append(record.model_dump(mode="json"))
        else:
            normalized.append(record)

    if not normalized:
        return False

    prior_hash = None
    for record in normalized:
        payload = json.dumps({"packetId": packet_id, **record}, sort_keys=True)
        current_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if prior_hash is not None and current_hash == prior_hash:
            return False
        prior_hash = current_hash
    return True
