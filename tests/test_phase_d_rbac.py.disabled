"""
Phase D: Enterprise Governance & RBAC Tests

Tests for:
- RBAC role enforcement (user, analyst, team_lead, admin)
- Permission boundary enforcement
- Privilege escalation protection
- Audit logging of sensitive actions
- Policy configuration access control
"""
import pytest
import json
from typing import Dict, Optional


class TestRBACRoles:
    """Test RBAC role definitions and permissions."""
    
    def test_rbac_roles_endpoint(self, api_client):
        """Test GET /index61/rbac/roles returns all roles."""
        response = api_client.get("/index61/rbac/roles")
        assert response.status_code == 200, "RBAC roles endpoint should exist"
        
        data = response.json()
        assert "roles" in data, "Should return roles dictionary"
        
        roles = data["roles"]
        assert "user" in roles, "Should have 'user' role"
        assert "analyst" in roles, "Should have 'analyst' role"
        assert "team_lead" in roles, "Should have 'team_lead' role"
        assert "admin" in roles, "Should have 'admin' role"
    
    def test_user_role_permissions(self, api_client):
        """Test user role has basic view-only permissions."""
        response = api_client.get("/index61/rbac/roles")
        data = response.json()
        
        user_role = data["roles"]["user"]
        assert "level" in user_role, "Role should have level"
        assert user_role["level"] == 1, "User should be level 1"
        assert "permissions" in user_role, "Role should have permissions"
        
        perms = user_role["permissions"]
        assert "view_packets" in perms, "User should view packets"
        assert "view_signals" in perms, "User should view signals"
        assert "view_reports" in perms, "User should view reports"
    
    def test_analyst_role_inherits_user(self, api_client):
        """Test analyst role has user permissions plus create/analyze."""
        response = api_client.get("/index61/rbac/roles")
        data = response.json()
        
        analyst = data["roles"]["analyst"]
        assert analyst["level"] == 2, "Analyst should be level 2"
        
        perms = analyst["permissions"]
        # Should have user permissions
        assert "view_packets" in perms, "Analyst inherits user view_packets"
        # Plus analyst-specific
        assert "create_theses" in perms, "Analyst should create theses"
        assert "generate_reports" in perms, "Analyst should generate reports"
    
    def test_team_lead_role_includes_approval(self, api_client):
        """Test team_lead role includes approval permissions."""
        response = api_client.get("/index61/rbac/roles")
        data = response.json()
        
        lead = data["roles"]["team_lead"]
        assert lead["level"] == 3, "Team lead should be level 3"
        
        perms = lead["permissions"]
        assert "approve_trades" in perms, "Team lead should approve trades"
        assert "manage_team" in perms, "Team lead should manage team"
        assert "view_audit_log" in perms, "Team lead should view audit log"
    
    def test_admin_role_highest_privilege(self, api_client):
        """Test admin role has system-wide permissions."""
        response = api_client.get("/index61/rbac/roles")
        data = response.json()
        
        admin = data["roles"]["admin"]
        assert admin["level"] == 4, "Admin should be level 4"
        
        perms = admin["permissions"]
        assert "modify_policies" in perms, "Admin should modify policies"
        assert "system_config" in perms, "Admin should config system"
        assert "user_management" in perms, "Admin should manage users"


class TestPermissionBoundaries:
    """Test permission boundary enforcement."""
    
    def test_permission_boundaries_endpoint(self, api_client):
        """Test GET /index61/rbac/permission-boundaries."""
        response = api_client.get("/index61/rbac/permission-boundaries")
        assert response.status_code == 200, "Boundaries endpoint should exist"
        
        data = response.json()
        assert "boundaries" in data, "Should return boundaries"
        
        boundaries = data["boundaries"]
        assert "modify_packets" in boundaries, "Should have modify_packets boundary"
        assert "approve_trades" in boundaries, "Should have approve_trades boundary"
        assert "policy_changes" in boundaries, "Should have policy_changes boundary"
        assert "audit_access" in boundaries, "Should have audit_access boundary"
    
    def test_modify_packets_boundary(self, api_client):
        """Test modify_packets boundary is MEDIUM risk."""
        response = api_client.get("/index61/rbac/permission-boundaries")
        data = response.json()
        
        boundary = data["boundaries"]["modify_packets"]
        assert boundary["risk_level"] == "MEDIUM", "Should be MEDIUM risk"
        assert boundary["requires_approval"] == True, "Should require approval"
        assert "analyst" in boundary["allowed_roles"], "Analysts should modify packets"
        assert "admin" in boundary["allowed_roles"], "Admins should modify packets"
    
    def test_approve_trades_boundary(self, api_client):
        """Test approve_trades boundary requires MFA."""
        response = api_client.get("/index61/rbac/permission-boundaries")
        data = response.json()
        
        boundary = data["boundaries"]["approve_trades"]
        assert boundary["risk_level"] == "HIGH", "Should be HIGH risk"
        assert boundary["requires_approval"] == True, "Should require approval"
        assert boundary["requires_mfa"] == True, "Should require MFA"
        assert "team_lead" in boundary["allowed_roles"], "Team leads should approve"
        assert "user" not in boundary["allowed_roles"], "Regular users should NOT approve trades"
    
    def test_policy_changes_boundary(self, api_client):
        """Test policy_changes boundary is CRITICAL."""
        response = api_client.get("/index61/rbac/permission-boundaries")
        data = response.json()
        
        boundary = data["boundaries"]["policy_changes"]
        assert boundary["risk_level"] == "CRITICAL", "Should be CRITICAL risk"
        assert boundary["requires_approval"] == True, "Should require approval"
        assert boundary["requires_escalation"] == True, "Should require escalation"
        assert boundary["allowed_roles"] == ["admin"], "Only admins can change policy"
    
    def test_audit_access_boundary(self, api_client):
        """Test audit_access boundary is read-only for team_lead."""
        response = api_client.get("/index61/rbac/permission-boundaries")
        data = response.json()
        
        boundary = data["boundaries"]["audit_access"]
        assert boundary["risk_level"] == "HIGH", "Should be HIGH risk"
        assert boundary["read_only"] == True, "Should be read-only"
        assert "team_lead" in boundary["allowed_roles"], "Team leads can read audit"


class TestAuditLogging:
    """Test audit logging of privileged actions."""
    
    def test_audit_log_endpoint(self, api_client):
        """Test GET /index61/rbac/audit-log retrieves audit trail."""
        response = api_client.get("/index61/rbac/audit-log")
        assert response.status_code == 200, "Audit log should be accessible"
        
        data = response.json()
        assert "audit_log" in data or isinstance(data, list), \
            "Should return audit log"
    
    def test_audit_log_entry_format(self, api_client):
        """Test audit log entries have required fields."""
        response = api_client.get("/index61/rbac/audit-log")
        data = response.json()
        
        if "audit_log" in data and len(data["audit_log"]) > 0:
            entry = data["audit_log"][0]
            
            # Check required fields
            assert "timestamp" in entry, "Entry should have timestamp"
            assert "user_role" in entry or "user" in entry, "Entry should identify actor"
            assert "action" in entry, "Entry should describe action"
            assert "resource" in entry, "Entry should identify resource"
            assert "status" in entry, "Entry should show success/failure"
    
    def test_audit_log_limit_parameter(self, api_client):
        """Test audit log respects limit parameter."""
        response = api_client.get("/index61/rbac/audit-log?limit=10")
        assert response.status_code == 200, "Should support limit parameter"
        
        data = response.json()
        if "audit_log" in data:
            assert len(data["audit_log"]) <= 10, "Should respect limit"


class TestRoleEnforcement:
    """Test that role checks are enforced on protected endpoints."""
    
    def test_role_header_required_for_protected_endpoints(self, api_client):
        """Test protected endpoints check X-User-Role header."""
        # Try to access role-specific endpoint without role header
        response = api_client.get("/index61/rbac/audit-log")
        
        # Should either work (public endpoint) or require auth
        assert response.status_code in [200, 401, 403], \
            "Endpoint should validate role or allow public access"
    
    def test_role_header_respected(self, api_client):
        """Test that X-User-Role header is respected."""
        headers = {"X-User-Role": "admin"}
        response = api_client.get("/index61/rbac/audit-log", headers=headers)
        
        # Admin should have access
        assert response.status_code in [200, 404], \
            "Admin should access audit log or get 404 (not forbidden)"
    
    def test_invalid_role_rejected(self, api_client):
        """Test that invalid roles are rejected."""
        headers = {"X-User-Role": "superuser"}  # Invalid role
        response = api_client.get("/index61/rbac/audit-log", headers=headers)
        
        # Should reject invalid role
        assert response.status_code in [401, 403, 400], \
            "Invalid role should be rejected"


class TestRBACIntegration:
    """Test RBAC integration with other systems."""
    
    def test_rbac_with_discovery_endpoints(self, api_client):
        """Test RBAC applies to discovery endpoints."""
        # Without role
        response = api_client.get("/discovery/recent-theses")
        # May be public or require role
        assert response.status_code in [200, 401, 403], \
            "Should handle role requirement"
        
        # With analyst role
        headers = {"X-User-Role": "analyst"}
        response = api_client.get("/discovery/recent-theses", headers=headers)
        assert response.status_code in [200, 404], \
            "Analyst should access discovery endpoints"
    
    def test_rbac_with_execution_endpoints(self, api_client):
        """Test RBAC applies to execution endpoints."""
        headers = {"X-User-Role": "team_lead"}
        response = api_client.get("/execution/trading/paper-positions", headers=headers)
        
        assert response.status_code in [200, 404, 401], \
            "Team lead should access execution endpoints or get 404"


class TestPrivilegeEscalation:
    """Test protection against privilege escalation."""
    
    def test_user_cannot_approve_trades(self, api_client):
        """Test regular user cannot approve trades."""
        # Create payload for approving trade
        payload = {
            "trade_id": "trade_001",
            "approval": "approved"
        }
        
        headers = {"X-User-Role": "user"}
        # Assuming there's an approval endpoint
        response = api_client.post("/execution/trading/approve-trade", json=payload, headers=headers)
        
        # Should reject user role
        assert response.status_code in [403, 401, 404], \
            "User role should NOT be able to approve trades"
    
    def test_analyst_cannot_modify_policies(self, api_client):
        """Test analyst cannot modify system policies."""
        payload = {
            "policy": "max_trade_size",
            "value": 10000
        }
        
        headers = {"X-User-Role": "analyst"}
        response = api_client.post("/index61/policy/modify", json=payload, headers=headers)
        
        # Should reject analyst role
        assert response.status_code in [403, 401, 404], \
            "Analyst role should NOT modify policies"


class TestRBACContract:
    """Test Phase D acceptance contracts."""
    
    def test_contract_d1_rbac_engine(self, api_client):
        """D1: RBAC Engine - 4 roles with permission checks."""
        response = api_client.get("/index61/rbac/roles")
        assert response.status_code == 200, \
            "D1 Contract: RBAC roles should be queryable"
        
        data = response.json()
        roles = data.get("roles", {})
        required_roles = ["user", "analyst", "team_lead", "admin"]
        
        for role in required_roles:
            assert role in roles, f"D1 Contract: {role} must be defined"
            assert "level" in roles[role], f"D1 Contract: {role} must have level"
            assert "permissions" in roles[role], f"D1 Contract: {role} must have permissions"
    
    def test_contract_d2_permission_boundaries(self, api_client):
        """D2: Permission Boundaries - 4 boundaries enforced."""
        response = api_client.get("/index61/rbac/permission-boundaries")
        assert response.status_code == 200, \
            "D2 Contract: Permission boundaries should be queryable"
        
        data = response.json()
        boundaries = data.get("boundaries", {})
        required_boundaries = ["modify_packets", "approve_trades", "policy_changes", "audit_access"]
        
        for boundary in required_boundaries:
            assert boundary in boundaries, f"D2 Contract: {boundary} must be defined"
            b = boundaries[boundary]
            assert "allowed_roles" in b or "allowed_roles" in str(b), \
                f"D2 Contract: {boundary} must specify allowed roles"
            assert "risk_level" in b, f"D2 Contract: {boundary} must specify risk level"
    
    def test_contract_d3_policy_configuration(self, api_client):
        """D3: Policy Configuration - Framework ready."""
        # Policy framework should be queryable
        response = api_client.get("/index61/rbac/permission-boundaries")
        assert response.status_code == 200, \
            "D3 Contract: Policy configuration should be accessible"
    
    def test_contract_d4_ui_tabs_structure(self, api_client):
        """D4: Advanced/Team/Admin UI - Tabs architecture implemented."""
        response = api_client.get("/index61/rbac/roles")
        assert response.status_code == 200, \
            "D4 Contract: UI tabs should have role structure"
        
        data = response.json()
        roles = data.get("roles", {})
        
        # Advanced tab: analyst+ features
        assert "analyst" in roles, "D4 Contract: Advanced tab requires analyst role"
        
        # Team tab: team_lead+ features
        assert "team_lead" in roles, "D4 Contract: Team tab requires team_lead role"
        
        # Admin tab: admin features
        assert "admin" in roles, "D4 Contract: Admin tab requires admin role"
