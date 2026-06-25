from __future__ import annotations

from datetime import UTC, datetime

from .models import DecisionPacket, ReportArtifact, ReportSection


def _utc_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _section_executive_summary(packet: DecisionPacket) -> ReportSection:
    decision_label = packet.decisionState.value if packet.decisionState else "Pending"
    content = (
        f"Ticker: {packet.ticker}\n"
        f"Asset Class: {packet.assetClass}\n"
        f"Time Horizon: {packet.timeHorizon}\n"
        f"Intended Expression: {packet.intendedExpression}\n"
        f"Decision: {decision_label}\n"
        f"Confidence: {packet.confidence}%\n\n"
        f"Thesis: {packet.thesis}"
    )
    return ReportSection(title="Executive Summary", content=content)


def _section_claims(packet: DecisionPacket) -> ReportSection:
    lines = [f"- [{c.kind.upper()}] {c.text} (confidence: {c.confidence}%)" for c in packet.claims]
    content = "\n".join(lines) if lines else "No claims recorded."
    return ReportSection(title="Claims & Evidence", content=content)


def _section_market_context(packet: DecisionPacket) -> ReportSection:
    lines: list[str] = []
    if packet.marketSnapshot:
        s = packet.marketSnapshot
        freshness = f"{s.freshnessSeconds}s" if s.freshnessSeconds is not None else "deterministic"
        lines += [
            f"Price: {s.price}",
            f"24h Change: {s.priceChange24h:.4f}%",
            f"Volume: {s.volume24h:,.0f}",
            f"Source: {s.dataSource}",
            f"Mode: {s.dataSourceConfidence}",
            f"Freshness: {freshness}",
        ]
    else:
        lines.append("Market snapshot: not fetched — run /packets/{id}/metrics/refresh first.")

    if packet.technicals:
        t = packet.technicals
        rsi_str = f"{t.rsi:.2f}" if t.rsi is not None else "N/A"
        lines += [
            "",
            "Technicals:",
            f"  Trend: {t.trend}",
            f"  RSI({t.rsiPeriod}): {rsi_str}",
            f"  Data Quality: {t.dataQuality}",
            f"  Data Mode: {t.dataMode}",
        ]
    else:
        lines.append("Technicals: not available.")

    if packet.sentiment:
        s = packet.sentiment
        lines += [
            "",
            "Sentiment:",
            f"  Overall: {s.overallScore:.0f} ({s.sentiment})",
            f"  Trend Direction: {s.trendDirection}",
            f"  Source Confidence: {s.sourceConfidence}",
            f"  Data Mode: {s.dataMode}",
        ]

    return ReportSection(title="Market Context", content="\n".join(lines))


def _section_validation(packet: DecisionPacket) -> ReportSection:
    v = packet.validation
    lines = [
        f"Status: {v.status}",
        f"Hypothesis: {v.hypothesis}",
        f"Null Hypothesis: {v.nullHypothesis}",
        f"Protocol: {v.protocol}",
    ]
    if v.refusalReason:
        lines.append(f"Refusal Reason: {v.refusalReason}")
    if v.dataRequirements:
        lines.append("Data Requirements:")
        lines += [f"  - {req}" for req in v.dataRequirements]
    return ReportSection(title="Validation Specification", content="\n".join(lines))


def _section_risk(packet: DecisionPacket) -> ReportSection:
    lines: list[str] = []
    if packet.riskMonitor:
        r = packet.riskMonitor
        lines += [
            f"Risk Status: {r.status}",
            f"Active Position Size: {r.activePositionSize:.1%}",
            f"Concentration Risk: {r.concentrationRisk}",
            f"Max Drawdown Threshold: {r.maxDrawdownThreshold:.1%}",
        ]
        if r.followUpTriggers:
            lines.append("Follow-up Triggers:")
            lines += [f"  - {t}" for t in r.followUpTriggers]
    else:
        lines.append("Risk monitor: not evaluated.")

    if packet.confidenceBreakdown:
        cb = packet.confidenceBreakdown
        lines += [
            "",
            "Confidence Breakdown:",
            f"  Overall: {cb.overallConfidence}%",
            f"  Evidence: {cb.evidenceScore}%",
            f"  Technical: {cb.technicalScore}%",
            f"  Sentiment: {cb.sentimentScore}%",
            f"  Validation: {cb.validationScore}%",
        ]
        if cb.blockers:
            lines.append("  Blockers:")
            lines += [f"    - {b}" for b in cb.blockers]

    return ReportSection(title="Risk & Confidence", content="\n".join(lines) if lines else "No risk data.")


def _section_audit_summary(packet: DecisionPacket) -> ReportSection:
    lines = [f"[{e.timestamp}] {e.eventType}: {e.detail}" for e in packet.audit]
    return ReportSection(title="Audit Trail", content="\n".join(lines) if lines else "No audit events.")


def generate_report(packet: DecisionPacket) -> ReportArtifact:
    sections = [
        _section_executive_summary(packet),
        _section_claims(packet),
        _section_market_context(packet),
        _section_validation(packet),
        _section_risk(packet),
        _section_audit_summary(packet),
    ]

    data_mode: str = "fallback"
    market_source: str | None = None
    freshness_seconds: int | None = None

    if packet.marketSnapshot:
        data_mode = packet.marketSnapshot.dataSourceConfidence
        market_source = packet.marketSnapshot.dataSource
        freshness_seconds = packet.marketSnapshot.freshnessSeconds

    provenance = (
        f"Data from {market_source}; mode={data_mode}"
        if market_source
        else f"No live market data attached; mode={data_mode}"
    )

    return ReportArtifact(
        packetId=packet.id,
        ticker=packet.ticker,
        title=f"Investment Decision Report: {packet.ticker}",
        createdAt=_utc_timestamp(),
        sections=sections,
        dataMode=data_mode,
        provenanceLabel=provenance,
        marketDataSource=market_source,
        marketDataFreshnessSeconds=freshness_seconds,
    )
