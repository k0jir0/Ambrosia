from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from services.api.app import index84_platform as platform
from services.api.app.research_lifecycle import MemoryLifecycleRepository, empty_lifecycle_state


@pytest.fixture(autouse=True)
def isolated_lifecycle(monkeypatch):
    repository = MemoryLifecycleRepository()
    monkeypatch.setattr(platform, "_memory_lifecycle_repository", repository)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("REQUIRE_DATABASE", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    token = platform._lifecycle_context.set(None)
    yield repository
    platform._lifecycle_context.reset(token)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(platform.router)
    return TestClient(app)


def test_memory_repository_persists_copies_and_isolates_duplicate_human_keys() -> None:
    repository = MemoryLifecycleRepository()
    first = empty_lifecycle_state()
    second = empty_lifecycle_state()
    first["signals"]["shared-signal"] = {"signalId": "shared-signal", "name": "Tenant A"}
    second["signals"]["shared-signal"] = {"signalId": "shared-signal", "name": "Tenant B"}

    repository.save("org-a", first)
    repository.save("org-b", second)
    first["signals"]["shared-signal"]["name"] = "mutated caller copy"

    assert repository.load("org-a")["signals"]["shared-signal"]["name"] == "Tenant A"
    assert repository.load("org-b")["signals"]["shared-signal"]["name"] == "Tenant B"


def test_endpoint_state_is_partitioned_by_current_principal(monkeypatch) -> None:
    active = {"principal": SimpleNamespace(organization_id="org-a")}
    monkeypatch.setattr(platform, "current_principal", lambda: active["principal"])
    request = platform.SignalCreateRequest(
        signalId="shared-signal",
        name="Tenant A Signal",
        universe=["SPY"],
        formula="close > moving_average",
    )
    platform.create_signal(request, None)

    active["principal"] = SimpleNamespace(organization_id="org-b")
    platform._lifecycle_context.set(None)
    platform.create_signal(request.model_copy(update={"name": "Tenant B Signal"}), None)

    active["principal"] = SimpleNamespace(organization_id="org-a")
    platform._lifecycle_context.set(None)
    assert platform.get_signal("shared-signal")["name"] == "Tenant A Signal"
    active["principal"] = SimpleNamespace(organization_id="org-b")
    platform._lifecycle_context.set(None)
    assert platform.get_signal("shared-signal")["name"] == "Tenant B Signal"


@pytest.mark.parametrize(
    ("method", "path", "enabled", "disabled"),
    [
        ("get", "/alpha/hypotheses", "ALPHA_LAB_READ_ENABLED", "false"),
        ("post", "/alpha/hypotheses", "ALPHA_LAB_WRITES_ENABLED", "false"),
        ("get", "/signals", "SIGNALS_LAB_READ_ENABLED", "false"),
        ("post", "/signals", "SIGNALS_LAB_WRITES_ENABLED", "false"),
    ],
)
def test_alpha_and_signal_read_write_switches_fail_closed(
    monkeypatch, method: str, path: str, enabled: str, disabled: str
) -> None:
    monkeypatch.setenv(enabled, disabled)
    response = _client().request(method.upper(), path, json={})

    assert response.status_code == 503
    assert enabled in response.json()["detail"]


def test_demo_seed_and_validation_have_independent_switches(monkeypatch) -> None:
    monkeypatch.setenv("SIGNALS_LAB_WRITES_ENABLED", "true")
    monkeypatch.setenv("ALPHA_LAB_DEMO_SEED_ENABLED", "false")
    seed_response = _client().post("/signals/seed-index97")

    monkeypatch.setenv("SIGNALS_VALIDATION_ENABLED", "false")
    validation_response = _client().post(
        "/signals/missing/validate",
        json={},
    )

    assert seed_response.status_code == 503
    assert "ALPHA_LAB_DEMO_SEED_ENABLED" in seed_response.json()["detail"]
    assert validation_response.status_code == 503
    assert "SIGNALS_VALIDATION_ENABLED" in validation_response.json()["detail"]


def test_qualified_lifecycle_write_fails_when_database_is_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("REQUIRE_DATABASE", "true")
    monkeypatch.setenv("SIGNALS_LAB_WRITES_ENABLED", "true")
    monkeypatch.setattr(
        platform,
        "current_principal",
        lambda: SimpleNamespace(organization_id="00000000-0000-0000-0000-000000000111"),
    )

    response = _client().post(
        "/signals",
        json={
            "signalId": "qualified-write",
            "name": "Qualified write",
            "universe": ["SPY"],
            "formula": "close > moving_average",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Tenant lifecycle database is unavailable"


def test_staging_defaults_and_execution_handoff_are_disabled(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "staging")
    for name in (
        "ALPHA_LAB_READ_ENABLED",
        "ALPHA_LAB_WRITES_ENABLED",
        "ALPHA_LAB_DEMO_SEED_ENABLED",
        "SIGNALS_LAB_READ_ENABLED",
        "SIGNALS_LAB_WRITES_ENABLED",
        "SIGNALS_VALIDATION_ENABLED",
        "SIGNALS_EXECUTION_HANDOFF_ENABLED",
    ):
        monkeypatch.delenv(name, raising=False)
        assert platform._env_enabled(name, development_default=True) is False

    request = platform.SignalDecisionWritebackRequest(
        reviewId="review-1",
        decisionState="pursue",
        decisionAction="BUY",
        approvalState="approved",
        executionReadiness="execution_candidate",
    )
    assert platform._resolve_execution_readiness({}, "BUY", request) == "execution_blocked"


def test_repository_write_failure_is_reported_not_swallowed(monkeypatch) -> None:
    class FailingRepository:
        def load(self, organization_id: str) -> dict[str, dict]:
            return empty_lifecycle_state()

        def save(self, organization_id: str, state: dict[str, dict]) -> None:
            raise OSError("database connection lost")

    monkeypatch.setattr(platform, "_lifecycle_repository", FailingRepository)
    monkeypatch.setattr(
        platform,
        "current_principal",
        lambda: SimpleNamespace(organization_id="org-qualified"),
    )
    platform._lifecycle_context.set(None)

    with pytest.raises(HTTPException) as failure:
        platform.create_signal(
            platform.SignalCreateRequest(
                signalId="must-persist",
                name="Must Persist",
                universe=["SPY"],
                formula="close > moving_average",
            ),
            None,
        )

    assert failure.value.status_code == 503
    assert failure.value.detail == "Tenant lifecycle write was not persisted"