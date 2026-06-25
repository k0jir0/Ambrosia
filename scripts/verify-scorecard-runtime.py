#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "api"))

REQUIRED_METRIC_KEYS = {
    "review_validity",
    "decision_consistency_avg",
    "packet_integrity",
    "data_quality",
    "agent_consensus",
    "backtest_validity",
    "risk_estimate",
    "confidence_calibration",
    "overall_status",
    "computed_at",
}

REQUIRED_SCORECARD_KEYS = {
    "certification_status",
    "overall_status",
    "all_metrics_present",
    "all_metrics_at_target",
    "metrics",
    "gates_passed",
    "computed_at",
}

REQUIRED_GATE_KEYS = {
    "all_metrics_computed",
    "all_metrics_at_target",
    "platform_status_ok",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify calibration metrics and scorecard runtime contracts."
    )
    parser.add_argument(
        "--output-json",
        default=str(ROOT / "artifacts" / "scorecard-runtime.json"),
        help="Path to JSON output artifact",
    )
    parser.add_argument(
        "--output-md",
        default=str(ROOT / "artifacts" / "scorecard-runtime.md"),
        help="Path to markdown output artifact",
    )
    return parser.parse_args()


def to_markdown(report: dict[str, object]) -> str:
    lines: list[str] = []
    lines.append("# Scorecard Runtime Verification")
    lines.append("")
    lines.append(f"Generated: {report['generatedAt']}")
    lines.append(f"Overall: {'PASS' if report['passed'] else 'FAIL'}")
    lines.append("")

    lines.append("## Endpoint Status")
    lines.append("")
    endpoints = report["endpoints"]
    lines.append(f"- /metrics: HTTP {endpoints['metricsStatusCode']}")
    lines.append(f"- /scorecard: HTTP {endpoints['scorecardStatusCode']}")
    lines.append(f"- /health/detailed: HTTP {endpoints['healthDetailedStatusCode']}")
    lines.append("")

    lines.append("## Runtime Snapshot")
    lines.append("")
    runtime = report["runtime"]
    lines.append(f"- metrics.overall_status: {runtime['metricsOverallStatus']}")
    lines.append(f"- scorecard.certification_status: {runtime['scorecardCertificationStatus']}")
    lines.append(f"- scorecard.overall_status: {runtime['scorecardOverallStatus']}")
    lines.append(f"- health.detailed.status: {runtime['healthDetailedStatus']}")
    lines.append(f"- scorecard.metrics_count: {runtime['scorecardMetricsCount']}")
    lines.append("")

    lines.append("## Gate Checks")
    lines.append("")
    for check in report["checks"]:
        lines.append(f"- {'PASS' if check['passed'] else 'FAIL'}: {check['name']} ({check['detail']})")

    if report["errors"]:
        lines.append("")
        lines.append("## Errors")
        lines.append("")
        for error in report["errors"]:
            lines.append(f"- {error}")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()

    from app.main import app  # noqa: PLC0415

    client = TestClient(app)

    errors: list[str] = []
    checks: list[dict[str, object]] = []

    metrics_resp = client.get("/metrics")
    scorecard_resp = client.get("/scorecard")
    health_resp = client.get("/health/detailed")

    checks.append(
        {
            "name": "metrics endpoint status",
            "passed": metrics_resp.status_code == 200,
            "detail": f"expected 200 got {metrics_resp.status_code}",
        }
    )
    checks.append(
        {
            "name": "scorecard endpoint status",
            "passed": scorecard_resp.status_code == 200,
            "detail": f"expected 200 got {scorecard_resp.status_code}",
        }
    )
    checks.append(
        {
            "name": "health/detailed endpoint status",
            "passed": health_resp.status_code == 200,
            "detail": f"expected 200 got {health_resp.status_code}",
        }
    )

    metrics_payload: dict[str, object] = metrics_resp.json() if metrics_resp.status_code == 200 else {}
    scorecard_payload: dict[str, object] = (
        scorecard_resp.json() if scorecard_resp.status_code == 200 else {}
    )
    health_payload: dict[str, object] = health_resp.json() if health_resp.status_code == 200 else {}

    missing_metric_keys = sorted(REQUIRED_METRIC_KEYS.difference(metrics_payload.keys()))
    checks.append(
        {
            "name": "metrics payload contract",
            "passed": not missing_metric_keys,
            "detail": "all required metric keys present"
            if not missing_metric_keys
            else f"missing keys: {', '.join(missing_metric_keys)}",
        }
    )

    missing_scorecard_keys = sorted(REQUIRED_SCORECARD_KEYS.difference(scorecard_payload.keys()))
    checks.append(
        {
            "name": "scorecard payload contract",
            "passed": not missing_scorecard_keys,
            "detail": "all required scorecard keys present"
            if not missing_scorecard_keys
            else f"missing keys: {', '.join(missing_scorecard_keys)}",
        }
    )

    metrics_count = len(scorecard_payload.get("metrics", [])) if scorecard_payload else 0
    checks.append(
        {
            "name": "scorecard includes 8 metric rows",
            "passed": metrics_count == 8,
            "detail": f"expected 8 got {metrics_count}",
        }
    )

    gates = scorecard_payload.get("gates_passed", {}) if scorecard_payload else {}
    missing_gate_keys = sorted(REQUIRED_GATE_KEYS.difference(gates.keys())) if isinstance(gates, dict) else sorted(REQUIRED_GATE_KEYS)
    checks.append(
        {
            "name": "scorecard gate flags present",
            "passed": not missing_gate_keys,
            "detail": "all required gate flags present"
            if not missing_gate_keys
            else f"missing gate flags: {', '.join(missing_gate_keys)}",
        }
    )

    metrics_status = metrics_payload.get("overall_status")
    scorecard_status = scorecard_payload.get("overall_status")
    checks.append(
        {
            "name": "metrics and scorecard status alignment",
            "passed": metrics_status == scorecard_status,
            "detail": f"metrics={metrics_status} scorecard={scorecard_status}",
        }
    )

    certification_status = scorecard_payload.get("certification_status")
    checks.append(
        {
            "name": "scorecard certification enum",
            "passed": certification_status in {"pre-certification", "certified", "revoked"},
            "detail": f"certification_status={certification_status}",
        }
    )

    for check in checks:
        if not bool(check["passed"]):
            errors.append(f"{check['name']}: {check['detail']}")

    report = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "passed": len(errors) == 0,
        "endpoints": {
            "metricsStatusCode": metrics_resp.status_code,
            "scorecardStatusCode": scorecard_resp.status_code,
            "healthDetailedStatusCode": health_resp.status_code,
        },
        "runtime": {
            "metricsOverallStatus": metrics_payload.get("overall_status"),
            "scorecardCertificationStatus": certification_status,
            "scorecardOverallStatus": scorecard_status,
            "healthDetailedStatus": health_payload.get("status"),
            "scorecardMetricsCount": metrics_count,
        },
        "checks": checks,
        "errors": errors,
    }

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)

    output_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(to_markdown(report), encoding="utf-8")

    print(f"Wrote {output_json}")
    print(f"Wrote {output_md}")
    if errors:
        print("Scorecard runtime verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Scorecard runtime verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
