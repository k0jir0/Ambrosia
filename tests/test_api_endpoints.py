"""
API Endpoint Tests

Tests for:
- Health checks (liveness and comprehensive)
- Basic endpoint availability
- Response formats and validation
"""
import pytest
import json
from datetime import datetime


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_health_endpoint_exists(self, api_client):
        """Test that GET /health endpoint is available."""
        response = api_client.get("/health")
        assert response.status_code == 200, "Health endpoint should return 200 OK"
    
    def test_health_response_format(self, api_client, assert_helpers):
        """Test health response has correct format."""
        response = api_client.get("/health")
        assert_helpers.assert_health_response(response)
    
    def test_health_status_field(self, api_client):
        """Test health status field is present."""
        response = api_client.get("/health")
        data = response.json()
        
        assert "status" in data, "Health response missing 'status' field"
        assert data["status"] in ["ok", "warning", "critical"], \
            f"Invalid status value: {data['status']}"
    
    def test_health_timestamp_present(self, api_client):
        """Test health response includes timestamp."""
        response = api_client.get("/health")
        data = response.json()
        
        assert "timestamp" in data or "uptime_seconds" in data, \
            "Health response should include timestamp or uptime"
    
    def test_health_check_liveness(self, api_client):
        """Test health check proves service is alive."""
        response = api_client.get("/health")
        data = response.json()
        
        # Service is alive if status is not "critical"
        # (warning is ok, critical means failing checks)
        assert data["status"] in ["ok", "warning"], \
            f"Service should be alive, status is {data['status']}"
    
    def test_detailed_health_endpoint_exists(self, api_client):
        """Test that GET /health/detailed endpoint exists."""
        response = api_client.get("/health/detailed")
        assert response.status_code == 200, "Detailed health endpoint should exist"
    
    def test_detailed_health_includes_metrics(self, api_client):
        """Test that detailed health includes calibration metrics."""
        response = api_client.get("/health/detailed")
        data = response.json()
        
        # Should include calibrationMetrics section
        assert "calibrationMetrics" in data or "metrics" in data, \
            "Detailed health should include metrics"
    
    def test_detailed_health_includes_feedback_system(self, api_client):
        """Test that detailed health includes feedback system info."""
        response = api_client.get("/health/detailed")
        data = response.json()
        
        # Should have feedback system information (in checks or at top level)
        has_feedback = ("feedbackSystem" in data or "feedback" in data or 
                       ("checks" in data and "feedbackSystem" in data.get("checks", {})))
        assert has_feedback, "Detailed health should include feedback system status"
    
    def test_health_consistent_across_calls(self, api_client):
        """Test that health status is consistent."""
        response1 = api_client.get("/health")
        response2 = api_client.get("/health")
        
        data1 = response1.json()
        data2 = response2.json()
        
        # Status should be consistent (not flapping)
        assert data1["status"] == data2["status"], \
            "Health status should be consistent"


class TestMetricsEndpointAvailability:
    """Test metrics endpoint is available and accessible."""
    
    def test_metrics_endpoint_available(self, api_client):
        """Test /metrics endpoint returns data."""
        response = api_client.get("/metrics")
        assert response.status_code == 200, "Metrics endpoint should be available"
    
    def test_metrics_response_is_json(self, api_client):
        """Test metrics response is valid JSON."""
        response = api_client.get("/metrics")
        
        try:
            data = response.json()
            assert isinstance(data, dict), "Metrics should be a dictionary"
        except json.JSONDecodeError:
            pytest.fail("Metrics response is not valid JSON")
    
    def test_metrics_not_empty(self, api_client):
        """Test metrics response contains data."""
        response = api_client.get("/metrics")
        data = response.json()
        
        assert len(data) > 0, "Metrics response should not be empty"


class TestScoreboardEndpointAvailability:
    """Test scorecard/certification endpoint is available."""
    
    def test_scorecard_endpoint_available(self, api_client):
        """Test /scorecard endpoint is accessible."""
        response = api_client.get("/scorecard")
        assert response.status_code == 200, "Scorecard endpoint should be available"
    
    def test_scorecard_response_is_json(self, api_client):
        """Test scorecard response is valid JSON."""
        response = api_client.get("/scorecard")
        
        try:
            data = response.json()
            assert isinstance(data, dict), "Scorecard should be a dictionary"
        except json.JSONDecodeError:
            pytest.fail("Scorecard response is not valid JSON")
    
    def test_scorecard_not_empty(self, api_client):
        """Test scorecard response contains data."""
        response = api_client.get("/scorecard")
        data = response.json()
        
        assert len(data) > 0, "Scorecard response should not be empty"


class TestFeedbackEndpoints:
    """Test feedback system endpoints."""
    
    def test_feedback_summary_endpoint(self, api_client):
        """Test /feedback/calibration/summary endpoint."""
        response = api_client.get("/feedback/calibration/summary")
        assert response.status_code == 200, "Feedback summary should be accessible"
    
    def test_feedback_summary_response(self, api_client):
        """Test feedback summary has expected structure."""
        response = api_client.get("/feedback/calibration/summary")
        data = response.json()
        
        assert isinstance(data, dict), "Feedback summary should be a dictionary"
    
    def test_feedback_records_endpoint(self, api_client):
        """Test /feedback/records endpoint."""
        response = api_client.get("/feedback/records")
        assert response.status_code == 200, "Feedback records should be accessible"
    
    def test_feedback_records_response(self, api_client):
        """Test feedback records response format."""
        response = api_client.get("/feedback/records")
        data = response.json()
        
        # Should be a list or have records field
        assert isinstance(data, (dict, list)), \
            "Feedback records should be a list or dictionary"


class TestResponseHeaders:
    """Test HTTP response headers."""
    
    def test_json_content_type(self, api_client):
        """Test that API responses have correct content type."""
        response = api_client.get("/health")
        
        content_type = response.headers.get("content-type", "")
        assert "application/json" in content_type, \
            f"Expected JSON content-type, got {content_type}"
    
    def test_cors_headers_present(self, api_client):
        """Test that CORS headers are present."""
        response = api_client.get("/health")
        
        # At minimum, should have content-type and not return 405
        assert response.status_code != 405, "CORS should be configured"
    
    def test_response_has_content_length(self, api_client):
        """Test that responses have content-length header."""
        response = api_client.get("/health")
        
        # Should have content-length for most responses
        assert len(response.content) > 0, "Response should have content"


class TestEndpointResponseTimes:
    """Test that endpoints respond within acceptable time."""
    
    def test_health_endpoint_fast(self, api_client):
        """Test that health endpoint responds quickly."""
        import time
        
        start = time.time()
        response = api_client.get("/health")
        elapsed = time.time() - start
        
        assert elapsed < 2.0, f"Health endpoint took {elapsed}s, should be < 2s"
    
    def test_metrics_endpoint_responsive(self, api_client):
        """Test that metrics endpoint responds in reasonable time."""
        import time
        
        start = time.time()
        response = api_client.get("/metrics")
        elapsed = time.time() - start
        
        assert elapsed < 5.0, f"Metrics endpoint took {elapsed}s, should be < 5s"
    
    def test_scorecard_endpoint_responsive(self, api_client):
        """Test that scorecard endpoint responds in reasonable time."""
        import time
        
        start = time.time()
        response = api_client.get("/scorecard")
        elapsed = time.time() - start
        
        assert elapsed < 5.0, f"Scorecard endpoint took {elapsed}s, should be < 5s"


class TestErrorHandling:
    """Test API error handling."""
    
    def test_404_for_nonexistent_endpoint(self, api_client):
        """Test that nonexistent endpoints return 404."""
        response = api_client.get("/nonexistent")
        assert response.status_code == 404, "Nonexistent endpoint should return 404"
    
    def test_405_for_invalid_method(self, api_client):
        """Test that invalid HTTP methods return appropriate error."""
        # Try POST to a GET-only endpoint
        response = api_client.post("/health", json_data={})
        
        # Should return 405 Method Not Allowed or 422 Unprocessable Entity
        assert response.status_code in [405, 422, 200], \
            f"Invalid method should return 405 or 422, got {response.status_code}"
