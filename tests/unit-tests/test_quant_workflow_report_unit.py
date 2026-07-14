from __future__ import annotations

from services.api.app import day6, day7, report
from services.api.app.models import (
    BacktestPrepareRequest,
    ConfidenceDeriveRequest,
    PortfolioContextUpdate,
    RiskEvaluateRequest,
)


def test_backtest_eligibility_passes_when_packet_has_required_inputs(packet_factory) -> None:
    packet = packet_factory(include_market=True, confidence=62, volume=5_000_000)

    eligible, reasons = day6.assess_eligibility(packet)

    assert eligible is True
    assert reasons == []


def test_backtest_eligibility_collects_all_missing_or_blocking_reasons(packet_factory) -> None:
    packet = packet_factory(
        include_market=False,
        confidence=30,
        validation_status="refused",
        risk_status="alert",
    )

    eligible, reasons = day6.assess_eligibility(packet)

    assert eligible is False
    assert "Validation status must be specified before running backtest" in reasons
    assert "Market snapshot is required" in reasons
    assert "Technicals are required" in reasons
    assert "Confidence too low for backtest eligibility" in reasons
    assert "Risk monitor in alert state" in reasons


def test_prepare_backtest_plan_reflects_eligibility_and_payload_constraints(packet_factory) -> None:
    packet = packet_factory(volume=100)
    plan = day6.prepare_backtest_plan(
        packet,
        BacktestPrepareRequest(
            lookbackPeriod=126,
            holdingPeriodDays=15,
            riskConstraints=["Unit max drawdown"],
        ),
    )

    assert plan.status == "ineligible"
    assert plan.lookbackPeriod == 126
    assert plan.holdingPeriodDays == 15
    assert plan.riskConstraints == ["Unit max drawdown"]
    assert "Liquidity is inadequate" in (plan.refusalReason or "")


def test_controlled_backtest_refuses_ineligible_packet_unless_forced(packet_factory) -> None:
    packet = packet_factory(include_market=False)

    refused = day6.run_controlled_backtest(packet, force_run=False)
    forced = day6.run_controlled_backtest(packet, force_run=True)

    assert refused.validityScore == "refused"
    assert refused.totalReturn is None
    assert forced.samplePeriod == "deterministic-controlled-252d"
    assert forced.totalReturn is not None
    assert "Run forced despite failed eligibility gates" in forced.hygienIssues


def test_evaluate_risk_maps_position_size_to_concentration_and_alerts(packet_factory) -> None:
    packet = packet_factory()

    low = day6.evaluate_risk(packet, RiskEvaluateRequest(activePositionSize=0.04, maxDrawdownThreshold=0.12))
    high = day6.evaluate_risk(packet, RiskEvaluateRequest(activePositionSize=0.2, maxDrawdownThreshold=0.12))

    assert low.concentrationRisk == "low"
    assert low.status == "monitoring"
    assert high.concentrationRisk == "high"
    assert high.status == "alert"
    assert high.correlationOverlap == ["Momentum"]


def test_portfolio_context_is_built_without_losing_dimensions() -> None:
    payload = PortfolioContextUpdate(
        grossExposure=0.8,
        netExposure=0.45,
        longExposure=0.7,
        shortExposure=0.25,
        concentrationBySector={"Financials": 0.2},
        concentrationByFactor={"Value": 0.3},
        relatedPositions=["XLF"],
        factorOverlap=["Value"],
        riskBudgetRemaining=0.12,
        sizingConstraints=["Max 3% NAV"],
    )

    context = day7.build_portfolio_context(payload)

    assert context.grossExposure == 0.8
    assert context.concentrationBySector == {"Financials": 0.2}
    assert context.factorOverlap == ["Value"]
    assert context.sizingConstraints == ["Max 3% NAV"]


def test_derive_confidence_clamps_scores_and_applies_risk_and_blocker_penalties(packet_factory) -> None:
    packet = packet_factory(risk_status="alert")

    components = day7.derive_confidence(
        packet,
        ConfidenceDeriveRequest(
            evidenceScore=110,
            technicalScore=-5,
            sentimentScore=64,
            interMarketScore=55,
            validationScore=70,
            tradeabilityScore=60,
            blockers=["missing_liquidity", "crowded_factor"],
        ),
    )

    assert components.evidenceScore == 100
    assert components.technicalScore == 0
    assert components.sourceProxyPenalties == 18
    assert components.riskAdjustedScore == components.overallConfidence - 6
    assert components.blockers == ["missing_liquidity", "crowded_factor"]


def test_generate_report_includes_all_core_sections_and_market_provenance(packet_factory) -> None:
    packet = packet_factory(include_market=True, risk_status="monitoring")

    artifact = report.generate_report(packet)
    section_titles = [section.title for section in artifact.sections]
    content = "\n".join(section.content for section in artifact.sections)

    assert artifact.packetId == packet.id
    assert artifact.title == "Investment Decision Report: SPY"
    assert artifact.dataMode == "fallback"
    assert artifact.marketDataSource == "unit-test-provider"
    assert "Data from unit-test-provider; mode=fallback" == artifact.provenanceLabel
    assert section_titles == [
        "Executive Summary",
        "Claims & Evidence",
        "Market Context",
        "Validation Specification",
        "Risk & Confidence",
        "Audit Trail",
    ]
    assert "Ticker: SPY" in content
    assert "Risk Status:" in content
    assert "Confidence Breakdown:" in content


def test_generate_report_handles_packets_without_market_context(packet_factory) -> None:
    packet = packet_factory(include_market=False)

    artifact = report.generate_report(packet)
    market_section = next(section for section in artifact.sections if section.title == "Market Context")

    assert artifact.dataMode == "fallback"
    assert artifact.marketDataSource is None
    assert artifact.provenanceLabel == "No live market data attached; mode=fallback"
    assert "Market snapshot: not fetched" in market_section.content
    assert "Technicals: not available" in market_section.content
