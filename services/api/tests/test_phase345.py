"""
Phase 3 / 4 / 5 acceptance tests.

Phase 3  — async report, health alerts
Phase 4  — workspaces, packet comments, approval flows
Phase 5  — workflow template lifecycle (create → publish → archive)
"""
from __future__ import annotations

import time as time_module

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_packet(packet_id: str, ticker: str = "SPY") -> dict:
    return {
        "id": packet_id,
        "title": f"Test packet {ticker}",
        "thesis": f"{ticker} breadth indicators are strengthening",
        "ticker": ticker,
        "assetClass": "ETF",
        "timeHorizon": "2-6 weeks",
        "intendedExpression": "Long ETF",
        "status": "synthesis",
        "decisionState": "watch",
        "confidence": 65,
        "trialCountImpact": 1,
        "followUpDate": "2026-07-15",
        "createdAt": "2026-06-25T10:00:00Z",
        "claims": [{"id": "c1", "kind": "sourced", "text": "breadth improving", "confidence": 70}],
        "strongestCritique": "macro headwinds",
        "disconfirmingTest": "underperforms for 10 sessions",
        "historicalAnalogue": {"title": "early cycle", "similarity": "breadth", "differences": "rates", "resolution": "stop"},
        "validation": {
            "status": "specified",
            "hypothesis": "SPY outperforms",
            "nullHypothesis": "no alpha",
            "dataRequirements": ["returns"],
            "protocol": "20-day rolling",
            "refusalReason": None,
        },
        "tradeability": [{"topic": "liquidity", "question": "enough?", "severity": "low"}],
        "sources": [{"id": "s1", "title": "snap", "sourceType": "internal", "timestamp": "2026-06-25T09:00:00Z", "permission": "user_owned", "relevance": 0.9}],
        "audit": [{"id": "a1", "timestamp": "10:00:00", "eventType": "packet.created", "detail": "test"}],
    }


# ---------------------------------------------------------------------------
# Phase 3 — async report
# ---------------------------------------------------------------------------

class TestPhase3AsyncReport:
    def test_report_async_enqueues_job(self) -> None:
        packet_id = "p3-report-async"
        client.post("/packets", json=_minimal_packet(packet_id))
        r = client.post(f"/packets/{packet_id}/report/async")
        assert r.status_code == 200
        job = r.json()
        assert job["id"].startswith("job-")
        assert job["jobType"] == "report.generate"
        assert job["state"] in {"queued", "running", "completed"}

    def test_report_async_completes(self) -> None:
        packet_id = "p3-report-async-complete"
        client.post("/packets", json=_minimal_packet(packet_id))
        job_id = client.post(f"/packets/{packet_id}/report/async").json()["id"]
        deadline = time_module.time() + 15
        while time_module.time() < deadline:
            j = client.get(f"/jobs/{job_id}").json()
            if j["state"] == "completed":
                assert j["result"] is not None
                assert "sections" in j["result"]
                return
            if j["state"] == "failed":
                raise AssertionError(f"Report job failed: {j.get('error')}")
            time_module.sleep(0.3)
        raise AssertionError("Async report did not complete within 15s")

    def test_report_async_404_for_missing_packet(self) -> None:
        assert client.post("/packets/missing-packet/report/async").status_code == 404


# ---------------------------------------------------------------------------
# Phase 3 — health alerts
# ---------------------------------------------------------------------------

class TestPhase3HealthAlerts:
    def test_health_detailed_has_alerts_field(self) -> None:
        r = client.get("/health/detailed")
        assert r.status_code == 200
        h = r.json()
        assert "alerts" in h
        assert isinstance(h["alerts"], list)

    def test_health_reports_missing_polygon_key_as_alert(self) -> None:
        r = client.get("/health/detailed")
        h = r.json()
        # Without POLYGON_API_KEY, an alert about Yahoo fallback must be present
        alert_texts = " ".join(h["alerts"])
        assert "NYSE" in alert_texts or "Polygon" in alert_texts or "fallback" in alert_texts.lower()

    def test_health_status_is_ok_or_degraded(self) -> None:
        h = client.get("/health/detailed").json()
        assert h["status"] in {"ok", "degraded"}


# ---------------------------------------------------------------------------
# Phase 4 — workspaces
# ---------------------------------------------------------------------------

class TestPhase4Workspaces:
    def test_workspace_create_get_list(self) -> None:
        r = client.post("/workspaces", json={"name": "Alpha Team", "description": "Internal alpha review", "ownerId": "user-alice"})
        assert r.status_code == 200
        ws = r.json()
        assert ws["id"].startswith("ws-")
        assert ws["ownerId"] == "user-alice"
        assert len(ws["members"]) == 1
        assert ws["members"][0]["role"] == "owner"

        get = client.get(f"/workspaces/{ws['id']}")
        assert get.status_code == 200
        assert get.json()["name"] == "Alpha Team"

        listed = client.get("/workspaces", params={"owner_id": "user-alice"})
        assert listed.status_code == 200
        assert any(w["id"] == ws["id"] for w in listed.json())

    def test_add_packet_to_workspace(self) -> None:
        packet_id = "p4-ws-packet"
        client.post("/packets", json=_minimal_packet(packet_id))
        ws_id = client.post("/workspaces", json={"name": "PM Workspace", "ownerId": "user-bob"}).json()["id"]

        r = client.post(f"/workspaces/{ws_id}/packets", json={"packetId": packet_id})
        assert r.status_code == 200
        assert packet_id in r.json()["packetIds"]

    def test_workspace_404_for_missing_id(self) -> None:
        assert client.get("/workspaces/no-such-ws").status_code == 404

    def test_add_packet_to_missing_workspace_returns_404(self) -> None:
        r = client.post("/workspaces/no-such-ws/packets", json={"packetId": "anything"})
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Phase 4 — packet comments
# ---------------------------------------------------------------------------

class TestPhase4PacketComments:
    def test_add_and_list_comments(self) -> None:
        packet_id = "p4-comments"
        client.post("/packets", json=_minimal_packet(packet_id))

        r = client.post(
            f"/packets/{packet_id}/comments",
            json={"authorId": "user-alice", "content": "Strong breadth confirmation from sector data.", "commentType": "general"},
        )
        assert r.status_code == 200
        comment = r.json()
        assert comment["id"].startswith("cmt-")
        assert comment["commentType"] == "general"

        client.post(
            f"/packets/{packet_id}/comments",
            json={"authorId": "user-bob", "content": "Risk flag: macro regime shift possible.", "commentType": "risk_flag"},
        )

        listed = client.get(f"/packets/{packet_id}/comments")
        assert listed.status_code == 200
        assert len(listed.json()) == 2
        types = {c["commentType"] for c in listed.json()}
        assert "general" in types
        assert "risk_flag" in types

    def test_comment_appended_to_packet_audit(self) -> None:
        packet_id = "p4-comment-audit"
        client.post("/packets", json=_minimal_packet(packet_id))
        client.post(
            f"/packets/{packet_id}/comments",
            json={"authorId": "user-carol", "content": "Critique: thesis needs stronger catalyst.", "commentType": "critique"},
        )
        audit = client.get(f"/packets/{packet_id}/audit").json()
        assert any(e["eventType"] == "comment.added" for e in audit)

    def test_comment_on_missing_packet_returns_404(self) -> None:
        r = client.post("/packets/no-such-packet/comments", json={"authorId": "u", "content": "hello"})
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# Phase 4 — approval flows
# ---------------------------------------------------------------------------

class TestPhase4ApprovalFlows:
    def test_approval_lifecycle(self) -> None:
        packet_id = "p4-approval"
        client.post("/packets", json=_minimal_packet(packet_id))

        r = client.post(
            f"/packets/{packet_id}/approval",
            json={"reviewerId": "pm-david", "decision": "approved", "note": "Thesis is well-supported."},
        )
        assert r.status_code == 200
        apv = r.json()
        assert apv["id"].startswith("apv-")
        assert apv["decision"] == "approved"
        assert apv["reviewerId"] == "pm-david"

        get = client.get(f"/packets/{packet_id}/approval")
        assert get.status_code == 200
        assert get.json()["decision"] == "approved"

    def test_approval_audited_on_packet(self) -> None:
        packet_id = "p4-approval-audit"
        client.post("/packets", json=_minimal_packet(packet_id))
        client.post(
            f"/packets/{packet_id}/approval",
            json={"reviewerId": "pm-eve", "decision": "needs_revision", "note": "Needs stronger disconfirming test."},
        )
        audit = client.get(f"/packets/{packet_id}/audit").json()
        assert any(e["eventType"] == "approval.recorded" for e in audit)

    def test_approval_overwrite_replaces_previous(self) -> None:
        packet_id = "p4-approval-overwrite"
        client.post("/packets", json=_minimal_packet(packet_id))
        client.post(f"/packets/{packet_id}/approval", json={"reviewerId": "pm-a", "decision": "rejected", "note": ""})
        client.post(f"/packets/{packet_id}/approval", json={"reviewerId": "pm-b", "decision": "approved", "note": "revised"})
        assert client.get(f"/packets/{packet_id}/approval").json()["decision"] == "approved"

    def test_approval_404_before_any_recorded(self) -> None:
        packet_id = "p4-no-approval"
        client.post("/packets", json=_minimal_packet(packet_id))
        assert client.get(f"/packets/{packet_id}/approval").status_code == 404


# ---------------------------------------------------------------------------
# Phase 5 — workflow templates
# ---------------------------------------------------------------------------

class TestPhase5WorkflowTemplates:
    def _create_template(self, name: str = "Momentum Review Template") -> dict:
        return client.post(
            "/workflows/templates",
            json={
                "name": name,
                "version": "1.0.0",
                "description": "Standard momentum equity review workflow",
                "category": "momentum_scan",
                "authorId": "analyst-alice",
                "steps": [
                    {"stepId": "s1", "name": "Scan candidates", "action": "scanner.run", "params": {"signalFilter": "momentum"}, "humanGate": False},
                    {"stepId": "s2", "name": "Review top candidates", "action": "review.create", "params": {}, "humanGate": True},
                    {"stepId": "s3", "name": "Evaluate risk", "action": "risk.evaluate", "params": {}, "humanGate": False},
                    {"stepId": "s4", "name": "PM decision", "action": "decision.record", "params": {}, "humanGate": True},
                ],
            },
        ).json()

    def test_template_create_and_get(self) -> None:
        t = self._create_template("Momentum Review Template A")
        assert t["id"].startswith("wft-")
        assert t["status"] == "draft"
        assert len(t["steps"]) == 4
        assert t["publishedAt"] is None

        get = client.get(f"/workflows/templates/{t['id']}")
        assert get.status_code == 200
        assert get.json()["name"] == "Momentum Review Template A"

    def test_template_publish_lifecycle(self) -> None:
        t = self._create_template("Equity Review Template B")
        assert t["status"] == "draft"

        pub = client.post(f"/workflows/templates/{t['id']}/publish")
        assert pub.status_code == 200
        pt = pub.json()
        assert pt["status"] == "published"
        assert pt["publishedAt"] is not None

    def test_template_archive_lifecycle(self) -> None:
        t = self._create_template("Risk Assessment Template C")
        client.post(f"/workflows/templates/{t['id']}/publish")
        arc = client.post(f"/workflows/templates/{t['id']}/archive")
        assert arc.status_code == 200
        assert arc.json()["status"] == "archived"

    def test_template_list_filter_by_status(self) -> None:
        t = self._create_template("Draft Template D")
        client.post(f"/workflows/templates/{t['id']}/publish")
        published = client.get("/workflows/templates", params={"status": "published"}).json()
        assert all(tmpl["status"] == "published" for tmpl in published)

        drafts = client.get("/workflows/templates", params={"status": "draft"}).json()
        assert all(tmpl["status"] == "draft" for tmpl in drafts)

    def test_template_steps_preserve_human_gates(self) -> None:
        t = self._create_template("Gated Workflow Template E")
        steps = t["steps"]
        human_gated = [s for s in steps if s["humanGate"]]
        assert len(human_gated) == 2  # s2 and s4

    def test_template_404_for_missing_id(self) -> None:
        assert client.get("/workflows/templates/no-such-template").status_code == 404
