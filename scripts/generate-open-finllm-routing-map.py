#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_PATH = ROOT / "artifacts" / "open-finllm-routing-map.json"


def main() -> int:
    routing_map = {
        "schemaVersion": "open-finllm-routing-map.v1",
        "generatedAt": datetime.now(UTC).isoformat(),
        "routes": [
            {
                "taskType": "numeric_qa",
                "benchmark": "financebench",
                "modelTier": "analysis",
                "policy": "table_extraction_plus_calculation_verification",
                "fallback": "abstain_if_verification_fails",
            },
            {
                "taskType": "financial_reasoning",
                "benchmark": "finqa",
                "modelTier": "analysis",
                "policy": "evidence_retrieval_plus_formula_trace",
                "fallback": "abstain_if_missing_evidence",
            },
            {
                "taskType": "table_numeric_qa",
                "benchmark": "tatqa",
                "modelTier": "analysis",
                "policy": "table_parser_plus_calculation_trace",
                "fallback": "abstain_if_table_parse_fails",
            },
        ],
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(routing_map, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {ARTIFACT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
