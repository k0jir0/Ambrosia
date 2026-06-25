"""
Feedback aggregator API endpoints — handles outcome records and calibration queries.

Integrates with the main FastAPI app to:
1. Accept POST /packets/{id}/outcome with feedback context
2. Route to feedback aggregator for calibration computation
3. Expose GET /calibration endpoints for workbench queries
4. Persist calibration data to Postgres (if DATABASE_URL set)
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .feedback import (
    FeedbackRecord,
    CalibrationBand,
    CohortCalibration,
    CalibrationAlert,
    CalibrationSummary,
    compute_confidence_band,
    compute_calibration_band,
    assess_calibration,
)
from .models import DecisionPacket
from .store import store

# Router for feedback-related endpoints
feedback_router = APIRouter(prefix="/feedback", tags=["feedback"])


# -----------------------------------------------------------------------
# Calibration Query Endpoints
# -----------------------------------------------------------------------

@feedback_router.get("/calibration/cohort", response_model=CohortCalibration)
def get_cohort_calibration(
    ticker: str = Query(..., description="Ticker symbol"),
    asset_class: str = Query(..., description="Asset class (ETF, Stock, etc.)"),
    time_horizon: str = Query(..., description="Time horizon (2-6 weeks, etc.)"),
) -> CohortCalibration:
    """
    Get aggregated calibration metrics for a decision cohort.
    
    Example: GET /feedback/calibration/cohort?ticker=SPY&asset_class=ETF&time_horizon=2-6%20weeks
    
    Returns:
        CohortCalibration with:
        - Accuracy by confidence band (60-70%, 70-80%, etc.)
        - Well-calibration assessment per band
        - Flags for over/under-confident patterns
    """
    cohort_data = store.get_cohort_calibration(ticker, asset_class, time_horizon)
    if cohort_data is None:
        # Return empty cohort if no data yet
        return CohortCalibration(
            ticker=ticker,
            asset_class=asset_class,
            time_horizon=time_horizon,
        )
    return cohort_data


@feedback_router.get("/calibration/band", response_model=CalibrationBand)
def get_band_calibration(
    ticker: str = Query(..., description="Ticker symbol"),
    confidence_band: str = Query(..., description="Confidence band (e.g., 60-70%)"),
) -> CalibrationBand:
    """
    Get calibration metrics for a specific confidence band across all time horizons.
    
    Example: GET /feedback/calibration/band?ticker=SPY&confidence_band=60-70%
    
    Returns:
        CalibrationBand with:
        - Decision count in band
        - Accuracy (target vs actual)
        - Calibration status (well-calibrated, over-confident, under-confident)
    """
    band_data = store.get_band_calibration(ticker, confidence_band)
    if band_data is None:
        # Return empty band if no data
        return CalibrationBand(
            confidence_band=confidence_band,
            decisions=0,
        )
    return band_data


@feedback_router.get("/calibration/summary", response_model=CalibrationSummary)
def get_calibration_summary() -> CalibrationSummary:
    """
    Get high-level summary of calibration quality across all cohorts.
    
    Example: GET /feedback/calibration/summary
    
    Returns:
        CalibrationSummary with:
        - Total feedback records processed
        - Count of well-calibrated vs over/under-confident cohorts
        - Top 3 over-confident and under-confident cohorts
        - Active alerts
    """
    return store.get_calibration_summary()


@feedback_router.get("/calibration/alerts", response_model=list[CalibrationAlert])
def list_calibration_alerts(
    severity: str = Query("warning", description="Filter by severity: info, warning, critical"),
    ticker: Optional[str] = Query(None, description="Filter by ticker"),
) -> list[CalibrationAlert]:
    """
    List active calibration alerts (over/under-confident patterns).
    
    Example: GET /feedback/calibration/alerts?severity=warning
    Example: GET /feedback/calibration/alerts?ticker=SPY&severity=critical
    
    Returns:
        List of CalibrationAlert with details on which bands need review.
    """
    return store.list_calibration_alerts(severity=severity, ticker=ticker)


# -----------------------------------------------------------------------
# Feedback Record Endpoints
# -----------------------------------------------------------------------

@feedback_router.post("/record", response_model=FeedbackRecord)
def record_feedback(
    packet_id: str,
    feedback: FeedbackRecord,
) -> FeedbackRecord:
    """
    Record outcome feedback for a decision packet.
    
    This endpoint is typically called after a decision outcome is known.
    
    Example request:
    ```json
    POST /feedback/record?packet_id=packet-123
    {
        "decision_state": "watch",
        "confidence": 65,
        "ticker": "SPY",
        "asset_class": "ETF",
        "time_horizon": "2-6 weeks",
        "outcome_date": "2026-07-15",
        "outcome": "won",
        "pnl": 2.5,
        "notes": "Thesis validated; breadth expansion held"
    }
    ```
    
    Returns:
        FeedbackRecord with ID assigned
    """
    # Verify packet exists
    packet = store.get_packet(packet_id)
    if packet is None:
        raise HTTPException(status_code=404, detail=f"Packet {packet_id} not found")
    
    # Enrich feedback with packet ID and persist
    feedback_record = FeedbackRecord(
        packet_id=packet_id,
        decision_state=feedback.decision_state or "watch",
        confidence=feedback.confidence,
        ticker=feedback.ticker,
        asset_class=feedback.asset_class,
        time_horizon=feedback.time_horizon,
        outcome_date=feedback.outcome_date,
        outcome=feedback.outcome,
        pnl=feedback.pnl,
        notes=feedback.notes,
    )
    
    # Persist feedback
    stored_feedback = store.save_feedback_record(feedback_record)
    
    # Update cohort calibration (recompute metrics)
    cohort_key = (feedback.ticker, feedback.asset_class, feedback.time_horizon)
    store.recompute_cohort_calibration(*cohort_key)
    
    return stored_feedback


@feedback_router.get("/records", response_model=list[FeedbackRecord])
def list_feedback_records(
    ticker: Optional[str] = Query(None),
    decision_state: Optional[str] = Query(None),
    outcome: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
) -> list[FeedbackRecord]:
    """
    List feedback records with optional filters.
    
    Example: GET /feedback/records?ticker=SPY&decision_state=watch&limit=50
    
    Returns:
        List of FeedbackRecord, ordered by recorded_at (newest first)
    """
    return store.list_feedback_records(
        ticker=ticker,
        decision_state=decision_state,
        outcome=outcome,
        limit=limit,
    )


@feedback_router.get("/records/{feedback_id}", response_model=FeedbackRecord)
def get_feedback_record(feedback_id: str) -> FeedbackRecord:
    """
    Get a specific feedback record by ID.
    
    Example: GET /feedback/records/feedback-abc123
    """
    record = store.get_feedback_record(feedback_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Feedback record {feedback_id} not found")
    return record


# -----------------------------------------------------------------------
# Calibration Health Check Integration
# -----------------------------------------------------------------------

def get_calibration_health_info() -> dict:
    """
    Return calibration health info for inclusion in /health/detailed endpoint.
    
    Example:
    ```json
    {
        "calibration": {
            "feedbackRecordsProcessed": 42,
            "cohortsAnalyzed": 5,
            "wellCalibratedCohorts": 4,
            "overConfidentCohorts": 1,
            "underConfidentCohorts": 0,
            "activeAlerts": 2
        }
    }
    ```
    """
    summary = store.get_calibration_summary()
    return {
        "calibration": {
            "feedbackRecordsProcessed": summary.total_feedback_records,
            "cohortsAnalyzed": summary.cohorts_analyzed,
            "wellCalibratedCohorts": summary.cohorts_well_calibrated,
            "overConfidentCohorts": summary.cohorts_over_confident,
            "underConfidentCohorts": summary.cohorts_under_confident,
            "activeAlerts": len(summary.alerts),
        }
    }
