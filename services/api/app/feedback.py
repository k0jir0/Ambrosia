"""
Feedback aggregator — computes decision quality metrics from recorded outcomes.

This module implements the feedback loop for Index52 Todo 2:
- Accepts outcome records (decision + realized result)
- Computes realized PnL, accuracy, and calibration error
- Aggregates per cohort (ticker, asset class, time horizon, confidence band)
- Exposes calibration quality view in workbench
- Persists feedback data durably (Postgres when DATABASE_URL set)

Data flow:
1. Operator records outcome: POST /packets/{id}/outcome
   - Decision: "watch" at 65% confidence
   - Outcome: "won" (decision was correct)
   - PnL: +2.5% realized return
   
2. Aggregator processes outcome and computes feedback:
   - Decision accuracy: was "watch" correct?
   - Calibration: at 65% confidence, how often was this right? (target: 65% accuracy)
   - Confidence well-calibrated: yes/no
   
3. Results persisted and indexed by cohort:
   - Cohort: ticker="SPY", asset_class="ETF", horizon="2-6 weeks", confidence_band="60-70%"
   - Count: 10 decisions in this cohort
   - Accuracy: 7/10 (70%) ← well-calibrated (target 65%)
   
4. Workbench displays calibration view:
   - "At 60-70% confidence over 30 packets, accuracy was 70%"
   - Flags over-confident (target 65%, actual 80%+) or under-confident (target 65%, actual <50%)
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class OutcomeResult(str, Enum):
    """Realized outcome of a decision."""
    won = "won"              # Decision was correct
    lost = "lost"            # Decision was incorrect
    whipsaw = "whipsaw"      # Decision oscillated (initially correct, then wrong, net negative)
    invalidated = "invalidated"  # Market moved in opposite direction beyond thesis invalidation test
    no_setup = "no_setup"    # Setup never materialized (thesis conditions not met)
    partial = "partial"      # Partial win (thesis correct but position size wrong, or half-size)


class FeedbackRecord(BaseModel):
    """Feedback record linking a decision to its realized outcome."""
    id: str = Field(default_factory=lambda: f"feedback-{uuid4().hex[:10]}")
    packet_id: str
    decision_state: str  # "watch", "pursue", "reject", etc.
    confidence: int = Field(ge=0, le=100)  # Confidence level at decision time
    
    # Cohort dimensions for aggregation
    ticker: str
    asset_class: str  # "ETF", "Stock", "Future", etc.
    time_horizon: str  # "2-6 weeks", "1-3 months", etc.
    
    # Outcome information
    outcome_date: str  # ISO date when outcome was realized
    outcome: OutcomeResult  # won/lost/whipsaw/etc.
    pnl: float | None = None  # Realized P&L in percent
    notes: str = ""
    
    # Metadata
    recorded_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    recorded_by: str = ""  # User ID or system identifier


class CalibrationBand(BaseModel):
    """Aggregated calibration metrics for a confidence band."""
    confidence_band: str  # "60-70%", "70-80%", etc.
    
    # Counts
    decisions: int = 0
    wins: int = 0
    losses: int = 0
    whipsaws: int = 0
    partials: int = 0
    
    # Derived metrics
    accuracy: float = 0.0  # wins / (wins + losses + whipsaws), 0-1
    win_rate: float = 0.0  # wins / decisions, 0-1
    partial_recovery_rate: float = 0.0  # partials / (partials + losses), 0-1
    
    # Calibration assessment
    target_accuracy: float = 0.5  # Default to 50%; will be set by compute_calibration_band
    calibration_error: float = 0.0  # |actual_accuracy - target_accuracy|
    is_well_calibrated: bool = True  # Within ±5% of target
    calibration_status: Literal["under-confident", "well-calibrated", "over-confident"] = "well-calibrated"
    
    # Historical data
    last_updated: str = Field(default_factory=lambda: datetime.now().isoformat())
    recent_packets: list[str] = []  # Last N packet IDs in this band


class CohortCalibration(BaseModel):
    """Aggregated calibration metrics for a decision cohort (ticker, asset class, etc.)."""
    id: str = Field(default_factory=lambda: f"cohort-{uuid4().hex[:10]}")
    
    # Cohort dimensions
    ticker: str
    asset_class: str
    time_horizon: str
    
    # Confidence band breakdown
    bands: dict[str, CalibrationBand] = {}  # Key: "60-70%", value: CalibrationBand
    
    # Overall metrics
    total_decisions: int = 0
    overall_accuracy: float = 0.0
    
    # Assessment flags
    flags: dict[str, bool] = Field(default_factory=dict)  # any_over_confident, any_under_confident


class CalibrationAlert(BaseModel):
    """Alert flagging over/under-confident decision patterns."""
    id: str = Field(default_factory=lambda: f"alert-{uuid4().hex[:10]}")
    ticker: str
    asset_class: str
    time_horizon: str
    confidence_band: str  # "60-70%"
    alert_type: Literal["over-confident", "under-confident"]
    target_accuracy: float
    actual_accuracy: float
    calibration_error: float
    decision_count: int
    severity: Literal["info", "warning", "critical"]
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class CalibrationSummary(BaseModel):
    """Summary of calibration quality across all cohorts."""
    total_decisions: int = 0
    overall_accuracy: float = 0.0
    total_alerts: int = 0
    over_confident_count: int = 0
    under_confident_count: int = 0
    well_calibrated_count: int = 0


def compute_confidence_band(confidence: int) -> str:
    """Map confidence level to band. E.g., 65 -> '60-70%'."""
    band_low = (confidence // 10) * 10
    band_high = band_low + 10
    return f"{band_low}-{band_high}%"


def assess_calibration(actual_accuracy: float, target_accuracy: float, threshold: float = 0.05) -> tuple[bool, Literal["under-confident", "well-calibrated", "over-confident"]]:
    """
    Assess if confidence level is well-calibrated.
    
    Args:
        actual_accuracy: Observed accuracy (0-1)
        target_accuracy: Target accuracy matching confidence level (0-1)
        threshold: Tolerance band around target (default 5%)
    
    Returns:
        (is_well_calibrated, status_label)
    """
    error = actual_accuracy - target_accuracy
    
    if error > threshold:
        return False, "over-confident"  # Actual > target: too confident
    elif error < -threshold:
        return False, "under-confident"  # Actual < target: not confident enough
    else:
        return True, "well-calibrated"  # Within tolerance


def compute_calibration_band(
    decisions: int,
    wins: int,
    losses: int,
    whipsaws: int = 0,
    partials: int = 0,
    confidence_level: int = 65,
) -> CalibrationBand:
    """
    Compute calibration metrics for a confidence band.
    
    Args:
        decisions: Total decisions in band
        wins: Decisions that were correct
        losses: Decisions that were wrong
        whipsaws: Decisions that oscillated (initially right, then wrong)
        partials: Decisions that were partially correct
        confidence_level: Confidence level for this band (used to compute target accuracy)
    
    Returns:
        CalibrationBand with computed metrics
    """
    band_str = compute_confidence_band(confidence_level)
    target_accuracy = confidence_level / 100.0
    
    # Accuracy: wins / (wins + losses + whipsaws)
    # Partials count as half-wins for accuracy calculation
    accuracy_denominator = wins + losses + whipsaws + partials
    if accuracy_denominator == 0:
        accuracy = 0.0
    else:
        accuracy = (wins + 0.5 * partials) / accuracy_denominator
    
    # Win rate: wins / total decisions
    win_rate = wins / decisions if decisions > 0 else 0.0
    
    # Partial recovery rate: how often partials occur vs losses
    partial_recovery_rate = partials / (partials + losses) if (partials + losses) > 0 else 0.0
    
    # Calibration assessment
    is_well_calibrated, status = assess_calibration(accuracy, target_accuracy)
    calibration_error = abs(accuracy - target_accuracy)
    
    band = CalibrationBand(
        confidence_band=band_str,
        decisions=decisions,
        wins=wins,
        losses=losses,
        whipsaws=whipsaws,
        partials=partials,
        accuracy=round(accuracy, 3),
        win_rate=round(win_rate, 3),
        partial_recovery_rate=round(partial_recovery_rate, 3),
        target_accuracy=round(target_accuracy, 3),
        calibration_error=round(calibration_error, 3),
        is_well_calibrated=is_well_calibrated,
        calibration_status=status,
    )
    return band
