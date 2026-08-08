import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from app import index84_platform
from app.main import app
from app.operations import Principal
from app.research_lifecycle import MemoryLifecycleRepository


client = TestClient(app)


@pytest.fixture
def tenant_lifecycle(monkeypatch: pytest.MonkeyPatch):
    repository = MemoryLifecycleRepository()
    current = {"organization_id": "organization-a"}

    def principal() -> Principal:
        return Principal(
            subject="analyst-146",
            role="analyst",
            team="research",
            auth_method="test",
            organization_id=current["organization_id"],
        )

    monkeypatch.setattr(index84_platform, "_lifecycle_repository", lambda: repository)
    monkeypatch.setattr(index84_platform, "current_principal", principal)
    monkeypatch.setenv("ALPHA_LAB_READ_ENABLED", "true")
    monkeypatch.setenv("SIGNALS_LAB_READ_ENABLED", "true")
    monkeypatch.setenv("ALPHA_LAB_WRITES_ENABLED", "true")
    monkeypatch.setenv("SIGNALS_LAB_WRITES_ENABLED", "true")
    return repository, current


def _create_signal(signal_id: str, formula: str = "close / sma(close, 20)") -> dict:
    response = client.post(
        "/signals",
        json={
            "signalId": signal_id,
            "name": f"Signal {signal_id}",
            "formula": formula,
            "benchmark": "SPY",
            "costModel": "10 bps round-trip",
            "universe": ["AAPL"],
        },
    )
    assert response.status_code == 201
    return response.json()


def test_reference_is_server_derived_hashed_and_immutable(tenant_lifecycle) -> None:
    repository, _ = tenant_lifecycle
    _create_signal("shared-signal")

    response = client.post(
        "/reviews/review-146/research-object-references",
        json={
            "objectId": "shared-signal",
            "versionId": "current",
            "objectType": "signal",
            "relationshipType": "challenges",
        },
    )
    assert response.status_code == 201
    reference = response.json()["reference"]
    canonical = json.dumps(reference["snapshot"], sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    assert reference["contentHash"] == hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert reference["organizationId"] == "organization-a"
    assert reference["actor"] == "analyst-146"
    assert reference["versionId"] == 1

    version_response = client.post(
        "/signals/shared-signal/versions",
        json={"formula": "close / sma(close, 50)"},
    )
    assert version_response.status_code == 201

    historical = client.get("/reviews/review-146/research-object-references").json()["references"][0]
    assert historical["snapshot"]["formula"] == "close / sma(close, 20)"
    assert historical["contentHash"] == reference["contentHash"]
    assert historical["driftStatus"] == "superseded"
    state = repository.load("organization-a")
    assert len(state["researchAttachmentEvents"]) == 1


def test_foreign_object_is_non_disclosing_and_browser_cannot_supply_authority(tenant_lifecycle) -> None:
    _, current = tenant_lifecycle
    _create_signal("overlapping-id", "tenant a formula")
    current["organization_id"] = "organization-b"

    assert client.get("/signals/overlapping-id").status_code == 404
    foreign_attach = client.post(
        "/reviews/review-b/research-object-references",
        json={
            "objectId": "overlapping-id",
            "versionId": 1,
            "objectType": "signal",
            "relationshipType": "supports",
        },
    )
    assert foreign_attach.status_code == 404
    assert foreign_attach.json()["detail"] == "Signal not found"

    forged = client.post(
        "/reviews/review-b/research-object-references",
        json={
            "objectId": "overlapping-id",
            "versionId": 1,
            "objectType": "signal",
            "relationshipType": "supports",
            "organizationId": "organization-a",
            "actor": "forged",
        },
    )
    assert forged.status_code == 422


def test_bounded_reads_and_read_switches_are_independent(tenant_lifecycle, monkeypatch: pytest.MonkeyPatch) -> None:
    for suffix in ("a", "b", "c"):
        _create_signal(f"page-{suffix}")

    first = client.get("/signals/read?limit=2")
    assert first.status_code == 200
    first_page = first.json()
    assert len(first_page["items"]) == 2
    assert first_page["nextCursor"]
    second = client.get(f"/signals/read?limit=2&cursor={first_page['nextCursor']}")
    assert second.status_code == 200
    assert len(second.json()["items"]) >= 1

    monkeypatch.setenv("SIGNALS_LAB_WRITES_ENABLED", "false")
    monkeypatch.setenv("SIGNALS_VALIDATION_ENABLED", "false")
    assert client.get("/signals/read?limit=1").status_code == 200
    assert client.post("/signals", json={"name": "blocked", "formula": "x"}).status_code == 503
    assert client.post("/signals/page-a/validate", json={}).status_code == 503

    monkeypatch.setenv("SIGNALS_LAB_READ_ENABLED", "false")
    assert client.get("/signals/read?limit=1").status_code == 503