#!/usr/bin/env python3
"""
Phase B2: Synthetic Monitoring with Regression Detection
Monitors production health and detects quality degradation in real-time.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal


@dataclass
class SyntheticProbeResult:
    """Result from a single synthetic probe execution"""
    probe_name: str
    status: Literal["pass", "warning", "fail"]
    latency_ms: float
    timestamp: str
    details: dict


@dataclass
class BaselineMetrics:
    """Baseline metrics for regression detection"""
    metric_name: str
    p50_ms: float  # Median latency
    p95_ms: float  # 95th percentile
    p99_ms: float  # 99th percentile
    error_rate_pct: float
    success_rate_pct: float


class RegressionDetector:
    """Detects regressions in synthetic monitoring data"""
    
    def __init__(self, baseline_window_hours: int = 24):
        self.baseline_window = timedelta(hours=baseline_window_hours)
        self.baselines: dict[str, BaselineMetrics] = {}
        self.history: list[SyntheticProbeResult] = []
    
    def record_probe(self, result: SyntheticProbeResult) -> None:
        """Record a probe result"""
        self.history.append(result)
        self._trim_history()
    
    def _trim_history(self) -> None:
        """Keep only recent history"""
        cutoff = datetime.fromisoformat(self.history[-1].timestamp) - self.baseline_window if self.history else datetime.now()
        self.history = [
            h for h in self.history
            if datetime.fromisoformat(h.timestamp) > cutoff
        ]
    
    def compute_baselines(self) -> dict[str, BaselineMetrics]:
        """Compute baseline metrics from history"""
        by_probe = {}
        for result in self.history:
            if result.probe_name not in by_probe:
                by_probe[result.probe_name] = []
            by_probe[result.probe_name].append(result)
        
        baselines = {}
        for probe_name, results in by_probe.items():
            latencies = sorted([r.latency_ms for r in results])
            errors = sum(1 for r in results if r.status == "fail")
            
            baselines[probe_name] = BaselineMetrics(
                metric_name=probe_name,
                p50_ms=latencies[len(latencies) // 2] if latencies else 0,
                p95_ms=latencies[int(len(latencies) * 0.95)] if latencies else 0,
                p99_ms=latencies[int(len(latencies) * 0.99)] if latencies else 0,
                error_rate_pct=(errors / len(results) * 100) if results else 0,
                success_rate_pct=((len(results) - errors) / len(results) * 100) if results else 100,
            )
        
        self.baselines = baselines
        return baselines
    
    def detect_regression(self, result: SyntheticProbeResult, threshold_pct: float = 20.0) -> dict:
        """Detect if a probe result indicates regression"""
        baseline = self.baselines.get(result.probe_name)
        
        if not baseline:
            return {"regression_detected": False, "reason": "no_baseline"}
        
        regression_signals = []
        
        # Latency regression: current > baseline p95 + 20%
        if result.latency_ms > baseline.p95_ms * (1 + threshold_pct / 100):
            regression_signals.append({
                "type": "latency",
                "current_ms": result.latency_ms,
                "baseline_p95_ms": baseline.p95_ms,
                "threshold_pct": threshold_pct,
            })
        
        # Error rate regression
        if result.status == "fail" and baseline.success_rate_pct > 99.0:
            regression_signals.append({
                "type": "error_rate",
                "current_status": result.status,
                "baseline_success_pct": baseline.success_rate_pct,
            })
        
        return {
            "probe_name": result.probe_name,
            "regression_detected": len(regression_signals) > 0,
            "signals": regression_signals,
            "baseline": asdict(baseline),
            "current": {
                "latency_ms": result.latency_ms,
                "status": result.status,
            },
        }


def generate_synthetic_monitoring_report(results: list[SyntheticProbeResult]) -> dict:
    """Generate comprehensive synthetic monitoring report"""
    detector = RegressionDetector()
    
    for result in results:
        detector.record_probe(result)
    
    baselines = detector.compute_baselines()
    regressions = []
    
    for result in results[-5:]:  # Check last 5 probes for regression
        regression_analysis = detector.detect_regression(result)
        if regression_analysis["regression_detected"]:
            regressions.append(regression_analysis)
    
    # Calculate health status
    recent_failures = sum(1 for r in results[-10:] if r.status == "fail") if results else 0
    health_status = "critical" if recent_failures >= 2 else ("warning" if recent_failures >= 1 else "ok")
    
    return {
        "timestamp": datetime.now().isoformat(),
        "health_status": health_status,
        "total_probes": len(results),
        "recent_probes_10": len(results[-10:]),
        "recent_failures": recent_failures,
        "baselines": {k: asdict(v) for k, v in baselines.items()},
        "regressions_detected": regressions,
        "recommendations": _generate_monitoring_recommendations(health_status, regressions),
    }


def _generate_monitoring_recommendations(health_status: str, regressions: list[dict]) -> list[str]:
    """Generate actionable recommendations"""
    recommendations = []
    
    if health_status == "critical":
        recommendations.append("CRITICAL: Multiple probe failures detected. Investigate immediately.")
    elif health_status == "warning":
        recommendations.append("WARNING: Probe failures or latency increases detected. Review logs.")
    else:
        recommendations.append("Synthetic monitoring healthy. No action required.")
    
    if regressions:
        for regression in regressions:
            probe = regression["probe_name"]
            for signal in regression.get("signals", []):
                if signal["type"] == "latency":
                    recommendations.append(
                        f"{probe}: Latency regression detected "
                        f"({signal['current_ms']:.0f}ms vs baseline {signal['baseline_p95_ms']:.0f}ms)"
                    )
                elif signal["type"] == "error_rate":
                    recommendations.append(
                        f"{probe}: Error rate increased; baseline was "
                        f"{signal['baseline_success_pct']:.1f}% success"
                    )
    
    return recommendations


def create_sample_monitoring_data() -> list[SyntheticProbeResult]:
    """Create sample monitoring probe results"""
    now = datetime.now()
    results = []
    
    probes = [
        ("health_check", 45, "pass"),
        ("packet_operations", 120, "pass"),
        ("market_data", 280, "pass"),
        ("feedback_system", 95, "pass"),
        ("scorecard", 65, "pass"),
    ]
    
    # Simulate 10 recent probe cycles
    for cycle in range(10):
        timestamp = (now - timedelta(minutes=60-cycle*6)).isoformat()
        for probe_name, baseline_latency, status in probes:
            # Add some realistic variance
            latency = baseline_latency + (cycle % 3) * 10
            if cycle == 8:  # Simulate degradation in recent cycle
                latency *= 1.25
            
            results.append(SyntheticProbeResult(
                probe_name=probe_name,
                status=status,
                latency_ms=latency,
                timestamp=timestamp,
                details={"cycle": cycle},
            ))
    
    return results


if __name__ == "__main__":
    # Generate sample report
    sample_results = create_sample_monitoring_data()
    report = generate_synthetic_monitoring_report(sample_results)
    
    # Save artifact
    artifact_path = Path("artifacts/synthetic-monitoring-regression.json")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(artifact_path, "w") as f:
        json.dump(report, f, indent=2)
    
    print("Synthetic Monitoring Regression Detection Report")
    print("=" * 70)
    print(f"Health Status: {report['health_status'].upper()}")
    print(f"Total Probes: {report['total_probes']}")
    print(f"Recent Failures (last 10): {report['recent_failures']}")
    
    if report["regressions_detected"]:
        print(f"\nRegressions Detected: {len(report['regressions_detected'])}")
        for reg in report["regressions_detected"]:
            print(f"  - {reg['probe_name']}: {len(reg['signals'])} signal(s)")
    
    print(f"\nRecommendations:")
    for i, rec in enumerate(report["recommendations"], 1):
        print(f"  {i}. {rec}")
    
    print(f"\nReport saved to: {artifact_path}")
