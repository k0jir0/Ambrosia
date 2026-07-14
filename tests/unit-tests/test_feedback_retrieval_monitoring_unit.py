from __future__ import annotations

from datetime import datetime, timedelta

from services.api.app.feedback import (
    assess_calibration,
    compute_calibration_band,
    compute_confidence_band,
)
from services.api.app.models import RetrievalHit
from services.api.app.retrieval_quality import (
    RetrievalQualityMetric,
    RetrievalQualityTracker,
    generate_retrieval_quality_report,
)
from services.api.app.synthetic_monitoring import (
    RegressionDetector,
    SyntheticProbeResult,
    create_sample_monitoring_data,
    generate_synthetic_monitoring_report,
)


def _hit(hit_id: str, score: float = 0.8) -> RetrievalHit:
    return RetrievalHit(
        kind="prior_review",
        id=hit_id,
        title=f"Hit {hit_id}",
        snippet="Relevant evidence",
        score=score,
    )


def test_confidence_band_and_calibration_math() -> None:
    assert compute_confidence_band(0) == "0-10%"
    assert compute_confidence_band(65) == "60-70%"
    assert compute_confidence_band(100) == "100-110%"
    assert assess_calibration(actual_accuracy=0.65, target_accuracy=0.65) == (True, "well-calibrated")
    assert assess_calibration(actual_accuracy=0.8, target_accuracy=0.65) == (False, "over-confident")
    assert assess_calibration(actual_accuracy=0.5, target_accuracy=0.65) == (False, "under-confident")


def test_compute_calibration_band_counts_partials_as_half_wins() -> None:
    band = compute_calibration_band(
        decisions=4,
        wins=2,
        losses=1,
        whipsaws=0,
        partials=1,
        confidence_level=60,
    )

    assert band.confidence_band == "60-70%"
    assert band.accuracy == 0.625
    assert band.win_rate == 0.5
    assert band.partial_recovery_rate == 0.5
    assert band.target_accuracy == 0.6
    assert band.is_well_calibrated is True


def test_retrieval_quality_metric_computes_ranking_metrics() -> None:
    metric = RetrievalQualityMetric(
        query="semiconductor momentum",
        ground_truth_hit_ids=["a", "c"],
        retrieved_hit_ids=["b", "a", "c"],
        relevance_scores={"a": 0.9, "b": 0.2, "c": 0.8},
        timestamp=datetime.now().isoformat(),
        data_mode="demo",
    )

    assert metric.precision_at_k(2) == 0.5
    assert metric.recall_at_k(2) == 0.5
    assert metric.mrr() == 0.5
    assert round(metric.mean_relevance_score(), 3) == 0.633
    assert 0 < metric.ndcg(3) < 1


def test_retrieval_quality_tracker_records_baseline_patterns_and_report() -> None:
    tracker = RetrievalQualityTracker()
    tracker.record_retrieval("semiconductor momentum", ["a", "b"], [_hit("a"), _hit("b"), _hit("x", 0.1)], "demo")
    tracker.record_retrieval("tech earnings risk", ["c"], [_hit("x", 0.1), _hit("c", 0.9)], "fallback")

    baseline = tracker.compute_baseline()
    semiconductor = tracker.quality_by_query_pattern("semiconductor")
    report = generate_retrieval_quality_report(tracker)

    assert baseline["sample_count"] == 2
    assert baseline["avg_precision_at_5"] > 0
    assert semiconductor is not None
    assert semiconductor.sample_count == 1
    assert semiconductor.data_mode_distribution["demo"] == 1
    assert report["summary"]["total_retrievals"] == 2
    assert report["quality_status"] == "good"


def test_retrieval_quality_tracker_detects_recent_drift_against_existing_baseline() -> None:
    tracker = RetrievalQualityTracker()
    for index in range(5):
        tracker.record_retrieval(f"tech good {index}", ["a"], [_hit("a"), _hit("b")], "demo")
    tracker.compute_baseline()
    tracker.record_retrieval("tech bad 1", ["a"], [_hit("x", 0.1), _hit("y", 0.1)], "demo")
    tracker.record_retrieval("tech bad 2", ["a"], [_hit("x", 0.1), _hit("y", 0.1)], "demo")

    drift = tracker.detect_drift(recent_window_size=2)

    assert drift["status"] == "ok"
    assert drift["drift_detected"] is True
    assert drift["recent_precision_at_5"] == 0


def test_regression_detector_builds_baselines_and_flags_latency_regression() -> None:
    now = datetime.now()
    detector = RegressionDetector()
    for index, latency in enumerate([100, 105, 110, 115, 120]):
        detector.record_probe(
            SyntheticProbeResult(
                probe_name="health",
                status="pass",
                latency_ms=latency,
                timestamp=(now + timedelta(minutes=index)).isoformat(),
                details={},
            )
        )
    detector.compute_baselines()

    regression = detector.detect_regression(
        SyntheticProbeResult(
            probe_name="health",
            status="pass",
            latency_ms=200,
            timestamp=(now + timedelta(minutes=10)).isoformat(),
            details={},
        )
    )

    assert regression["regression_detected"] is True
    assert regression["signals"][0]["type"] == "latency"


def test_synthetic_monitoring_report_summarizes_health_and_recommendations() -> None:
    sample_results = create_sample_monitoring_data()
    report = generate_synthetic_monitoring_report(sample_results)
    failing = [
        SyntheticProbeResult("health", "fail", 100, datetime.now().isoformat(), {}),
        SyntheticProbeResult("market", "fail", 200, datetime.now().isoformat(), {}),
    ]
    critical = generate_synthetic_monitoring_report(failing)

    assert report["total_probes"] == len(sample_results)
    assert report["health_status"] == "ok"
    assert "baselines" in report
    assert critical["health_status"] == "critical"
    assert any("CRITICAL" in item for item in critical["recommendations"])
