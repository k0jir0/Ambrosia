"""
Calibration metrics — measures decision quality across 8 core functions.

Implements Index52 Todo 3: compute 8 metrics that feed into operational scorecard.
Each metric has a target value and status determination (ok/warning/critical).

Metrics:
1. Review Validity (75% target) - review → packet conversion
2. Decision Consistency (100%) - decision state frequency
3. Packet Integrity (90%) - required field completeness
4. Data Quality (95%) - market data freshness & availability
5. Agent Consensus (70%) - specialist agent agreement
6. Backtest Validity (0.75 correlation) - backtest prediction accuracy
7. Risk Estimate Accuracy (80%) - risk alert accuracy
8. Confidence Calibration (N% → N%) - confidence band calibration

Data flow:
1. store.get_calibration_metrics() called by health check
2. Computes all 8 metrics in parallel
3. Returns CalibrationMetricsBoard with aggregated results
4. Health check includes metrics + overall_status
5. Operational scorecard (Todo 4) uses these metrics for certification
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ===== METRIC DATA MODELS =====

class ReviewValidityMetric(BaseModel):
    """Measures review → packet conversion rate."""
    total_reviews: int = 0
    reviews_converted: int = 0
    conversion_rate: float = 0.0
    target: float = 0.75
    status: Literal["ok", "low"] = "ok"
    last_updated: str = Field(default_factory=lambda: datetime.now().isoformat())


class DecisionConsistencyMetric(BaseModel):
    """Measures consistency of decision states within cohorts."""
    cohort: str  # "SPY/ETF/2-6 weeks"
    total_decisions: int = 0
    dominant_state: str | None = None
    dominant_state_count: int = 0
    consistency_score: float = 0.0
    target: float = 1.0
    status: Literal["ok", "warning"] = "ok"


class PacketIntegrityMetric(BaseModel):
    """Measures completeness of required packet fields."""
    total_packets: int = 0
    complete_packets: int = 0
    integrity_score: float = 0.0
    target: float = 0.90
    missing_fields: dict[str, int] = {}  # field -> count missing
    status: Literal["ok", "warning"] = "ok"


class DataQualityMetric(BaseModel):
    """Measures freshness and availability of market data."""
    total_packets: int = 0
    with_market_data: int = 0
    with_live_data: int = 0  # not fallback
    with_fresh_data: int = 0  # <5 min old
    quality_score: float = 0.0
    fallback_count: int = 0
    target: float = 0.95
    status: Literal["ok", "degraded"] = "ok"


class AgentConsensusMetric(BaseModel):
    """Measures agreement between specialist agents."""
    total_packets: int = 0
    packets_multi_agent: int = 0
    consensus_packets: int = 0  # agreement detected
    avg_consensus_score: float = 0.0
    divergence_count: int = 0
    target: float = 0.70
    status: Literal["ok", "warning"] = "ok"


class BacktestValidityMetric(BaseModel):
    """Correlates backtest predictions with live outcomes."""
    total_cohorts: int = 0
    cohorts_backtested: int = 0
    avg_correlation: float = 0.0
    prediction_error: float = 0.0
    aligned_cohorts: int = 0  # correlation >= target
    target: float = 0.75
    status: Literal["ok", "warning"] = "ok"


class RiskEstimateMetric(BaseModel):
    """Measures risk alert accuracy."""
    total_packets: int = 0
    high_risk_alerts: int = 0
    high_risk_accurate: int = 0
    low_risk_alerts: int = 0
    low_risk_accurate: int = 0
    estimate_accuracy: float = 0.0
    target: float = 0.80
    status: Literal["ok", "warning"] = "ok"


class ConfidenceCalibrationMetric(BaseModel):
    """Measures confidence band calibration (N% confidence → N% accuracy)."""
    total_bands: int = 0
    well_calibrated_bands: int = 0
    over_confident_bands: int = 0
    under_confident_bands: int = 0
    calibration_score: float = 0.0
    target: float = 0.75
    status: Literal["ok", "warning"] = "ok"


class CalibrationMetricsBoard(BaseModel):
    """Complete metrics snapshot for platform health."""
    review_validity: ReviewValidityMetric
    decision_consistency_avg: float = 0.0  # average across cohorts
    packet_integrity: PacketIntegrityMetric
    data_quality: DataQualityMetric
    agent_consensus: AgentConsensusMetric
    backtest_validity: BacktestValidityMetric
    risk_estimate: RiskEstimateMetric
    confidence_calibration: ConfidenceCalibrationMetric
    
    computed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    overall_status: Literal["ok", "warning", "critical"] = "ok"


# ===== METRIC COMPUTATION FUNCTIONS =====

def compute_review_validity(store) -> ReviewValidityMetric:
    """Compute review → packet conversion rate."""
    reviews = store.list_reviews()
    packets = store.list_packets()
    
    if not reviews:
        return ReviewValidityMetric(total_reviews=0, status="ok")
    
    converted = 0
    for packet in packets:
        # Check if packet was created from a review
        for event in packet.audit:
            if event.eventType == "review.converted_to_packet":
                converted += 1
                break
    
    rate = converted / len(reviews)
    return ReviewValidityMetric(
        total_reviews=len(reviews),
        reviews_converted=converted,
        conversion_rate=round(rate, 3),
        status="ok" if rate >= 0.75 else "low"
    )


def compute_decision_consistency(store) -> float:
    """Compute average consistency of decision states within cohorts."""
    from collections import defaultdict
    
    packets = store.list_packets()
    if not packets:
        return 1.0
    
    # Group by (ticker, assetClass, timeHorizon)
    cohorts = defaultdict(lambda: defaultdict(int))
    for packet in packets:
        if packet.decisionState:
            key = (packet.ticker.lower(), packet.assetClass.lower(), packet.timeHorizon.lower())
            cohorts[key][packet.decisionState.value] += 1
    
    # For each cohort, compute consistency (max frequency / total)
    if not cohorts:
        return 1.0
    
    scores = []
    for cohort_decisions in cohorts.values():
        total = sum(cohort_decisions.values())
        max_count = max(cohort_decisions.values())
        consistency = max_count / total if total > 0 else 0.0
        scores.append(consistency)
    
    return round(sum(scores) / len(scores), 3) if scores else 1.0


def compute_packet_integrity(store) -> PacketIntegrityMetric:
    """Check completeness of required packet fields."""
    packets = store.list_packets()
    
    required_fields = [
        "id", "ticker", "assetClass", "timeHorizon",
        "confidence", "decisionState", "thesis"
    ]
    
    if not packets:
        return PacketIntegrityMetric(total_packets=0)
    
    complete = 0
    missing_counts = {field: 0 for field in required_fields}
    
    for packet in packets:
        all_present = True
        for field in required_fields:
            value = getattr(packet, field, None)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing_counts[field] += 1
                all_present = False
        
        if all_present:
            complete += 1
    
    integrity = complete / len(packets)
    return PacketIntegrityMetric(
        total_packets=len(packets),
        complete_packets=complete,
        integrity_score=round(integrity, 3),
        missing_fields={k: v for k, v in missing_counts.items() if v > 0},
        status="ok" if integrity >= 0.90 else "warning"
    )


def compute_data_quality(store) -> DataQualityMetric:
    """Measure freshness and availability of market data."""
    from datetime import datetime as dt, timedelta
    
    packets = store.list_packets()
    if not packets:
        return DataQualityMetric(total_packets=0)
    
    with_market_data = 0
    with_live_data = 0
    with_fresh_data = 0
    
    for packet in packets:
        if packet.marketSnapshot:
            with_market_data += 1
            
            # Check if live (not fallback)
            mode = getattr(packet.marketSnapshot, "dataMode", "fallback")
            if mode not in ["fallback", "cached"]:
                with_live_data += 1
            
            # Check freshness (<5 min old)
            timestamp_str = getattr(packet.marketSnapshot, "timestamp", None)
            if timestamp_str:
                try:
                    timestamp = dt.fromisoformat(timestamp_str)
                    age = dt.now() - timestamp
                    if age < timedelta(minutes=5):
                        with_fresh_data += 1
                except (ValueError, TypeError):
                    pass
    
    quality = (with_market_data + with_live_data + with_fresh_data) / (3 * len(packets))
    fallback = len(packets) - with_live_data
    
    return DataQualityMetric(
        total_packets=len(packets),
        with_market_data=with_market_data,
        with_live_data=with_live_data,
        with_fresh_data=with_fresh_data,
        quality_score=round(quality, 3),
        fallback_count=fallback,
        status="ok" if quality >= 0.95 else "degraded"
    )


def compute_agent_consensus(store) -> AgentConsensusMetric:
    """Measure agreement between specialist agents."""
    packets = store.list_packets()
    if not packets:
        return AgentConsensusMetric(total_packets=0)
    
    multi_agent = 0
    consensus_count = 0
    total_consensus = 0.0
    
    for packet in packets:
        agent_outputs = getattr(packet, "agentOutputs", None)
        if agent_outputs and len(agent_outputs) > 1:
            multi_agent += 1
            
            # Simple consensus: check if all agents agree on decision direction
            # For now, use confidence breakdown variance
            confidence_breakdown = getattr(packet, "confidenceBreakdown", None)
            if confidence_breakdown:
                scores = []
                for component in [
                    getattr(confidence_breakdown, "evidence", 0),
                    getattr(confidence_breakdown, "technicalScore", 0),
                    getattr(confidence_breakdown, "sentimentScore", 0),
                ]:
                    if component:
                        scores.append(component)
                
                if len(scores) > 1:
                    avg = sum(scores) / len(scores)
                    variance = sum((x - avg) ** 2 for x in scores) / len(scores)
                    # Low variance = high consensus (normalize to 0-1)
                    consensus = 1.0 - min(variance / 50, 1.0)  # Normalize by expected max variance
                    total_consensus += consensus
                    if consensus > 0.70:
                        consensus_count += 1
    
    avg_consensus = (total_consensus / multi_agent) if multi_agent > 0 else 0.0
    
    return AgentConsensusMetric(
        total_packets=len(packets),
        packets_multi_agent=multi_agent,
        consensus_packets=consensus_count,
        avg_consensus_score=round(avg_consensus, 3),
        divergence_count=max(0, multi_agent - consensus_count),
        status="ok" if avg_consensus >= 0.70 else "warning"
    )


def compute_backtest_validity(store) -> BacktestValidityMetric:
    """Correlate backtest predictions with live outcomes."""
    from collections import defaultdict
    
    packets = store.list_packets()
    feedback_records = list(store._feedback_records.values()) if hasattr(store, '_feedback_records') else []
    
    if not packets or not feedback_records:
        return BacktestValidityMetric(total_packets=0)
    
    # Group by cohort and compare backtest predictions to actual outcomes
    cohort_correlations = defaultdict(lambda: {"predicted": [], "actual": []})
    
    for packet in packets:
        if packet.backtestResult:
            key = (packet.ticker.lower(), packet.assetClass.lower(), packet.timeHorizon.lower())
            predicted_accuracy = getattr(packet.backtestResult, "expectedWinRate", 0.5)
            cohort_correlations[key]["predicted"].append(predicted_accuracy)
    
    for feedback in feedback_records:
        key = (feedback.ticker.lower(), feedback.asset_class.lower(), feedback.time_horizon.lower())
        actual = 1.0 if feedback.outcome.value == "won" else (0.5 if feedback.outcome.value == "partial" else 0.0)
        cohort_correlations[key]["actual"].append(actual)
    
    # Compute correlation for cohorts with both prediction and actual
    correlations = []
    aligned = 0
    
    for key, data in cohort_correlations.items():
        if data["predicted"] and data["actual"]:
            predicted_mean = sum(data["predicted"]) / len(data["predicted"])
            actual_mean = sum(data["actual"]) / len(data["actual"])
            
            # Simple correlation: compare means
            correlation = 1.0 - abs(predicted_mean - actual_mean)
            correlations.append(correlation)
            
            if correlation >= 0.75:
                aligned += 1
    
    avg_correlation = (sum(correlations) / len(correlations)) if correlations else 0.0
    prediction_error = sum(abs(p - a) for p, a in zip(
        [x["predicted"][0] if x["predicted"] else 0.5 for x in cohort_correlations.values()],
        [sum(x["actual"]) / len(x["actual"]) if x["actual"] else 0.5 for x in cohort_correlations.values()]
    )) / max(len(cohort_correlations), 1)
    
    return BacktestValidityMetric(
        total_cohorts=len(cohort_correlations),
        cohorts_backtested=sum(1 for x in cohort_correlations.values() if x["predicted"] and x["actual"]),
        avg_correlation=round(avg_correlation, 3),
        prediction_error=round(prediction_error, 3),
        aligned_cohorts=aligned,
        status="ok" if avg_correlation >= 0.75 else "warning"
    )


def compute_risk_estimate_accuracy(store) -> RiskEstimateMetric:
    """Measure risk alert accuracy."""
    packets = store.list_packets()
    feedback_records = list(store._feedback_records.values()) if hasattr(store, '_feedback_records') else []
    
    if not packets:
        return RiskEstimateMetric(total_packets=0)
    
    high_risk_alerts = 0
    high_risk_accurate = 0
    low_risk_alerts = 0
    low_risk_accurate = 0
    
    for packet in packets:
        risk_monitor = getattr(packet, "riskMonitor", None)
        if not risk_monitor:
            continue
        
        risk_level = getattr(risk_monitor, "overallRiskLevel", "medium")
        max_drawdown = getattr(risk_monitor, "maxDrawdown", 0.0)
        
        # Determine if high risk
        is_high_risk = risk_level == "high" or max_drawdown > 0.15
        
        # Find corresponding feedback
        feedback = next((f for f in feedback_records if f.packet_id == packet.id), None)
        if feedback:
            from .feedback import OutcomeResult
            is_loss = feedback.outcome in [OutcomeResult.lost, OutcomeResult.whipsaw]
            
            if is_high_risk:
                high_risk_alerts += 1
                if is_loss:
                    high_risk_accurate += 1
            else:
                low_risk_alerts += 1
                if not is_loss:
                    low_risk_accurate += 1
    
    total_alerts = high_risk_alerts + low_risk_alerts
    if total_alerts > 0:
        accuracy = (high_risk_accurate + low_risk_accurate) / total_alerts
    else:
        accuracy = 0.0
    
    return RiskEstimateMetric(
        total_packets=len(packets),
        high_risk_alerts=high_risk_alerts,
        high_risk_accurate=high_risk_accurate,
        low_risk_alerts=low_risk_alerts,
        low_risk_accurate=low_risk_accurate,
        estimate_accuracy=round(accuracy, 3),
        status="ok" if accuracy >= 0.80 else "warning"
    )


def compute_confidence_calibration(store) -> ConfidenceCalibrationMetric:
    """Measure overall confidence band calibration."""
    # Use existing calibration summary from feedback system
    if not hasattr(store, 'get_calibration_summary'):
        return ConfidenceCalibrationMetric(total_bands=0)
    
    cal_summary = store.get_calibration_summary()
    
    total_bands = (
        cal_summary.well_calibrated_count + 
        cal_summary.over_confident_count + 
        cal_summary.under_confident_count
    )
    
    if total_bands == 0:
        return ConfidenceCalibrationMetric(total_bands=0)
    
    calibration_score = cal_summary.well_calibrated_count / total_bands
    
    return ConfidenceCalibrationMetric(
        total_bands=total_bands,
        well_calibrated_bands=cal_summary.well_calibrated_count,
        over_confident_bands=cal_summary.over_confident_count,
        under_confident_bands=cal_summary.under_confident_count,
        calibration_score=round(calibration_score, 3),
        status="ok" if calibration_score >= 0.75 else "warning"
    )


def compute_all_metrics(store) -> CalibrationMetricsBoard:
    """Compute all 8 metrics and return aggregated board."""
    # Compute each metric
    review_validity = compute_review_validity(store)
    decision_consistency_avg = compute_decision_consistency(store)
    packet_integrity = compute_packet_integrity(store)
    data_quality = compute_data_quality(store)
    agent_consensus = compute_agent_consensus(store)
    backtest_validity = compute_backtest_validity(store)
    risk_estimate = compute_risk_estimate_accuracy(store)
    confidence_calibration = compute_confidence_calibration(store)
    
    # Determine overall status
    statuses = [
        review_validity.status,
        packet_integrity.status,
        data_quality.status,
        agent_consensus.status,
        backtest_validity.status,
        risk_estimate.status,
        confidence_calibration.status,
    ]
    
    if "critical" in statuses:
        overall_status = "critical"
    elif "warning" in statuses:
        overall_status = "warning"
    else:
        overall_status = "ok"
    
    return CalibrationMetricsBoard(
        review_validity=review_validity,
        decision_consistency_avg=decision_consistency_avg,
        packet_integrity=packet_integrity,
        data_quality=data_quality,
        agent_consensus=agent_consensus,
        backtest_validity=backtest_validity,
        risk_estimate=risk_estimate,
        confidence_calibration=confidence_calibration,
        overall_status=overall_status
    )
