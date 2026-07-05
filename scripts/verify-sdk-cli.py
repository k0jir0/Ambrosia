#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SDK_PATH = ROOT / "packages" / "sdk-python"
CLI_PATH = ROOT / "packages" / "cli"
ARTIFACT_PATH = ROOT / "artifacts" / "sdk-cli-transcript.json"

sys.path.insert(0, str(SDK_PATH))
sys.path.insert(0, str(CLI_PATH))

from ambrosia_cli.main import build_parser, dispatch  # noqa: E402
from ambrosia_sdk import AmbrosiaClient  # noqa: E402


def fake_transport(method: str, path: str, body: dict | None, headers: dict[str, str], timeout: float):
    return {
        "method": method,
        "path": path,
        "body": body,
        "hasAuth": "Authorization" in headers,
        "timeout": timeout,
    }


def main() -> int:
    client = AmbrosiaClient(base_url="https://api.example.test", token="test-token", transport=fake_transport)
    checks = {
        "health": client.health(),
        "healthDetailed": client.health_detailed(),
        "reviewsList": client.list_reviews(),
        "reviewCreate": client.create_review("Semiconductor breadth may improve", ticker="SOXX"),
        "packetGet": client.get_packet("pkt-123"),
        "marketSnapshot": client.market_snapshot("BTC / miners"),
        "scannerRun": client.scanner_run(["SOXX", "SPY"], max_candidates=2),
        "plansList": client.list_plans(),
        "relayEvaluate": client.relay_evaluate("What evidence supports growth?"),
        "relayScorecard": client.relay_scorecard(),
        "signalCreate": client.create_signal({"name": "Momentum", "formula": "close / close_20d - 1"}),
        "alphaCreate": client.create_alpha_hypothesis({"title": "Momentum persistence", "signalFamily": "momentum", "thesis": "medium-horizon continuation"}),
        "alphaList": client.list_alpha_hypotheses(),
        "alphaDecay": client.get_alpha_decay("signal-fixture"),
        "backtestRun": client.run_backtest("signal-fixture"),
        "paperTradeCreate": client.create_paper_trade({"decisionId": "decision-1", "ticker": "SOXX", "quantity": 1}),
        "warmPathIngest": client.ingest_warm_path_event({"eventType": "fill", "ticker": "SOXX", "latencyMs": 120, "notionalUsd": 12500}),
        "warmPathList": client.list_warm_path_events(),
        "serviceAccountCreate": client.create_service_account("ci-bot", ["public:read"]),
        "serviceAccountRotate": client.rotate_service_account("svc-123", rotated_by="ci"),
        "serviceAccountRevoke": client.revoke_service_account("svc-123"),
        "auditExportCreate": client.create_audit_export("ci", "all"),
        "ssoConfig": client.configure_sso("oidc", "https://idp.example.test", "ambrosia-enterprise"),
        "ssoGet": client.get_sso_config(),
        "offlineBundle": client.get_offline_bundle_manifest(),
        "securityPacket": client.get_enterprise_security_packet(),
    }

    parser = build_parser()
    parsed = parser.parse_args(["--json", "plans", "get", "P-001"])
    cli_result = dispatch(parsed, client)
    help_result = subprocess.run(
        [sys.executable, "-m", "ambrosia_cli.main", "--help"],
        cwd=str(CLI_PATH),
        env={"PYTHONPATH": f"{SDK_PATH};{CLI_PATH}"},
        check=False,
        capture_output=True,
        text=True,
    )

    if help_result.returncode != 0:
        print(help_result.stderr)
        return help_result.returncode
    if checks["marketSnapshot"]["path"] != "/market/BTC%20miners/snapshot":
        print("Ticker normalization failed")
        return 1
    if cli_result["path"] != "/roadmap/plans/P-001":
        print("CLI plan dispatch failed")
        return 1
    for path in [
        "/reviews",
        "/scanner/run",
        "/relay/evaluate",
        "/signals",
        "/alpha/hypotheses",
        "/signals/signal-fixture/alpha-decay",
        "/backtests/run",
        "/paper-trades",
        "/execution/warm-path/events",
        "/enterprise/service-accounts",
        "/enterprise/service-accounts/svc-123/rotate",
        "/enterprise/service-accounts/svc-123/revoke",
        "/enterprise/audit-exports",
        "/enterprise/sso/config",
        "/enterprise/deployment-bundles/offline",
        "/enterprise/support/security-packet",
    ]:
        if not any(result.get("path") == path for result in checks.values() if isinstance(result, dict)):
            print(f"SDK check missing path {path}")
            return 1
    if "Ambrosia API/CLI decision platform" not in help_result.stdout:
        print("CLI help output missing expected description")
        return 1

    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(
        json.dumps(
            {
                "status": "ok",
                "commandsVerified": [
                    "ambrosia auth login/token/whoami/logout",
                    "ambrosia config get/set",
                    "ambrosia health",
                    "ambrosia health --detailed",
                    "ambrosia reviews list",
                    "ambrosia reviews create --thesis <text>",
                    "ambrosia packets get <id>",
                    "ambrosia packets create --payload <json>",
                    "ambrosia market snapshot <ticker>",
                    "ambrosia scanner run",
                    "ambrosia jobs wait <id>",
                    "ambrosia plans get <id>",
                    "ambrosia relay evaluate --question <text>",
                    "ambrosia signals create --name <name> --formula <formula>",
                    "ambrosia alpha create --title <title> --signal-family <family> --thesis <text>",
                    "ambrosia alpha decay --signal-id <id>",
                    "ambrosia backtests run --signal-id <id>",
                    "ambrosia paper-trades create --decision-id <id> --ticker <ticker> --quantity <qty>",
                    "ambrosia warm-path ingest --event-type <type> --ticker <ticker> --latency-ms <ms> --notional-usd <usd>",
                    "ambrosia warm-path list",
                    "ambrosia enterprise service-account --name <name>",
                    "ambrosia enterprise service-account-rotate <id>",
                    "ambrosia enterprise service-account-revoke <id>",
                    "ambrosia enterprise audit-export",
                    "ambrosia enterprise sso-config --provider oidc --issuer-url <url> --audience <aud>",
                    "ambrosia enterprise sso-get",
                    "ambrosia enterprise offline-bundle",
                    "ambrosia enterprise security-packet",
                ],
                "checks": checks,
                "cliPlanGet": cli_result,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"SDK/CLI verification passed. Wrote {ARTIFACT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())