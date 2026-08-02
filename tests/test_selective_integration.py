from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "services" / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "services" / "api"))

from app.models import (
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
    DisconfirmationOutcome,
    RiskGateOutcome,
    DecisionMemoryRecord,
)
from app.selective_integration import (
    attach_provenance,
    evaluate_risk_gate,
    run_disconfirmation,
    create_decision_memory_record,
    verify_audit_chain,
)
from app.store import ReviewStore


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
    assert any("concentration" in reason.lower() for reason in outcome.reasons)


def test_decision_memory_can_be_recorded_and_retrieved() -> None:
    packet = _make_packet()
    store = ReviewStore()
    memory = create_decision_memory_record(packet, outcome="outperformed", notes="Positive outcome", score=82)
    stored = store.append_packet_memory(packet.id, memory)
    assert stored.memoryId == memory.memoryId
    assert store.get_packet_memory(packet.id)[0].packetId == packet.id
    assert verify_audit_chain([memory.model_dump(mode="json")], packet.id)
