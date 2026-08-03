#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API_ROOT = ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.models import Claim, DecisionPacket, ProvenanceMetadata  # noqa: E402
from app.selective_integration import (  # noqa: E402
    attach_provenance,
    build_packet_provenance,
    build_workflow_status,
    create_decision_memory_record,
    evaluate_risk_gate,
    run_disconfirmation,
    score_memory_relevance,
    verify_audit_chain,
)


def _fixture() -> DecisionPacket:
    payload = json.loads(
        (ROOT / "packages" / "schemas" / "fixtures" / "packet-selective.fixture.json").read_text(
            encoding="utf-8"
        )
    )
    payload["riskMonitor"] = {
        "activePositionSize": 0.05,
        "concentrationRisk": "low",
        "correlationOverlap": [],
        "varAtRisk": 0.02,
        "maxDrawdownThreshold": 0.10,
        "followUpTriggers": [],
        "status": "safe",
    }
    return DecisionPacket.model_validate(payload)


def _case(case_id: str, passed: bool, evidence: dict) -> dict:
    return {"id": case_id, "passed": passed, "evidence": evidence}


def run_evaluation() -> dict:
    cases: list[dict] = []

    valid = _fixture()
    valid = attach_provenance(valid, build_packet_provenance(valid), replace=True)
    disconfirmation = run_disconfirmation(valid)
    risk = evaluate_risk_gate(valid)
    workflow = build_workflow_status(valid, disconfirmation, risk)
    cases.append(
        _case(
            "valid-governed-packet",
            disconfirmation.status.value == "pass"
            and risk.status.value == "pass"
            and workflow.state.value == "promotable",
            {
                "disconfirmation": disconfirmation.status.value,
                "risk": risk.status.value,
                "workflow": workflow.state.value,
            },
        )
    )

    no_risk = valid.model_copy(update={"riskMonitor": None})
    no_risk_result = evaluate_risk_gate(no_risk)
    cases.append(
        _case(
            "missing-risk-fails-closed",
            no_risk_result.status.value == "insufficient_data"
            and "riskMonitor" in no_risk_result.missingInputs,
            no_risk_result.model_dump(mode="json"),
        )
    )

    stale = attach_provenance(
        valid,
        [
            ProvenanceMetadata(
                source="stale-market",
                sourceType="market",
                timestamp="2026-07-01T10:00:00Z",
                freshnessSeconds=1000,
                freshnessSlaSeconds=60,
                stale=True,
                coverageStatus="full",
                dataMode="live",
            )
        ],
        replace=True,
    )
    stale_result = evaluate_risk_gate(stale)
    cases.append(
        _case(
            "stale-market-data-blocks",
            stale_result.status.value == "blocked"
            and any("stale" in item for item in stale_result.hardBlocks),
            stale_result.model_dump(mode="json"),
        )
    )

    contradicted = valid.model_copy(
        update={
            "claims": [
                *valid.claims,
                Claim(
                    id="contradiction-1",
                    kind="contradiction",
                    text="Independent evidence contradicts the primary claim.",
                    evidence="source-1",
                    confidence=90,
                ),
            ]
        }
    )
    contradiction_result = run_disconfirmation(contradicted)
    cases.append(
        _case(
            "contradiction-requires-human-review",
            contradiction_result.status.value == "requires_human_review"
            and contradiction_result.requiresHumanReview,
            contradiction_result.model_dump(mode="json"),
        )
    )

    first = create_decision_memory_record(valid, outcome="watch")
    second = create_decision_memory_record(
        valid,
        outcome="outperformed",
        score=80,
        record_type="resolution",
        observed_at="2026-08-20T10:00:00Z",
        previous_record=first,
    )
    tampered = second.model_copy(update={"outcome": "underperformed"})
    cases.append(
        _case(
            "audit-chain-tamper-detected",
            verify_audit_chain([first, second], valid.id)
            and not verify_audit_chain([first, tampered], valid.id),
            {"validChain": True, "tamperedChainRejected": True},
        )
    )

    future_score = score_memory_relevance(
        second,
        "outperformed",
        now=datetime(2026, 8, 10, tzinfo=UTC),
    )
    observed_score = score_memory_relevance(
        second,
        "outperformed",
        now=datetime(2026, 8, 21, tzinfo=UTC),
    )
    cases.append(
        _case(
            "future-outcome-leakage-prevented",
            future_score is None and observed_score is not None,
            {"beforeObservation": future_score, "afterObservation": observed_score},
        )
    )

    passed = sum(1 for case in cases if case["passed"])
    return {
        "schemaVersion": "selective-integration-eval.v1",
        "generatedAt": datetime.now(UTC).isoformat(),
        "summary": {
            "passed": passed,
            "total": len(cases),
            "passRate": round(passed / len(cases), 4),
            "releaseGate": "pass" if passed == len(cases) else "fail",
        },
        "cases": cases,
        "dataMode": "synthetic",
        "limitations": [
            "This suite validates deterministic invariants, not investment performance.",
            "PostgreSQL concurrency and production-provider behavior require environment certification.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = run_evaluation()
    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["summary"]["releaseGate"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
