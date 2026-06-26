"""
PHASE D: RBAC (Role-Based Access Control) Middleware
Enforces 4 roles: user, analyst, team_lead, admin
"""

from fastapi import Request, HTTPException, Depends
from functools import wraps
from typing import List, Optional
import jwt
from datetime import datetime

# Role definitions
ROLES = {
    "user": {
        "level": 1,
        "permissions": ["view_packets", "view_signals", "view_reports"]
    },
    "analyst": {
        "level": 2,
        "permissions": ["view_packets", "view_signals", "view_reports", "create_theses", "generate_reports"]
    },
    "team_lead": {
        "level": 3,
        "permissions": [
            "view_packets", "view_signals", "view_reports", "create_theses", "generate_reports",
            "approve_trades", "manage_team", "view_audit_log"
        ]
    },
    "admin": {
        "level": 4,
        "permissions": [
            "view_packets", "view_signals", "view_reports", "create_theses", "generate_reports",
            "approve_trades", "manage_team", "view_audit_log", "modify_policies", "system_config",
            "user_management", "export_data"
        ]
    }
}

class RBACMiddleware:
    """RBAC enforcement middleware"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Extract user role from header
        headers = dict(scope.get("headers", []))
        auth_header = headers.get(b"authorization", b"").decode()
        
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            # In real implementation: decode JWT
            # For now, extract role from custom header
            user_role = headers.get(b"x-user-role", b"user").decode()
            scope["user_role"] = user_role
        
        await self.app(scope, receive, send)

class RoleChecker:
    """Verify user has required role"""
    
    def __init__(self, required_role: str):
        self.required_role = required_role
    
    async def __call__(self, request: Request):
        user_role = request.headers.get("X-User-Role", "user")
        
        required_level = ROLES.get(self.required_role, {}).get("level", 0)
        user_level = ROLES.get(user_role, {}).get("level", 0)
        
        if user_level < required_level:
            raise HTTPException(
                status_code=403,
                detail=f"Required role: {self.required_role}, got: {user_role}"
            )
        
        return user_role

class PermissionChecker:
    """Verify user has specific permission"""
    
    def __init__(self, required_permission: str):
        self.required_permission = required_permission
    
    async def __call__(self, request: Request):
        user_role = request.headers.get("X-User-Role", "user")
        role_info = ROLES.get(user_role, {})
        
        if self.required_permission not in role_info.get("permissions", []):
            raise HTTPException(
                status_code=403,
                detail=f"Missing permission: {self.required_permission}"
            )
        
        return user_role

def require_role(role: str):
    """Decorator to require specific role"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, request: Request = None, **kwargs):
            if not request:
                return await func(*args, **kwargs)
            
            user_role = request.headers.get("X-User-Role", "user")
            required_level = ROLES.get(role, {}).get("level", 0)
            user_level = ROLES.get(user_role, {}).get("level", 0)
            
            if user_level < required_level:
                raise HTTPException(
                    status_code=403,
                    detail=f"Required role: {role}"
                )
            
            return await func(*args, request=request, **kwargs)
        return wrapper
    return decorator

def require_permission(permission: str):
    """Decorator to require specific permission"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, request: Request = None, **kwargs):
            if not request:
                return await func(*args, **kwargs)
            
            user_role = request.headers.get("X-User-Role", "user")
            role_info = ROLES.get(user_role, {})
            
            if permission not in role_info.get("permissions", []):
                raise HTTPException(
                    status_code=403,
                    detail=f"Missing permission: {permission}"
                )
            
            return await func(*args, request=request, **kwargs)
        return wrapper
    return decorator

# Audit logging
class AuditLog:
    """Track all privileged actions"""
    
    logs = []
    
    @classmethod
    def log_action(cls, user_role: str, action: str, resource: str, details: dict = None):
        """Log a privileged action"""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "user_role": user_role,
            "action": action,
            "resource": resource,
            "details": details or {},
            "status": "SUCCESS"
        }
        cls.logs.append(entry)
        return entry
    
    @classmethod
    def get_audit_log(cls, limit: int = 100):
        """Retrieve audit log"""
        return cls.logs[-limit:]

# Permission boundaries
PERMISSION_BOUNDARIES = {
    "modify_packets": {
        "allowed_roles": ["analyst", "team_lead", "admin"],
        "risk_level": "MEDIUM",
        "requires_approval": True
    },
    "approve_trades": {
        "allowed_roles": ["team_lead", "admin"],
        "risk_level": "HIGH",
        "requires_approval": True,
        "requires_mfa": True
    },
    "policy_changes": {
        "allowed_roles": ["admin"],
        "risk_level": "CRITICAL",
        "requires_approval": True,
        "requires_escalation": True
    },
    "audit_access": {
        "allowed_roles": ["team_lead", "admin"],
        "risk_level": "HIGH",
        "read_only": True
    }
}

def check_permission_boundary(user_role: str, action: str) -> bool:
    """Check if action is allowed for role"""
    boundary = PERMISSION_BOUNDARIES.get(action, {})
    allowed_roles = boundary.get("allowed_roles", [])
    
    return user_role in allowed_roles
