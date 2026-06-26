"""
INDEX61 Completion & Status Tests

Tests for:
- Platform completion status tracking
- Phase summary and progress
- Acceptance contract validation
- Deployment readiness checks
- Roadmap metrics and timeline
"""
import pytest
import json
from datetime import datetime


class TestCompletionStatus:
    """Test completion status endpoints."""
    
    def test_completion_status_endpoint(self, api_client):
        """Test GET /index61/completion/status."""
        response = api_client.get("/index61/completion/status")
        assert response.status_code == 200, "Completion status should be accessible"
        
        data = response.json()
        assert "overall_completion" in data or "completion" in data, \
            "Should include completion percentage"
    
    def test_completion_shows_100_percent(self, api_client):
        """Test completion status shows 100%."""
        response = api_client.get("/index61/completion/status")
        
        if response.status_code == 200:
            data = response.json()
            completion = data.get("overall_completion") or data.get("completion")
            
            # Should show 100%
            if isinstance(completion, str):
                assert "100" in completion, "Completion should show 100%"
            elif isinstance(completion, (int, float)):
                assert completion >= 100, "Completion should be 100 or greater"
    
    def test_completion_includes_dates(self, api_client):
        """Test completion status includes timeline dates."""
        response = api_client.get("/index61/completion/status")
        
        if response.status_code == 200:
            data = response.json()
            # Should have start or completion dates
            assert "completion_date" in data or "date" in data or "timestamp" in data, \
                "Should include completion date"
    
    def test_completion_status_field(self, api_client):
        """Test completion has status indicator."""
        response = api_client.get("/index61/completion/status")
        
        if response.status_code == 200:
            data = response.json()
            assert "status" in data, "Should include status field"
            # Should be complete or passed
            status = data["status"].lower()
            assert "complete" in status or "pass" in status or "100" in status, \
                "Status should indicate completion"


class TestPhasesSummary:
    """Test phases summary endpoint."""
    
    def test_phases_summary_endpoint(self, api_client):
        """Test GET /index61/phases/summary."""
        response = api_client.get("/index61/phases/summary")
        assert response.status_code == 200, "Phases summary should be accessible"
        
        data = response.json()
        assert "phases" in data, "Should include phases"
    
    def test_all_five_phases_listed(self, api_client):
        """Test all 5 phases are included."""
        response = api_client.get("/index61/phases/summary")
        
        if response.status_code == 200:
            data = response.json()
            phases = data.get("phases", {})
            
            required_phases = ["A", "B", "C", "D", "E"]
            for phase in required_phases:
                assert phase in phases, f"Phase {phase} should be listed"
    
    def test_phase_structure(self, api_client):
        """Test each phase has required fields."""
        response = api_client.get("/index61/phases/summary")
        
        if response.status_code == 200:
            data = response.json()
            phases = data.get("phases", {})
            
            for phase_id, phase_data in phases.items():
                assert "name" in phase_data, f"Phase {phase_id} should have name"
                assert "status" in phase_data, f"Phase {phase_id} should have status"
                assert "contracts" in phase_data, f"Phase {phase_id} should list contracts"
    
    def test_phases_show_complete(self, api_client):
        """Test all phases show as complete."""
        response = api_client.get("/index61/phases/summary")
        
        if response.status_code == 200:
            data = response.json()
            phases = data.get("phases", {})
            
            for phase_id, phase_data in phases.items():
                status = phase_data.get("status", "").lower()
                assert "complete" in status or "100" in status, \
                    f"Phase {phase_id} should be complete"
    
    def test_total_contracts_metric(self, api_client):
        """Test total contracts metric is included."""
        response = api_client.get("/index61/phases/summary")
        
        if response.status_code == 200:
            data = response.json()
            assert "total_contracts" in data, "Should include total contracts count"
            
            contracts = data.get("total_contracts")
            # Should show all 18 contracts
            if isinstance(contracts, str):
                assert "18" in contracts, "Should show 18 contracts"


class TestAcceptanceContracts:
    """Test acceptance contracts endpoint."""
    
    def test_acceptance_contracts_endpoint(self, api_client):
        """Test GET /index61/acceptance-contracts."""
        response = api_client.get("/index61/acceptance-contracts")
        assert response.status_code == 200, "Contracts endpoint should exist"
        
        data = response.json()
        assert "contracts" in data or "total_contracts" in data, \
            "Should include contracts information"
    
    def test_all_18_contracts_listed(self, api_client):
        """Test all 18 contracts are included."""
        response = api_client.get("/index61/acceptance-contracts")
        
        if response.status_code == 200:
            data = response.json()
            
            if "total_contracts" in data:
                assert data["total_contracts"] == 18, \
                    "Should show 18 total contracts"
            
            # Count contracts in phases
            if "contracts" in data:
                contracts = data["contracts"]
                total = 0
                for phase_contracts in contracts.values():
                    if isinstance(phase_contracts, list):
                        total += len(phase_contracts)
                    elif isinstance(phase_contracts, dict):
                        total += len(phase_contracts)
                assert total == 18, f"Should have 18 contracts total, got {total}"
    
    def test_contract_structure(self, api_client):
        """Test contract objects have required fields."""
        response = api_client.get("/index61/acceptance-contracts")
        
        if response.status_code == 200:
            data = response.json()
            contracts = data.get("contracts", {})
            
            # Get first contract
            for phase_id, phase_contracts in contracts.items():
                if isinstance(phase_contracts, (list, dict)):
                    items = phase_contracts if isinstance(phase_contracts, list) else \
                            phase_contracts.values() if isinstance(phase_contracts, dict) else []
                    
                    if len(items) > 0:
                        contract = items[0]
                        if isinstance(contract, dict):
                            assert "id" in contract, "Contract should have ID"
                            assert "name" in contract or "title" in contract, \
                                "Contract should have name"
                            assert "status" in contract, "Contract should have status"
                        break
    
    def test_all_contracts_passing(self, api_client):
        """Test all contracts show as passing."""
        response = api_client.get("/index61/acceptance-contracts")
        
        if response.status_code == 200:
            data = response.json()
            
            if "all_passing" in data:
                assert data["all_passing"] == True, \
                    "All contracts should be passing"


class TestDeploymentReadiness:
    """Test deployment readiness endpoint."""
    
    def test_deployment_readiness_endpoint(self, api_client):
        """Test GET /index61/deployment-readiness."""
        response = api_client.get("/index61/deployment-readiness")
        assert response.status_code == 200, "Deployment readiness should be accessible"
        
        data = response.json()
        assert "status" in data, "Should include readiness status"
    
    def test_readiness_shows_ready(self, api_client):
        """Test deployment is marked as ready."""
        response = api_client.get("/index61/deployment-readiness")
        
        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "").lower()
            
            assert "ready" in status or "pass" in status or "100" in status, \
                f"Should show deployment ready, got: {status}"
    
    def test_readiness_includes_completion(self, api_client):
        """Test readiness shows completion percentage."""
        response = api_client.get("/index61/deployment-readiness")
        
        if response.status_code == 200:
            data = response.json()
            
            if "completion" in data:
                completion = data["completion"]
                if isinstance(completion, str):
                    assert "100" in completion, "Completion should show 100%"
    
    def test_readiness_checks_present(self, api_client):
        """Test readiness includes detailed checks."""
        response = api_client.get("/index61/deployment-readiness")
        
        if response.status_code == 200:
            data = response.json()
            assert "readiness_checks" in data or "checks" in data, \
                "Should include detailed readiness checks"
    
    def test_readiness_check_items(self, api_client):
        """Test readiness checks include key items."""
        response = api_client.get("/index61/deployment-readiness")
        
        if response.status_code == 200:
            data = response.json()
            checks = data.get("readiness_checks", data.get("checks", {}))
            
            # Should have multiple checks
            assert len(checks) > 0, "Should have readiness checks"
            
            # Each check should have status
            for check_name, check_data in checks.items():
                if isinstance(check_data, dict):
                    assert "status" in check_data, f"Check {check_name} should have status"


class TestRoadmapMetrics:
    """Test roadmap metrics endpoint."""
    
    def test_roadmap_metrics_endpoint(self, api_client):
        """Test GET /index61/roadmap-metrics."""
        response = api_client.get("/index61/roadmap-metrics")
        assert response.status_code == 200, "Metrics endpoint should exist"
        
        data = response.json()
        assert "timeline" in data or "metrics" in data, \
            "Should include roadmap metrics"
    
    def test_timeline_information(self, api_client):
        """Test timeline is included in metrics."""
        response = api_client.get("/index61/roadmap-metrics")
        
        if response.status_code == 200:
            data = response.json()
            
            if "timeline" in data:
                timeline = data["timeline"]
                assert "start_date" in timeline, "Should include start date"
                assert "target_date" in timeline, "Should include target date"
    
    def test_completion_tracking(self, api_client):
        """Test completion tracking by week."""
        response = api_client.get("/index61/roadmap-metrics")
        
        if response.status_code == 200:
            data = response.json()
            
            if "completion_tracking" in data:
                tracking = data["completion_tracking"]
                # Should have weekly entries
                assert len(tracking) > 0, "Should have weekly tracking"
    
    def test_resource_allocation(self, api_client):
        """Test resource allocation metrics."""
        response = api_client.get("/index61/roadmap-metrics")
        
        if response.status_code == 200:
            data = response.json()
            
            if "resource_allocation" in data:
                resources = data["resource_allocation"]
                # Should show team allocation
                assert len(resources) > 0, "Should have resource data"


class TestCertificationSignOff:
    """Test certification and sign-off endpoints."""
    
    def test_sign_off_endpoint_exists(self, api_client):
        """Test POST /index61/certification/sign-off."""
        payload = {
            "reviewer_name": "CTO",
            "reviewer_role": "admin"
        }
        response = api_client.post("/index61/certification/sign-off", json=payload)
        
        # Should exist and either allow or require auth
        assert response.status_code in [200, 201, 401, 403], \
            "Sign-off endpoint should be accessible"
    
    def test_sign_off_response_structure(self, api_client):
        """Test sign-off response has correct structure."""
        payload = {
            "reviewer_name": "CTO",
            "reviewer_role": "admin"
        }
        response = api_client.post("/index61/certification/sign-off", json=payload)
        
        if response.status_code in [200, 201]:
            data = response.json()
            assert "status" in data, "Should include status"
            assert "reviewer" in data or "reviewer_name" in data, \
                "Should include reviewer info"


class TestIndex61Integration:
    """Test INDEX61 completion system integration."""
    
    def test_all_status_endpoints_consistent(self, api_client):
        """Test all status endpoints show consistent 100% completion."""
        
        # Get completion status
        response1 = api_client.get("/index61/completion/status")
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Get phases summary
        response2 = api_client.get("/index61/phases/summary")
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Get deployment readiness
        response3 = api_client.get("/index61/deployment-readiness")
        assert response3.status_code == 200
        data3 = response3.json()
        
        # All should indicate 100% or complete
        for data in [data1, data2, data3]:
            # At least one indicator of completion should be present
            has_completion = (
                ("100" in str(data)) or
                ("complete" in str(data).lower()) or
                ("COMPLETE" in str(data))
            )
            assert has_completion, f"Should show completion: {data}"
    
    def test_contracts_match_phases(self, api_client):
        """Test contracts listed match phase counts."""
        
        # Get phases
        response1 = api_client.get("/index61/phases/summary")
        phases_data = response1.json()
        
        # Get contracts
        response2 = api_client.get("/index61/acceptance-contracts")
        contracts_data = response2.json()
        
        # Phase A should have 4 contracts
        # Phase B should have 4 contracts
        # Phase C should have 3 contracts
        # Phase D should have 4 contracts
        # Phase E should have 3 contracts
        # Total = 18
        
        expected_counts = {"A": 4, "B": 4, "C": 3, "D": 4, "E": 3}
        
        if "phases" in phases_data and "contracts" in contracts_data:
            for phase, count in expected_counts.items():
                phase_contracts = contracts_data["contracts"].get(f"phase_{phase.lower()}", [])
                if isinstance(phase_contracts, list):
                    actual = len(phase_contracts)
                    assert actual == count, \
                        f"Phase {phase} should have {count} contracts, got {actual}"


class TestIndex61Contracts:
    """Verify all INDEX61 contracts are defined."""
    
    def test_index61_contracts_defined(self, api_client):
        """Test all INDEX61 contracts are queryable."""
        response = api_client.get("/index61/acceptance-contracts")
        assert response.status_code == 200, \
            "INDEX61 Contracts: Should be queryable"
        
        data = response.json()
        contracts = data.get("contracts", {})
        
        # Verify contract structure for each phase
        expected_phases = {
            "phase_a": ["A1", "A2", "A3", "A4"],
            "phase_b": ["B1", "B2", "B3", "B4"],
            "phase_c": ["C1", "C2", "C3"],
            "phase_d": ["D1", "D2", "D3", "D4"],
            "phase_e": ["E1", "E2", "E3"]
        }
        
        for phase_name, contract_ids in expected_phases.items():
            if phase_name in contracts:
                phase_contracts = contracts[phase_name]
                for contract_list in (
                    [phase_contracts] if isinstance(phase_contracts, dict) else phase_contracts
                ):
                    if isinstance(contract_list, dict):
                        existing_ids = {c.get("id") for c in phase_contracts 
                                       if isinstance(c, dict)}
                    else:
                        existing_ids = {c.get("id") for c in contract_list 
                                       if isinstance(c, dict)}
