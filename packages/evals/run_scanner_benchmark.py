from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "api"))

from app.main import app  # noqa: E402

FIXTURES_PATH = Path(__file__).with_name("scanner_fixtures.json")
BASELINE_PATH = Path(__file__).with_name("scanner_baseline.json")

DEFAULT_THRESHOLDS = {
    "passRate": 1.0,
    "avgCandidatesDropPct": 0.30,
    "avgTopScoreDropPct": 0.25,
    "provenanceRate": 1.0,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run scanner benchmark and drift checks.")
    parser.add_argument("--fixtures", default=str(FIXTURES_PATH), help="Path to scanner fixture JSON")
    parser.add_argument("--baseline", default=str(BASELINE_PATH), help="Path to scanner baseline JSON")
    parser.add_argument(
        "--output-json",
        default=str(ROOT / "artifacts" / "scanner-benchmark.json"),
        help="Path to scanner benchmark JSON artifact",
    )
    parser.add_argument(
        "--output-md",
        default=str(ROOT / "artifacts" / "scanner-benchmark.md"),
        help="Path to scanner benchmark markdown artifact",
    )
    parser.add_argument("--update-baseline", action="store_true", help="Update baseline with current run")
    return parser.parse_args()


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def run_case(client: TestClient, case: dict) -> dict:
    response = client.post("/scanner/run", json=case["request"])
    if response.status_code != 200:
        return {
            "id": case["id"],
            "passed": False,
            "statusCode": response.status_code,
            "candidates": 0,
            "topScore": 0.0,
            "provenanceRate": 0.0,
            "failures": [f"scanner endpoint returned status {response.status_code}"],
        }

    payload = response.json()
    candidates = payload.get("candidates", [])
    expect = case["expect"]
    failures: list[str] = []

    candidate_count = len(candidates)
    if candidate_count < int(expect.get("minCandidates", 0)):
        failures.append(
            f"candidate count {candidate_count} below min {expect.get('minCandidates', 0)}"
        )
    if candidate_count > int(expect.get("maxCandidates", case["request"]["maxCandidates"])):
        failures.append(
            f"candidate count {candidate_count} above max {expect.get('maxCandidates')}"
        )

    allowed_signals = set(expect.get("allowedSignals", []))
    invalid_signals = sorted(
        {candidate.get("signal") for candidate in candidates if candidate.get("signal") not in allowed_signals}
    )
    if invalid_signals:
        failures.append(f"invalid signals for filter: {', '.join(invalid_signals)}")

    requested_universe = case["request"].get("universe") or []
    if requested_universe:
        returned_universe = payload.get("universe", [])
        if len(returned_universe) != len(requested_universe):
            failures.append(
                f"totalScanned mismatch: expected {len(requested_universe)} got {payload.get('totalScanned')}"
            )

    provenance_ok = [
        bool(candidate.get("dataSource")) and candidate.get("dataMode") in {"live", "fallback", "demo"}
        for candidate in candidates
    ]
    provenance_rate = (sum(1 for ok in provenance_ok if ok) / candidate_count) if candidate_count else 1.0
    if provenance_rate < 1.0:
        failures.append("some candidates missing provenance fields")

    top_score = max((float(candidate.get("score", 0.0)) for candidate in candidates), default=0.0)

    return {
        "id": case["id"],
        "passed": len(failures) == 0,
        "statusCode": 200,
        "candidates": candidate_count,
        "topScore": round(top_score, 4),
        "provenanceRate": round(provenance_rate, 4),
        "dataMode": payload.get("dataMode"),
        "failures": failures,
    }


def drift_check(metrics: dict[str, float], baseline: dict[str, object]) -> list[str]:
    thresholds = baseline.get("thresholds", DEFAULT_THRESHOLDS)
    baseline_metrics = baseline["metrics"]
    errors: list[str] = []

    if metrics["passRate"] < float(thresholds["passRate"]):
        errors.append(
            f"passRate {metrics['passRate']:.4f} below threshold {float(thresholds['passRate']):.4f}"
        )

    if metrics["provenanceRate"] < float(thresholds["provenanceRate"]):
        errors.append(
            f"provenanceRate {metrics['provenanceRate']:.4f} below threshold {float(thresholds['provenanceRate']):.4f}"
        )

    baseline_avg_candidates = float(baseline_metrics["avgCandidates"])
    min_avg_candidates = baseline_avg_candidates * (1.0 - float(thresholds["avgCandidatesDropPct"]))
    if metrics["avgCandidates"] < min_avg_candidates:
        errors.append(
            f"avgCandidates {metrics['avgCandidates']:.4f} below allowed floor {min_avg_candidates:.4f}"
        )

    baseline_avg_top_score = float(baseline_metrics["avgTopScore"])
    min_avg_top_score = baseline_avg_top_score * (1.0 - float(thresholds["avgTopScoreDropPct"]))
    if metrics["avgTopScore"] < min_avg_top_score:
        errors.append(
            f"avgTopScore {metrics['avgTopScore']:.4f} below allowed floor {min_avg_top_score:.4f}"
        )

    return errors


def to_markdown(report: dict[str, object]) -> str:
    lines: list[str] = []
    lines.append("# Scanner Benchmark Report")
    lines.append("")
    lines.append(f"Generated: {report['generatedAt']}")
    lines.append(f"Cases: {report['summary']['totalCases']}")
    lines.append(f"Passes: {report['summary']['passedCases']}")
    lines.append("")
    lines.append("## Aggregate Metrics")
    lines.append("")
    lines.append(f"- passRate: {report['metrics']['passRate']:.4f}")
    lines.append(f"- avgCandidates: {report['metrics']['avgCandidates']:.4f}")
    lines.append(f"- avgTopScore: {report['metrics']['avgTopScore']:.4f}")
    lines.append(f"- provenanceRate: {report['metrics']['provenanceRate']:.4f}")
    lines.append("")
    lines.append("## Case Results")
    lines.append("")
    lines.append("| Case | Passed | Candidates | Top Score | Provenance Rate | Data Mode | Failures |")
    lines.append("| --- | --- | ---: | ---: | ---: | --- | --- |")
    for case in report["cases"]:
        failures = "; ".join(case["failures"]) if case["failures"] else "-"
        lines.append(
            f"| {case['id']} | {'PASS' if case['passed'] else 'FAIL'} | {case['candidates']} | {case['topScore']} | {case['provenanceRate']} | {case.get('dataMode', 'n/a')} | {failures} |"
        )
    lines.append("")
    if report["driftErrors"]:
        lines.append("## Drift Check")
        lines.append("")
        for error in report["driftErrors"]:
            lines.append(f"- FAIL: {error}")
    else:
        lines.append("## Drift Check")
        lines.append("")
        lines.append("- PASS: Metrics within allowed drift thresholds")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()

    fixtures_obj = load_json(Path(args.fixtures))
    if not isinstance(fixtures_obj, list) or not fixtures_obj:
        print("scanner fixtures must be a non-empty JSON array")
        return 2

    client = TestClient(app)
    case_results = [run_case(client, case) for case in fixtures_obj]

    passed_cases = sum(1 for case in case_results if case["passed"])
    metrics = {
        "passRate": passed_cases / len(case_results),
        "avgCandidates": mean([float(case["candidates"]) for case in case_results]),
        "avgTopScore": mean([float(case["topScore"]) for case in case_results]),
        "provenanceRate": mean([float(case["provenanceRate"]) for case in case_results]),
    }

    baseline_path = Path(args.baseline)
    if args.update_baseline or not baseline_path.exists():
        baseline = {
            "version": 1,
            "generatedAt": datetime.now(UTC).isoformat(),
            "metrics": {
                "passRate": round(metrics["passRate"], 4),
                "avgCandidates": round(metrics["avgCandidates"], 4),
                "avgTopScore": round(metrics["avgTopScore"], 4),
                "provenanceRate": round(metrics["provenanceRate"], 4),
            },
            "thresholds": DEFAULT_THRESHOLDS,
        }
        baseline_path.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
        print(f"Updated baseline: {baseline_path}")
    else:
        baseline = load_json(baseline_path)
        if not isinstance(baseline, dict):
            print("scanner baseline must be a JSON object")
            return 2

    drift_errors = drift_check(metrics, baseline)

    report = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "summary": {
            "totalCases": len(case_results),
            "passedCases": passed_cases,
            "failedCases": len(case_results) - passed_cases,
        },
        "metrics": {
            "passRate": round(metrics["passRate"], 4),
            "avgCandidates": round(metrics["avgCandidates"], 4),
            "avgTopScore": round(metrics["avgTopScore"], 4),
            "provenanceRate": round(metrics["provenanceRate"], 4),
        },
        "baseline": baseline,
        "driftErrors": drift_errors,
        "cases": case_results,
    }

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(to_markdown(report), encoding="utf-8")

    print(f"Wrote {output_json}")
    print(f"Wrote {output_md}")

    if drift_errors:
        for error in drift_errors:
            print(f"- drift failure: {error}")
        return 1

    print("Scanner benchmark passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
