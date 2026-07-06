from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "packages" / "cli"))
sys.path.insert(0, str(ROOT / "packages" / "sdk-python"))

from ambrosia_cli.main import build_parser, dispatch
from ambrosia_sdk import AmbrosiaClient


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
    assert result["body"]["decisionQuality"] == "D4"
    assert result["body"]["evidenceLinks"] == ["docs/evidence-a", "docs/evidence-b"]


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
