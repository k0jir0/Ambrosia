from __future__ import annotations

from datetime import UTC, datetime

from .coordinator import PIPELINE_VERSION, _ticker_identity
from .models import (
    DecisionPacket,
    MaterialClaim,
    ReportArtifact,
    ReportSection,
    SpecialistAgentOutput,
    VerificationFinding,
)


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

    return ReportSection(
        title="Risk & Confidence", content="\n".join(lines) if lines else "No risk data."
    )


def _section_audit_summary(packet: DecisionPacket) -> ReportSection:
    lines = [f"[{e.timestamp}] {e.eventType}: {e.detail}" for e in packet.audit]
    return ReportSection(
        title="Audit Trail", content="\n".join(lines) if lines else "No audit events."
    )


def _verified_outputs(
    packet: DecisionPacket, llm_runs: list[dict] | None = None
) -> list[SpecialistAgentOutput]:
    outputs = [
        item
        for item in (packet.agentOutputs or {}).values()
        if item
        and item.schemaVersion == "specialist-output.v2"
        and item.verificationStatus in {"passed", "repaired", "abstained"}
    ]
    for run in llm_runs or []:
        value = run.get("structured_output") or {}
        if value.get("schemaVersion") != "specialist-output.v2" or run.get(
            "verification_status"
        ) != "passed":
            continue
        claims = [MaterialClaim.model_validate(item) for item in value.get("materialClaims", [])]
        outputs.append(
            SpecialistAgentOutput(
                role=value.get("role", "durableSpecialist"),
                summary=value.get("roleConclusion") or value.get("summary") or "Verified output",
                keyPoints=[item.text for item in claims[:3]],
                timestamp=str(run.get("created_at") or _utc_timestamp()),
                provider="ollama-local-worker",
                fallbackUsed=False,
                schemaVersion="specialist-output.v2",
                verificationStatus="passed",
                materialClaims=claims,
                rejectedClaims=[
                    MaterialClaim.model_validate(item) for item in value.get("rejectedClaims", [])
                ],
                verificationFindings=[
                    VerificationFinding.model_validate(item)
                    for item in value.get("verificationFindings", [])
                ],
                calculationArtifacts=value.get("calculationArtifacts", []),
                missingEvidence=value.get("missingEvidence", []),
                modelDigest=run.get("model_digest"),
                evidencePackHash=run.get("evidence_pack_hash"),
                promptTemplateId=run.get("prompt_template_id"),
            )
        )
    return outputs


def _claims(outputs):
    admitted, rejected = {}, {}
    for output in outputs:
        admitted.update(
            {
                item.claimId: item
                for item in output.materialClaims
                if item.admissionStatus in {"admitted", "repaired", "human_review"}
            }
        )
        rejected.update({item.claimId: item for item in output.rejectedClaims})
    return list(admitted.values()), list(rejected.values())


def _claim_text(claims):
    return (
        "\n".join(
            f"- [{item.claimType.upper()} / {item.materiality}] {item.text} (evidence: {', '.join(item.supportingEvidenceIds) or 'admitted premises'}; uncertainty: {item.uncertainty:.2f})"
            + (f"\n  Falsifier: {item.falsifier}" if item.falsifier else "")
            for item in claims
        )
        or "No verified claims were admitted for this section."
    )


def _verified_section(title, claims, mode="mixed"):
    return ReportSection(
        title=title,
        content=_claim_text(claims),
        evidenceMode=mode,
        claimIds=[item.claimId for item in claims],
        citationEvidenceIds=sorted({ref for item in claims for ref in item.supportingEvidenceIds}),
        verificationStatus="passed" if claims else "unavailable",
    )


def _intelligence_sections(outputs, admitted, rejected):
    by_role = {item.role: item.materialClaims for item in outputs}

    def role(*names):
        return [claim for name in names for claim in by_role.get(name, [])]

    fundamental, scenarios, risks, disagreements = (
        role("fundamental"),
        role("bull", "bear"),
        role("risk", "bear"),
        role("bull", "bear"),
    )
    gaps = sorted({gap for output in outputs for gap in output.missingEvidence})
    findings = [finding for output in outputs for finding in output.verificationFindings]
    human_rejected = [claim for output in outputs for claim in output.humanRejectedClaims]
    calculations = [
        item
        for output in outputs
        for item in output.calculationArtifacts
        if item.validationStatus == "passed"
    ]
    calc_text = "\n".join(
        f"- {item.calculationId}: {item.formula} = {item.result} {item.units or ''} ({item.roundingRule})"
        for item in calculations
    )
    return [
        _verified_section("Verified Executive Intelligence", role("pmSynthesis") or admitted[:5]),
        _verified_section("Business & Fundamental Profile", fundamental, "derived"),
        ReportSection(
            title="Latest Filing & Earnings Delta",
            content=_claim_text(fundamental)
            if fundamental
            else "No point-in-time filing or earnings evidence was admitted; this section abstains.",
            evidenceMode="mixed" if fundamental else "unavailable",
            verificationStatus="passed" if fundamental else "unavailable",
        ),
        ReportSection(
            title="KPI & Segment Trends",
            content=calc_text or "No deterministic KPI calculation artifacts were attached.",
            evidenceMode="derived" if calculations else "unavailable",
            citationEvidenceIds=sorted(
                {ref for item in calculations for ref in item.inputEvidenceIds}
            ),
            verificationStatus="passed" if calculations else "unavailable",
        ),
        _verified_section(
            "Valuation & Conditional Scenarios",
            [item for item in scenarios if item.claimType in {"scenario", "inference"}],
        ),
        _verified_section("Bull / Bear Adjudication", disagreements),
        _verified_section("Risks, Falsifiers & Monitoring Triggers", risks),
        ReportSection(
            title="Evidence Gaps",
            content="\n".join(f"- {gap}" for gap in gaps)
            or "No specialist evidence gaps were declared.",
            evidenceMode="unavailable" if gaps else "mixed",
            verificationStatus="partial" if gaps else "passed",
        ),
        ReportSection(
            title="Verification Appendix",
            content="\n".join(
                f"- {item.claimId}: {item.status} via {item.verifier}" for item in findings
            )
            or "No verifier findings recorded.",
            evidenceMode="mixed",
            claimIds=[item.claimId for item in findings],
            citationEvidenceIds=sorted({ref for item in findings for ref in item.evidenceIds}),
            verificationStatus="passed" if findings else "unavailable",
        ),
        ReportSection(
            title="Human Review Appendix",
            content="\n".join(
                f"- REJECTED [{item.claimId}] {item.originalText} "
                f"(reviewer: {item.reviewerId}; reason: {item.reason})"
                for item in human_rejected
            )
            or "No human-rejected proposal claims were retained for review.",
            evidenceMode="mixed" if human_rejected else "unavailable",
            claimIds=[item.claimId for item in human_rejected],
            citationEvidenceIds=sorted(
                {
                    reference
                    for item in human_rejected
                    for reference in item.supportingEvidenceIds
                }
            ),
            verificationStatus="partial" if human_rejected else "unavailable",
        ),
    ]


def _coverage(admitted, rejected):
    weight = {"low": 1, "medium": 2, "high": 3}
    good = sum(weight[item.materiality] for item in admitted)
    total = good + sum(weight[item.materiality] for item in rejected)
    return good / total if total else 0


def generate_report(packet: DecisionPacket, llm_runs: list[dict] | None = None) -> ReportArtifact:
    sections = [
        _section_executive_summary(packet),
        _section_claims(packet),
        _section_market_context(packet),
        _section_validation(packet),
        _section_risk(packet),
        _section_audit_summary(packet),
    ]
    verified = _verified_outputs(packet, llm_runs)
    admitted, rejected = _claims(verified)
    server_rejected = [
        item
        for run in llm_runs or []
        for item in (run.get("structured_output") or {}).get("rejectedClaims", [])
    ]
    calculations = [
        item
        for output in verified
        for item in output.calculationArtifacts
        if item.validationStatus == "passed"
    ]
    if verified:
        sections[0] = sections[0].model_copy(
            update={"evidenceMode": "user_asserted", "verificationStatus": "partial"}
        )
        sections[2] = sections[2].model_copy(
            update={"evidenceMode": "mixed", "verificationStatus": "partial"}
        )
        sections.extend(_intelligence_sections(verified, admitted, rejected))

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

    provider = packet.providerInfo or {}
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
        schemaVersion="ticker-intelligence-report.v2"
        if verified or llm_runs
        else "ticker-intelligence-report.v1",
        tickerIdentity=_ticker_identity(packet) if verified else None,
        asOf=packet.marketSnapshot.timestamp if packet.marketSnapshot else packet.createdAt,
        knowledgeCutoff=max(
            [packet.createdAt, *[item.timestamp for item in packet.sources]],
            default=packet.createdAt,
        ),
        modelDigest=next((item.modelDigest for item in verified if item.modelDigest), None),
        promptVersion=next(
            (item.promptTemplateId for item in verified if item.promptTemplateId), None
        ),
        pipelineVersion=PIPELINE_VERSION if verified else None,
        sourceSnapshotHash=next(
            (item.evidencePackHash for item in verified if item.evidencePackHash), None
        ),
        verifiedClaimCoverage=_coverage(admitted, rejected),
        unresolvedMaterialClaimCount=sum(
            item.materiality in {"medium", "high"} for item in rejected
        ),
        calculationArtifacts=calculations,
        rejectedClaimIds=sorted(
            {item.claimId for item in rejected}
            | {str(item.get("claimId")) for item in server_rejected if item.get("claimId")}
        ),
        reportValidationStatus="passed"
        if verified and not rejected
        else "partial"
        if verified or llm_runs
        else "legacy",
        operationId=provider.get("operationId"),
        providerRequested=provider.get("requestedProvider"),
        providerUsed=provider.get("actualProvider") or provider.get("type"),
        verificationStatus=provider.get("verificationStatus"),
        traceparent=provider.get("traceparent")
        or next((run.get("trace_id") for run in (llm_runs or []) if run.get("trace_id")), None),
    )
