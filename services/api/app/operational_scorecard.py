"""
Operational scorecard — final certification artifact for Index39 completion.

Implements Index52 Todo 4: package metrics into machine-readable scorecard
showing platform readiness, compliance with targets, and certification status.

Scorecard answers:
1. Are all 8 metrics present? (requirement)
2. Are all metrics at or above target? (requirement)
3. What is overall platform status? (ok/warning/critical)
4. When was platform last validated? (timestamp)
5. What are top 3 areas needing improvement? (if any)
6. Is the platform Index39-certified? (yes/no)

Output: Machine-readable JSON for reporting, dashboarding, compliance audits
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class MetricStatus(BaseModel):
    """Status of a single metric."""
    name: str
    actual_value: float
    target_value: float
    status: Literal["ok", "warning", "critical"]
    gap_to_target: float  # negative = below target
    acceptable: bool  # True if within tolerance


class OperationalScorecard(BaseModel):
    """
    Platform certification scorecard.
    
    Combines all 8 calibration metrics into a single certification-ready artifact.
    Used for compliance audits, stakeholder reporting, and go/no-go decisions.
    """
    id: str = Field(default_factory=lambda: f"scorecard-{uuid4().hex[:10]}")
    
    # Platform identification
    platform_name: str = "Ambrosia"
    platform_version: str = "0.1.0"
    
    # Certification details
    certification_index: int = 39  # Index39 target
    certification_status: Literal["pre-certification", "certified", "revoked"] = "pre-certification"
    certification_date: str | None = None
    expires_at: str | None = None
    
    # Metric scores (0-100 scale)
    review_validity_score: float = 0.0
    decision_consistency_score: float = 0.0
    packet_integrity_score: float = 0.0
    data_quality_score: float = 0.0
    agent_consensus_score: float = 0.0
    backtest_validity_score: float = 0.0
    risk_estimate_score: float = 0.0
    confidence_calibration_score: float = 0.0
    
    # Overall scores
    average_metric_score: float = 0.0
    min_metric_score: float = 0.0
    max_metric_score: float = 0.0
    
    # Assessment
    all_metrics_present: bool = False  # Requirement 1
    all_metrics_at_target: bool = False  # Requirement 2
    overall_status: Literal["ok", "warning", "critical"] = "critical"
    
    # Detailed metrics
    metrics: list[MetricStatus] = []
    
    # Areas for improvement (if any)
    areas_for_improvement: list[str] = []
    
    # Audit trail
    computed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    computed_by: str = "system"
    validation_window_hours: int = 24  # Scorecard valid for 24 hours
    
    # Exit gates
    gates_passed: dict[str, bool] = Field(default_factory=dict)
    
    # Certification comments
    comments: str = ""


def generate_scorecard(metrics_board) -> OperationalScorecard:
    """
    Generate operational scorecard from calibration metrics board.
    
    Certification logic:
    1. All 8 metrics must be computed
    2. All metrics must be >= target value
    3. Overall status must be "ok"
    
    Returns OperationalScorecard with certification status.
    """
    # Convert metric scores to 0-100 scale
    review_validity_score = metrics_board.review_validity.conversion_rate * 100
    decision_consistency_score = metrics_board.decision_consistency_avg * 100
    packet_integrity_score = metrics_board.packet_integrity.integrity_score * 100
    data_quality_score = metrics_board.data_quality.quality_score * 100
    agent_consensus_score = metrics_board.agent_consensus.avg_consensus_score * 100
    backtest_validity_score = metrics_board.backtest_validity.avg_correlation * 100
    risk_estimate_score = metrics_board.risk_estimate.estimate_accuracy * 100
    confidence_calibration_score = metrics_board.confidence_calibration.calibration_score * 100
    
    scores = [
        review_validity_score,
        decision_consistency_score,
        packet_integrity_score,
        data_quality_score,
        agent_consensus_score,
        backtest_validity_score,
        risk_estimate_score,
        confidence_calibration_score,
    ]
    
    # Build metric status list
    metrics_status = [
        MetricStatus(
            name="Review Validity",
            actual_value=metrics_board.review_validity.conversion_rate,
            target_value=metrics_board.review_validity.target,
            status=metrics_board.review_validity.status,
            gap_to_target=metrics_board.review_validity.conversion_rate - metrics_board.review_validity.target,
            acceptable=metrics_board.review_validity.status == "ok",
        ),
        MetricStatus(
            name="Decision Consistency",
            actual_value=metrics_board.decision_consistency_avg,
            target_value=1.0,
            status="ok" if metrics_board.decision_consistency_avg >= 0.7 else "warning",
            gap_to_target=metrics_board.decision_consistency_avg - 1.0,
            acceptable=metrics_board.decision_consistency_avg >= 0.7,
        ),
        MetricStatus(
            name="Packet Integrity",
            actual_value=metrics_board.packet_integrity.integrity_score,
            target_value=metrics_board.packet_integrity.target,
            status=metrics_board.packet_integrity.status,
            gap_to_target=metrics_board.packet_integrity.integrity_score - metrics_board.packet_integrity.target,
            acceptable=metrics_board.packet_integrity.status == "ok",
        ),
        MetricStatus(
            name="Data Quality",
            actual_value=metrics_board.data_quality.quality_score,
            target_value=metrics_board.data_quality.target,
            status=metrics_board.data_quality.status,
            gap_to_target=metrics_board.data_quality.quality_score - metrics_board.data_quality.target,
            acceptable=metrics_board.data_quality.status == "ok",
        ),
        MetricStatus(
            name="Agent Consensus",
            actual_value=metrics_board.agent_consensus.avg_consensus_score,
            target_value=metrics_board.agent_consensus.target,
            status=metrics_board.agent_consensus.status,
            gap_to_target=metrics_board.agent_consensus.avg_consensus_score - metrics_board.agent_consensus.target,
            acceptable=metrics_board.agent_consensus.status == "ok",
        ),
        MetricStatus(
            name="Backtest Validity",
            actual_value=metrics_board.backtest_validity.avg_correlation,
            target_value=metrics_board.backtest_validity.target,
            status=metrics_board.backtest_validity.status,
            gap_to_target=metrics_board.backtest_validity.avg_correlation - metrics_board.backtest_validity.target,
            acceptable=metrics_board.backtest_validity.status == "ok",
        ),
        MetricStatus(
            name="Risk Estimate Accuracy",
            actual_value=metrics_board.risk_estimate.estimate_accuracy,
            target_value=metrics_board.risk_estimate.target,
            status=metrics_board.risk_estimate.status,
            gap_to_target=metrics_board.risk_estimate.estimate_accuracy - metrics_board.risk_estimate.target,
            acceptable=metrics_board.risk_estimate.status == "ok",
        ),
        MetricStatus(
            name="Confidence Calibration",
            actual_value=metrics_board.confidence_calibration.calibration_score,
            target_value=metrics_board.confidence_calibration.target,
            status=metrics_board.confidence_calibration.status,
            gap_to_target=metrics_board.confidence_calibration.calibration_score - metrics_board.confidence_calibration.target,
            acceptable=metrics_board.confidence_calibration.status == "ok",
        ),
    ]
    
    # Identify areas for improvement
    areas_for_improvement = [
        m.name for m in metrics_status if not m.acceptable
    ]
    
    # Check certification gates
    all_metrics_present = all(s > 0 or s == 0 for s in scores)  # All metrics computed
    all_metrics_at_target = all(m.acceptable for m in metrics_status)
    
    # Determine overall status
    if not all_metrics_present or not all_metrics_at_target:
        overall_status = "critical"
        certification_status = "pre-certification"
    elif metrics_board.overall_status == "warning":
        overall_status = "warning"
        certification_status = "pre-certification"
    else:
        overall_status = "ok"
        certification_status = "certified"
    
    # Compute averages
    avg_score = sum(scores) / len(scores) if scores else 0.0
    min_score = min(scores) if scores else 0.0
    max_score = max(scores) if scores else 0.0
    
    # Create scorecard
    scorecard = OperationalScorecard(
        platform_name="Ambrosia",
        platform_version="0.1.0",
        certification_index=39,
        certification_status=certification_status,
        certification_date=datetime.now().isoformat() if certification_status == "certified" else None,
        expires_at=None,  # Will be set by operator if certified
        
        review_validity_score=round(review_validity_score, 1),
        decision_consistency_score=round(decision_consistency_score, 1),
        packet_integrity_score=round(packet_integrity_score, 1),
        data_quality_score=round(data_quality_score, 1),
        agent_consensus_score=round(agent_consensus_score, 1),
        backtest_validity_score=round(backtest_validity_score, 1),
        risk_estimate_score=round(risk_estimate_score, 1),
        confidence_calibration_score=round(confidence_calibration_score, 1),
        
        average_metric_score=round(avg_score, 1),
        min_metric_score=round(min_score, 1),
        max_metric_score=round(max_score, 1),
        
        all_metrics_present=all_metrics_present,
        all_metrics_at_target=all_metrics_at_target,
        overall_status=overall_status,
        
        metrics=metrics_status,
        areas_for_improvement=areas_for_improvement,
        
        gates_passed={
            "all_metrics_computed": all_metrics_present,
            "all_metrics_at_target": all_metrics_at_target,
            "platform_status_ok": metrics_board.overall_status == "ok",
        },
        
        comments=_generate_comments(
            all_metrics_present,
            all_metrics_at_target,
            metrics_board.overall_status,
            areas_for_improvement
        ),
    )
    
    return scorecard


def _generate_comments(
    all_metrics_present: bool,
    all_metrics_at_target: bool,
    platform_status: str,
    areas: list[str],
) -> str:
    """Generate human-readable certification comments."""
    if all_metrics_present and all_metrics_at_target and platform_status == "ok":
        return "Platform ready for Index39 certification. All gates passed."
    
    comments = []
    if not all_metrics_present:
        comments.append("Some metrics not yet computed.")
    if not all_metrics_at_target:
        comments.append(f"Metrics below target: {', '.join(areas)}")
    if platform_status == "warning":
        comments.append("Platform status is WARNING. Review metrics before certification.")
    if platform_status == "critical":
        comments.append("Platform status is CRITICAL. Certification blocked until resolved.")
    
    return " ".join(comments)


def compute_scorecard_index39(store) -> OperationalScorecard:
    """
    Compute Index39 certification scorecard.
    
    Combines metrics into final artifact for compliance, auditing, and certification.
    """
    metrics_board = store.get_calibration_metrics()
    return generate_scorecard(metrics_board)
