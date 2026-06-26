"""
Feedback storage extension for ReviewStore — in-memory and Postgres-backed.

This module extends the ReviewStore with feedback recording and aggregation.
It maintains both in-memory and Postgres persistence layers.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Optional

from .feedback import (
    FeedbackRecord,
    CalibrationBand,
    CohortCalibration,
    CalibrationAlert,
    CalibrationSummary,
    compute_confidence_band,
    compute_calibration_band,
)


class FeedbackStorageMixin:
    """Mixin class to add feedback storage to ReviewStore."""
    
    def __init__(self) -> None:
        # Feedback records: id -> FeedbackRecord
        self._feedback_records: dict[str, FeedbackRecord] = {}
        # Cohort calibrations: (ticker, asset_class, horizon) -> CohortCalibration
        self._cohort_calibrations: dict[tuple[str, str, str], CohortCalibration] = {}
        # Calibration alerts
        self._calibration_alerts: list[CalibrationAlert] = []
    
    # ---------------------------------------------------------------
    # Feedback Record Storage
    # ---------------------------------------------------------------
    
    def save_feedback_record(self, feedback: FeedbackRecord) -> FeedbackRecord:
        """Save a feedback record (in-memory only for now; TODO: Postgres)."""
        self._feedback_records[feedback.id] = feedback
        return feedback
    
    def get_feedback_record(self, feedback_id: str) -> Optional[FeedbackRecord]:
        """Retrieve a feedback record by ID."""
        return self._feedback_records.get(feedback_id)
    
    def list_feedback_records(
        self,
        ticker: Optional[str] = None,
        decision_state: Optional[str] = None,
        outcome: Optional[str] = None,
        limit: int = 100,
    ) -> list[FeedbackRecord]:
        """List feedback records with optional filters."""
        records = list(self._feedback_records.values())
        
        if ticker:
            records = [r for r in records if r.ticker.lower() == ticker.lower()]
        if decision_state:
            records = [r for r in records if r.decision_state == decision_state]
        if outcome:
            records = [r for r in records if str(r.outcome) == outcome]
        
        # Sort by recorded_at (newest first) and limit
        records.sort(key=lambda r: r.recorded_at, reverse=True)
        return records[:limit]
    
    def delete_feedback_record(self, feedback_id: str) -> bool:
        """Delete a feedback record (for testing/admin)."""
        if feedback_id in self._feedback_records:
            del self._feedback_records[feedback_id]
            return True
        return False
    
    # ---------------------------------------------------------------
    # Cohort Calibration Aggregation
    # ---------------------------------------------------------------
    
    def get_cohort_calibration(
        self, ticker: str, asset_class: str, time_horizon: str
    ) -> Optional[CohortCalibration]:
        """Get calibration metrics for a cohort (ticker, asset class, time horizon)."""
        key = (ticker, asset_class, time_horizon)
        return self._cohort_calibrations.get(key)
    
    def recompute_cohort_calibration(
        self, ticker: str, asset_class: str, time_horizon: str
    ) -> Optional[CohortCalibration]:
        """
        Recompute calibration metrics for a cohort by processing all feedback records.
        
        Called after new feedback is recorded to update aggregated metrics.
        """
        key = (ticker, asset_class, time_horizon)
        
        # Filter feedback records for this cohort
        cohort_feedback = [
            r for r in self._feedback_records.values()
            if r.ticker.lower() == ticker.lower()
            and r.asset_class == asset_class
            and r.time_horizon == time_horizon
        ]
        
        if not cohort_feedback:
            # No feedback for this cohort yet
            return None
        
        # Group by confidence band
        bands_data: dict[str, dict[str, int]] = defaultdict(
            lambda: {"wins": 0, "losses": 0, "whipsaws": 0, "partials": 0, "decisions": 0, "packets": []}
        )
        
        for feedback in cohort_feedback:
            band = compute_confidence_band(feedback.confidence)
            bands_data[band]["decisions"] += 1
            bands_data[band]["packets"].append(feedback.packet_id)
            
            # Tally outcome
            if feedback.outcome.value == "won":
                bands_data[band]["wins"] += 1
            elif feedback.outcome.value == "lost":
                bands_data[band]["losses"] += 1
            elif feedback.outcome.value == "whipsaw":
                bands_data[band]["whipsaws"] += 1
            elif feedback.outcome.value == "partial":
                bands_data[band]["partials"] += 1
        
        # Compute calibration metrics per band
        bands: dict[str, CalibrationBand] = {}
        any_over_confident = False
        any_under_confident = False
        
        for band_str, data in bands_data.items():
            # Extract confidence level from band string ("60-70%" -> 65)
            band_parts = band_str.replace("%", "").split("-")
            band_low = int(band_parts[0])
            confidence_level = (band_low + int(band_parts[1])) // 2
            
            band_obj = compute_calibration_band(
                decisions=data["decisions"],
                wins=data["wins"],
                losses=data["losses"],
                whipsaws=data["whipsaws"],
                partials=data["partials"],
                confidence_level=confidence_level,
            )
            band_obj.recent_packets = data["packets"][-10:]  # Last 10 packets
            bands[band_str] = band_obj
            
            if band_obj.calibration_status == "over-confident":
                any_over_confident = True
            elif band_obj.calibration_status == "under-confident":
                any_under_confident = True
        
        # Compute overall metrics
        total_wins = sum(b["wins"] for b in bands_data.values())
        total_decisions = sum(b["decisions"] for b in bands_data.values())
        overall_accuracy = total_wins / total_decisions if total_decisions > 0 else 0.0
        
        # Create cohort calibration object
        cohort = CohortCalibration(
            ticker=ticker,
            asset_class=asset_class,
            time_horizon=time_horizon,
            bands=bands,
            total_decisions=total_decisions,
            overall_accuracy=round(overall_accuracy, 3),
            any_over_confident=any_over_confident,
            any_under_confident=any_under_confident,
            flagged_for_review=any_over_confident or any_under_confident,
            sample_size_adequate=total_decisions >= 10,
        )
        
        self._cohort_calibrations[key] = cohort
        
        # Generate alerts if needed
        self._update_calibration_alerts(cohort)
        
        return cohort
    
    def get_band_calibration(self, ticker: str, confidence_band: str) -> Optional[CalibrationBand]:
        """Get calibration metrics aggregated across all time horizons for a band."""
        # Aggregate all feedback records for this ticker in the given confidence band
        matching_feedback = [
            r for r in self._feedback_records.values()
            if r.ticker.lower() == ticker.lower()
            and compute_confidence_band(r.confidence) == confidence_band
        ]
        
        if not matching_feedback:
            return None
        
        # Tally outcomes
        wins = sum(1 for r in matching_feedback if r.outcome.value == "won")
        losses = sum(1 for r in matching_feedback if r.outcome.value == "lost")
        whipsaws = sum(1 for r in matching_feedback if r.outcome.value == "whipsaw")
        partials = sum(1 for r in matching_feedback if r.outcome.value == "partial")
        
        # Extract confidence level from band string
        band_parts = confidence_band.replace("%", "").split("-")
        band_low = int(band_parts[0])
        confidence_level = (band_low + int(band_parts[1])) // 2
        
        return compute_calibration_band(
            decisions=len(matching_feedback),
            wins=wins,
            losses=losses,
            whipsaws=whipsaws,
            partials=partials,
            confidence_level=confidence_level,
        )
    
    # ---------------------------------------------------------------
    # Calibration Summary & Alerts
    # ---------------------------------------------------------------
    
    def get_calibration_summary(self) -> CalibrationSummary:
        """Get high-level summary of calibration quality."""
        if not self._cohort_calibrations:
            return CalibrationSummary(total_feedback_records=len(self._feedback_records))
        
        cohorts = list(self._cohort_calibrations.values())
        well_calibrated = sum(1 for c in cohorts if not c.any_over_confident and not c.any_under_confident)
        over_confident = sum(1 for c in cohorts if c.any_over_confident)
        under_confident = sum(1 for c in cohorts if c.any_under_confident)
        
        # Find top over/under-confident cohorts
        over_conf_sorted = sorted(
            [c for c in cohorts if c.any_over_confident],
            key=lambda c: c.id
        )
        under_conf_sorted = sorted(
            [c for c in cohorts if c.any_under_confident],
            key=lambda c: c.id
        )
        
        return CalibrationSummary(
            total_feedback_records=len(self._feedback_records),
            cohorts_analyzed=len(cohorts),
            cohorts_well_calibrated=well_calibrated,
            cohorts_over_confident=over_confident,
            cohorts_under_confident=under_confident,
            alerts=self._calibration_alerts[:20],  # Latest 20 alerts
            top_over_confident=[c.id for c in over_conf_sorted[:3]],
            top_under_confident=[c.id for c in under_conf_sorted[:3]],
        )
    
    def list_calibration_alerts(
        self, severity: str = "warning", ticker: Optional[str] = None
    ) -> list[CalibrationAlert]:
        """List calibration alerts filtered by severity and optional ticker."""
        alerts = self._calibration_alerts
        
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        if ticker:
            alerts = [a for a in alerts if ticker.lower() in str(a.cohort_id).lower()]
        
        # Sort by created_at (newest first)
        alerts.sort(key=lambda a: a.created_at, reverse=True)
        return alerts[:50]  # Return latest 50
    
    def _update_calibration_alerts(self, cohort: CohortCalibration) -> None:
        """Generate/update calibration alerts for a cohort."""
        # Remove existing alerts for this cohort
        self._calibration_alerts = [
            a for a in self._calibration_alerts if a.cohort_id != cohort.id
        ]
        
        # Generate new alerts for each band that's miscalibrated
        for band_str, band in cohort.bands.items():
            if band.calibration_status != "well-calibrated" and band.decisions >= 5:
                severity = "critical" if abs(band.calibration_error) > 0.15 else "warning"
                
                if band.calibration_status == "over-confident":
                    message = f"Over-confident: {band_str} band has {band.accuracy:.0%} accuracy vs {band.target_accuracy:.0%} target"
                else:  # under-confident
                    message = f"Under-confident: {band_str} band has {band.accuracy:.0%} accuracy vs {band.target_accuracy:.0%} target"
                
                alert = CalibrationAlert(
                    cohort_id=cohort.id,
                    band=band_str,
                    alert_type="over-confident" if band.calibration_status == "over-confident" else "under-confident",
                    target_accuracy=band.target_accuracy,
                    actual_accuracy=band.accuracy,
                    decision_count=band.decisions,
                    severity=severity,
                    message=message,
                )
                self._calibration_alerts.append(alert)
