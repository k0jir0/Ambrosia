from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_root_test_scripts_expose_stack_unit_entrypoint() -> None:
    package_json = json.loads(_read("package.json"))
    scripts = package_json["scripts"]

    assert scripts["test:api"] == "cd services/api && uv run --frozen pytest"
    assert scripts["test:mobile"] == "pnpm --filter @ambrosia/mobile test"
    assert scripts["typecheck:mobile"] == "pnpm --filter @ambrosia/mobile typecheck"
    assert scripts["build:web"] == "pnpm --filter @ambrosia/web build"
    assert scripts["test:unit"] == "uv run --project services/api --frozen pytest tests/unit-tests -q"


def test_fastapi_routes_wire_review_scanner_and_mobile_surfaces() -> None:
    main_py = _read("services/api/app/main.py")

    assert "app.include_router(mobile_router)" in main_py
    assert '@app.post("/reviews", response_model=TradeReview)' in main_py
    assert '@app.patch("/reviews/{review_id}/decision", response_model=TradeReview)' in main_py
    assert '@app.post("/scanner/run", response_model=ScannerResult)' in main_py
    assert "return run_scanner(body)" in main_py


def test_web_and_mobile_clients_share_review_and_signal_decision_contracts() -> None:
    web_api = _read("apps/web/src/lib/api.ts")
    mobile_api = _read("apps/mobile/src/api.ts")

    for expected in [
        "createReview",
        "recordDecision",
        "writebackSignalDecision",
        "/reviews",
        "/signals/${encodeURIComponent(signalId)}/writeback-decision",
    ]:
        assert expected in web_api

    for expected in [
        "buildReviewCreatePayload",
        "buildReviewInputFromScannerCandidate",
        "createReview",
        "getReviewSummary",
        "recordReviewDecision",
        "writebackSignalDecision",
        "promoteScannerCandidate",
    ]:
        assert expected in mobile_api

    assert "sourcePointer: `scanner:${candidate.ticker}:${candidate.signal}:${candidate.scannedAt}`" in mobile_api
    assert 'decisionAction: decisionState === "pursue" ? "HOLD" : "BLOCK"' in mobile_api


def test_mobile_control_plane_schema_preserves_governance_and_route_contract() -> None:
    schema = json.loads(_read("packages/schemas/mobile-control-plane.v1.json"))

    assert schema["properties"]["schemaVersion"]["const"] == "mobile-control-plane.v1"
    governance_required = set(schema["properties"]["governance"]["required"])
    route_required = set(schema["properties"]["routes"]["items"]["required"])

    assert {
        "backendSystemOfRecord",
        "humanDecisionAuthority",
        "llmInLiveOrderLoop",
        "finalDecisionsRequireServerConfirmation",
    }.issubset(governance_required)
    assert {
        "method",
        "path",
        "mobileModule",
        "clientFunction",
        "sourceOfTruth",
        "mutating",
        "requiresServerConfirmation",
    }.issubset(route_required)
    assert schema["properties"]["routes"]["items"]["properties"]["sourceOfTruth"]["enum"] == ["fastapi"]
