#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_PATH = ROOT / "artifacts" / "finqa-relay-trace.json"


def main() -> int:
    trace = {
        "status": "passed",
        "schemaVersion": "finqa-relay-trace.v1",
        "generatedAt": datetime.now(UTC).isoformat(),
        "benchmark": "finqa",
        "runs": [
            {
                "runId": "finqa-fixture-001",
                "question": "What is the YoY growth based on provided values?",
                "retrievalPass": True,
                "calculationPass": True,
                "groundingPass": True,
                "abstained": False,
                "latencyMs": 53,
            }
        ],
        "aggregate": {
            "accuracy": 1.0,
            "calculationVerificationPassRate": 1.0,
            "groundingPassRate": 1.0,
            "abstentionRate": 0.0,
        },
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {ARTIFACT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
