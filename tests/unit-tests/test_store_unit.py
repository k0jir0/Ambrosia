from __future__ import annotations

from services.api.app.feedback import FeedbackRecord, OutcomeResult
from services.api.app.models import (
    AuditEventCreate,
    BrokerSandboxOrderRequest,
    DecisionState,
    OutcomeUpdate,
    PacketApprovalCreate,
    PacketApprovalDecision,
    PacketCommentCreate,
    PacketCommentType,
    WorkflowStep,
    WorkflowTemplateCreate,
    WorkspaceCreateRequest,
)
from services.api.app.store import ReviewStore


def _memory_store(monkeypatch) -> ReviewStore:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REQUIRE_DATABASE", raising=False)
    return ReviewStore()


def test_review_store_saves_lists_and_updates_review_decisions(monkeypatch, review_factory) -> None:
    store = _memory_store(monkeypatch)
    older = review_factory(ticker="SPY").model_copy(update={"createdAt": "2026-07-12T00:00:00Z"})
    newer = review_factory(ticker="QQQ").model_copy(update={"createdAt": "2026-07-13T00:00:00Z"})

    store.save_review(older)
    store.save_review(newer)
    updated = store.record_decision(older.id, DecisionState.watch)

    assert [review.ticker for review in store.list_reviews()] == ["QQQ", "SPY"]
    assert store.get_review(older.id) is not None
    assert updated is not None
    assert updated.decisionState == DecisionState.watch
    assert updated.status.value == "decision_recorded"
    assert updated.audit[-1].eventType == "decision.recorded"
    assert store.record_decision("missing", DecisionState.reject) is None


def test_review_store_records_outcome_as_audit_event(monkeypatch, sample_review) -> None:
    store = _memory_store(monkeypatch)
    store.save_review(sample_review)

    updated = store.record_outcome(
        sample_review.id,
        OutcomeUpdate(outcome="won after catalyst confirmation", outcome_date="2026-07-20"),
    )

    assert updated is not None
    assert updated.audit[-1].eventType == "outcome.recorded"
    assert "2026-07-20" in updated.audit[-1].detail
    assert store.record_outcome("missing", OutcomeUpdate(outcome="lost", outcome_date="2026-07-20")) is None


def test_review_store_packet_filters_and_audit_updates(monkeypatch, packet_factory) -> None:
    store = _memory_store(monkeypatch)
    spy = packet_factory(ticker="SPY").model_copy(update={"createdAt": "2026-07-12T00:00:00Z"})
    qqq = packet_factory(ticker="QQQ").model_copy(
        update={
            "id": "pkt-qqq-unit",
            "createdAt": "2026-07-13T00:00:00Z",
            "decisionState": DecisionState.pursue,
        }
    )

    store.save_packet(spy)
    store.save_packet(qqq)
    audited = store.add_packet_audit_event(
        spy.id,
        AuditEventCreate(eventType="unit.audit", detail="Unit audit added"),
    )

    assert [packet.ticker for packet in store.list_packets()] == ["QQQ", "SPY"]
    assert [packet.ticker for packet in store.list_packets(ticker="spy")] == ["SPY"]
    assert [packet.ticker for packet in store.list_packets(search="unit packet")] == ["QQQ", "SPY"]
    assert [packet.ticker for packet in store.list_packets(decision_state=DecisionState.pursue)] == ["QQQ"]
    assert audited is not None
    assert audited.audit[-1].eventType == "unit.audit"
    assert store.add_packet_audit_event("missing", AuditEventCreate(eventType="x.y", detail="No packet")) is None
    assert store.get_packet_audit("missing") is None


def test_review_store_job_lifecycle(monkeypatch) -> None:
    store = _memory_store(monkeypatch)

    job = store.enqueue_job("scanner.run", "universe=SPY")
    store.start_job(job.id)
    running = store.get_job(job.id)
    store.complete_job(job.id, {"candidates": 2})
    completed = store.get_job(job.id)
    failed = store.enqueue_job("report.generate", "packet=pkt-1")
    store.fail_job(failed.id, "boom")

    assert job.state.value == "queued"
    assert running is not None and running.state.value == "running"
    assert completed is not None and completed.state.value == "completed"
    assert completed.result == {"candidates": 2}
    assert store.get_job(failed.id).state.value == "failed"
    assert store.list_jobs(job_type="scanner.run")[0].id == job.id


def test_review_store_collaboration_objects(monkeypatch) -> None:
    store = _memory_store(monkeypatch)

    workspace = store.create_workspace(
        WorkspaceCreateRequest(name="Unit Workspace", description="Review room", ownerId="owner-1")
    )
    with_packet = store.add_packet_to_workspace(workspace.id, "pkt-1")
    duplicate = store.add_packet_to_workspace(workspace.id, "pkt-1")
    comment = store.add_packet_comment(
        "pkt-1",
        PacketCommentCreate(authorId="analyst-1", content="Needs liquidity check", commentType=PacketCommentType.risk_flag),
    )
    approval = store.set_packet_approval(
        "pkt-1",
        PacketApprovalCreate(
            reviewerId="lead-1",
            decision=PacketApprovalDecision.needs_revision,
            note="Add slippage evidence",
        ),
    )

    assert workspace.members[0].role.value == "owner"
    assert with_packet is not None and with_packet.packetIds == ["pkt-1"]
    assert duplicate is not None and duplicate.packetIds == ["pkt-1"]
    assert store.add_packet_to_workspace("missing", "pkt-1") is None
    assert store.list_workspaces(owner_id="owner-1")[0].id == workspace.id
    assert comment.commentType == PacketCommentType.risk_flag
    assert store.list_packet_comments("pkt-1") == [comment]
    assert approval.decision == PacketApprovalDecision.needs_revision
    assert store.get_packet_approval("pkt-1") == approval


def test_review_store_workflow_template_and_guardrail_lifecycle(monkeypatch) -> None:
    store = _memory_store(monkeypatch)

    template = store.create_workflow_template(
        WorkflowTemplateCreate(
            name="Unit Review",
            authorId="owner-1",
            steps=[WorkflowStep(stepId="s1", name="Validate", action="validate", humanGate=True)],
        )
    )
    published = store.publish_workflow_template(template.id)
    archived = store.archive_workflow_template(template.id)
    profile = store.create_guardrail_profile({"name": "Unit Guardrail", "rules": [{"id": "r1"}]})
    active = store.activate_guardrail_profile(profile["id"], updated_by="admin")

    assert template.status.value == "draft"
    assert published is not None and published.status.value == "published"
    assert archived is not None and archived.status.value == "archived"
    assert store.publish_workflow_template("missing") is None
    assert active is not None and active["active"] is True
    assert store.get_active_guardrail_profile()["id"] == profile["id"]
    assert store.activate_guardrail_profile("missing", updated_by="admin") is None


def test_review_store_feedback_calibration_and_alerts(monkeypatch) -> None:
    store = _memory_store(monkeypatch)
    records = [
        FeedbackRecord(
            packet_id="pkt-1",
            decision_state="pursue",
            confidence=80,
            ticker="SPY",
            asset_class="ETF",
            time_horizon="1-4 weeks",
            outcome_date="2026-07-20",
            outcome=OutcomeResult.lost,
        ),
        FeedbackRecord(
            packet_id="pkt-2",
            decision_state="watch",
            confidence=80,
            ticker="SPY",
            asset_class="ETF",
            time_horizon="1-4 weeks",
            outcome_date="2026-07-21",
            outcome=OutcomeResult.lost,
        ),
        FeedbackRecord(
            packet_id="pkt-3",
            decision_state="watch",
            confidence=80,
            ticker="SPY",
            asset_class="ETF",
            time_horizon="1-4 weeks",
            outcome_date="2026-07-22",
            outcome=OutcomeResult.partial,
        ),
    ]
    for record in records:
        store.save_feedback_record(record)

    cohort = store.recompute_cohort_calibration("SPY", "ETF", "1-4 weeks")
    band = store.get_band_calibration("SPY", "80-90%")
    summary = store.get_calibration_summary()
    alerts = store.list_calibration_alerts(ticker="SPY")

    assert cohort.total_decisions == 3
    assert cohort.flags["any_under_confident"] is True
    assert band is not None and band.decisions == 3
    assert summary.total_decisions == 3
    assert summary.total_alerts == 1
    assert alerts[0].alert_type == "under-confident"
    assert store.get_feedback_record(records[0].id) == records[0]
    assert len(store.list_feedback_records(outcome="lost")) == 2


def test_review_store_sandbox_orders_mobile_alerts_and_attribution(monkeypatch, sample_packet) -> None:
    store = _memory_store(monkeypatch)
    store.save_packet(sample_packet)

    order = store.simulate_sandbox_order(
        BrokerSandboxOrderRequest(ticker="spy", quantity=10, side="buy", price=500, source="unit")
    )
    alert = store.emit_mobile_alert(sample_packet.id, "risk.updated", "warning", "Risk changed")
    attribution = store.compute_attribution_report(sample_packet.id, pnl=2.5, horizon_days=5)
    admin_audit = store.add_admin_audit_event("policy.update", "admin", "policy-1", "Updated policy")

    assert order["ticker"] == "SPY"
    assert store.list_sandbox_positions()[0]["quantity"] == 10
    assert alert["ticker"] == sample_packet.ticker
    assert store.list_mobile_alert_events()[0]["id"] == alert["id"]
    assert attribution is not None and attribution["packetId"] == sample_packet.id
    assert store.get_attribution_report(sample_packet.id) == attribution
    assert store.compute_attribution_report("missing", pnl=1, horizon_days=1) is None
    assert store.list_admin_audit_events(event_type="policy.update") == [admin_audit]
