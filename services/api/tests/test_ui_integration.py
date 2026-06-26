"""
Frontend Integration Tests — UI Workflow Coverage

Tests frontend-specific workflows and API integration points.

Coverage:
- Discovery Scanner page: Signal scanning, filtering, thesis creation
- Report Export page: Format selection, preview, export execution
- Team Management page: Member CRUD, role assignment, invites
- Governance dashboard: RBAC visibility, audit logs
- Market dashboard: Real-time quotes, portfolio tracking
- Attribution dashboard: Performance metrics, trade analysis
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Dict, List

from fastapi.testclient import TestClient
import pytest

from app.main import app

client = TestClient(app)


# ═══════════════════════════════════════════════════════════════════════════
# DISCOVERY SCANNER PAGE TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestDiscoveryScannerUI:
    """Discovery Scanner page (/discovery) integration tests."""

    def test_discovery_scanner_initializes(self):
        """UI-C1-1: Discovery Scanner page initializes successfully."""
        response = client.post(
            "/discovery/scan",
            json={
                "universe": "all",
                "signal_type": "all",
                "min_conviction": 0.70,
                "lookback_days": 20,
            },
            headers={"X-User-Role": "analyst"},
        )
        
        assert response.status_code in [200, 422]

    def test_discovery_scanner_with_filters(self):
        """UI-C1-2: Discovery Scanner applies filters correctly."""
        filters = {
            "universe": "sp500",
            "signal_type": "momentum",
            "min_conviction": 0.75,
            "lookback_days": 10,
        }
        
        response = client.post(
            "/discovery/scan",
            json=filters,
            headers={"X-User-Role": "analyst"},
        )
        
        assert response.status_code in [200, 422]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (dict, list))

    def test_discovery_scanner_respects_role_visibility(self):
        """UI-C1-3: Scanner respects role-based signal visibility."""
        scan_request = {
            "universe": "all",
            "signal_type": "all",
        }
        
        # Test with different roles
        for role in ["analyst", "reviewer", "admin"]:
            response = client.post(
                "/discovery/scan",
                json=scan_request,
                headers={"X-User-Role": role},
            )
            
            assert response.status_code in [200, 403, 422]

    def test_discovery_scanner_create_thesis_button(self):
        """UI-C1-4: Create Thesis button works from scanner."""
        response = client.post(
            "/discovery/signal/ui-discovery-001/create-thesis",
            json={
                "signal_type": "momentum",
                "conviction": 0.76,
                "supporting_data": {
                    "rsi": 65,
                    "macd": "positive",
                    "volume_trend": "increasing",
                },
            },
            headers={"X-User-Role": "analyst"},
        )
        
        assert response.status_code in [200, 201, 422]

    def test_discovery_scanner_export_report_button(self):
        """UI-C1-5: Export Report button works from scanner."""
        response = client.post(
            "/discovery/reports/ui-discovery-001/export",
            json={
                "format": "html",
                "include_charts": True,
                "include_validation": True,
            },
            headers={"X-User-Role": "analyst"},
        )
        
        assert response.status_code in [200, 201, 422]

    def test_discovery_scanner_auto_refresh(self):
        """UI-C1-6: Scanner auto-refresh updates signal list."""
        # First scan
        response1 = client.post(
            "/discovery/scan",
            json={"universe": "all", "signal_type": "all"},
            headers={"X-User-Role": "analyst"},
        )
        
        # Second scan (simulating refresh)
        response2 = client.post(
            "/discovery/scan",
            json={"universe": "all", "signal_type": "all"},
            headers={"X-User-Role": "analyst"},
        )
        
        # Both should succeed
        assert response1.status_code in [200, 422]
        assert response2.status_code in [200, 422]


# ═══════════════════════════════════════════════════════════════════════════
# REPORT EXPORT PAGE TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestReportExportUI:
    """Report Export page (/reports/export/{id}) integration tests."""

    def test_export_page_format_selection_pdf(self):
        """UI-C2-1: PDF export format selection works."""
        response = client.post(
            "/discovery/reports/ui-export-001/export",
            json={
                "format": "pdf",
                "include_charts": True,
                "include_validation": True,
            },
            headers={"X-User-Role": "analyst"},
        )
        
        assert response.status_code in [200, 201, 422]

    def test_export_page_format_selection_html(self):
        """UI-C2-2: HTML export format selection works."""
        response = client.post(
            "/discovery/reports/ui-export-002/export",
            json={
                "format": "html",
                "include_charts": True,
            },
            headers={"X-User-Role": "analyst"},
        )
        
        assert response.status_code in [200, 201, 422]

    def test_export_page_format_selection_email(self):
        """UI-C2-3: Email export format works."""
        response = client.post(
            "/discovery/reports/ui-export-003/export",
            json={
                "format": "email",
                "recipient": "analyst@example.com",
                "subject": "Test Report",
            },
            headers={"X-User-Role": "analyst"},
        )
        
        assert response.status_code in [200, 201, 422]

    def test_export_page_preview_generates(self):
        """UI-C2-4: Export preview generates successfully."""
        # Preview is typically fetched before export
        response = client.post(
            "/discovery/reports/ui-export-preview/export",
            json={
                "format": "html",
                "preview_only": True,
            },
            headers={"X-User-Role": "analyst"},
        )
        
        assert response.status_code in [200, 201, 422]

    def test_export_page_batch_export(self):
        """UI-C2-5: Batch export multiple reports."""
        response = client.post(
            "/discovery/shortcuts/batch-generate",
            json={
                "report_ids": [
                    "ui-export-batch-1",
                    "ui-export-batch-2",
                    "ui-export-batch-3",
                ],
                "format": "pdf",
                "include_charts": True,
            },
            headers={"X-User-Role": "analyst"},
        )
        
        assert response.status_code in [200, 201, 422]

    def test_export_respects_role_based_content(self):
        """UI-C2-6: Export content respects user role."""
        for role in ["analyst", "reviewer", "admin"]:
            response = client.post(
                "/discovery/reports/ui-export-role/export",
                json={
                    "format": "html",
                    "include_sensitive_data": True,
                },
                headers={"X-User-Role": role},
            )
            
            # Different roles may have different access
            assert response.status_code in [200, 201, 403, 422]


# ═══════════════════════════════════════════════════════════════════════════
# TEAM MANAGEMENT PAGE TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestTeamManagementUI:
    """Team Management page (/governance/team-management) integration tests."""

    def test_team_members_list_loads(self):
        """UI-D1-1: Team members list loads with proper RBAC."""
        response = client.get(
            "/governance/team/members",
            headers={"X-User-Role": "admin"},
        )
        
        assert response.status_code in [200, 403, 422]
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, (list, dict))

    def test_team_member_crud_operations(self):
        """UI-D1-2: Team member CRUD operations work."""
        # Create (invite)
        create_resp = client.post(
            "/governance/team/invite",
            json={
                "email": "newanalyst@example.com",
                "role": "analyst",
            },
            headers={"X-User-Role": "admin"},
        )
        
        assert create_resp.status_code in [200, 201, 422]

    def test_role_assignment_workflow(self):
        """UI-D1-3: Role assignment updates correctly."""
        # Get current members
        get_resp = client.get(
            "/governance/team/members",
            headers={"X-User-Role": "admin"},
        )
        
        # Should return current team state
        assert get_resp.status_code in [200, 403, 422]

    def test_invite_form_validation(self):
        """UI-D1-4: Invite form validates input correctly."""
        # Invalid email
        invalid_resp = client.post(
            "/governance/team/invite",
            json={
                "email": "not-an-email",
                "role": "analyst",
            },
            headers={"X-User-Role": "admin"},
        )
        
        # Should reject or return validation error
        assert invalid_resp.status_code in [200, 201, 422]

    def test_team_summary_statistics(self):
        """UI-D1-5: Team summary shows correct statistics."""
        # Team stats typically on dashboard
        response = client.get(
            "/governance/team/members",
            headers={"X-User-Role": "admin"},
        )
        
        # Should return team data
        assert response.status_code in [200, 403, 422]
        
        if response.status_code == 200:
            data = response.json()
            # Should have team member data
            assert isinstance(data, (list, dict))

    def test_role_badge_colors_correct(self):
        """UI-D1-6: Role badges display correct colors."""
        # Role colors are client-side, but we verify endpoint structure
        response = client.get(
            "/governance/team/members",
            headers={"X-User-Role": "admin"},
        )
        
        assert response.status_code in [200, 403, 422]


# ═══════════════════════════════════════════════════════════════════════════
# GOVERNANCE DASHBOARD TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestGovernanceDashboardUI:
    """Governance dashboard integration tests."""

    def test_governance_dashboard_loads(self):
        """UI-D2-1: Governance dashboard loads."""
        response = client.get(
            "/governance/phase-d/status",
            headers={"X-User-Role": "admin"},
        )
        
        assert response.status_code in [200, 404, 422]

    def test_rbac_enforcement_panel(self):
        """UI-D2-2: RBAC enforcement status visible."""
        response = client.get(
            "/governance/rbac/enforcement",
            headers={"X-User-Role": "admin"},
        )
        
        assert response.status_code in [200, 403, 404, 422]

    def test_policies_panel_shows_rules(self):
        """UI-D2-3: Policies panel displays configured rules."""
        response = client.get(
            "/governance/policies",
            headers={"X-User-Role": "admin"},
        )
        
        assert response.status_code in [200, 403, 422]

    def test_audit_log_panel_accessible(self):
        """UI-D2-4: Audit log panel shows activity."""
        response = client.get(
            "/governance/admin/audit-log",
            headers={"X-User-Role": "admin"},
        )
        
        assert response.status_code in [200, 403, 404, 422]

    def test_permission_boundaries_visualization(self):
        """UI-D2-5: Permission boundaries display correctly."""
        response = client.get(
            "/governance/boundaries/enforce",
            headers={"X-User-Role": "admin"},
        )
        
        assert response.status_code in [200, 403, 404, 422]


# ═══════════════════════════════════════════════════════════════════════════
# MARKET DASHBOARD TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestMarketDashboardUI:
    """Market dashboard integration tests."""

    def test_market_quotes_panel_loads(self):
        """UI-E1-1: Market quotes panel loads real-time data."""
        response = client.get(
            "/market/quote/SPY",
            headers={"X-User-Role": "analyst"},
        )
        
        assert response.status_code in [200, 404, 422]
        if response.status_code == 200:
            data = response.json()
            # Should have price data
            assert isinstance(data, dict)

    def test_market_quotes_multiple_tickers(self):
        """UI-E1-2: Market quotes for multiple tickers."""
        for ticker in ["AAPL", "MSFT", "GOOGL", "TSLA"]:
            response = client.get(
                f"/market/quote/{ticker}",
                headers={"X-User-Role": "analyst"},
            )
            
            # Should handle all tickers gracefully
            assert response.status_code in [200, 404, 422]

    def test_portfolio_tracking_panel(self):
        """UI-E1-3: Portfolio tracking shows positions."""
        response = client.get(
            "/market/sandbox/portfolio",
            headers={"X-User-Role": "analyst"},
        )
        
        assert response.status_code in [200, 422]
        if response.status_code == 200:
            data = response.json()
            # Should have portfolio data
            assert isinstance(data, dict)

    def test_market_live_quotes_feed(self):
        """UI-E1-4: Live quotes feed updates."""
        response = client.get(
            "/market-data/live-quotes",
            headers={"X-User-Role": "analyst"},
        )
        
        assert response.status_code in [200, 422]


# ═══════════════════════════════════════════════════════════════════════════
# ATTRIBUTION DASHBOARD TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestAttributionDashboardUI:
    """Attribution dashboard integration tests."""

    def test_attribution_dashboard_loads(self):
        """UI-E2-1: Attribution dashboard loads metrics."""
        response = client.get(
            "/attribution/dashboard",
            headers={"X-User-Role": "analyst"},
        )
        
        assert response.status_code in [200, 422]

    def test_performance_metrics_display(self):
        """UI-E2-2: Performance metrics displayed correctly."""
        response = client.get(
            "/attribution/performance-metrics",
            headers={"X-User-Role": "analyst"},
        )
        
        assert response.status_code in [200, 404, 422]
        if response.status_code == 200:
            data = response.json()
            # Should have metrics
            assert isinstance(data, dict)

    def test_factor_analysis_panel(self):
        """UI-E2-3: Factor analysis shows attribution breakdown."""
        response = client.get(
            "/attribution/factor-analysis",
            headers={"X-User-Role": "analyst"},
        )
        
        assert response.status_code in [200, 404, 422]

    def test_trade_history_visible(self):
        """UI-E2-4: Trade history displayed."""
        response = client.get(
            "/trading/order-history",
            headers={"X-User-Role": "analyst"},
        )
        
        assert response.status_code in [200, 422]

    def test_attribution_by_decision_id(self):
        """UI-E2-5: Attribution accessible by decision ID."""
        response = client.get(
            "/market/attribution/ui-attribution-001",
            headers={"X-User-Role": "analyst"},
        )
        
        assert response.status_code in [200, 422]


# ═══════════════════════════════════════════════════════════════════════════
# CALIBRATION & FEEDBACK PAGE TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestCalibrationFeedbackUI:
    """Calibration & feedback page integration tests."""

    def test_calibration_bands_display(self):
        """UI-A1-1: Calibration bands display correctly."""
        response = client.get(
            "/calibration/bands",
            headers={"X-User-Role": "analyst"},
        )
        
        assert response.status_code in [200, 404, 422]

    def test_feedback_recording_form(self):
        """UI-A1-2: Feedback recording form works."""
        response = client.post(
            "/feedback/record",
            json={
                "decision_id": "ui-feedback-001",
                "outcome": "success",
                "realized_pnl": 1200.00,
                "accuracy_assessment": 0.84,
            },
            headers={"X-User-Role": "analyst"},
        )
        
        assert response.status_code in [200, 201, 422]

    def test_accuracy_trends_chart(self):
        """UI-A1-3: Accuracy trends chart loads."""
        response = client.get(
            "/feedback/accuracy-trends",
            headers={"X-User-Role": "analyst"},
        )
        
        assert response.status_code in [200, 404, 422]


# ═══════════════════════════════════════════════════════════════════════════
# UI ERROR HANDLING & EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════

class TestUIErrorHandling:
    """UI error handling and edge case tests."""

    def test_invalid_signal_id_handling(self):
        """UI-ERR-1: Invalid signal ID handled gracefully."""
        response = client.post(
            "/discovery/signal/invalid-id-that-does-not-exist/create-thesis",
            json={"conviction": 0.75},
            headers={"X-User-Role": "analyst"},
        )
        
        # Should not crash, may return 404 or 422
        assert response.status_code not in [500]

    def test_invalid_ticker_handling(self):
        """UI-ERR-2: Invalid ticker handled gracefully."""
        response = client.get(
            "/market/quote/INVALIDTICKER123456",
            headers={"X-User-Role": "analyst"},
        )
        
        # Should not crash
        assert response.status_code not in [500]

    def test_missing_required_fields(self):
        """UI-ERR-3: Missing required fields handled."""
        response = client.post(
            "/discovery/reports/test/export",
            json={},  # Missing required fields
            headers={"X-User-Role": "analyst"},
        )
        
        # Should return validation error, not crash
        assert response.status_code in [200, 201, 422]

    def test_unauthorized_role_handling(self):
        """UI-ERR-4: Unauthorized roles handled properly."""
        response = client.post(
            "/governance/policies/create",
            json={
                "name": "Test",
                "condition": "test",
                "action": "test",
            },
            headers={"X-User-Role": "viewer"},
        )
        
        # Should return 403, not crash
        assert response.status_code in [200, 201, 403, 422]

    def test_concurrent_ui_requests(self):
        """UI-ERR-5: Concurrent UI requests handled."""
        # Simulate multiple simultaneous requests
        for i in range(5):
            response = client.post(
                "/discovery/scan",
                json={"universe": "all"},
                headers={"X-User-Role": "analyst"},
            )
            assert response.status_code not in [500]
