#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "packages" / "evals" / "financebench" / "open_subset.json"
ARTIFACT_PATH = ROOT / "artifacts" / "financebench-relay-trace.json"


def build_trace(item: dict) -> dict:
    document = item["documents"][0]
    table = document["tables"][0]
    values = {row["metric"]: row["value"] for row in table["rows"]}
    revenue = float(values["Revenue"])
    gross_profit = float(values["Gross profit"])
    gross_margin = gross_profit / revenue
    answer = f"{gross_margin * 100:.1f}%"

    return {
        "schemaVersion": "benchmark-trace.v1",
        "traceId": f"trace-{item['questionId']}",
        "benchmark": "financebench-open-fixture",
        "questionId": item["questionId"],
        "retrievalEvents": [
            {
                "documentId": document["documentId"],
                "title": document["title"],
                "score": 1.0,
                "reason": "Synthetic fixture contains the requested revenue and gross profit rows."
            }
        ],
        "tableExtractions": [
            {
                "tableId": table["tableId"],
                "fields": values
            }
        ],
        "calculations": [
            {
                "name": "gross_margin",
                "formula": "gross_profit / revenue",
                "inputs": {"gross_profit": gross_profit, "revenue": revenue},
                "result": gross_margin,
                "display": answer
            }
        ],
        "verification": {
            "expectedAnswer": item["expectedAnswer"],
            "actualAnswer": answer,
            "passed": answer == item["expectedAnswer"]
        },
        "grounding": {
            "supported": True,
            "citations": [f"{document['documentId']}#{table['tableId']}"]
        },
        "abstention": {
            "required": False,
            "reason": "All required fields were present in the retrieved table."
        },
        "modelRoute": {
            "route": "deterministic-financebench-relay.v1",
            "costUsd": 0.0,
            "latencyMs": 0
        }
    }


def main() -> int:
    items = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    traces = [build_trace(item) for item in items]
    failed = [trace for trace in traces if not trace["verification"]["passed"]]
    artifact = {
        "status": "failed" if failed else "passed",
        "traceCount": len(traces),
        "failureCount": len(failed),
        "traces": traces,
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {ARTIFACT_PATH.relative_to(ROOT)}")
    if failed:
        print(f"FinanceBench relay failed for {len(failed)} trace(s)")
        return 1
    print("FinanceBench relay fixture passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())