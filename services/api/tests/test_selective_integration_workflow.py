from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import DecisionPacket
from app.selective_integration import create_decision_memory_record, verify_audit_chain
from app.store import ReviewStore, store


client = TestClient(app)
ROOT = Path(__file__).resolve().parents[3]
FIXTURE = json.loads(
    (ROOT / "packages" / "schemas" / "fixtures" / "packet-selective.fixture.json").read_text(
        encoding="utf-8"
    )
)


def _packet_payload(*, with_risk: bool) -> dict:
    payload = deepcopy(FIXTURE)
    payload["id"] = f"packet-selective-{uuid4().hex[:10]}"
    if with_risk:
        payload["riskMonitor"] = {
            "activePositionSize": 0.05,
            "concentrationRisk": "low",
            "correlationOverlap": [],
            "varAtRisk": 0.02,
            "maxDrawdownThreshold": 0.10,
            "followUpTriggers": [],
            "status": "safe",
        }
    return payload


def test_enforced_packet_lifecycle_is_idempotent_and_auditable() -> None:
    payload = _packet_payload(with_risk=True)
    packet_id = payload["id"]
    created = client.post("/packets", json=payload)
    assert created.status_code == 200

    integrated = client.post(f"/packets/{packet_id}/selective-integrate")
    assert integrated.status_code == 200
    body = integrated.json()
    assert body["disconfirmationResult"]["status"] == "pass"
    assert body["riskGateResult"]["status"] == "pass"
    assert body["integrationStatus"]["state"] == "promotable"
    assert len(body["memoryRecords"]) == 1

    repeated = client.post(f"/packets/{packet_id}/selective-integrate")
    assert repeated.status_code == 200
    assert len(repeated.json()["memoryRecords"]) == 1

    decided = client.post(
        f"/packets/{packet_id}/decision",
        json={
            "decision_state": "watch",
            "rationale": "Human reviewer accepts the governed packet for observation.",
            "actor": "workflow-test",
        },
    )
    assert decided.status_code == 200
    assert decided.json()["integrationStatus"]["state"] == "decided"

    resolved = client.post(
        f"/packets/{packet_id}/memory/resolve",
        json={
            "outcome": "outperformed",
            "observedAt": "2026-08-30T20:00:00Z",
            "score": 82,
            "notes": "Forward observation window completed.",
            "evidenceReferences": ["source-1"],
            "actor": "workflow-test",
        },
    )
    assert resolved.status_code == 200
    assert resolved.json()["integrationStatus"]["state"] == "resolved"

    memory_response = client.get(f"/packets/{packet_id}/memory")
    assert memory_response.status_code == 200
    memory = memory_response.json()
    assert len(memory) == 2
    assert verify_audit_chain(memory, packet_id)

    audit_response = client.get(f"/packets/{packet_id}/audit-chain/verify")
    assert audit_response.status_code == 200
    assert audit_response.json()["valid"] is True
    assert audit_response.json()["eventCount"] >= 4
    decision_event = next(
        event
        for event in store._packet_audit_chains[packet_id]
        if event.eventType == "decision.recorded"
    )
    assert decision_event.actor == "local-developer"

    removed_tail = store._packet_audit_chains[packet_id].pop()
    truncated = client.get(f"/packets/{packet_id}/audit-chain/verify")
    assert truncated.status_code == 200
    assert truncated.json()["valid"] is False
    store._packet_audit_chains[packet_id].append(removed_tail)


def test_missing_risk_data_blocks_packet_promotion() -> None:
    payload = _packet_payload(with_risk=False)
    packet_id = payload["id"]
    assert client.post("/packets", json=payload).status_code == 200

    integrated = client.post(f"/packets/{packet_id}/selective-integrate")
    assert integrated.status_code == 200
    body = integrated.json()
    assert body["riskGateResult"]["status"] == "insufficient_data"
    assert body["integrationStatus"]["state"] == "blocked"

    decision = client.post(
        f"/packets/{packet_id}/decision",
        json={"decision_state": "watch", "rationale": "Attempted bypass"},
    )
    assert decision.status_code == 409
    assert decision.json()["detail"]["code"] == "packet_not_promotable"


def test_legacy_outcome_route_resolves_governed_memory() -> None:
    payload = _packet_payload(with_risk=True)
    packet_id = payload["id"]
    assert client.post("/packets", json=payload).status_code == 200
    assert client.post(f"/packets/{packet_id}/selective-integrate").status_code == 200
    assert client.post(
        f"/packets/{packet_id}/decision",
        json={"decision_state": "watch", "rationale": "Compatibility outcome fixture"},
    ).status_code == 200

    response = client.post(
        f"/packets/{packet_id}/outcome",
        json={
            "outcome": "won",
            "outcome_date": "2026-08-30",
            "pnl": 0.04,
            "notes": "Forward compatibility observation.",
        },
    )
    assert response.status_code == 200
    assert response.json()["integrationStatus"]["state"] == "resolved"
    assert len(client.get(f"/packets/{packet_id}/memory").json()) == 2
    assert client.get(f"/packets/{packet_id}/audit-chain/verify").json()["valid"] is True


def test_stage_order_and_input_invalidation_are_enforced() -> None:
    payload = _packet_payload(with_risk=True)
    packet_id = payload["id"]
    assert client.post("/packets", json=payload).status_code == 200

    early = client.post(f"/packets/{packet_id}/disconfirmation/run")
    assert early.status_code == 409

    provenance = client.post(f"/packets/{packet_id}/provenance/refresh")
    assert provenance.status_code == 200
    assert provenance.json()["integrationStatus"]["state"] == "evidence_ready"

    disconfirmation = client.post(f"/packets/{packet_id}/disconfirmation/run")
    assert disconfirmation.status_code == 200
    assert disconfirmation.json()["integrationStatus"]["state"] == "risk_pending"

    risk = client.post(f"/packets/{packet_id}/risk-gate/run")
    assert risk.status_code == 200
    assert risk.json()["integrationStatus"]["state"] == "promotable"

    changed = client.post(
        f"/packets/{packet_id}/risk/evaluate",
        json={"activePositionSize": 0.04, "maxDrawdownThreshold": 0.10},
    )
    assert changed.status_code == 200
    changed_body = changed.json()
    assert changed_body["packetVersion"] == risk.json()["packetVersion"] + 1
    assert changed_body["disconfirmationResult"] is None
    assert changed_body["riskGateResult"] is None
    assert changed_body["integrationStatus"]["state"] == "not_started"


def test_packet_schema_fixture_matches_canonical_backend_contract() -> None:
    payload = _packet_payload(with_risk=False)
    response = client.post("/packets", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["schemaVersion"] == "packet.v1"
    assert body["contractVersion"] == "selective-integration.v1"
    assert body["packetVersion"] == 1
    assert body["integrationStatus"]["state"] == "not_started"

    schema = json.loads((ROOT / "packages" / "schemas" / "packet.v1.json").read_text(encoding="utf-8"))
    missing = [field for field in schema["required"] if field not in body]
    assert missing == []


def test_feature_flags_disable_stages_and_enforce_legacy_write_boundaries(monkeypatch) -> None:
    payload = _packet_payload(with_risk=True)
    packet_id = payload["id"]
    assert client.post("/packets", json=payload).status_code == 200

    monkeypatch.setenv("SELECTIVE_INTEGRATION_ENABLED", "false")
    disabled = client.post(f"/packets/{packet_id}/selective-integrate")
    assert disabled.status_code == 503

    monkeypatch.setenv("SELECTIVE_INTEGRATION_ENABLED", "true")
    review = client.post(
        "/reviews",
        json={"thesis": "Governed review writeback requires its packet", "ticker": "SPY"},
    ).json()
    monkeypatch.setenv("SELECTIVE_INTEGRATION_ENFORCED", "true")
    blocked = client.patch(
        f"/reviews/{review['id']}/decision",
        json={"decision_state": "watch"},
    )
    assert blocked.status_code == 409


def test_chain_conflict_fails_closed_without_disabling_database(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    isolated_store = ReviewStore()
    packet = DecisionPacket.model_validate(_packet_payload(with_risk=True))
    memory = create_decision_memory_record(packet, outcome="integration_promotable")

    class ConflictingPacketStore:
        def commit_selective_integration(self, *args, **kwargs):
            raise ValueError("decision memory hash-chain position is stale")

    isolated_store._packet_db = ConflictingPacketStore()
    isolated_store._db_enabled = True

    with pytest.raises(ValueError, match="hash-chain position is stale"):
        isolated_store.commit_selective_integration(
            packet,
            memory,
            event_type="selective.integration.applied",
            detail="conflict fixture",
        )

    assert isolated_store._db_enabled is True
