from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from .index84_platform import (
    get_alpha_decay,
    get_signal,
    get_signal_alpha_context,
    get_signal_decision_links,
    get_signal_outcome_rollup,
    get_signal_program_metrics,
    get_weekly_quality_scorecard,
    list_alpha_hypotheses,
    list_signal_policy_events,
    list_signal_validation_runs,
    list_signals,
)
from .market_providers import market_provider_status
from .models import ScannerRunRequest, TradeReview
from .providers import provider_status
from .scanner import run_scanner
from .store import store
from .tool_boundaries import list_tool_boundaries

router = APIRouter(prefix="/mobile", tags=["mobile"])


def _now() -> str:
    return datetime.now().isoformat()


def _review_summary(review: TradeReview) -> dict:
    return {
        "id": review.id,
        "schemaVersion": review.schemaVersion,
        "workflowVersion": review.workflowVersion,
        "title": review.title,
        "thesis": review.thesis,
        "ticker": review.ticker,
        "assetClass": review.assetClass,
        "timeHorizon": review.timeHorizon,
        "intendedExpression": review.intendedExpression,
        "status": review.status.value if hasattr(review.status, "value") else review.status,
        "decisionState": review.decisionState.value if review.decisionState is not None else None,
        "confidence": review.confidence,
        "followUpDate": review.followUpDate,
        "createdAt": review.createdAt,
        "strongestCritique": review.strongestCritique,
        "disconfirmingTest": review.disconfirmingTest,
        "validation": review.validation.model_dump(mode="json"),
        "tradeability": [item.model_dump(mode="json") for item in review.tradeability],
        "claimCount": len(review.claims),
        "sourceCount": len(review.sources),
        "auditCount": len(review.audit),
    }


def _review_hard_blocks(review: TradeReview) -> list[str]:
    blocks: list[str] = []
    if review.validation.status == "refused":
        blocks.append("validation_refused")
    if not review.sources:
        blocks.append("missing_sources")
    if any(item.severity == "high" for item in review.tradeability):
        blocks.append("high_tradeability_question")
    if review.confidence < 50:
        blocks.append("low_confidence")
    return blocks


def _review_next_action(review: TradeReview, hard_blocks: list[str]) -> str:
    if review.decisionState is None and hard_blocks:
        return "resolve_hard_blocks_before_pursue"
    if review.decisionState is None:
        return "capture_human_decision"
    return "record_or_monitor_outcome"


def _review_runbook(review: TradeReview, hard_blocks: list[str]) -> list[dict]:
    status = review.status.value if hasattr(review.status, "value") else str(review.status)
    stages = [
        ("intake", "Intake", "Thesis normalized into review.v1."),
        ("retrieval", "Evidence", "Claims, source pointers, and analogue context reviewed."),
        ("adversarial_review", "Adversarial", "Critique and falsification test prepared."),
        ("validation", "Validation", "Protocol and data requirements checked."),
        ("tradeability", "Risk", "Tradeability and controls inspected."),
        ("synthesis", "Decision", "Human decision can be captured after gates."),
        ("decision_recorded", "Outcome", "Monitor or record post-decision outcome."),
    ]
    stage_order = [stage[0] for stage in stages]
    current_index = stage_order.index(status) if status in stage_order else 0
    return [
        {
            "id": stage_id,
            "label": label,
            "status": (
                "blocked"
                if stage_id in {"validation", "tradeability", "synthesis"} and hard_blocks and review.decisionState is None
                else "complete"
                if index <= current_index or (stage_id == "decision_recorded" and review.decisionState is not None)
                else "pending"
            ),
            "detail": detail,
        }
        for index, (stage_id, label, detail) in enumerate(stages)
    ]


def _review_provider_provenance(review: TradeReview) -> dict:
    return {
        "mode": "deterministic_review_engine",
        "fallbackUsed": False,
        "sourceCount": len(review.sources),
        "auditCount": len(review.audit),
        "provider": "ambrosia-fastapi",
        "lastAuditEvent": review.audit[-1].model_dump(mode="json") if review.audit else None,
    }


def _review_risk_gate(review: TradeReview, hard_blocks: list[str]) -> dict:
    high_questions = [item for item in review.tradeability if item.severity == "high"]
    return {
        "status": "blocked" if high_questions or "validation_refused" in hard_blocks else "review_required",
        "hardBlockCount": len(hard_blocks),
        "highSeverityCount": len(high_questions),
        "tradeabilityQuestions": [item.model_dump(mode="json") for item in review.tradeability],
        "requiresServerConfirmation": True,
        "executionAuthority": "human_review_only",
    }


def _review_signal_writeback_hint(review: TradeReview, hard_blocks: list[str]) -> dict:
    can_write_decision = review.decisionState is not None and not hard_blocks
    return {
        "status": "ready_to_link" if can_write_decision else "review_or_evidence_required",
        "requiresLinkedSignal": True,
        "canWriteDecision": can_write_decision,
        "suggestedAction": "link_signal_and_write_decision" if can_write_decision else _review_next_action(review, hard_blocks),
        "decisionState": review.decisionState.value if review.decisionState is not None else None,
        "executionReadiness": "paper_trade_ready" if can_write_decision and review.decisionState.value == "pursue" else "not_executable",
    }


def _review_report_status(review: TradeReview) -> dict:
    report_events = [event for event in review.audit if "report" in event.eventType]
    return {
        "status": "generated" if report_events else "not_generated",
        "latestEvent": report_events[-1].model_dump(mode="json") if report_events else None,
        "exportAvailable": bool(report_events),
        "desktopRoute": f"/reports/export?id={review.id}",
    }


def _signal_id(signal: dict) -> str:
    return str(signal.get("signalId") or signal.get("id") or "")


def _active_signal(signal: dict) -> bool:
    return str(signal.get("status", "")).lower() not in {"retired", "blocked"}


def _signal_summary(signal: dict) -> dict:
    return {
        "signalId": _signal_id(signal),
        "name": signal.get("name"),
        "status": signal.get("status"),
        "activeVersion": signal.get("activeVersion", signal.get("version", 1)),
        "version": signal.get("version", signal.get("activeVersion", 1)),
        "universe": signal.get("universe", []),
        "horizon": signal.get("horizon"),
        "formula": signal.get("formula"),
        "benchmark": signal.get("benchmark"),
        "costModel": signal.get("costModel"),
        "linkedReviewCount": signal.get("linkedReviewCount", 0),
        "latestDecisionState": signal.get("latestDecisionState"),
        "latestDecisionAction": signal.get("latestDecisionAction"),
        "executionReadiness": signal.get("executionReadiness"),
        "latestOutcomeQuality": signal.get("latestOutcomeQuality"),
        "outcomeCount": signal.get("outcomeCount", 0),
        "updatedAt": signal.get("updatedAt"),
    }


def _alpha_summary(hypothesis: dict) -> dict:
    return {
        "hypothesisId": hypothesis.get("hypothesisId"),
        "title": hypothesis.get("title"),
        "signalFamily": hypothesis.get("signalFamily"),
        "thesis": hypothesis.get("thesis"),
        "universe": hypothesis.get("universe", []),
        "horizon": hypothesis.get("horizon"),
        "status": hypothesis.get("status"),
        "planQuality": hypothesis.get("planQuality"),
        "linkedSignals": hypothesis.get("linkedSignals", []),
        "updatedAt": hypothesis.get("updatedAt"),
    }


def _enterprise_status() -> dict:
    return {
        "schemaVersion": "mobile-enterprise-status.v1",
        "status": "ok",
        "service": "ambrosia-api",
        "timestamp": _now(),
        "persistence": store.persistence_status(),
        "providers": provider_status(),
        "marketProviders": market_provider_status(),
        "toolBoundaries": [boundary.model_dump(mode="json") for boundary in list_tool_boundaries()],
        "governance": {
            "humanDecisionAuthority": True,
            "llmInLiveOrderLoop": False,
            "mobileFinalDecisionsRequireServerConfirmation": True,
        },
    }


@router.get("/today")
def get_mobile_today(
    include_scanner: bool = Query(False, description="Run a small live scanner sample for mobile triage."),
) -> dict:
    reviews = store.list_reviews()
    review_summaries = [_review_summary(review) for review in reviews]
    pending_reviews = [item for item in review_summaries if item["decisionState"] is None]
    decided_reviews = [item for item in review_summaries if item["decisionState"] is not None]
    signals = [_signal_summary(signal) for signal in list_signals()]
    active_signals = [signal for signal in signals if str(signal.get("status", "")).lower() not in {"retired", "blocked"}]
    alpha_hypotheses = [_alpha_summary(item) for item in list_alpha_hypotheses()]

    scanner_candidates: list[dict] = []
    scanner_status = "not_requested"
    if include_scanner:
        try:
            scanner = run_scanner(
                ScannerRunRequest(
                    universe=["SPY", "QQQ", "JPM", "SOXX"],
                    maxCandidates=4,
                    minVolume=0,
                    signalFilter="all",
                )
            )
            scanner_candidates = [candidate.model_dump(mode="json") for candidate in scanner.candidates]
            scanner_status = scanner.dataMode
        except Exception as exc:  # pragma: no cover - provider/network dependent
            scanner_status = f"unavailable:{exc.__class__.__name__}"

    priority_queue = [
        {
            "kind": "review_decision",
            "id": review["id"],
            "label": f"{review['ticker']} review awaits decision",
            "severity": "warning" if review["validation"]["status"] == "specified" else "critical",
            "nextAction": "open_review",
        }
        for review in pending_reviews[:5]
    ]
    priority_queue.extend(
        {
            "kind": "signal_readiness",
            "id": signal["signalId"],
            "label": f"{signal['name']} has execution readiness: {signal.get('executionReadiness') or 'not assessed'}",
            "severity": "info" if signal.get("executionReadiness") else "warning",
            "nextAction": "open_signal",
        }
        for signal in active_signals[:5]
    )

    return {
        "schemaVersion": "mobile-today.v1",
        "source": "api",
        "loadedAt": _now(),
        "health": {
            "status": "ok",
            "service": "ambrosia-api",
            "persistence": store.persistence_status(),
        },
        "summary": {
            "pendingReviews": len(pending_reviews),
            "decidedReviews": len(decided_reviews),
            "activeSignals": len(active_signals),
            "scannerCandidates": len(scanner_candidates),
            "alphaHypotheses": len(alpha_hypotheses),
            "priorityItems": len(priority_queue),
        },
        "pendingReviews": pending_reviews[:10],
        "recentReviews": review_summaries[:10],
        "scannerCandidates": scanner_candidates,
        "scannerStatus": scanner_status,
        "signals": signals[:20],
        "alphaHypotheses": alpha_hypotheses[:20],
        "programMetrics": get_signal_program_metrics(),
        "qualityScorecard": get_weekly_quality_scorecard(),
        "priorityQueue": priority_queue[:12],
        "enterpriseStatus": _enterprise_status(),
        "freshness": {
            "reviews": "live",
            "signals": "live",
            "scanner": "live" if include_scanner and scanner_candidates else scanner_status,
        },
    }


@router.get("/reviews/{review_id}/summary")
def get_mobile_review_summary(review_id: str) -> dict:
    review = store.get_review(review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")

    hard_blocks = _review_hard_blocks(review)
    summary = _review_summary(review)
    return {
        "schemaVersion": "mobile-review-summary.v1",
        "review": summary,
        "historicalAnalogue": review.historicalAnalogue.model_dump(mode="json"),
        "claims": [claim.model_dump(mode="json") for claim in review.claims],
        "sources": [source.model_dump(mode="json") for source in review.sources],
        "audit": [event.model_dump(mode="json") for event in review.audit],
        "runbook": _review_runbook(review, hard_blocks),
        "providerProvenance": _review_provider_provenance(review),
        "riskGate": _review_risk_gate(review, hard_blocks),
        "signalWriteback": _review_signal_writeback_hint(review, hard_blocks),
        "reportStatus": _review_report_status(review),
        "hardBlocks": hard_blocks,
        "softAdvisories": [
            item.topic
            for item in review.tradeability
            if item.severity in {"low", "medium"}
        ],
        "canPursue": not hard_blocks,
        "availableDecisionStates": ["pursue", "watch", "reject", "needs_more_data"],
        "nextAction": _review_next_action(review, hard_blocks),
        "freshness": "live",
        "updatedAt": _now(),
    }


@router.get("/signals/{signal_id}/decision-readiness")
def get_mobile_signal_decision_readiness(signal_id: str) -> dict:
    signal = get_signal(signal_id)
    validation_runs = list_signal_validation_runs(signal_id)
    policy_events = list_signal_policy_events(signal_id)
    decision_links = get_signal_decision_links(signal_id)
    outcome_rollup = get_signal_outcome_rollup(signal_id)
    alpha_context = get_signal_alpha_context(signal_id)
    alpha_decay = get_alpha_decay(signal_id)

    hard_blocks: list[str] = []
    if not validation_runs:
        hard_blocks.append("missing_validation_run")
    if not decision_links:
        hard_blocks.append("missing_review_link")
    if str(signal.get("status", "")).lower() == "retired":
        hard_blocks.append("signal_retired")
    if str(signal.get("executionReadiness", "")).lower().startswith("execution_blocked"):
        hard_blocks.append("execution_blocked")
    if alpha_decay.get("decayDetected"):
        hard_blocks.append("alpha_decay_detected")

    latest_link = decision_links[0] if decision_links else {}
    evidence_links = latest_link.get("evidenceLinks") or []
    verifier_status = str(latest_link.get("verifierStatus") or "").lower()
    if latest_link and not evidence_links:
        hard_blocks.append("missing_decision_evidence")
    if latest_link and verifier_status and verifier_status != "passed":
        hard_blocks.append("verifier_not_passed")

    if hard_blocks:
        readiness = "blocked_pending_evidence"
        next_action = "resolve_hard_blocks"
    elif not signal.get("latestDecisionAction"):
        readiness = "review_required"
        next_action = "write_back_review_decision"
    elif outcome_rollup.get("outcomeCount", 0) == 0:
        readiness = "outcome_due"
        next_action = "record_outcome"
    else:
        readiness = signal.get("executionReadiness") or "decision_ready"
        next_action = "monitor_or_revalidate"

    return {
        "schemaVersion": "mobile-signal-decision-readiness.v1",
        "signal": _signal_summary(signal),
        "decisionReadiness": readiness,
        "nextAction": next_action,
        "hardBlocks": hard_blocks,
        "validationRuns": validation_runs,
        "policyEvents": policy_events,
        "decisionLinks": decision_links,
        "outcomeRollup": outcome_rollup,
        "alphaContext": alpha_context,
        "alphaDecay": alpha_decay,
        "humanDecisionAuthority": True,
        "llmInLiveOrderLoop": False,
        "updatedAt": _now(),
    }


@router.get("/enterprise/status")
def get_mobile_enterprise_status() -> dict:
    status = _enterprise_status()
    status["counts"] = {
        "reviews": len(store.list_reviews()),
        "signals": len(list_signals()),
        "alphaHypotheses": len(list_alpha_hypotheses()),
    }
    return status
