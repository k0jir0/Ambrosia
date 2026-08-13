from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "packages" / "cli"))
sys.path.insert(0, str(ROOT / "packages" / "sdk-python"))

from ambrosia_cli.main import build_parser, dispatch, get_command_catalog, main  # noqa: E402
from ambrosia_sdk import (  # noqa: E402
    AmbrosiaClient,
    SignalCreate,
    SignalDecisionWriteback,
)


def fake_transport(method: str, path: str, body: dict | None, headers: dict[str, str], timeout: float):
    return {
        "method": method,
        "path": path,
        "body": body,
        "headers": headers,
        "timeout": timeout,
    }


def make_client() -> AmbrosiaClient:
    return AmbrosiaClient(base_url="https://api.example.test", token="test-token", transport=fake_transport)


def test_commands_catalog_is_numbered() -> None:
    parser = build_parser()
    args = parser.parse_args(["commands", "list"])
    result = dispatch(args, make_client())

    assert isinstance(result, list)
    assert len(result) > 0
    assert result[0]["index"] == 1
    assert "command" in result[0]


def test_cli_guide_registry_is_parser_derived_and_truthful() -> None:
    catalog = get_command_catalog()

    assert catalog
    assert all(entry["implementationStatus"] == "implemented" for entry in catalog)
    assert all(entry["authority"] in {"read", "write"} for entry in catalog)
    assert all(
        entry["qualificationStatus"] != "qualified" or entry["authority"] == "read"
        for entry in catalog
    )
    assert next(entry for entry in catalog if entry["command"] == "ambrosia scanner run")["authority"] == "write"
    assert next(entry for entry in catalog if entry["command"] == "ambrosia health")["endpoint"] == "/health"


def test_every_command_in_catalog_is_marked_tested() -> None:
    catalog = get_command_catalog()

    assert all(entry["testStatus"] == "tested" for entry in catalog)


def test_no_args_prints_help(capsys) -> None:
    exit_code = main([])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Ambrosia API/CLI decision platform" in captured.out


def test_examples_command_is_discoverable() -> None:
    parser = build_parser()
    args = parser.parse_args(["examples"])
    result = dispatch(args, make_client())

    assert any("ambrosia commands list" in item["command"] for item in result)


def test_status_dispatch_reports_context_and_health() -> None:
    parser = build_parser()
    args = parser.parse_args(["status"])
    context = {
        "profile": "default",
        "configPath": "~/.ambrosia/config.json",
        "apiUrl": "https://api.example.test",
        "apiUrlSource": "flag",
        "tokenConfigured": True,
        "tokenSource": "token-file",
        "timeout": 65.0,
    }
    result = dispatch(args, make_client(), context)

    assert result["status"] == "ok"
    assert result["apiUrl"] == "https://api.example.test"
    assert result["apiUrlSource"] == "flag"
    assert result["tokenConfigured"] is True
    assert result["apiReachable"] is True
    assert result["apiHealth"]["path"] == "/health"


def test_quickstart_dry_run_returns_staging_commands(monkeypatch) -> None:
    monkeypatch.setenv("AMBROSIA_STAGING_API_URL", "https://staging.ambrosia.example/api")
    parser = build_parser()
    args = parser.parse_args(["quickstart", "--target", "staging"])
    result = dispatch(args, make_client())

    assert result["status"] == "ready"
    assert result["target"] == "staging"
    assert result["apiUrl"] == "https://staging.ambrosia.example/api"
    assert result["writeProfile"] is False
    assert "ambrosia status" in result["nextCommands"]


def test_relay_runs_dispatch_path() -> None:
    parser = build_parser()
    args = parser.parse_args(["relay", "runs", "--limit", "25", "--offset", "5"])
    result = dispatch(args, make_client())

    assert result["method"] == "GET"
    assert result["path"] == "/relay/runs?offset=5&limit=25"


def test_signal_writeback_decision_payload() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "signals",
            "writeback-decision",
            "--signal-id",
            "signal-1",
            "--review-id",
            "review-9",
            "--decision-state",
            "pursue",
            "--decision-action",
            "BUY",
            "--decision-quality",
            "D4",
            "--evidence-links",
            "docs/evidence-a,docs/evidence-b",
            "--verifier-status",
            "passed",
            "--review-date",
            "2026-07-06",
        ]
    )
    result = dispatch(args, make_client())

    assert result["method"] == "POST"
    assert result["path"] == "/signals/signal-1/writeback-decision"
    assert result["body"]["reviewId"] == "review-9"
    assert result["body"]["decisionAction"] == "BUY"
    assert result["body"]["decisionQuality"] == "D4"
    assert result["body"]["evidenceLinks"] == ["docs/evidence-a", "docs/evidence-b"]


def test_signal_link_review_payload() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "signals",
            "link-review",
            "--signal-id",
            "signal-1",
            "--review-id",
            "review-9",
            "--hypothesis-id",
            "alpha-1",
            "--signal-version",
            "2",
        ]
    )
    result = dispatch(args, make_client())

    assert result["method"] == "POST"
    assert result["path"] == "/signals/signal-1/link-review"
    assert result["body"] == {"reviewId": "review-9", "hypothesisId": "alpha-1", "signalVersion": 2}


def test_sdk_typed_signal_payloads_dispatch() -> None:
    client = make_client()

    signal_result = client.create_signal(SignalCreate(name="Momentum", formula="close/close_20d-1", universe=["SPY"]))
    decision_result = client.writeback_signal_decision(
        "signal-1",
        SignalDecisionWriteback(review_id="review-1", decision_state="pursue", evidence_links=["docs/evidence"]),
    )

    assert signal_result["body"]["name"] == "Momentum"
    assert signal_result["body"]["universe"] == ["SPY"]
    assert decision_result["body"]["reviewId"] == "review-1"
    assert decision_result["body"]["evidenceLinks"] == ["docs/evidence"]


def test_quality_scorecard_route() -> None:
    parser = build_parser()
    args = parser.parse_args(["signals", "quality-scorecard"])
    result = dispatch(args, make_client())

    assert result["method"] == "GET"
    assert result["path"] == "/signals/quality-scorecard/weekly"


def test_enterprise_service_accounts_list() -> None:
    parser = build_parser()
    args = parser.parse_args(["enterprise", "service-accounts"])
    result = dispatch(args, make_client())

    assert result["method"] == "GET"
    assert result["path"] == "/enterprise/service-accounts"
