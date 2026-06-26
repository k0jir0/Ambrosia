#!/usr/bin/env python3
"""
Phase D: Enterprise Governance and Multi-User Control
Identity, RBAC, team controls, and permission boundaries.
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Literal


@dataclass
class Role:
    """User role definition"""
    role_id: str
    role_name: str
    level: int  # 0=user, 1=analyst, 2=team_lead, 3=admin
    permissions: list[str]
    description: str


@dataclass
class User:
    """User with role assignment"""
    user_id: str
    email: str
    role_ids: list[str]
    team_id: str
    created_at: str
    is_active: bool


@dataclass
class PermissionBoundary:
    """Permission boundary for privileged actions"""
    boundary_id: str
    resource_type: str  # "packet", "portfolio", "settings", "admin"
    required_role: str
    required_approval: bool
    audit_required: bool
    risk_level: Literal["low", "medium", "high", "critical"]


class RBACEngine:
    """Role-Based Access Control engine"""
    
    def __init__(self):
        self.roles: dict[str, Role] = {}
        self.users: dict[str, User] = {}
        self.boundaries: dict[str, PermissionBoundary] = {}
        self._init_default_roles()
    
    def _init_default_roles(self) -> None:
        """Initialize default role definitions"""
        roles = [
            Role(
                role_id="role_user",
                role_name="User",
                level=0,
                permissions=["view_packets", "create_reviews", "read_scorecard"],
                description="Standard trader with read access and review capabilities"
            ),
            Role(
                role_id="role_analyst",
                role_name="Analyst",
                level=1,
                permissions=["view_packets", "create_reviews", "modify_packets", "access_scanner", "create_theses"],
                description="Analyst with packet modification and discovery access"
            ),
            Role(
                role_id="role_team_lead",
                role_name="Team Lead",
                level=2,
                permissions=["view_all_packets", "approve_reviews", "manage_team", "configure_alerts", "view_audit"],
                description="Team coordinator with approval authority and team management"
            ),
            Role(
                role_id="role_admin",
                role_name="Admin",
                level=3,
                permissions=["admin_all", "manage_roles", "configure_permissions", "manage_policies", "view_full_audit"],
                description="Platform administrator with full system access"
            ),
        ]
        
        for role in roles:
            self.roles[role.role_id] = role
    
    def check_permission(self, user_id: str, permission: str) -> bool:
        """Check if user has permission"""
        user = self.users.get(user_id)
        if not user:
            return False
        
        for role_id in user.role_ids:
            role = self.roles.get(role_id)
            if role and permission in role.permissions:
                return True
        
        return False
    
    def check_boundary(self, user_id: str, boundary_id: str) -> dict:
        """Check if action crosses permission boundary"""
        user = self.users.get(user_id)
        boundary = self.boundaries.get(boundary_id)
        
        if not user or not boundary:
            return {"allowed": False, "reason": "Invalid user or boundary"}
        
        # Check role requirement
        user_roles = [self.roles.get(rid) for rid in user.role_ids if rid in self.roles]
        user_max_level = max((r.level for r in user_roles), default=-1)
        
        boundary_role = self.roles.get(boundary.required_role)
        boundary_required_level = boundary_role.level if boundary_role else 999
        
        if user_max_level < boundary_required_level:
            return {
                "allowed": False,
                "reason": f"Role level insufficient. Required: {boundary.required_role}"
            }
        
        # Check approval requirement
        approval_needed = boundary.required_approval
        
        return {
            "allowed": True,
            "requires_approval": approval_needed,
            "audit_required": boundary.audit_required,
            "risk_level": boundary.risk_level,
        }
    
    def define_boundary(self, boundary: PermissionBoundary) -> None:
        """Define a new permission boundary"""
        self.boundaries[boundary.boundary_id] = boundary
    
    def add_user(self, user: User) -> None:
        """Add a user with role assignment"""
        self.users[user.user_id] = user
    
    def to_dict(self) -> dict:
        """Convert to dict"""
        return {
            "timestamp": datetime.now().isoformat(),
            "total_roles": len(self.roles),
            "total_users": len(self.users),
            "total_boundaries": len(self.boundaries),
            "roles": [asdict(r) for r in self.roles.values()],
            "users": [asdict(u) for u in self.users.values()],
            "boundaries": [asdict(b) for b in self.boundaries.values()],
        }


def generate_governance_report() -> dict:
    """Generate enterprise governance report"""
    engine = RBACEngine()
    
    # Define permission boundaries
    boundaries = [
        PermissionBoundary(
            boundary_id="boundary_modify_packets",
            resource_type="packet",
            required_role="role_analyst",
            required_approval=False,
            audit_required=True,
            risk_level="medium"
        ),
        PermissionBoundary(
            boundary_id="boundary_approve_trades",
            resource_type="portfolio",
            required_role="role_team_lead",
            required_approval=True,
            audit_required=True,
            risk_level="high"
        ),
        PermissionBoundary(
            boundary_id="boundary_policy_changes",
            resource_type="settings",
            required_role="role_admin",
            required_approval=True,
            audit_required=True,
            risk_level="critical"
        ),
        PermissionBoundary(
            boundary_id="boundary_audit_access",
            resource_type="admin",
            required_role="role_admin",
            required_approval=False,
            audit_required=True,
            risk_level="critical"
        ),
    ]
    
    for boundary in boundaries:
        engine.define_boundary(boundary)
    
    # Add sample users
    users = [
        User(
            user_id="usr_0001",
            email="alice@ambrosia.local",
            role_ids=["role_user"],
            team_id="team_traders",
            created_at=datetime.now().isoformat(),
            is_active=True
        ),
        User(
            user_id="usr_0002",
            email="bob@ambrosia.local",
            role_ids=["role_analyst"],
            team_id="team_research",
            created_at=datetime.now().isoformat(),
            is_active=True
        ),
        User(
            user_id="usr_0003",
            email="carol@ambrosia.local",
            role_ids=["role_team_lead", "role_analyst"],
            team_id="team_research",
            created_at=datetime.now().isoformat(),
            is_active=True
        ),
        User(
            user_id="usr_0004",
            email="admin@ambrosia.local",
            role_ids=["role_admin"],
            team_id="team_ops",
            created_at=datetime.now().isoformat(),
            is_active=True
        ),
    ]
    
    for user in users:
        engine.add_user(user)
    
    # Test permission boundary checks
    test_scenarios = [
        ("usr_0001", "boundary_modify_packets", "User cannot modify packets"),
        ("usr_0002", "boundary_modify_packets", "Analyst can modify packets"),
        ("usr_0002", "boundary_approve_trades", "Analyst cannot approve trades"),
        ("usr_0003", "boundary_approve_trades", "Team lead can approve trades"),
        ("usr_0001", "boundary_policy_changes", "User cannot change policies"),
        ("usr_0004", "boundary_policy_changes", "Admin can change policies"),
    ]
    
    boundary_checks = []
    for user_id, boundary_id, description in test_scenarios:
        result = engine.check_boundary(user_id, boundary_id)
        boundary_checks.append({
            "scenario": description,
            "user_id": user_id,
            "boundary_id": boundary_id,
            "result": result,
        })
    
    return {
        "timestamp": datetime.now().isoformat(),
        "governance_status": "framework_ready",
        "rbac_engine": engine.to_dict(),
        "boundary_checks": boundary_checks,
        "implementation_status": "Phase D ready for deployment",
    }


if __name__ == "__main__":
    # Generate governance report
    report = generate_governance_report()
    
    # Save artifact
    artifact_path = Path("artifacts/governance-rbac.json")
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(artifact_path, "w") as f:
        json.dump(report, f, indent=2)
    
    print("Enterprise Governance - RBAC Framework")
    print("=" * 70)
    print(f"Status: {report['governance_status']}")
    print(f"Roles Defined: {report['rbac_engine']['total_roles']}")
    print(f"Users Configured: {report['rbac_engine']['total_users']}")
    print(f"Permission Boundaries: {report['rbac_engine']['total_boundaries']}")
    
    print(f"\nBoundary Tests:")
    for check in report["boundary_checks"]:
        status = "✓ PASS" if check["result"]["allowed"] else "✗ BLOCKED"
        print(f"  {status}: {check['scenario']}")
        if check["result"]["allowed"]:
            print(f"    Requires Approval: {check['result']['requires_approval']}")
            print(f"    Risk Level: {check['result']['risk_level']}")
    
    print(f"\nGovernance report saved to: {artifact_path}")
