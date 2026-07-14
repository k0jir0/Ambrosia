from __future__ import annotations

from services.api.app.execution_loop import BrokerSandbox, generate_execution_loop_demo
from services.api.app.governance_rbac import (
    PermissionBoundary,
    RBACEngine,
    User,
    generate_governance_report,
)
from services.api.app.phase_d_rbac import AuditLog, check_permission_boundary


def test_rbac_engine_checks_role_permissions_and_boundaries() -> None:
    engine = RBACEngine()
    engine.add_user(
        User(
            user_id="u1",
            email="analyst@example.com",
            role_ids=["role_analyst"],
            team_id="research",
            created_at="2026-07-13T00:00:00Z",
            is_active=True,
        )
    )
    engine.define_boundary(
        PermissionBoundary(
            boundary_id="modify",
            resource_type="packet",
            required_role="role_analyst",
            required_approval=False,
            audit_required=True,
            risk_level="medium",
        )
    )

    assert engine.check_permission("u1", "modify_packets") is True
    assert engine.check_permission("u1", "manage_roles") is False
    assert engine.check_permission("missing", "modify_packets") is False
    assert engine.check_boundary("u1", "modify") == {
        "allowed": True,
        "requires_approval": False,
        "audit_required": True,
        "risk_level": "medium",
    }
    assert engine.check_boundary("missing", "modify")["allowed"] is False


def test_rbac_engine_blocks_insufficient_role_level() -> None:
    engine = RBACEngine()
    engine.add_user(
        User(
            user_id="u1",
            email="user@example.com",
            role_ids=["role_user"],
            team_id="trading",
            created_at="2026-07-13T00:00:00Z",
            is_active=True,
        )
    )
    engine.define_boundary(
        PermissionBoundary(
            boundary_id="approve",
            resource_type="portfolio",
            required_role="role_team_lead",
            required_approval=True,
            audit_required=True,
            risk_level="high",
        )
    )

    result = engine.check_boundary("u1", "approve")

    assert result["allowed"] is False
    assert "Role level insufficient" in result["reason"]


def test_governance_report_contains_expected_boundary_scenarios() -> None:
    report = generate_governance_report()

    assert report["governance_status"] == "framework_ready"
    assert report["rbac_engine"]["total_roles"] == 4
    assert report["rbac_engine"]["total_boundaries"] == 4
    assert any(check["result"]["allowed"] for check in report["boundary_checks"])
    assert any(not check["result"]["allowed"] for check in report["boundary_checks"])


def test_phase_d_permission_boundary_and_audit_log_helpers() -> None:
    AuditLog.logs = []

    assert check_permission_boundary("analyst", "modify_packets") is True
    assert check_permission_boundary("analyst", "policy_changes") is False
    assert check_permission_boundary("admin", "policy_changes") is True

    entry = AuditLog.log_action("admin", "policy_changes", "guardrail", {"id": "g1"})

    assert entry["status"] == "SUCCESS"
    assert AuditLog.get_audit_log(limit=1) == [entry]


def test_broker_sandbox_buy_sell_and_portfolio_accounting() -> None:
    sandbox = BrokerSandbox(initial_cash=10_000)

    buy = sandbox.place_order("SPY", "buy", 10, 100)
    sandbox.positions["SPY"].current_price = 110
    sell = sandbox.place_order("SPY", "sell", 4, 110)
    snapshot = sandbox.get_portfolio_snapshot()

    assert buy.status == "filled"
    assert sell.status == "filled"
    assert sandbox.cash == 9_440
    assert sandbox.positions["SPY"].quantity == 6
    assert sandbox.positions["SPY"].realized_pnl == 40
    assert snapshot["total_positions"] == 1
    assert snapshot["total_unrealized_pnl"] == 60


def test_broker_sandbox_does_not_open_position_when_cash_is_insufficient() -> None:
    sandbox = BrokerSandbox(initial_cash=100)

    order = sandbox.place_order("NVDA", "buy", 10, 50)

    assert order.status == "filled"
    assert sandbox.cash == 100
    assert sandbox.positions == {}


def test_broker_sandbox_attribution_and_demo_shape() -> None:
    sandbox = BrokerSandbox()
    attribution = sandbox.record_attribution(
        ticker="SPY",
        entry_thesis="Unit thesis",
        factors=["breadth", "risk"],
        outcome="position_closed",
        pnl_pct=2.4,
    )
    demo = generate_execution_loop_demo()

    assert attribution.execution_id == "attr_000001"
    assert attribution.factors == ["breadth", "risk"]
    assert demo["total_orders"] == 3
    assert demo["total_executions"] == 3
    assert demo["portfolio_snapshot"]["cash_available"] > 0
