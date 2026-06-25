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

FIXTURES_PATH = Path(__file__).with_name("retrieval_fixtures.json")
BASELINE_PATH = Path(__file__).with_name("retrieval_baseline.json")

DEFAULT_THRESHOLDS = {
    "retrievalRecallRate": 0.9,
    "avgResultsDropPct": 0.25,
    "avgTopScoreDropPct": 0.30,
}


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def build_packet_payload(packet_id: str, ticker: str, asset_class: str, time_horizon: str, source_title: str, source_type: str) -> dict:
    return {
        "id": packet_id,
        "title": f"Retrieval benchmark packet: {ticker}",
        "thesis": f"{ticker} benchmark retrieval packet",
        "ticker": ticker,
        "assetClass": asset_class,
        "timeHorizon": time_horizon,
        "intendedExpression": "Benchmark",
        "status": "synthesis",
        "decisionState": "watch",
        "confidence": 70,
        "trialCountImpact": 1,
        "followUpDate": "2026-07-15",
        "createdAt": "2026-06-25T10:00:00Z",
        "claims": [
            {
                "id": "claim-1",
                "kind": "sourced",
                "text": "Benchmark claim",
                "evidence": "benchmark evidence",
                "confidence": 75,
            }
        ],
        "strongestCritique": "Benchmark critique",
        "disconfirmingTest": "Benchmark disconfirming test",
        "historicalAnalogue": {
            "title": "Benchmark analogue",
            "similarity": "similar",
            "differences": "different",
            "resolution": "risk constraints",
        },
        "validation": {
            "status": "specified",
            "hypothesis": "Benchmark hypothesis",
            "nullHypothesis": "Benchmark null",
            "dataRequirements": ["daily returns"],
            "protocol": "benchmark protocol",
            "refusalReason": None,
        },
        "tradeability": [
            {
                "topic": "liquidity",
                "question": "Can this be executed with low slippage?",
                "severity": "low",
            }
        ],
        "sources": [
            {
                "id": "src-benchmark-1",
                "title": source_title,
                "sourceType": source_type,
                "timestamp": "2026-06-25T09:00:00Z",
                "permission": "user_owned",
                "relevance": 0.9,
            }
        ],
        "audit": [
            {
                "id": "audit-1",
                "timestamp": "10:00:00",
                "eventType": "packet.created",
                "detail": "Retrieval benchmark packet created",
            }
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run retrieval benchmark and drift checks.")
    parser.add_argument(
        "--fixtures",
        default=str(FIXTURES_PATH),
        help="Path to retrieval fixture JSON",
    )
    parser.add_argument(
        "--baseline",
        default=str(BASELINE_PATH),
        help="Path to retrieval baseline JSON",
    )
    parser.add_argument(
        "--output-json",
        default=str(ROOT / "artifacts" / "retrieval-benchmark.json"),
        help="Path for benchmark JSON artifact",
    )
    parser.add_argument(
        "--output-md",
        default=str(ROOT / "artifacts" / "retrieval-benchmark.md"),
        help="Path for benchmark markdown artifact",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Update baseline file from current benchmark run",
    )
    return parser.parse_args()


def run_case(client: TestClient, case: dict, case_index: int) -> dict:
    origin_review = client.post("/reviews", json=case["originReview"]).json()
    related_review_ids: list[str] = []
    for review in case.get("relatedReviews", []):
        related_review = client.post("/reviews", json=review).json()
        related_review_ids.append(related_review["id"])

    packet_cfg = case["packet"]
    packet_payload = build_packet_payload(
        packet_id=f"pkt-{origin_review['id']}",
        ticker=packet_cfg["ticker"],
        asset_class=packet_cfg["assetClass"],
        time_horizon=packet_cfg["timeHorizon"],
        source_title=packet_cfg["sourceTitle"],
        source_type=packet_cfg["sourceType"],
    )
    create_packet_response = client.post("/packets", json=packet_payload)
    if create_packet_response.status_code != 200:
        raise RuntimeError(f"{case['id']}: packet creation failed")

    retrieval_response = client.post(
        f"/packets/{packet_payload['id']}/retrieve",
        json={"query": case["query"], "topK": case.get("topK", 5)},
    )
    if retrieval_response.status_code != 200:
        raise RuntimeError(f"{case['id']}: retrieval endpoint failed")

    payload = retrieval_response.json()
    results = payload["results"]
    kinds = {row["kind"] for row in results}
    ids = {row["id"] for row in results}

    expect = case["expect"]
    checks: list[tuple[bool, str]] = []
    checks.append((len(results) >= expect.get("minResults", 1), "minimum result count"))
    for kind in expect.get("requiredKinds", []):
        checks.append((kind in kinds, f"required hit kind {kind}"))

    if expect.get("requireRelatedReviewMatch"):
        checks.append((all(review_id in ids for review_id in related_review_ids), "related review present in hits"))

    case_passed = all(ok for ok, _ in checks)
    failures = [detail for ok, detail in checks if not ok]

    top_score = max((float(row.get("score", 0.0)) for row in results), default=0.0)
    return {
        "id": case["id"],
        "passed": case_passed,
        "results": len(results),
        "topScore": round(top_score, 4),
        "kinds": sorted(kinds),
        "failures": failures,
        "query": case["query"],
        "index": case_index,
    }


def drift_check(metrics: dict[str, float], baseline: dict[str, object]) -> list[str]:
    baseline_metrics = baseline["metrics"]
    thresholds = baseline.get("thresholds", DEFAULT_THRESHOLDS)
    errors: list[str] = []

    if metrics["retrievalRecallRate"] < float(thresholds["retrievalRecallRate"]):
        errors.append(
            f"retrievalRecallRate {metrics['retrievalRecallRate']:.4f} below threshold {float(thresholds['retrievalRecallRate']):.4f}"
        )

    baseline_avg_results = float(baseline_metrics["avgResults"])
    min_avg_results = baseline_avg_results * (1.0 - float(thresholds["avgResultsDropPct"]))
    if metrics["avgResults"] < min_avg_results:
        errors.append(
            f"avgResults {metrics['avgResults']:.4f} below allowed floor {min_avg_results:.4f}"
        )

    baseline_avg_top_score = float(baseline_metrics["avgTopScore"])
    min_avg_top_score = baseline_avg_top_score * (1.0 - float(thresholds["avgTopScoreDropPct"]))
    if metrics["avgTopScore"] < min_avg_top_score:
        errors.append(
            f"avgTopScore {metrics['avgTopScore']:.4f} below allowed floor {min_avg_top_score:.4f}"
        )

    return errors


def markdown_report(report: dict[str, object]) -> str:
    lines: list[str] = []
    lines.append("# Retrieval Benchmark Report")
    lines.append("")
    lines.append(f"Generated: {report['generatedAt']}")
    lines.append(f"Fixtures: {report['summary']['totalCases']}")
    lines.append(f"Passes: {report['summary']['passedCases']}")
    lines.append("")
    lines.append("## Aggregate Metrics")
    lines.append("")
    metrics = report["metrics"]
    lines.append(f"- retrievalRecallRate: {metrics['retrievalRecallRate']:.4f}")
    lines.append(f"- avgResults: {metrics['avgResults']:.4f}")
    lines.append(f"- avgTopScore: {metrics['avgTopScore']:.4f}")
    lines.append("")
    lines.append("## Case Results")
    lines.append("")
    lines.append("| Case | Passed | Results | Top Score | Kinds | Failures |")
    lines.append("| --- | --- | ---: | ---: | --- | --- |")
    for case in report["cases"]:
        failures = "; ".join(case["failures"]) if case["failures"] else "-"
        lines.append(
            f"| {case['id']} | {'PASS' if case['passed'] else 'FAIL'} | {case['results']} | {case['topScore']} | {', '.join(case['kinds'])} | {failures} |"
        )

    lines.append("")
    if report["driftErrors"]:
        lines.append("## Drift Check")
        lines.append("")
        for err in report["driftErrors"]:
            lines.append(f"- FAIL: {err}")
    else:
        lines.append("## Drift Check")
        lines.append("")
        lines.append("- PASS: Metrics within allowed drift thresholds")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    fixtures = load_json(Path(args.fixtures))
    if not isinstance(fixtures, list) or not fixtures:
        print("retrieval fixtures must be a non-empty JSON array")
        return 2

    client = TestClient(app)
    case_results = [run_case(client, case, idx) for idx, case in enumerate(fixtures, start=1)]

    passed_cases = sum(1 for row in case_results if row["passed"])
    metrics = {
        "retrievalRecallRate": passed_cases / len(case_results),
        "avgResults": mean([float(row["results"]) for row in case_results]),
        "avgTopScore": mean([float(row["topScore"]) for row in case_results]),
    }

    baseline_path = Path(args.baseline)
    baseline: dict[str, object]
    if args.update_baseline or not baseline_path.exists():
        baseline = {
            "version": 1,
            "generatedAt": datetime.now(UTC).isoformat(),
            "metrics": {
                "retrievalRecallRate": round(metrics["retrievalRecallRate"], 4),
                "avgResults": round(metrics["avgResults"], 4),
                "avgTopScore": round(metrics["avgTopScore"], 4),
            },
            "thresholds": DEFAULT_THRESHOLDS,
        }
        baseline_path.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
        print(f"Updated baseline: {baseline_path}")
    else:
        baseline_obj = load_json(baseline_path)
        if not isinstance(baseline_obj, dict):
            print("baseline file must be a JSON object")
            return 2
        baseline = baseline_obj

    drift_errors = drift_check(metrics, baseline)

    report = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "summary": {
            "totalCases": len(case_results),
            "passedCases": passed_cases,
            "failedCases": len(case_results) - passed_cases,
        },
        "metrics": {
            "retrievalRecallRate": round(metrics["retrievalRecallRate"], 4),
            "avgResults": round(metrics["avgResults"], 4),
            "avgTopScore": round(metrics["avgTopScore"], 4),
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
    output_md.write_text(markdown_report(report), encoding="utf-8")

    print(f"Wrote {output_json}")
    print(f"Wrote {output_md}")
    if drift_errors:
        for err in drift_errors:
            print(f"- drift failure: {err}")
        return 1

    print("Retrieval benchmark passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
