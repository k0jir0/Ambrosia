from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime
from typing import Iterable
from uuid import uuid4

from .models import (
    CoverageStatus,
    DataMode,
    DecisionMemoryRecord,
    DecisionPacket,
    DisconfirmationOutcome,
    DisconfirmationStatus,
    IntegrationStage,
    MetricLineage,
    NumericCheck,
    PacketAuditChainEvent,
    PacketWorkflowStatus,
    ProvenanceMetadata,
    RiskGateOutcome,
    RiskGateStatus,
)

ZERO_HASH = "0" * 64
DISCONFIRMATION_POLICY_VERSION = "disconfirmation.v1"
RISK_POLICY_VERSION = "risk-policy.v1"
INTEGRATION_POLICY_VERSION = "selective-integration.v1"


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _sha256(payload: dict) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def packet_content_hash(packet: DecisionPacket) -> str:
    payload = packet.model_dump(mode="json")
    payload.pop("memoryRecords", None)
    return _sha256(payload)


def _provenance_envelope_id(item: ProvenanceMetadata) -> str:
    payload = item.model_dump(mode="json", exclude={"envelopeId"})
    return f"env-{_sha256(payload)[:16]}"


def _normalize_provenance(item: ProvenanceMetadata | dict) -> ProvenanceMetadata:
    normalized = ProvenanceMetadata.model_validate(
        item.model_dump(mode="json") if isinstance(item, ProvenanceMetadata) else item
    )
    stale = normalized.stale
    if (
        normalized.freshnessSeconds is not None
        and normalized.freshnessSlaSeconds is not None
        and normalized.freshnessSeconds > normalized.freshnessSlaSeconds
    ):
        stale = True
    normalized = normalized.model_copy(
        update={
            "retrievedAt": normalized.retrievedAt or _utc_now(),
            "asOf": normalized.asOf or normalized.timestamp,
            "stale": stale,
        }
    )
    if normalized.envelopeId is None:
        normalized = normalized.model_copy(update={"envelopeId": _provenance_envelope_id(normalized)})
    return normalized


def attach_provenance(
    packet: DecisionPacket,
    provenance: list[ProvenanceMetadata | dict],
    *,
    replace: bool = False,
) -> DecisionPacket:
    existing = [] if replace else list(packet.provenance)
    merged: dict[str, ProvenanceMetadata] = {}
    for item in [*existing, *provenance]:
        normalized = _normalize_provenance(item)
        merged[normalized.envelopeId or _provenance_envelope_id(normalized)] = normalized
    return packet.model_copy(update={"provenance": list(merged.values())})


def build_packet_provenance(packet: DecisionPacket) -> list[ProvenanceMetadata]:
    """Build honest packet provenance from the packet's actual source-bearing fields."""
    now = _utc_now()
    provenance: list[ProvenanceMetadata] = []

    for source in packet.sources:
        provenance.append(
            ProvenanceMetadata(
                source=source.title,
                sourceType=source.sourceType,
                timestamp=source.timestamp,
                retrievedAt=now,
                asOf=source.timestamp,
                coverageStatus=CoverageStatus.full,
                dataMode=DataMode.fallback,
                pointInTime=True,
                confidence="verified" if source.permission in {"public", "user_owned"} else "pointer_only",
                notes=f"Packet source {source.id}; permission={source.permission}",
            )
        )

    market_envelope_ids: list[str] = []
    if packet.marketSnapshot is not None:
        market = packet.marketSnapshot
        market_item = _normalize_provenance(
            ProvenanceMetadata(
                source=market.dataSource,
                sourceType="market",
                timestamp=market.timestamp,
                retrievedAt=now,
                asOf=market.timestamp,
                freshnessSeconds=market.freshnessSeconds,
                freshnessSlaSeconds=900,
                coverageStatus=CoverageStatus.full,
                dataMode=DataMode(market.dataSourceConfidence),
                pointInTime=True,
                confidence="verified" if market.dataSourceConfidence == "live" else "estimated",
                notes="Market snapshot provenance",
            )
        )
        market_envelope_ids.append(market_item.envelopeId or "")
        provenance.append(market_item)

    if packet.technicals is not None:
        technicals = packet.technicals
        provenance.append(
            ProvenanceMetadata(
                source="Ambrosia technical indicator calculator",
                sourceType="calculation",
                timestamp=technicals.updateTime,
                retrievedAt=now,
                asOf=technicals.updateTime,
                freshnessSlaSeconds=900,
                coverageStatus=CoverageStatus.full,
                dataMode=DataMode(technicals.dataMode),
                pointInTime=True,
                confidence=technicals.dataQuality,
                notes="Derived technical metrics",
                lineage=MetricLineage(
                    function="market_data.build_technicals",
                    parameters={"rsiPeriod": technicals.rsiPeriod},
                    inputEnvelopeIds=[item for item in market_envelope_ids if item],
                    codeVersion="quant-agent.v1",
                    computedAt=technicals.updateTime,
                ),
            )
        )

    if packet.sentiment is not None:
        sentiment = packet.sentiment
        provenance.append(
            ProvenanceMetadata(
                source=", ".join(sentiment.sources) if sentiment.sources else "sentiment-adapter",
                sourceType="sentiment",
                timestamp=sentiment.lastUpdated,
                retrievedAt=now,
                asOf=sentiment.lastUpdated,
                freshnessSlaSeconds=3600,
                coverageStatus=CoverageStatus.full if sentiment.sources else CoverageStatus.partial,
                dataMode=DataMode(sentiment.dataMode),
                pointInTime=True,
                confidence=sentiment.sourceConfidence,
                notes="Sentiment adapter provenance",
            )
        )

    if not provenance:
        provenance.append(
            ProvenanceMetadata(
                source="packet-input",
                sourceType="review",
                timestamp=packet.createdAt,
                retrievedAt=now,
                asOf=packet.createdAt,
                coverageStatus=CoverageStatus.partial,
                dataMode=DataMode.fallback,
                pointInTime=True,
                confidence="unverified",
                notes="Only packet-authored input is available; external evidence provenance is missing.",
            )
        )

    return [_normalize_provenance(item) for item in provenance]


def _disconfirmation_input_hash(packet: DecisionPacket) -> str:
    return _sha256(
        {
            "packetId": packet.id,
            "packetVersion": packet.packetVersion,
            "thesis": packet.thesis,
            "claims": [claim.model_dump(mode="json") for claim in packet.claims],
            "strongestCritique": packet.strongestCritique,
            "disconfirmingTest": packet.disconfirmingTest,
            "validation": packet.validation.model_dump(mode="json"),
            "sources": [source.model_dump(mode="json") for source in packet.sources],
            "provenance": [item.model_dump(mode="json") for item in packet.provenance],
            "backtestResult": packet.backtestResult.model_dump(mode="json") if packet.backtestResult else None,
            "riskMonitor": packet.riskMonitor.model_dump(mode="json") if packet.riskMonitor else None,
            "confidenceBreakdown": (
                packet.confidenceBreakdown.model_dump(mode="json")
                if packet.confidenceBreakdown
                else None
            ),
        }
    )


def _numeric_disconfirmation_checks(packet: DecisionPacket) -> list[NumericCheck]:
    checks = [
        NumericCheck(
            name="packet_confidence_contract",
            expression="0 <= confidence <= 100",
            passed=0 <= packet.confidence <= 100,
            observedValue=float(packet.confidence),
            threshold=100.0,
            notes="Recomputed from the canonical packet value.",
        )
    ]
    if packet.confidenceBreakdown is not None:
        breakdown = packet.confidenceBreakdown
        checks.append(
            NumericCheck(
                name="risk_adjustment_non_increasing",
                expression="riskAdjustedScore <= overallConfidence",
                passed=breakdown.riskAdjustedScore <= breakdown.overallConfidence,
                observedValue=float(breakdown.riskAdjustedScore),
                threshold=float(breakdown.overallConfidence),
                notes="Risk adjustment must not increase the pre-risk confidence score.",
            )
        )
    if packet.backtestResult is not None and packet.riskMonitor is not None:
        drawdown = packet.backtestResult.maxDrawdown
        if drawdown is not None:
            observed_drawdown = abs(float(drawdown))
            threshold = float(packet.riskMonitor.maxDrawdownThreshold)
            checks.append(
                NumericCheck(
                    name="backtest_drawdown_within_declared_limit",
                    expression="abs(backtest.maxDrawdown) <= riskMonitor.maxDrawdownThreshold",
                    passed=observed_drawdown <= threshold,
                    observedValue=observed_drawdown,
                    threshold=threshold,
                    notes="Recomputed using absolute drawdown magnitude and the packet risk limit.",
                )
            )
    return checks


def run_disconfirmation(packet: DecisionPacket) -> DisconfirmationOutcome:
    missing: list[str] = []
    reasons: list[str] = []

    if not packet.thesis or len(packet.thesis.split()) < 4:
        missing.append("thesis is too short to falsify")
    if not packet.validation.hypothesis.strip():
        missing.append("validation hypothesis is missing")
    if not packet.validation.nullHypothesis.strip():
        missing.append("null hypothesis is missing")
    if not packet.disconfirmingTest or len(packet.disconfirmingTest.split()) < 6:
        missing.append("disconfirming test is not operationally specific")
    if not packet.claims:
        missing.append("no claims are available to test")
    if not packet.provenance:
        missing.append("evidence provenance is missing")
    elif all(item.coverageStatus == CoverageStatus.unavailable for item in packet.provenance):
        missing.append("all evidence provenance is unavailable")

    sourced_without_evidence = [
        claim.id for claim in packet.claims if claim.kind == "sourced" and not (claim.evidence or "").strip()
    ]
    if sourced_without_evidence:
        missing.append(
            "sourced claims missing evidence: " + ", ".join(sorted(sourced_without_evidence))
        )

    contradictions = [claim.text for claim in packet.claims if claim.kind == "contradiction"]
    if packet.validation.status == "refused":
        reasons.append(packet.validation.refusalReason or "validation was refused")

    if contradictions:
        status = DisconfirmationStatus.requires_human_review
        reasons.append("contradictory evidence requires human review")
    elif packet.validation.status == "refused":
        status = DisconfirmationStatus.failed
    elif missing:
        status = DisconfirmationStatus.insufficient_evidence
        reasons.extend(missing)
    else:
        status = DisconfirmationStatus.passed

    requires_human_review = status != DisconfirmationStatus.passed
    summary_by_status = {
        DisconfirmationStatus.passed: "Disconfirmation completed with traceable evidence and a falsifiable test.",
        DisconfirmationStatus.failed: "Disconfirmation failed because validation refused the proposed test.",
        DisconfirmationStatus.insufficient_evidence: "Disconfirmation could not complete because required evidence is missing.",
        DisconfirmationStatus.requires_human_review: "Disconfirmation found contradictory evidence requiring human judgment.",
        DisconfirmationStatus.not_run: "Disconfirmation has not run.",
    }

    evidence_references = [source.id for source in packet.sources]
    evidence_references.extend(
        item.envelopeId for item in packet.provenance if item.envelopeId is not None
    )

    return DisconfirmationOutcome(
        status=status,
        requiresHumanReview=requires_human_review,
        summary=summary_by_status[status],
        reasons=reasons,
        claimsTested=[claim.id for claim in packet.claims],
        falsifiableConditions=[
            value
            for value in [packet.disconfirmingTest, packet.validation.nullHypothesis]
            if value.strip()
        ],
        alternativeExplanations=[
            value
            for value in [packet.strongestCritique, packet.historicalAnalogue.differences]
            if value.strip()
        ],
        evidenceReferences=evidence_references,
        contradictions=contradictions,
        missingEvidence=missing,
        numericChecks=_numeric_disconfirmation_checks(packet),
        evaluator="ambrosia-deterministic",
        policyVersion=DISCONFIRMATION_POLICY_VERSION,
        packetVersion=packet.packetVersion,
        evaluatedAt=_utc_now(),
        inputHash=_disconfirmation_input_hash(packet),
    )


def _risk_input_hash(packet: DecisionPacket) -> str:
    return _sha256(
        {
            "packetId": packet.id,
            "packetVersion": packet.packetVersion,
            "riskMonitor": packet.riskMonitor.model_dump(mode="json") if packet.riskMonitor else None,
            "portfolioContext": packet.portfolioContext.model_dump(mode="json") if packet.portfolioContext else None,
            "provenance": [item.model_dump(mode="json") for item in packet.provenance],
        }
    )


def evaluate_risk_gate(packet: DecisionPacket) -> RiskGateOutcome:
    missing_inputs: list[str] = []
    warnings: list[str] = []
    hard_blocks: list[str] = []

    monitor = packet.riskMonitor
    if monitor is None:
        missing_inputs.append("riskMonitor")
    else:
        if monitor.activePositionSize < 0:
            missing_inputs.append("riskMonitor.activePositionSize must be non-negative")
        elif monitor.activePositionSize > 0.15:
            hard_blocks.append("active position size exceeds the 15% policy limit")
        elif monitor.activePositionSize > 0.10:
            warnings.append("active position size exceeds the 10% warning threshold")

        if monitor.concentrationRisk == "high":
            hard_blocks.append("concentration risk is high")
        elif monitor.concentrationRisk == "medium":
            warnings.append("concentration risk is medium")

        if monitor.maxDrawdownThreshold <= 0:
            missing_inputs.append("riskMonitor.maxDrawdownThreshold must be positive")
        if monitor.varAtRisk is None:
            missing_inputs.append("riskMonitor.varAtRisk")
        elif monitor.varAtRisk > monitor.maxDrawdownThreshold:
            hard_blocks.append("var-at-risk exceeds the max-drawdown threshold")

        if monitor.status == "alert":
            hard_blocks.append("risk monitor is in alert state")
        if len(monitor.correlationOverlap) >= 3:
            warnings.append("three or more correlated positions overlap with this packet")

    portfolio = packet.portfolioContext
    if portfolio is not None:
        if portfolio.riskBudgetRemaining <= 0:
            hard_blocks.append("portfolio risk budget is exhausted")
        if portfolio.grossExposure > 2.0:
            hard_blocks.append("gross exposure exceeds the 2.0 policy limit")
        if abs(portfolio.netExposure) > 1.5:
            hard_blocks.append("absolute net exposure exceeds the 1.5 policy limit")
        if len(portfolio.factorOverlap) >= 3:
            warnings.append("portfolio has material factor overlap")

    if not packet.provenance:
        missing_inputs.append("provenance")
    elif any(item.stale and item.sourceType in {"market", "calculation"} for item in packet.provenance):
        hard_blocks.append("required market or calculation provenance is stale")
    elif any(item.coverageStatus == CoverageStatus.partial for item in packet.provenance):
        warnings.append("packet provenance coverage is partial")

    if hard_blocks:
        status = RiskGateStatus.blocked
    elif missing_inputs:
        status = RiskGateStatus.insufficient_data
    elif warnings:
        status = RiskGateStatus.warning
    else:
        status = RiskGateStatus.passed

    reasons = [*hard_blocks, *missing_inputs, *warnings]
    return RiskGateOutcome(
        status=status,
        reasons=reasons,
        warnings=warnings,
        hardBlocks=hard_blocks,
        missingInputs=missing_inputs,
        evaluator="ambrosia-deterministic",
        policyVersion=RISK_POLICY_VERSION,
        packetVersion=packet.packetVersion,
        evaluatedAt=_utc_now(),
        inputHash=_risk_input_hash(packet),
    )


def _memory_hash_payload(record: DecisionMemoryRecord) -> dict:
    return record.model_dump(mode="json", exclude={"eventHash"})


def create_decision_memory_record(
    packet: DecisionPacket,
    *,
    outcome: str,
    notes: str | None = None,
    score: int | None = None,
    record_type: str = "checkpoint",
    observed_at: str | None = None,
    evidence_references: list[str] | None = None,
    previous_record: DecisionMemoryRecord | None = None,
) -> DecisionMemoryRecord:
    sequence = previous_record.sequence + 1 if previous_record else 1
    previous_hash = previous_record.eventHash if previous_record else ZERO_HASH
    record = DecisionMemoryRecord(
        memoryId=f"mem-{uuid4().hex[:10]}",
        packetId=packet.id,
        packetVersion=packet.packetVersion,
        recordType=record_type,
        outcome=outcome,
        notes=notes,
        score=score,
        createdAt=_utc_now(),
        observedAt=observed_at,
        evidenceReferences=evidence_references or [],
        packetContentHash=packet_content_hash(packet),
        sequence=sequence,
        previousHash=previous_hash,
        eventHash="",
    )
    return record.model_copy(update={"eventHash": _sha256(_memory_hash_payload(record))})


def _audit_hash_payload(event: PacketAuditChainEvent) -> dict:
    return event.model_dump(mode="json", exclude={"eventHash"})


def create_packet_audit_event(
    packet: DecisionPacket,
    *,
    event_type: str,
    detail: str,
    actor: str = "system",
    previous_event: PacketAuditChainEvent | None = None,
) -> PacketAuditChainEvent:
    event = PacketAuditChainEvent(
        sequence=previous_event.sequence + 1 if previous_event else 1,
        packetId=packet.id,
        packetVersion=packet.packetVersion,
        eventType=event_type,
        detail=detail,
        actor=actor,
        createdAt=_utc_now(),
        payloadHash=packet_content_hash(packet),
        previousHash=previous_event.eventHash if previous_event else ZERO_HASH,
        eventHash="",
    )
    return event.model_copy(update={"eventHash": _sha256(_audit_hash_payload(event))})


def verify_audit_chain(
    records: Iterable[dict | DecisionMemoryRecord | PacketAuditChainEvent],
    packet_id: str,
    *,
    expected_head: str | None = None,
    expected_count: int | None = None,
) -> bool:
    normalized = list(records)
    if not normalized:
        return False

    previous_hash = ZERO_HASH
    expected_sequence = 1
    for item in normalized:
        if isinstance(item, PacketAuditChainEvent):
            record = item
            payload = _audit_hash_payload(record)
        elif isinstance(item, DecisionMemoryRecord):
            record = item
            payload = _memory_hash_payload(record)
        else:
            if "eventType" in item and "payloadHash" in item:
                record = PacketAuditChainEvent.model_validate(item)
                payload = _audit_hash_payload(record)
            else:
                record = DecisionMemoryRecord.model_validate(item)
                payload = _memory_hash_payload(record)

        if record.packetId != packet_id:
            return False
        if record.sequence != expected_sequence:
            return False
        if record.previousHash != previous_hash:
            return False
        calculated = _sha256(payload)
        if not hmac.compare_digest(calculated, record.eventHash):
            return False
        previous_hash = record.eventHash
        expected_sequence += 1

    if expected_count is not None and expected_sequence - 1 != expected_count:
        return False
    if expected_head is not None and not hmac.compare_digest(previous_hash, expected_head):
        return False
    return True


def score_memory_relevance(
    record: DecisionMemoryRecord,
    query: str,
    *,
    now: datetime | None = None,
) -> tuple[float, dict[str, float]] | None:
    """Return an explainable outcome-weighted score without future-observation leakage."""
    evaluation_time = now or datetime.now(UTC)
    if evaluation_time.tzinfo is None:
        evaluation_time = evaluation_time.replace(tzinfo=UTC)

    if record.recordType == "resolution" and record.observedAt:
        observed_at = datetime.fromisoformat(record.observedAt.replace("Z", "+00:00"))
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=UTC)
        if observed_at > evaluation_time:
            return None

    query_terms = {term for term in query.lower().split() if term}
    memory_text = " ".join(
        [record.outcome, record.notes or "", *record.evidenceReferences]
    ).lower()
    matched_terms = sum(1 for term in query_terms if term in memory_text)
    similarity = matched_terms / max(1, len(query_terms))

    created_at = datetime.fromisoformat(record.createdAt.replace("Z", "+00:00"))
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    age_days = max(0.0, (evaluation_time - created_at).total_seconds() / 86_400)
    recency = 1.0 / (1.0 + age_days / 30.0)
    outcome_quality = (
        (record.score / 100.0)
        if record.recordType == "resolution" and record.score is not None
        else 0.5
    )
    resolution_weight = 1.0 if record.recordType == "resolution" else 0.35

    components = {
        "similarity": round(similarity, 4),
        "recency": round(recency, 4),
        "outcomeQuality": round(outcome_quality, 4),
        "resolutionWeight": round(resolution_weight, 4),
    }
    total = (
        0.50 * similarity
        + 0.15 * recency
        + 0.25 * outcome_quality
        + 0.10 * resolution_weight
    )
    return round(min(1.0, max(0.0, total)), 4), components


def build_workflow_status(
    packet: DecisionPacket,
    disconfirmation: DisconfirmationOutcome,
    risk_gate: RiskGateOutcome,
) -> PacketWorkflowStatus:
    completed = ["provenance", "disconfirmation", "risk_gate"]
    blockers: list[str] = []

    if disconfirmation.status != DisconfirmationStatus.passed:
        blockers.extend(disconfirmation.reasons or [disconfirmation.summary])
    if risk_gate.status in {RiskGateStatus.blocked, RiskGateStatus.insufficient_data}:
        blockers.extend(risk_gate.reasons)

    if disconfirmation.status == DisconfirmationStatus.passed and risk_gate.status == RiskGateStatus.passed:
        state = IntegrationStage.promotable
        next_action = "Record the human decision."
    elif (
        disconfirmation.status == DisconfirmationStatus.requires_human_review
        or risk_gate.status == RiskGateStatus.warning
    ):
        state = IntegrationStage.human_review
        next_action = "Resolve the flagged evidence or risk warnings through human review."
    else:
        state = IntegrationStage.blocked
        next_action = "Resolve all blockers, refresh affected evidence, and rerun integration."

    return PacketWorkflowStatus(
        state=state,
        completedStages=completed,
        blockers=list(dict.fromkeys(blockers)),
        nextAction=next_action,
        policyVersion=INTEGRATION_POLICY_VERSION,
        updatedAt=_utc_now(),
    )


def invalidate_integration(
    packet: DecisionPacket,
    *,
    reason: str,
    clear_provenance: bool = False,
) -> DecisionPacket:
    stale_stages = list(packet.integrationStatus.completedStages)
    return packet.model_copy(
        update={
            "packetVersion": packet.packetVersion + 1,
            "workflowRunId": None,
            "provenance": [] if clear_provenance else packet.provenance,
            "disconfirmationResult": None,
            "riskGateResult": None,
            "integrationStatus": PacketWorkflowStatus(
                state=IntegrationStage.not_started,
                staleStages=stale_stages,
                blockers=[reason],
                nextAction="Rerun selective integration for the new packet version.",
                policyVersion=INTEGRATION_POLICY_VERSION,
                updatedAt=_utc_now(),
            ),
        }
    )


def packet_promotion_blockers(packet: DecisionPacket) -> list[str]:
    blockers: list[str] = []
    if packet.integrationStatus.state != IntegrationStage.promotable:
        blockers.append(
            f"packet integration state is {packet.integrationStatus.state.value}, not promotable"
        )
    if packet.disconfirmationResult is None:
        blockers.append("disconfirmation has not run")
    elif packet.disconfirmationResult.status != DisconfirmationStatus.passed:
        blockers.append(f"disconfirmation status is {packet.disconfirmationResult.status.value}")
    elif packet.disconfirmationResult.packetVersion != packet.packetVersion:
        blockers.append("disconfirmation result is stale for the current packet version")
    if packet.riskGateResult is None:
        blockers.append("risk gate has not run")
    elif packet.riskGateResult.status != RiskGateStatus.passed:
        blockers.append(f"risk-gate status is {packet.riskGateResult.status.value}")
    elif packet.riskGateResult.packetVersion != packet.packetVersion:
        blockers.append("risk-gate result is stale for the current packet version")
    if not packet.provenance:
        blockers.append("packet provenance is missing")
    return blockers
