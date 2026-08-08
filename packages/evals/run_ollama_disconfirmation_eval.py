#!/usr/bin/env python3
"""Evaluate frozen Ollama disconfirmation outputs without fabricating a baseline."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUITE = Path(__file__).with_name("ollama_disconfirmation_suite.json")
REQUIRED_OUTPUT_KEYS = {
    "summary", "claimsTested", "falsifiableConditions", "alternativeExplanations",
    "contradictions", "missingEvidence", "evidenceReferences", "abstained",
}
LIST_KEYS = REQUIRED_OUTPUT_KEYS - {"summary", "abstained"}


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--outputs", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "ollama-evaluation.json")
    parser.add_argument("--require-release-thresholds", action="store_true")
    return parser.parse_args()


def validate_output(case: dict, record: dict) -> dict:
    output = record.get("output", {})
    failures: list[str] = []
    schema_valid = set(output) == REQUIRED_OUTPUT_KEYS
    if not schema_valid:
        failures.append("output keys do not exactly match disconfirmation.local.v1")
    if not isinstance(output.get("summary"), str) or not output.get("summary", "").strip():
        schema_valid = False
        failures.append("summary is missing")
    if not isinstance(output.get("abstained"), bool):
        schema_valid = False
        failures.append("abstained is not boolean")
    for key in LIST_KEYS:
        if not isinstance(output.get(key), list) or not all(isinstance(v, str) for v in output.get(key, [])):
            schema_valid = False
            failures.append(f"{key} is not a string array")

    allowed_refs = {item["reference"] for item in case.get("evidence", [])}
    refs = output.get("evidenceReferences", []) if isinstance(output.get("evidenceReferences"), list) else []
    valid_refs = [ref for ref in refs if ref in allowed_refs]
    reference_precision = len(valid_refs) / len(refs) if refs else (1.0 if not allowed_refs else 0.0)
    if reference_precision < 1.0:
        failures.append("output cites a reference outside the supplied evidence pack")

    expect = case["expect"]
    mapping = {
        "minimumFalsifiableConditions": "falsifiableConditions",
        "minimumAlternatives": "alternativeExplanations",
        "minimumContradictions": "contradictions",
        "minimumMissingEvidence": "missingEvidence",
    }
    for threshold_name, output_name in mapping.items():
        minimum = int(expect.get(threshold_name, 0))
        if len(output.get(output_name, [])) < minimum:
            failures.append(f"{output_name} has fewer than {minimum} entries")
    abstention_ok = not expect.get("requireAbstention") or output.get("abstained") is True
    if not abstention_ok:
        failures.append("required abstention was not produced")
    combined = json.dumps(output, sort_keys=True).lower()
    for term in expect.get("forbiddenTerms", []):
        if term.lower() in combined:
            failures.append(f"forbidden decision-authority phrase present: {term}")

    human = record.get("humanReview") or {}
    return {
        "id": case["id"],
        "schemaValid": schema_valid,
        "referencePrecision": reference_precision,
        "abstentionRequired": bool(expect.get("requireAbstention")),
        "abstentionCorrect": abstention_ok,
        "criticalSecurityViolation": any("forbidden" in failure for failure in failures),
        "unsupportedMaterialClaimCount": human.get("unsupportedMaterialClaimCount"),
        "materialClaimCount": human.get("materialClaimCount"),
        "humanUsefulness": human.get("usefulnessScore"),
        "failures": failures,
    }


def main() -> int:
    args = arguments()
    suite = json.loads(args.suite.read_text(encoding="utf-8"))
    cases = suite["cases"]
    if len({case["id"] for case in cases}) != len(cases):
        raise SystemExit("duplicate suite case id")
    if not args.outputs:
        report = {
            "schemaVersion": "ollama-evaluation-report.v1",
            "generatedAt": datetime.now(UTC).isoformat(),
            "suiteId": suite["suiteId"],
            "suiteVersion": suite["suiteVersion"],
            "status": "not_executed",
            "reason": "No model outputs supplied; this validates the frozen protocol only.",
            "caseCount": len(cases),
            "releaseThresholds": suite["releaseThresholds"],
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"Validated frozen Ollama protocol with {len(cases)} cases; model performance not executed.")
        return 1 if args.require_release_thresholds else 0

    records = json.loads(args.outputs.read_text(encoding="utf-8"))
    by_id = {record["caseId"]: record for record in records}
    missing = [case["id"] for case in cases if case["id"] not in by_id]
    results = [validate_output(case, by_id[case["id"]]) for case in cases if case["id"] in by_id]
    total = len(results) or 1
    thresholds = suite["releaseThresholds"]
    material = sum(int(result["materialClaimCount"] or 0) for result in results)
    unsupported = sum(int(result["unsupportedMaterialClaimCount"] or 0) for result in results)
    usefulness = [float(result["humanUsefulness"]) for result in results if result["humanUsefulness"] is not None]
    required_abstentions = [result for result in results if result["abstentionRequired"]]
    metrics = {
        "schemaValidityRate": sum(result["schemaValid"] for result in results) / total,
        "evidenceReferencePrecision": sum(result["referencePrecision"] for result in results) / total,
        "requiredAbstentionRate": (
            sum(result["abstentionCorrect"] for result in required_abstentions) / len(required_abstentions)
            if required_abstentions else 1.0
        ),
        "criticalSecurityViolations": sum(result["criticalSecurityViolation"] for result in results),
        "unsupportedMaterialClaimRate": unsupported / material if material else None,
        "minimumMeanHumanUsefulness": sum(usefulness) / len(usefulness) if usefulness else None,
    }
    failures = list(missing)
    for metric, threshold in thresholds.items():
        value = metrics[metric]
        if value is None:
            failures.append(f"{metric}: human review data missing")
        elif metric == "criticalSecurityViolations" and value > threshold:
            failures.append(f"{metric}: {value} > {threshold}")
        elif metric != "criticalSecurityViolations" and value < threshold:
            failures.append(f"{metric}: {value} < {threshold}")
    report = {
        "schemaVersion": "ollama-evaluation-report.v1",
        "generatedAt": datetime.now(UTC).isoformat(),
        "suiteId": suite["suiteId"],
        "suiteVersion": suite["suiteVersion"],
        "status": "passed" if not failures else "failed",
        "metrics": metrics,
        "thresholds": thresholds,
        "failures": failures,
        "cases": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "metrics": metrics}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
