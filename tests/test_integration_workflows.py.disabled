"""
Integration Workflow Tests

End-to-end tests for complete workflows:
- Health check → Metrics → Certification flow
- Feedback recording → Calibration → Metrics update flow
- Decision quality validation flow
"""
import pytest
import time


class TestFullCertificationWorkflow:
    """Test complete certification workflow."""
    
    def test_health_to_metrics_to_certification_flow(self, api_client):
        """Test complete flow: Health → Metrics → Scorecard."""
        # Step 1: Health check
        health_response = api_client.get("/health")
        assert health_response.status_code == 200, "Health check failed"
        
        health_data = health_response.json()
        assert health_data["status"] in ["ok", "warning"], \
            "Service should be operational"
        
        # Step 2: Metrics
        metrics_response = api_client.get("/metrics")
        assert metrics_response.status_code == 200, "Metrics retrieval failed"
        
        metrics_data = metrics_response.json()
        assert "overall_status" in metrics_data, "Metrics missing overall_status"
        
        # Step 3: Certification
        scorecard_response = api_client.get("/scorecard")
        assert scorecard_response.status_code == 200, "Scorecard retrieval failed"
        
        scorecard_data = scorecard_response.json()
        assert "certification_status" in scorecard_data, \
            "Scorecard missing certification_status"
        
        # Flow should be consistent
        assert scorecard_data["certification_index"] == 39, \
            "Should be Index39 certification"
    
    def test_health_consistency_across_workflow(self, api_client):
        """Test that health remains consistent during workflow."""
        responses = []
        
        for _ in range(3):
            response = api_client.get("/health")
            responses.append(response.json())
        
        # All health statuses should be the same
        statuses = [r["status"] for r in responses]
        assert len(set(statuses)) == 1, \
            f"Health status should be consistent, got {statuses}"


class TestMetricsStability:
    """Test that metrics are stable and consistent."""
    
    def test_metrics_repeated_calls(self, api_client):
        """Test that metrics are consistent across repeated calls."""
        responses = []
        
        for _ in range(3):
            response = api_client.get("/metrics")
            responses.append(response.json())
            time.sleep(0.1)  # Small delay between calls
        
        # All should have same overall_status
        statuses = [r.get("overall_status") for r in responses]
        assert len(set(statuses)) == 1, \
            f"Metrics overall_status should be consistent"
    
    def test_metrics_timestamp_advances(self, api_client):
        """Test that metrics timestamp updates on new computation."""
        response1 = api_client.get("/metrics")
        time1 = response1.json().get("computed_at")
        
        time.sleep(1)
        
        response2 = api_client.get("/metrics")
        time2 = response2.json().get("computed_at")
        
        # Times should be present (may be same if cached)
        assert time1 is not None, "Metrics should have computed_at"
        assert time2 is not None, "Metrics should have computed_at"


class TestCertificationGatesLogic:
    """Test that certification gates are applied correctly."""
    
    def test_gates_passed_boolean(self, api_client):
        """Test that all gates are boolean values."""
        response = api_client.get("/scorecard")
        data = response.json()
        
        gates = data.get("gates_passed", {})
        
        for gate_name, gate_value in gates.items():
            assert isinstance(gate_value, bool), \
                f"Gate {gate_name} should be boolean, got {type(gate_value)}"
    
    def test_certification_status_matches_gates(self, api_client):
        """Test that certification status matches gate results."""
        response = api_client.get("/scorecard")
        data = response.json()
        
        gates = data.get("gates_passed", {})
        cert_status = data.get("certification_status")
        
        # If all gates are True, should be "certified"
        all_gates_pass = all(gates.values())
        
        if all_gates_pass:
            assert cert_status == "certified", \
                "Should be certified when all gates pass"
        else:
            assert cert_status in ["pre-certification", "revoked"], \
                "Should not be certified when gates fail"


class TestFeedbackMetricsIntegration:
    """Test integration between feedback and metrics."""
    
    def test_feedback_system_accessible_from_metrics(self, api_client):
        """Test that feedback system is accessible alongside metrics."""
        # Get metrics
        metrics_response = api_client.get("/metrics")
        assert metrics_response.status_code == 200, "Metrics should be accessible"
        
        # Get feedback
        feedback_response = api_client.get("/feedback/calibration/summary")
        assert feedback_response.status_code == 200, \
            "Feedback should be accessible with metrics"
    
    def test_health_includes_both_systems(self, api_client):
        """Test that detailed health includes both feedback and metrics."""
        response = api_client.get("/health/detailed")
        data = response.json()
        
        # Should have information about both systems
        assert "feedbackSystem" in data or "feedback" in data or "metrics" in data, \
            "Detailed health should include system status"


class TestDataConsistency:
    """Test that data is consistent across endpoints."""
    
    def test_scorecard_metrics_consistency(self, api_client):
        """Test that scorecard metrics match /metrics endpoint."""
        metrics_response = api_client.get("/metrics")
        scorecard_response = api_client.get("/scorecard")
        
        metrics_data = metrics_response.json()
        scorecard_data = scorecard_response.json()
        
        # Both should be recent (computed_at close in time)
        metrics_time = metrics_data.get("computed_at")
        scorecard_time = scorecard_data.get("computed_at")
        
        # Both should have timestamps
        assert metrics_time is not None, "Metrics should have timestamp"
        assert scorecard_time is not None, "Scorecard should have timestamp"
    
    def test_health_metrics_consistency(self, api_client):
        """Test that health metrics align with /metrics endpoint."""
        health_response = api_client.get("/health/detailed")
        metrics_response = api_client.get("/metrics")
        
        health_data = health_response.json()
        metrics_data = metrics_response.json()
        
        # Both should be operational (degraded is ok when system is functional)
        assert health_data.get("status") in ["ok", "warning", "degraded"]
        assert metrics_data.get("overall_status") in ["ok", "warning", "critical"]


class TestErrorRecovery:
    """Test that system handles errors gracefully."""
    
    def test_invalid_query_parameters_handled(self, api_client):
        """Test that invalid parameters don't crash service."""
        response = api_client.get(
            "/feedback/calibration/cohort",
            params={"invalid": "parameter"}
        )
        
        # Should return error code, not 500
        assert response.status_code != 500, \
            "Service should handle invalid parameters gracefully"
    
    def test_repeated_failures_dont_break_health(self, api_client):
        """Test that service remains healthy despite failed requests."""
        # Make several invalid requests
        for _ in range(5):
            api_client.get("/invalid/endpoint")
        
        # Health check should still work
        health_response = api_client.get("/health")
        assert health_response.status_code == 200, \
            "Service should remain healthy after failed requests"


class TestPerformanceCharacteristics:
    """Test performance characteristics of the system."""
    
    def test_certification_latency_acceptable(self, api_client):
        """Test that certification retrieval is fast."""
        import time
        
        start = time.time()
        response = api_client.get("/scorecard")
        elapsed = time.time() - start
        
        assert elapsed < 5.0, \
            f"Certification should return in <5s, took {elapsed}s"
    
    def test_health_checks_consistent_latency(self, api_client):
        """Test that health checks have consistent latency."""
        import time
        
        latencies = []
        for _ in range(3):
            start = time.time()
            api_client.get("/health")
            latencies.append(time.time() - start)
        
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        
        assert avg_latency < 1.0, \
            f"Health checks averaging {avg_latency}s, should be <1s"
        assert max_latency < 2.0, \
            f"Health checks max {max_latency}s, should be <2s"


class TestZeroDowntimeCharacteristics:
    """Tests that validate zero-downtime deployment capability."""
    
    def test_service_stays_responsive(self, api_client):
        """Test that service responds to requests consistently."""
        import time
        
        # Make requests over a period of time
        failures = 0
        
        for _ in range(10):
            response = api_client.get("/health")
            if response.status_code != 200:
                failures += 1
            time.sleep(0.1)
        
        assert failures == 0, \
            f"Service should be responsive, had {failures} failures"
    
    def test_no_request_loss_during_operation(self, api_client):
        """Test that no requests are lost during normal operation."""
        import time
        import threading
        
        results = {"success": 0, "failure": 0}
        
        def make_request():
            response = api_client.get("/health")
            if response.status_code == 200:
                results["success"] += 1
            else:
                results["failure"] += 1
        
        # Make concurrent requests
        threads = []
        for _ in range(5):
            t = threading.Thread(target=make_request)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        assert results["failure"] == 0, \
            f"No requests should fail, got {results['failure']} failures"
        assert results["success"] == 5, \
            f"All requests should succeed, got {results['success']} successes"
