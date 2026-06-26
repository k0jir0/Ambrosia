"""
Retrieval Quality Module - Phase A2 Implementation
Measures and monitors hybrid retrieval quality with pgvector integration.

This module provides:
- Relevance quality computation and tracking
- Drift detection for retrieval accuracy
- Benchmark fixtures for eval
- Monitoring endpoints for operators
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, UTC
from typing import Literal

from .models import RetrievalHit


@dataclass
class RetrievalQualityMetric:
    """Single retrieval quality data point"""
    query: str
    ground_truth_hit_ids: list[str]  # What should have been retrieved
    retrieved_hit_ids: list[str]  # What was actually retrieved
    relevance_scores: dict[str, float]  # hit_id -> relevance (0.0-1.0)
    timestamp: str
    data_mode: Literal["live", "fallback", "demo"]
    
    def precision_at_k(self, k: int = 5) -> float:
        """Precision@K: fraction of top-k results that are relevant"""
        if not self.retrieved_hit_ids:
            return 0.0
        top_k = set(self.retrieved_hit_ids[:k])
        relevant_in_top_k = len(top_k.intersection(set(self.ground_truth_hit_ids)))
        return relevant_in_top_k / min(k, len(self.retrieved_hit_ids))
    
    def recall_at_k(self, k: int = 5) -> float:
        """Recall@K: fraction of all relevant results in top-k"""
        if not self.ground_truth_hit_ids:
            return 0.0
        top_k = set(self.retrieved_hit_ids[:k])
        relevant_in_top_k = len(top_k.intersection(set(self.ground_truth_hit_ids)))
        return relevant_in_top_k / len(self.ground_truth_hit_ids)
    
    def ndcg(self, k: int = 5) -> float:
        """Normalized Discounted Cumulative Gain@K
        Measures ranking quality considering position decay.
        """
        if not self.ground_truth_hit_ids:
            return 0.0
        
        # Compute DCG
        dcg = 0.0
        ground_truth_set = set(self.ground_truth_hit_ids)
        for i, hit_id in enumerate(self.retrieved_hit_ids[:k], start=1):
            if hit_id in ground_truth_set:
                dcg += 1.0 / (1.0 + i)
        
        # Compute ideal DCG (perfect ranking)
        idcg = 0.0
        for i in range(1, min(k, len(self.ground_truth_hit_ids)) + 1):
            idcg += 1.0 / (1.0 + i)
        
        return dcg / idcg if idcg > 0 else 0.0
    
    def mrr(self) -> float:
        """Mean Reciprocal Rank: 1 / rank of first relevant result"""
        ground_truth_set = set(self.ground_truth_hit_ids)
        for i, hit_id in enumerate(self.retrieved_hit_ids, start=1):
            if hit_id in ground_truth_set:
                return 1.0 / i
        return 0.0
    
    def mean_relevance_score(self) -> float:
        """Average relevance score of retrieved results"""
        if not self.retrieved_hit_ids:
            return 0.0
        scores = [
            self.relevance_scores.get(hit_id, 0.0)
            for hit_id in self.retrieved_hit_ids
        ]
        return sum(scores) / len(scores)


@dataclass
class RetrievalQualityBand:
    """Aggregated metrics for a cohort"""
    query_pattern: str  # e.g., "semiconductor", "tech earnings"
    sample_count: int
    avg_precision_at_5: float
    avg_recall_at_5: float
    avg_ndcg_at_5: float
    avg_mrr: float
    avg_relevance_score: float
    data_mode_distribution: dict[Literal["live", "fallback", "demo"], int]
    quality_status: Literal["excellent", "good", "acceptable", "degraded"]
    last_updated: str


class RetrievalQualityTracker:
    """Tracks and computes retrieval quality metrics"""
    
    def __init__(self, max_history_days: int = 30):
        self.max_history_days = max_history_days
        self.metrics: list[RetrievalQualityMetric] = []
        self.baseline: dict[str, float] | None = None
    
    def record_retrieval(
        self,
        query: str,
        ground_truth_hit_ids: list[str],
        retrieved_hits: list[RetrievalHit],
        data_mode: Literal["live", "fallback", "demo"],
    ) -> None:
        """Record a retrieval result for quality tracking"""
        metric = RetrievalQualityMetric(
            query=query,
            ground_truth_hit_ids=ground_truth_hit_ids,
            retrieved_hit_ids=[hit.id for hit in retrieved_hits],
            relevance_scores={hit.id: hit.score for hit in retrieved_hits},
            timestamp=datetime.now(UTC).isoformat(),
            data_mode=data_mode,
        )
        self.metrics.append(metric)
        self._prune_old_metrics()
    
    def _prune_old_metrics(self) -> None:
        """Remove metrics older than max_history_days"""
        cutoff = datetime.now(UTC) - timedelta(days=self.max_history_days)
        self.metrics = [
            m for m in self.metrics
            if datetime.fromisoformat(m.timestamp.replace('Z', '+00:00')) > cutoff
        ]
    
    def compute_baseline(self) -> dict[str, float]:
        """Compute baseline quality metrics from all historical data"""
        if not self.metrics:
            return {
                "avg_precision_at_5": 0.0,
                "avg_recall_at_5": 0.0,
                "avg_ndcg_at_5": 0.0,
                "avg_mrr": 0.0,
                "avg_relevance_score": 0.0,
                "sample_count": 0,
            }
        
        baseline = {
            "avg_precision_at_5": sum(m.precision_at_k(5) for m in self.metrics) / len(self.metrics),
            "avg_recall_at_5": sum(m.recall_at_k(5) for m in self.metrics) / len(self.metrics),
            "avg_ndcg_at_5": sum(m.ndcg(5) for m in self.metrics) / len(self.metrics),
            "avg_mrr": sum(m.mrr() for m in self.metrics) / len(self.metrics),
            "avg_relevance_score": sum(m.mean_relevance_score() for m in self.metrics) / len(self.metrics),
            "sample_count": len(self.metrics),
        }
        self.baseline = baseline
        return baseline
    
    def detect_drift(self, recent_window_size: int = 20) -> dict:
        """Detect quality drift in recent retrievals vs baseline"""
        if not self.baseline or len(self.metrics) < recent_window_size:
            return {"status": "insufficient_data", "drift_detected": False}
        
        recent_metrics = self.metrics[-recent_window_size:]
        recent_precision = sum(m.precision_at_k(5) for m in recent_metrics) / len(recent_metrics)
        recent_ndcg = sum(m.ndcg(5) for m in recent_metrics) / len(recent_metrics)
        
        baseline_precision = self.baseline["avg_precision_at_5"]
        baseline_ndcg = self.baseline["avg_ndcg_at_5"]
        
        # Detect if recent performance is significantly worse (>15% degradation)
        precision_drift = (baseline_precision - recent_precision) / (baseline_precision + 0.001)
        ndcg_drift = (baseline_ndcg - recent_ndcg) / (baseline_ndcg + 0.001)
        
        drift_detected = precision_drift > 0.15 or ndcg_drift > 0.15
        
        return {
            "status": "ok",
            "drift_detected": drift_detected,
            "recent_precision_at_5": recent_precision,
            "recent_ndcg_at_5": recent_ndcg,
            "baseline_precision_at_5": baseline_precision,
            "baseline_ndcg_at_5": baseline_ndcg,
            "precision_drift_pct": precision_drift * 100,
            "ndcg_drift_pct": ndcg_drift * 100,
            "window_size": recent_window_size,
        }
    
    def quality_by_query_pattern(self, pattern_prefix: str) -> RetrievalQualityBand | None:
        """Aggregate quality metrics for queries matching a pattern"""
        matching_metrics = [
            m for m in self.metrics
            if pattern_prefix.lower() in m.query.lower()
        ]
        
        if not matching_metrics:
            return None
        
        avg_p5 = sum(m.precision_at_k(5) for m in matching_metrics) / len(matching_metrics)
        avg_r5 = sum(m.recall_at_k(5) for m in matching_metrics) / len(matching_metrics)
        avg_ndcg = sum(m.ndcg(5) for m in matching_metrics) / len(matching_metrics)
        avg_mrr = sum(m.mrr() for m in matching_metrics) / len(matching_metrics)
        avg_rel = sum(m.mean_relevance_score() for m in matching_metrics) / len(matching_metrics)
        
        # Count data modes
        mode_dist: dict[Literal["live", "fallback", "demo"], int] = {"live": 0, "fallback": 0, "demo": 0}
        for m in matching_metrics:
            mode_dist[m.data_mode] += 1
        
        # Determine quality status
        if avg_ndcg >= 0.85:
            status = "excellent"
        elif avg_ndcg >= 0.70:
            status = "good"
        elif avg_ndcg >= 0.50:
            status = "acceptable"
        else:
            status = "degraded"
        
        return RetrievalQualityBand(
            query_pattern=pattern_prefix,
            sample_count=len(matching_metrics),
            avg_precision_at_5=avg_p5,
            avg_recall_at_5=avg_r5,
            avg_ndcg_at_5=avg_ndcg,
            avg_mrr=avg_mrr,
            avg_relevance_score=avg_rel,
            data_mode_distribution=mode_dist,
            quality_status=status,
            last_updated=datetime.now(UTC).isoformat(),
        )


def generate_retrieval_quality_report(tracker: RetrievalQualityTracker) -> dict:
    """Generate comprehensive retrieval quality report for monitoring"""
    baseline = tracker.compute_baseline()
    drift = tracker.detect_drift()
    
    # Sample common query patterns
    patterns = ["semiconductor", "tech", "earnings", "momentum", "risk"]
    pattern_stats = []
    for pattern in patterns:
        band = tracker.quality_by_query_pattern(pattern)
        if band:
            pattern_stats.append({
                "pattern": pattern,
                "sample_count": band.sample_count,
                "avg_ndcg_at_5": band.avg_ndcg_at_5,
                "quality_status": band.quality_status,
            })
    
    return {
        "summary": {
            "total_retrievals": baseline["sample_count"],
            "baseline_ndcg_at_5": baseline["avg_ndcg_at_5"],
            "baseline_precision_at_5": baseline["avg_precision_at_5"],
            "baseline_recall_at_5": baseline["avg_recall_at_5"],
            "baseline_mrr": baseline["avg_mrr"],
        },
        "drift": drift,
        "by_pattern": pattern_stats,
        "quality_status": "good" if not drift.get("drift_detected") else "degraded",
        "recommendations": _generate_recommendations(baseline, drift),
    }


def _generate_recommendations(baseline: dict, drift: dict) -> list[str]:
    """Generate actionable recommendations based on metrics"""
    recommendations = []
    
    if drift.get("drift_detected"):
        recommendations.append(
            "Retrieval quality has degraded significantly. "
            "Check market data freshness and hybrid search relevance scoring."
        )
    
    if baseline.get("avg_recall_at_5", 0.0) < 0.60:
        recommendations.append(
            "Recall@5 is below target (60%). Consider expanding pgvector search or adjusting BM25 weights."
        )
    
    if baseline.get("avg_precision_at_5", 0.0) < 0.70:
        recommendations.append(
            "Precision@5 is below target (70%). Review result ranking and relevance scoring."
        )
    
    if not recommendations:
        recommendations.append("Retrieval quality is within acceptable ranges. No action needed.")
    
    return recommendations


# Export singleton for app-level tracking
_quality_tracker: RetrievalQualityTracker | None = None


def get_retrieval_quality_tracker() -> RetrievalQualityTracker:
    """Get or create the global retrieval quality tracker"""
    global _quality_tracker
    if _quality_tracker is None:
        _quality_tracker = RetrievalQualityTracker()
    return _quality_tracker
