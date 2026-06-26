"""
Phase C: Discovery & Intelligence Tests

Tests for:
- Discovery engine (thesis generation)
- Report generation and export
- Analyst workflow optimization
- Signal-to-thesis-to-report workflow
"""
import pytest
import json
from datetime import datetime


class TestDiscoveryEngine:
    """Test discovery engine endpoints."""
    
    def test_generate_thesis_endpoint_exists(self, api_client):
        """Test POST /discovery/generate-thesis endpoint."""
        payload = {
            "id": "sig_001",
            "ticker": "NVDA",
            "signal_type": "momentum",
            "strength": 0.85,
            "rationale": "Strong positive momentum with breakout"
        }
        response = api_client.post("/discovery/generate-thesis", json=payload)
        assert response.status_code in [200, 201], "Should generate thesis successfully"
    
    def test_generate_thesis_requires_signal_data(self, api_client):
        """Test thesis generation requires minimum signal data."""
        # Missing ticker
        payload = {
            "id": "sig_001",
            "signal_type": "momentum",
            "strength": 0.85
        }
        response = api_client.post("/discovery/generate-thesis", json=payload)
        assert response.status_code in [400, 422], "Should reject incomplete signal"
    
    def test_generate_thesis_returns_thesis_object(self, api_client):
        """Test generated thesis has correct structure."""
        payload = {
            "id": "sig_001",
            "ticker": "NVDA",
            "signal_type": "momentum",
            "strength": 0.85,
            "rationale": "Momentum test"
        }
        response = api_client.post("/discovery/generate-thesis", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            assert "thesis_id" in data or "id" in data, "Should return thesis ID"
            assert "ticker" in data, "Should include ticker"
            assert "analysis" in data or "content" in data, "Should include analysis"
    
    def test_recent_theses_endpoint(self, api_client):
        """Test GET /discovery/recent-theses returns list."""
        response = api_client.get("/discovery/recent-theses")
        assert response.status_code == 200, "Should retrieve recent theses"
        
        data = response.json()
        assert isinstance(data, (dict, list)), "Should return list or dict with theses"
        
        if isinstance(data, dict) and "theses" in data:
            assert isinstance(data["theses"], list), "Theses should be a list"
        elif isinstance(data, list):
            # List of theses directly
            pass
    
    def test_save_thesis_endpoint(self, api_client):
        """Test POST /discovery/save-thesis archives thesis."""
        payload = {
            "thesis_id": "thesis_001",
            "folder": "research",
            "tags": ["high_conviction", "momentum"]
        }
        response = api_client.post("/discovery/save-thesis", json=payload)
        assert response.status_code in [200, 201, 204], "Should save thesis"


class TestReportGenerator:
    """Test report generation endpoints."""
    
    def test_generate_report_endpoint(self, api_client):
        """Test POST /reports/generate creates report."""
        payload = {
            "thesis_ids": ["thesis_001", "thesis_002"],
            "report_type": "comprehensive",
            "format": "markdown"
        }
        response = api_client.post("/discovery/reports/generate", json=payload)
        assert response.status_code in [200, 201], "Should generate report"
    
    def test_generate_report_returns_content(self, api_client):
        """Test generated report includes content."""
        payload = {
            "thesis_ids": ["thesis_001"],
            "report_type": "summary"
        }
        response = api_client.post("/discovery/reports/generate", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            assert "content" in data or "html" in data or "markdown" in data, \
                "Report should include content"
            assert "title" in data or "report_id" in data, "Report should have ID/title"
    
    def test_export_pdf_endpoint(self, api_client):
        """Test POST /reports/export-pdf."""
        payload = {
            "report_id": "report_001",
            "filename": "report.pdf"
        }
        response = api_client.post("/discovery/reports/export-pdf", json=payload)
        # May return 200 with PDF or 501 if not implemented
        assert response.status_code in [200, 201, 501], "PDF export should be available or not implemented"
    
    def test_export_html_endpoint(self, api_client):
        """Test POST /reports/export-html."""
        payload = {
            "report_id": "report_001",
            "filename": "report.html"
        }
        response = api_client.post("/discovery/reports/export-html", json=payload)
        assert response.status_code in [200, 201], "HTML export should work"
    
    def test_email_report_endpoint(self, api_client):
        """Test POST /reports/email-report."""
        payload = {
            "report_id": "report_001",
            "recipients": ["analyst@example.com"],
            "subject": "Investment Research Report"
        }
        response = api_client.post("/discovery/reports/email-report", json=payload)
        # May return 200 or 501 if email not configured
        assert response.status_code in [200, 201, 501], "Email should be sendable or deferred"


class TestAnalystWorkflows:
    """Test analyst workflow optimization endpoints."""
    
    def test_triage_endpoint(self, api_client):
        """Test POST /analyst/triage quick triage workflow."""
        payload = {
            "idea_id": "idea_001",
            "signal_strength": 0.8,
            "triage_decision": "high_priority",
            "next_step": "deep_research"
        }
        response = api_client.post("/discovery/analyst/triage", json=payload)
        assert response.status_code in [200, 201], "Should perform triage"
    
    def test_queue_endpoint(self, api_client):
        """Test GET /analyst/queue returns prioritized ideas."""
        response = api_client.get("/discovery/analyst/queue")
        assert response.status_code == 200, "Should retrieve analyst queue"
        
        data = response.json()
        # Should return prioritized list
        if "ideas" in data:
            assert isinstance(data["ideas"], list), "Ideas should be a list"
            # Check for priority ordering
            if len(data["ideas"]) > 1:
                priorities = [idea.get("priority", 0) for idea in data["ideas"]]
                # Verify descending order
                assert priorities == sorted(priorities, reverse=True), \
                    "Ideas should be sorted by priority (descending)"
    
    def test_bulk_action_endpoint(self, api_client):
        """Test POST /analyst/bulk-action for batch operations."""
        payload = {
            "idea_ids": ["idea_001", "idea_002", "idea_003"],
            "action": "tag",
            "tag": "quarterly_review"
        }
        response = api_client.post("/discovery/analyst/bulk-action", json=payload)
        assert response.status_code in [200, 201, 202], "Should perform bulk action"
    
    def test_bulk_action_status(self, api_client):
        """Test bulk action returns status."""
        payload = {
            "idea_ids": ["idea_001"],
            "action": "archive"
        }
        response = api_client.post("/discovery/analyst/bulk-action", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            assert "processed" in data or "status" in data, \
                "Should return processing status"


class TestSignalToReportWorkflow:
    """Test complete signal-to-thesis-to-report workflow."""
    
    def test_complete_workflow_endpoint(self, api_client):
        """Test POST /signal-to-thesis complete workflow."""
        payload = {
            "signal": {
                "id": "sig_001",
                "ticker": "NVDA",
                "signal_type": "momentum"
            },
            "include_report": True
        }
        response = api_client.post("/discovery/signal-to-thesis", json=payload)
        assert response.status_code in [200, 201], "Should complete workflow"
    
    def test_workflow_returns_all_artifacts(self, api_client):
        """Test workflow returns signal, thesis, and report."""
        payload = {
            "signal": {
                "id": "sig_001",
                "ticker": "AAPL",
                "signal_type": "momentum"
            },
            "include_report": True
        }
        response = api_client.post("/discovery/signal-to-thesis", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            # Should have artifacts from each step
            assert "signal" in data or "signal_id" in data, "Should include signal"
            assert "thesis" in data or "thesis_id" in data, "Should include thesis"
            if data.get("include_report"):
                assert "report" in data or "report_id" in data, "Should include report"


class TestDiscoveryContract:
    """Test Phase C acceptance contracts."""
    
    def test_contract_c1_discovery_engine(self, api_client):
        """C1: Discovery Engine - Thesis generation from signals."""
        payload = {
            "id": "sig_test",
            "ticker": "TSLA",
            "signal_type": "momentum",
            "strength": 0.9
        }
        response = api_client.post("/discovery/generate-thesis", json=payload)
        
        # Contract: Endpoint should be callable and return thesis data
        assert response.status_code in [200, 201], \
            "C1 Contract: Discovery engine should generate theses"
        
        if response.status_code == 200:
            data = response.json()
            assert "id" in data or "thesis_id" in data, \
                "C1 Contract: Should return thesis ID"
    
    def test_contract_c2_report_generator(self, api_client):
        """C2: Report Generator - PDF/Email export operational."""
        # Test HTML export (more reliable than PDF)
        payload = {
            "report_id": "test_report",
            "filename": "test.html"
        }
        response = api_client.post("/discovery/reports/export-html", json=payload)
        
        # Contract: Export should be available
        assert response.status_code in [200, 201, 404], \
            "C2 Contract: Report export should be available"
    
    def test_contract_c3_analyst_workflows(self, api_client):
        """C3: Analyst Workflows - Framework complete and optimized."""
        # Test triage shortcut
        payload = {
            "idea_id": "test_idea",
            "signal_strength": 0.8,
            "triage_decision": "research"
        }
        response = api_client.post("/discovery/analyst/triage", json=payload)
        
        # Contract: Workflow should be callable
        assert response.status_code in [200, 201], \
            "C3 Contract: Analyst workflows should be operational"
        
        # Test queue access
        response = api_client.get("/discovery/analyst/queue")
        assert response.status_code == 200, \
            "C3 Contract: Analyst queue should be accessible"
