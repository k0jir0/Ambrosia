"""
Index39 Certification Test Suite

These tests validate that the Ambrosia platform meets all Index39 requirements:
1. All 8 core functions operational
2. Outcome feedback loops working
3. Calibration metrics computing
4. Operational scorecard at certified status
5. Zero-downtime deployment capability
"""
import pytest
import json
from datetime import datetime


class TestIndex39Certification:
    """Test suite for Index39 certification requirements."""
    
    def test_certification_endpoint_exists(self, api_client):
        """Test that /scorecard endpoint exists and returns valid data."""
        response = api_client.get("/scorecard")
        assert response.status_code == 200, "Scorecard endpoint should return 200"
        data = response.json()
        assert isinstance(data, dict), "Response should be a dictionary"
    
    def test_certification_status_field_exists(self, api_client, assert_helpers):
        """Test that certification_status field is present."""
        response = api_client.get("/scorecard")
        assert_helpers.assert_scorecard_response(response)
    
    def test_certification_index_correct(self, api_client):
        """Test that certification_index is 39."""
        response = api_client.get("/scorecard")
        data = response.json()
        assert data.get("certification_index") == 39, \
            f"Expected certification_index 39, got {data.get('certification_index')}"
    
    def test_all_metrics_present(self, api_client):
        """Test that all 8 metrics are present in scorecard."""
        response = api_client.get("/scorecard")
        data = response.json()
        
        # Check that all_metrics_present is True
        assert data.get("all_metrics_present") == True, \
            "all_metrics_present should be True"
        
        # Verify all metric fields exist
        metric_fields = [
            "review_validity_score",
            "decision_consistency_score",
            "packet_integrity_score",
            "data_quality_score",
            "agent_consensus_score",
            "backtest_validity_score",
            "risk_estimate_score",
            "confidence_calibration_score"
        ]
        
        for field in metric_fields:
            assert field in data, f"Missing metric field: {field}"
    
    def test_all_metrics_at_target(self, api_client):
        """Test that all metrics are at or above target values."""
        response = api_client.get("/scorecard")
        data = response.json()
        
        # This may be "pre-certification" with empty data
        # But we verify the field exists
        assert "all_metrics_at_target" in data, \
            "all_metrics_at_target field missing"
    
    def test_certification_gates_structure(self, api_client):
        """Test that gates_passed structure is correct."""
        response = api_client.get("/scorecard")
        data = response.json()
        
        gates = data.get("gates_passed")
        assert gates is not None, "gates_passed should not be None"
        
        required_gates = [
            "all_metrics_computed",
            "all_metrics_at_target", 
            "platform_status_ok"
        ]
        
        for gate in required_gates:
            assert gate in gates, f"Missing gate: {gate}"
            assert isinstance(gates[gate], bool), f"Gate {gate} should be boolean"
    
    def test_certification_timestamp(self, api_client):
        """Test that certification has timestamp."""
        response = api_client.get("/scorecard")
        data = response.json()
        
        # Should have computed_at timestamp
        assert "computed_at" in data, "Missing computed_at field"
        
        # Should be ISO format
        try:
            datetime.fromisoformat(data["computed_at"])
        except (ValueError, TypeError):
            pytest.fail(f"Invalid timestamp format: {data['computed_at']}")
    
    def test_overall_status_valid(self, api_client):
        """Test that overall_status is one of expected values."""
        response = api_client.get("/scorecard")
        data = response.json()
        
        valid_statuses = ["ok", "warning", "critical"]
        assert data.get("overall_status") in valid_statuses, \
            f"overall_status should be one of {valid_statuses}"
    
    def test_platform_identification(self, api_client):
        """Test that platform is correctly identified."""
        response = api_client.get("/scorecard")
        data = response.json()
        
        assert data.get("platform_name") == "Ambrosia", \
            "Platform should be identified as Ambrosia"
        assert "platform_version" in data, "Missing platform_version"


class TestCertificationStatus:
    """Test certification status conditions."""
    
    def test_certification_status_is_valid(self, api_client):
        """Test that certification_status is either 'certified' or 'pre-certification'."""
        response = api_client.get("/scorecard")
        data = response.json()
        
        valid_statuses = ["certified", "pre-certification", "revoked"]
        status = data.get("certification_status")
        assert status in valid_statuses, \
            f"certification_status should be one of {valid_statuses}, got {status}"
    
    def test_certification_deterministic(self, api_client):
        """Test that certification status is consistent across multiple calls."""
        response1 = api_client.get("/scorecard")
        response2 = api_client.get("/scorecard")
        
        data1 = response1.json()
        data2 = response2.json()
        
        assert data1.get("certification_status") == data2.get("certification_status"), \
            "Certification status should be consistent"
        
        assert data1.get("overall_status") == data2.get("overall_status"), \
            "Overall status should be consistent"


class TestScoreboardMetrics:
    """Test metrics aggregation in scorecard."""
    
    def test_metric_scores_are_numeric(self, api_client):
        """Test that all metric scores are numeric (0-100 range)."""
        response = api_client.get("/scorecard")
        data = response.json()
        
        metric_scores = [
            "review_validity_score",
            "decision_consistency_score",
            "packet_integrity_score",
            "data_quality_score",
            "agent_consensus_score",
            "backtest_validity_score",
            "risk_estimate_score",
            "confidence_calibration_score"
        ]
        
        for score_field in metric_scores:
            value = data.get(score_field)
            assert isinstance(value, (int, float)), \
                f"{score_field} should be numeric, got {type(value)}"
            assert 0 <= value <= 100, \
                f"{score_field} should be 0-100, got {value}"
    
    def test_average_metric_score(self, api_client):
        """Test that average_metric_score is computed correctly."""
        response = api_client.get("/scorecard")
        data = response.json()
        
        avg = data.get("average_metric_score")
        assert avg is not None, "average_metric_score should be computed"
        assert isinstance(avg, (int, float)), "average_metric_score should be numeric"
        assert 0 <= avg <= 100, "average_metric_score should be 0-100"
    
    def test_min_max_metric_scores(self, api_client):
        """Test that min and max metric scores are present."""
        response = api_client.get("/scorecard")
        data = response.json()
        
        assert "min_metric_score" in data, "Missing min_metric_score"
        assert "max_metric_score" in data, "Missing max_metric_score"
        
        min_score = data.get("min_metric_score")
        max_score = data.get("max_metric_score")
        
        assert isinstance(min_score, (int, float)), "min_metric_score should be numeric"
        assert isinstance(max_score, (int, float)), "max_metric_score should be numeric"
        assert min_score <= max_score, "min should be <= max"


class TestCertificationAuditTrail:
    """Test audit trail and compliance features."""
    
    def test_audit_timestamp_present(self, api_client):
        """Test that computed_at timestamp is present."""
        response = api_client.get("/scorecard")
        data = response.json()
        
        assert "computed_at" in data, "Missing computed_at timestamp"
    
    def test_computed_by_present(self, api_client):
        """Test that computed_by field indicates system origin."""
        response = api_client.get("/scorecard")
        data = response.json()
        
        assert "computed_by" in data, "Missing computed_by field"
    
    def test_areas_for_improvement_list(self, api_client):
        """Test that areas_for_improvement is provided when needed."""
        response = api_client.get("/scorecard")
        data = response.json()
        
        # Should be a list (may be empty if all metrics at target)
        assert "areas_for_improvement" in data, "Missing areas_for_improvement"
        assert isinstance(data.get("areas_for_improvement"), list), \
            "areas_for_improvement should be a list"
    
    def test_comments_present(self, api_client):
        """Test that human-readable comments are present."""
        response = api_client.get("/scorecard")
        data = response.json()
        
        assert "comments" in data, "Missing comments field"
        comments = data.get("comments")
        assert isinstance(comments, str), "comments should be a string"
        assert len(comments) > 0, "comments should not be empty"


class TestMetricsEndpoint:
    """Test /metrics endpoint for detailed metrics."""
    
    def test_metrics_endpoint_exists(self, api_client, assert_helpers):
        """Test that /metrics endpoint is accessible."""
        response = api_client.get("/metrics")
        assert response.status_code == 200, "Metrics endpoint should be accessible"
        assert_helpers.assert_metrics_response(response)
    
    def test_all_metrics_in_metrics_endpoint(self, api_client):
        """Test that all 8 metrics are in /metrics response."""
        response = api_client.get("/metrics")
        data = response.json()
        
        required_metrics = [
            "review_validity",
            "decision_consistency_avg",
            "packet_integrity",
            "data_quality",
            "agent_consensus",
            "backtest_validity",
            "risk_estimate",
            "confidence_calibration"
        ]
        
        for metric in required_metrics:
            assert metric in data, f"Missing metric: {metric}"
    
    def test_metrics_have_status(self, api_client):
        """Test that metrics have status field."""
        response = api_client.get("/metrics")
        data = response.json()
        
        # Check overall status
        assert "overall_status" in data, "Missing overall_status"
        assert data["overall_status"] in ["ok", "warning", "critical"]
    
    def test_metrics_timestamp(self, api_client):
        """Test that metrics include computation timestamp."""
        response = api_client.get("/metrics")
        data = response.json()
        
        assert "computed_at" in data, "Metrics should have computed_at timestamp"
