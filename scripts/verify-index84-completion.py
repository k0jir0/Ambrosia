#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER_PATH = ROOT / "docs" / "roadmap" / "pdo-ledger.seed.json"
SCHEMA_VERSION_PATH = ROOT / "infra" / "db" / "schema-version.json"
ARTIFACT_PATH = ROOT / "artifacts" / "index84-completion.json"
REPORT_PATH = ROOT / "artifacts" / "index84-completion.md"

PLAN_EVIDENCE = {
    "P-001": ["artifacts/index84-route-inventory.json", "artifacts/web-control-plane-evidence.json"],
    "P-002": ["infra/db/migrations/V0002__roadmap_pdo.sql", "infra/db/migrations/V0003__execution_enterprise_readiness.sql"],
    "P-003": ["artifacts/index84-route-inventory.json", "artifacts/openapi/public.json", "artifacts/openapi/admin.json"],
    "P-004": ["artifacts/web-control-plane-evidence.json", "docs/roadmap/frontend-control-plane-matrix.md"],
    "P-005": ["packages/sdk-python/ambrosia_sdk/client.py", "packages/cli/ambrosia_cli/main.py", "artifacts/sdk-cli-transcript.json"],
    "P-006": ["packages/schemas/alpha-signal.v1.json", "packages/schemas/fixtures/alpha-signal.fixture.json"],
    "P-007": ["packages/schemas/alpha-signal.v1.json", "packages/evals/run_decision_memory_fixture.py"],
    "P-008": ["packages/schemas/benchmark-trace.v1.json", "artifacts/financebench-relay-trace.json"],
    "P-009": ["packages/schemas/paper-decision-loop.v1.json", "artifacts/decision-memory-attribution.json"],
    "P-010": ["artifacts/decision-memory-attribution.json"],
    "P-011": ["artifacts/web-control-plane-evidence.json"],
    "P-012": ["artifacts/enterprise-execution-readiness.json", "infra/db/migrations/V0003__execution_enterprise_readiness.sql"],
}

REQUIRED_COMMAND_SURFACES = {
    "roadmap:routes:check": "generate-index84-route-inventory.py --check",
    "roadmap:openapi:check": "generate-index84-route-inventory.py --check-openapi",
    "sdk:check": "verify-sdk-cli.py",
    "index84:literal:check": "verify-index84-literal.py",
    "evals:financebench": "run_financebench_relay.py",
    "evals:decision-memory": "run_decision_memory_fixture.py",
    "enterprise:execution:check": "verify-enterprise-execution.py",
    "schemas:index84:check": "verify-index84-schemas.py",
    "web:control-plane:check": "verify-web-control-plane.py",
    "evals:finqa": "run_finqa_relay.py",
    "evals:tatqa": "run_tatqa_relay.py",
    "routing-map:open-finllm": "generate-open-finllm-routing-map.py",
    "index85:benchmarks:check": "verify-index85-benchmarks.py",
    "release:evidence": "generate-release-evidence.py",
    "release:readiness:check": "verify-release-readiness.py",
    "production:evidence:check": "verify-production-evidence.py",
    "docs:consistency:check": "verify-docs-consistency.py",
    "evals:alpha-decay": "run_alpha_decay_fixture.py",
    "frontend:quality:evidence": "generate-frontend-quality-evidence.py",
    "hotpath:design:check": "verify-hotpath-design.py",
    "index86:closure:check": "verify-index86-closure.py",
}

LITERAL_EVIDENCE = [
    "artifacts/index84-literal-completion.json",
    "services/api/app/index84_platform.py",
    "infra/db/migrations/V0004__index84_full_platform.sql",
    "artifacts/release-evidence.json",
    "artifacts/release-checksums.sha256",
    "artifacts/open-finllm-routing-map.json",
    "artifacts/finqa-relay-trace.json",
    "artifacts/tatqa-relay-trace.json",
    "artifacts/rollout-evidence-packet.json",
    "artifacts/alpha-decay-alerts.json",
    "artifacts/frontend-quality-evidence.json",
    "artifacts/hotpath-readiness.json",
]


def main() -> int:
    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    plans = {plan["plan_id"]: plan for plan in ledger.get("plans", [])}
    package = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))
    schema_version = json.loads(SCHEMA_VERSION_PATH.read_text(encoding="utf-8"))

    errors: list[str] = []
    plan_results = []

    for plan_id, evidence_paths in PLAN_EVIDENCE.items():
        if plan_id not in plans:
            errors.append(f"Missing plan {plan_id} in ledger")
        missing = [path for path in evidence_paths if not (ROOT / path).exists()]
        if missing:
            errors.append(f"{plan_id} missing evidence: {', '.join(missing)}")
        plan_results.append(
            {
                "planId": plan_id,
                "title": plans.get(plan_id, {}).get("title", "unknown"),
                "accepted": not missing and plan_id in plans,
                "evidence": evidence_paths,
                "missing": missing,
            }
        )

    if set(plans) != set(PLAN_EVIDENCE):
        extra = sorted(set(plans) - set(PLAN_EVIDENCE))
        missing = sorted(set(PLAN_EVIDENCE) - set(plans))
        if extra:
            errors.append(f"Ledger has unmapped plans: {', '.join(extra)}")
        if missing:
            errors.append(f"Completion map missing plans: {', '.join(missing)}")

    scripts = package.get("scripts", {})
    for script_name, expected_fragment in REQUIRED_COMMAND_SURFACES.items():
        script = scripts.get(script_name, "")
        if expected_fragment not in script:
            errors.append(f"package.json script {script_name} missing expected fragment {expected_fragment}")

    missing_literal = [path for path in LITERAL_EVIDENCE if not (ROOT / path).exists()]
    if missing_literal:
        errors.append(f"Missing literal Index84 evidence: {', '.join(missing_literal)}")
    else:
        literal = json.loads((ROOT / "artifacts" / "index84-literal-completion.json").read_text(encoding="utf-8"))
        if literal.get("status") != "passed":
            errors.append("Literal Index84 verifier artifact did not pass")

    db_schema_version = str(schema_version.get("dbSchemaVersion", "")).strip().lower()
    try:
        db_schema_numeric = int(db_schema_version.lstrip("v"))
    except ValueError:
        db_schema_numeric = -1

    if db_schema_numeric < 4:
        errors.append("dbSchemaVersion must be v0004 or higher for literal Index84 completion")

    completion = {
        "status": "failed" if errors else "passed",
        "completionPercent": 100 if not errors else round((len([p for p in plan_results if p["accepted"]]) / 12) * 100, 1),
        "planCount": len(plan_results),
        "acceptedPlans": sum(1 for result in plan_results if result["accepted"]),
        "dbSchemaVersion": schema_version.get("dbSchemaVersion"),
        "plans": plan_results,
        "literalEvidence": LITERAL_EVIDENCE,
        "errors": errors,
        "memoryUpdate": "Index84 completion now includes local/CI evidence for the literal relay, feature-store, signal, backtest, paper-trade, execution, enterprise, SDK/CLI, web-control-plane expectations, and Index85 release/benchmark/documentation closure gates.",
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(completion, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(render_markdown(completion), encoding="utf-8")

    if errors:
        print("Index84 completion verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Index84 completion verification passed. Wrote {ARTIFACT_PATH.relative_to(ROOT)}")
    return 0


def render_markdown(completion: dict) -> str:
    lines = [
        "# Index84 Completion Evidence",
        "",
        f"- Status: {completion['status']}",
        f"- Completion: {completion['completionPercent']}%",
        f"- Accepted plans: {completion['acceptedPlans']}/{completion['planCount']}",
        f"- DB schema version: {completion['dbSchemaVersion']}",
        f"- Literal Index84 evidence: {len(completion['literalEvidence'])} required artifacts",
        "",
        "| Plan | Accepted | Evidence |",
        "| --- | --- | --- |",
    ]
    for plan in completion["plans"]:
        evidence = "<br>".join(plan["evidence"])
        lines.append(f"| {plan['planId']} | {plan['accepted']} | {evidence} |")
    lines.extend(["", f"Memory update: {completion['memoryUpdate']}", ""])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())