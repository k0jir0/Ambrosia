"""
Calibration Metrics Tests

Tests for the 8 calibration metrics:
1. Review Validity
2. Decision Consistency
3. Packet Integrity
4. Data Quality
5. Agent Consensus
6. Backtest Validity
7. Risk Estimate Accuracy
8. Confidence Calibration
"""
import pytest


class TestReviewValidityMetric:
    """Tests for Review Validity metric (Target: 75%)."""
    
    def test_review_validity_present(self, api_client):
        """Test that review_validity metric is present."""
        response = api_client.get("/metrics")
        data = response.json()
        
        assert "review_validity" in data, "review_validity metric missing"
    
    def test_review_validity_has_conversion_rate(self, api_client):
        """Test that review_validity has conversion_rate field."""
        response = api_client.get("/metrics")
        data = response.json()
        
        metric = data.get("review_validity")
        assert "conversion_rate" in metric, "Missing conversion_rate"
        assert isinstance(metric["conversion_rate"], (int, float))
    
    def test_review_validity_has_target(self, api_client):
        """Test that review_validity metric has target field."""
        response = api_client.get("/metrics")
        data = response.json()
        
        metric = data.get("review_validity")
        assert "target" in metric, "Missing target field"
        assert metric["target"] == 0.75 or metric["target"] == 75, \
            "Review validity target should be 75%"
    
    def test_review_validity_has_status(self, api_client):
        """Test that review_validity metric has status."""
        response = api_client.get("/metrics")
        data = response.json()
        
        metric = data.get("review_validity")
        assert "status" in metric, "Missing status field"
        assert metric["status"] in ["ok", "warning", "critical"]


class TestDecisionConsistencyMetric:
    """Tests for Decision Consistency metric (Target: 100%)."""
    
    def test_decision_consistency_present(self, api_client):
        """Test that decision_consistency metric is present."""
        response = api_client.get("/metrics")
        data = response.json()
        
        assert "decision_consistency_avg" in data, \
            "decision_consistency_avg metric missing"
    
    def test_decision_consistency_is_numeric(self, api_client):
        """Test that decision_consistency is numeric."""
        response = api_client.get("/metrics")
        data = response.json()
        
        value = data.get("decision_consistency_avg")
        assert isinstance(value, (int, float)), \
            "decision_consistency_avg should be numeric"


class TestPacketIntegrityMetric:
    """Tests for Packet Integrity metric (Target: 90%)."""
    
    def test_packet_integrity_present(self, api_client):
        """Test that packet_integrity metric is present."""
        response = api_client.get("/metrics")
        data = response.json()
        
        assert "packet_integrity" in data, "packet_integrity metric missing"
    
    def test_packet_integrity_has_score(self, api_client):
        """Test that packet_integrity has integrity_score."""
        response = api_client.get("/metrics")
        data = response.json()
        
        metric = data.get("packet_integrity")
        assert "integrity_score" in metric, "Missing integrity_score"
        assert isinstance(metric["integrity_score"], (int, float))
        assert 0 <= metric["integrity_score"] <= 1, \
            "integrity_score should be 0-1 range"
    
    def test_packet_integrity_has_target(self, api_client):
        """Test that packet_integrity has target field."""
        response = api_client.get("/metrics")
        data = response.json()
        
        metric = data.get("packet_integrity")
        assert "target" in metric, "Missing target field"
        assert metric["target"] == 0.90 or metric["target"] == 90, \
            "Packet integrity target should be 90%"
    
    def test_packet_integrity_has_status(self, api_client):
        """Test that packet_integrity has status."""
        response = api_client.get("/metrics")
        data = response.json()
        
        metric = data.get("packet_integrity")
        assert "status" in metric, "Missing status field"


class TestDataQualityMetric:
    """Tests for Data Quality metric (Target: 95%)."""
    
    def test_data_quality_present(self, api_client):
        """Test that data_quality metric is present."""
        response = api_client.get("/metrics")
        data = response.json()
        
        assert "data_quality" in data, "data_quality metric missing"
    
    def test_data_quality_has_score(self, api_client):
        """Test that data_quality has quality_score."""
        response = api_client.get("/metrics")
        data = response.json()
        
        metric = data.get("data_quality")
        assert "quality_score" in metric, "Missing quality_score"
        assert isinstance(metric["quality_score"], (int, float))
    
    def test_data_quality_target(self, api_client):
        """Test that data_quality target is correct."""
        response = api_client.get("/metrics")
        data = response.json()
        
        metric = data.get("data_quality")
        assert "target" in metric, "Missing target"
        assert metric["target"] == 0.95 or metric["target"] == 95, \
            "Data quality target should be 95%"


class TestAgentConsensusMetric:
    """Tests for Agent Consensus metric (Target: 70%)."""
    
    def test_agent_consensus_present(self, api_client):
        """Test that agent_consensus metric is present."""
        response = api_client.get("/metrics")
        data = response.json()
        
        assert "agent_consensus" in data, "agent_consensus metric missing"
    
    def test_agent_consensus_has_score(self, api_client):
        """Test that agent_consensus has avg_consensus_score."""
        response = api_client.get("/metrics")
        data = response.json()
        
        metric = data.get("agent_consensus")
        assert "avg_consensus_score" in metric or "score" in metric, \
            "Missing consensus score"
    
    def test_agent_consensus_target(self, api_client):
        """Test that agent_consensus target is correct."""
        response = api_client.get("/metrics")
        data = response.json()
        
        metric = data.get("agent_consensus")
        assert "target" in metric, "Missing target"
        assert metric["target"] == 0.70 or metric["target"] == 70, \
            "Agent consensus target should be 70%"


class TestBacktestValidityMetric:
    """Tests for Backtest Validity metric (Target: 0.75 correlation)."""
    
    def test_backtest_validity_present(self, api_client):
        """Test that backtest_validity metric is present."""
        response = api_client.get("/metrics")
        data = response.json()
        
        assert "backtest_validity" in data, "backtest_validity metric missing"
    
    def test_backtest_validity_has_correlation(self, api_client):
        """Test that backtest_validity has correlation."""
        response = api_client.get("/metrics")
        data = response.json()
        
        metric = data.get("backtest_validity")
        assert "avg_correlation" in metric or "correlation" in metric, \
            "Missing correlation field"
    
    def test_backtest_validity_target(self, api_client):
        """Test that backtest_validity target is correct."""
        response = api_client.get("/metrics")
        data = response.json()
        
        metric = data.get("backtest_validity")
        assert "target" in metric, "Missing target"
        assert metric["target"] == 0.75, \
            "Backtest validity target should be 0.75 correlation"


class TestRiskEstimateMetric:
    """Tests for Risk Estimate Accuracy metric (Target: 80%)."""
    
    def test_risk_estimate_present(self, api_client):
        """Test that risk_estimate metric is present."""
        response = api_client.get("/metrics")
        data = response.json()
        
        assert "risk_estimate" in data, "risk_estimate metric missing"
    
    def test_risk_estimate_has_accuracy(self, api_client):
        """Test that risk_estimate has estimate_accuracy."""
        response = api_client.get("/metrics")
        data = response.json()
        
        metric = data.get("risk_estimate")
        assert "estimate_accuracy" in metric or "accuracy" in metric, \
            "Missing estimate accuracy"
    
    def test_risk_estimate_target(self, api_client):
        """Test that risk_estimate target is correct."""
        response = api_client.get("/metrics")
        data = response.json()
        
        metric = data.get("risk_estimate")
        assert "target" in metric, "Missing target"
        assert metric["target"] == 0.80 or metric["target"] == 80, \
            "Risk estimate target should be 80%"


class TestConfidenceCalibrationMetric:
    """Tests for Confidence Calibration metric (Target: 75%)."""
    
    def test_confidence_calibration_present(self, api_client):
        """Test that confidence_calibration metric is present."""
        response = api_client.get("/metrics")
        data = response.json()
        
        assert "confidence_calibration" in data, \
            "confidence_calibration metric missing"
    
    def test_confidence_calibration_has_score(self, api_client):
        """Test that confidence_calibration has calibration_score."""
        response = api_client.get("/metrics")
        data = response.json()
        
        metric = data.get("confidence_calibration")
        assert "calibration_score" in metric or "score" in metric, \
            "Missing calibration score"
    
    def test_confidence_calibration_target(self, api_client):
        """Test that confidence_calibration target is correct."""
        response = api_client.get("/metrics")
        data = response.json()
        
        metric = data.get("confidence_calibration")
        assert "target" in metric, "Missing target"
        assert metric["target"] == 0.75 or metric["target"] == 75, \
            "Confidence calibration target should be 75%"


class TestMetricsAggregation:
    """Tests for metrics aggregation logic."""
    
    def test_overall_status_computed(self, api_client):
        """Test that overall_status is computed from all metrics."""
        response = api_client.get("/metrics")
        data = response.json()
        
        assert "overall_status" in data, "overall_status missing"
        assert data["overall_status"] in ["ok", "warning", "critical"]
    
    def test_metrics_consistency(self, api_client):
        """Test that metrics are consistent across calls."""
        response1 = api_client.get("/metrics")
        response2 = api_client.get("/metrics")
        
        data1 = response1.json()
        data2 = response2.json()
        
        # Overall status should be consistent
        assert data1.get("overall_status") == data2.get("overall_status"), \
            "Metrics should be consistent"


class TestMetricsDataValidation:
    """Tests for metrics data types and ranges."""
    
    def test_metric_values_in_valid_range(self, api_client):
        """Test that metric values are in valid ranges."""
        response = api_client.get("/metrics")
        data = response.json()
        
        # Check numeric fields are in 0-1 range (normalized)
        for metric_name in ["decision_consistency_avg"]:
            value = data.get(metric_name)
            if value is not None:
                assert 0 <= value <= 1, \
                    f"{metric_name} should be 0-1, got {value}"
    
    def test_target_values_documented(self, api_client):
        """Test that all metrics document their targets."""
        response = api_client.get("/metrics")
        data = response.json()
        
        metric_fields = [
            "review_validity",
            "packet_integrity",
            "data_quality",
            "agent_consensus",
            "backtest_validity",
            "risk_estimate",
            "confidence_calibration"
        ]
        
        for field in metric_fields:
            metric = data.get(field)
            if isinstance(metric, dict):
                assert "target" in metric, f"{field} missing target"
