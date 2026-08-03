from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "services" / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "services" / "api"))

from app.models import (  # noqa: E402
    CoverageStatus,
    DecisionPacket,
    DecisionState,
    ReviewStatus,
    RiskMonitor,
    ValidationSpec,
    HistoricalAnalogue,
    TradeabilityQuestion,
    SourcePointer,
    AuditEvent,
    Claim,
    ProvenanceMetadata,
    DisconfirmationStatus,
    IntegrationStage,
    RiskGateStatus,
)
from app.selective_integration import (  # noqa: E402
    attach_provenance,
    build_workflow_status,
    evaluate_risk_gate,
    invalidate_integration,
    packet_decision_blockers,
    run_disconfirmation,
    score_memory_relevance,
    create_decision_memory_record,
    verify_audit_chain,
)
from app.store import ReviewStore  # noqa: E402


def _make_packet() -> DecisionPacket:
    return DecisionPacket(
        id="pkt-test-1",
        title="Test packet",
        thesis="A structured thesis for review",
        ticker="AAPL",
        assetClass="equity",
        timeHorizon="medium_term",
        intendedExpression="Long bias on quality signal",
        status=ReviewStatus.validation,
        decisionState=DecisionState.watch,
        confidence=72,
        trialCountImpact=1,
        followUpDate="2026-08-10",
        createdAt="2026-08-02T10:00:00",
        claims=[Claim(id="c1", kind="sourced", text="Evidence available", evidence="source", confidence=85)],
        strongestCritique="The thesis is plausible but needs a tighter evidence barrier.",
        disconfirmingTest="If the signal fails the corroboration step, reject the thesis.",
        historicalAnalogue=HistoricalAnalogue(
            title="Previous setup",
            similarity="similar structure",
            differences="lower volatility",
            resolution="recovered",
        ),
        validation=ValidationSpec(
            status="specified",
            hypothesis="The thesis will outperform",
            nullHypothesis="The thesis will not outperform",
            dataRequirements=["price", "volume"],
            protocol="Use bench checks",
            refusalReason=None,
        ),
        tradeability=[TradeabilityQuestion(topic="risk", question="Is the setup acceptable?", severity="medium")],
        sources=[SourcePointer(id="s1", title="Source", sourceType="market", timestamp="2026-08-02", permission="public", relevance=0.9)],
        audit=[AuditEvent(id="a1", timestamp="2026-08-02T10:00:00", eventType="created", detail="packet created")],
    )


def test_packet_provenance_and_disconfirmation_flow() -> None:
    packet = _make_packet()
    packet = attach_provenance(
        packet,
        [
            ProvenanceMetadata(
                source="market-feed",
                sourceType="market",
                timestamp="2026-08-02T10:00:00",
                freshnessSeconds=60,
                dataMode="live",
                confidence="verified",
                notes="Live snapshot",
            )
        ],
    )

    assert packet.provenance[0].source == "market-feed"
    outcome = run_disconfirmation(packet)
    assert outcome.status == "pass"
    assert outcome.requiresHumanReview is False
    assert outcome.evaluator == "ambrosia-deterministic"
    assert outcome.numericChecks[0].name == "packet_confidence_contract"
    assert outcome.numericChecks[0].passed is True


def test_risk_gate_blocks_when_concentration_risk_is_high() -> None:
    packet = _make_packet()
    packet.riskMonitor = RiskMonitor(
        activePositionSize=0.2,
        concentrationRisk="high",
        correlationOverlap=["SPY"],
        varAtRisk=0.15,
        maxDrawdownThreshold=0.05,
        followUpTriggers=["concentration"],
        status="alert",
    )

    outcome = evaluate_risk_gate(packet)
    assert outcome.status == "blocked"
    assert outcome.evaluator == "ambrosia-deterministic"
    assert any("concentration" in reason.lower() for reason in outcome.reasons)


def test_decision_memory_can_be_recorded_and_retrieved() -> None:
    packet = _make_packet()
    store = ReviewStore()
    memory = create_decision_memory_record(packet, outcome="outperformed", notes="Positive outcome", score=82)
    stored = store.append_packet_memory(packet.id, memory)
    assert stored.memoryId == memory.memoryId
    assert store.get_packet_memory(packet.id)[0].packetId == packet.id
    assert verify_audit_chain([memory.model_dump(mode="json")], packet.id)


def test_disconfirmation_uses_evidence_not_initial_confidence() -> None:
    packet = _make_packet().model_copy(update={"confidence": 25})
    packet = attach_provenance(
        packet,
        [
            ProvenanceMetadata(
                source="source",
                sourceType="market",
                timestamp="2026-08-02T10:00:00Z",
                coverageStatus=CoverageStatus.full,
                dataMode="fallback",
            )
        ],
    )
    outcome = run_disconfirmation(packet)
    assert outcome.status == DisconfirmationStatus.passed


def test_missing_risk_data_fails_closed() -> None:
    packet = attach_provenance(
        _make_packet(),
        [
            ProvenanceMetadata(
                source="source",
                sourceType="market",
                timestamp="2026-08-02T10:00:00Z",
                coverageStatus="full",
                dataMode="fallback",
            )
        ],
    )
    outcome = evaluate_risk_gate(packet)
    assert outcome.status == RiskGateStatus.insufficient_data
    assert "riskMonitor" in outcome.missingInputs


def test_only_promoting_decisions_require_promotion_readiness() -> None:
    packet = _make_packet()

    assert packet_decision_blockers(packet, DecisionState.needs_more_data) == []
    assert packet_decision_blockers(packet, DecisionState.watch) == []
    assert packet_decision_blockers(packet, DecisionState.reject) == []
    assert "packet integration state is not_started, not promotable" in packet_decision_blockers(
        packet,
        DecisionState.pursue,
    )


def test_audit_chain_detects_tampering_and_reordering() -> None:
    packet = _make_packet()
    first = create_decision_memory_record(packet, outcome="watch", notes="checkpoint")
    second = create_decision_memory_record(
        packet,
        outcome="won",
        notes="resolved",
        record_type="resolution",
        observed_at="2026-08-20T10:00:00Z",
        previous_record=first,
    )
    assert verify_audit_chain([first, second], packet.id)
    assert verify_audit_chain(
        [first, second],
        packet.id,
        expected_count=2,
        expected_head=second.eventHash,
    )

    tampered = second.model_copy(update={"outcome": "lost"})
    assert not verify_audit_chain([first, tampered], packet.id)
    assert not verify_audit_chain([second, first], packet.id)
    assert not verify_audit_chain([second], packet.id)
    assert not verify_audit_chain(
        [first],
        packet.id,
        expected_count=2,
        expected_head=second.eventHash,
    )


def test_input_change_invalidates_downstream_results() -> None:
    packet = attach_provenance(
        _make_packet(),
        [
            ProvenanceMetadata(
                source="source",
                sourceType="market",
                timestamp="2026-08-02T10:00:00Z",
                coverageStatus="full",
                dataMode="fallback",
            )
        ],
    )
    disconfirmation = run_disconfirmation(packet)
    risk = evaluate_risk_gate(packet)
    packet = packet.model_copy(
        update={
            "disconfirmationResult": disconfirmation,
            "riskGateResult": risk,
            "integrationStatus": build_workflow_status(packet, disconfirmation, risk),
        }
    )

    invalidated = invalidate_integration(packet, reason="evidence changed", clear_provenance=True)
    assert invalidated.packetVersion == packet.packetVersion + 1
    assert invalidated.disconfirmationResult is None
    assert invalidated.riskGateResult is None
    assert invalidated.provenance == []
    assert invalidated.integrationStatus.state == IntegrationStage.not_started


def test_outcome_weighted_memory_is_explainable_and_prevents_future_leakage() -> None:
    packet = _make_packet()
    resolved = create_decision_memory_record(
        packet,
        outcome="outperformed",
        notes="Semiconductor breadth improved after the review window.",
        score=84,
        record_type="resolution",
        observed_at="2026-08-20T10:00:00Z",
    )
    before_observation = score_memory_relevance(
        resolved,
        "semiconductor breadth",
        now=datetime(2026, 8, 10, tzinfo=UTC),
    )
    assert before_observation is None

    after_observation = score_memory_relevance(
        resolved,
        "semiconductor breadth",
        now=datetime(2026, 8, 21, tzinfo=UTC),
    )
    assert after_observation is not None
    score, components = after_observation
    assert score > 0.5
    assert set(components) == {"similarity", "recency", "outcomeQuality", "resolutionWeight"}
