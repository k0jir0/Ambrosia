"""
Shared test fixtures and configuration for Index52 test suite.

This module provides:
- API client for making requests to the Ambrosia stack
- Test data factories for creating test packets, reviews, feedback
- Database fixtures (in-memory or staging)
- Common assertions and helpers
"""
import pytest
import requests
import json
from typing import Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import time


@dataclass
class TestConfig:
    """Test configuration based on environment."""
    base_url: str
    timeout: int = 10
    retry_attempts: int = 3
    retry_delay: float = 0.5


@pytest.fixture(scope="session")
def api_client():
    """Create HTTP client for API testing."""
    base_url = "http://127.0.0.1:8001"  # Override with env var if needed
    
    class APIClient:
        def __init__(self, base_url: str, timeout: int = 10):
            self.base_url = base_url
            self.timeout = timeout
            self.session = requests.Session()
        
        def get(self, endpoint: str, params: Optional[dict] = None, **kwargs):
            """GET request with retry logic."""
            url = f"{self.base_url}{endpoint}"
            for attempt in range(3):
                try:
                    response = self.session.get(url, params=params, timeout=self.timeout, **kwargs)
                    return response
                except requests.Timeout:
                    if attempt < 2:
                        time.sleep(0.5)
                    else:
                        raise
            return response
        
        def post(self, endpoint: str, json_data: Optional[dict] = None, **kwargs):
            """POST request with retry logic."""
            url = f"{self.base_url}{endpoint}"
            for attempt in range(3):
                try:
                    response = self.session.post(url, json=json_data, timeout=self.timeout, **kwargs)
                    return response
                except requests.Timeout:
                    if attempt < 2:
                        time.sleep(0.5)
                    else:
                        raise
            return response
        
        def close(self):
            """Close session."""
            self.session.close()
    
    client = APIClient(base_url)
    yield client
    client.close()


@pytest.fixture
def sample_packet_data():
    """Sample packet data for testing."""
    return {
        "ticker": "SPY",
        "asset_class": "ETF",
        "time_horizon": "2-6 weeks",
        "confidence": 65,
        "decision_state": "watch",
        "thesis": "Technical setup suggests consolidation before breakout",
        "support_level": 450.0,
        "resistance_level": 460.0,
        "suggested_entry": 455.0
    }


@pytest.fixture
def sample_feedback_data():
    """Sample feedback data for testing."""
    return {
        "outcome": "won",
        "outcome_date": datetime.utcnow().isoformat(),
        "pnl": 2.5,
        "exit_price": 457.5,
        "description": "Trade closed at target"
    }


@pytest.fixture
def sample_review_data():
    """Sample review data for testing."""
    return {
        "ticker": "SPY",
        "asset_class": "ETF",
        "status": "completed",
        "thesis": "Market review for SPY",
        "technical_setup": "Consolidation pattern",
        "risk_factors": ["Fed policy", "Earnings"],
        "confidence_level": 70
    }


class AssertionHelpers:
    """Common assertion helpers for API responses."""
    
    @staticmethod
    def assert_health_response(response: requests.Response):
        """Validate health check response format."""
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        assert "status" in data, "Missing 'status' field"
        assert data["status"] in ["ok", "warning", "critical"], f"Invalid status: {data['status']}"
    
    @staticmethod
    def assert_metrics_response(response: requests.Response):
        """Validate metrics response includes all 8 metrics."""
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        required_metrics = [
            "review_validity",
            "decision_consistency_avg",
            "packet_integrity",
            "data_quality",
            "agent_consensus",
            "backtest_validity",
            "risk_estimate",
            "confidence_calibration",
            "overall_status"
        ]
        
        for metric in required_metrics:
            assert metric in data, f"Missing metric: {metric}"
    
    @staticmethod
    def assert_scorecard_response(response: requests.Response):
        """Validate scorecard (certification artifact) response."""
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        data = response.json()
        
        required_fields = [
            "certification_status",
            "certification_index",
            "all_metrics_present",
            "all_metrics_at_target",
            "overall_status",
            "gates_passed"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
        
        # Validate gates_passed structure
        gates = data["gates_passed"]
        assert "all_metrics_computed" in gates
        assert "all_metrics_at_target" in gates
        assert "platform_status_ok" in gates
    
    @staticmethod
    def assert_certified(response: requests.Response, expected_status: str = "certified"):
        """Assert certification status."""
        data = response.json()
        assert data.get("certification_status") == expected_status, \
            f"Expected {expected_status}, got {data.get('certification_status')}"


@pytest.fixture
def assert_helpers():
    """Provide assertion helpers to tests."""
    return AssertionHelpers()
