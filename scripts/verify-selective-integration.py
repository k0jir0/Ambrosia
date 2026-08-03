#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API_ROOT = ROOT / "services" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))
if str(ROOT / "packages" / "evals") not in sys.path:
    sys.path.insert(0, str(ROOT / "packages" / "evals"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from app.models import DecisionPacket  # noqa: E402
from app.main import app  # noqa: E402
from run_selective_integration import run_evaluation  # noqa: E402


def require_tokens(path: Path, tokens: list[str], errors: list[str]) -> None:
    content = path.read_text(encoding="utf-8")
    for token in tokens:
        if token not in content:
            errors.append(f"{path.relative_to(ROOT)} missing required token: {token}")


def validate_local_schema_refs(value: object, definitions: dict, errors: list[str]) -> None:
    if isinstance(value, dict):
        reference = value.get("$ref")
        if isinstance(reference, str) and reference.startswith("#/$defs/"):
            name = reference.removeprefix("#/$defs/")
            if name not in definitions:
                errors.append(f"packet schema contains unresolved local reference: {reference}")
        for nested in value.values():
            validate_local_schema_refs(nested, definitions, errors)
    elif isinstance(value, list):
        for nested in value:
            validate_local_schema_refs(nested, definitions, errors)


def main() -> int:
    errors: list[str] = []
    schema_path = ROOT / "packages" / "schemas" / "packet.v1.json"
    fixture_path = ROOT / "packages" / "schemas" / "fixtures" / "packet-selective.fixture.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    validate_local_schema_refs(schema, schema.get("$defs", {}), errors)

    missing = [field for field in schema.get("required", []) if field not in fixture]
    if missing:
        errors.append(f"packet fixture missing schema-required fields: {', '.join(missing)}")
    try:
        DecisionPacket.model_validate(fixture)
    except Exception as exc:
        errors.append(f"packet fixture failed canonical Pydantic validation: {exc}")

    openapi = app.openapi()
    openapi_schemas = openapi.get("components", {}).get("schemas", {})
    for model_name in [
        "ProvenanceMetadata",
        "DisconfirmationOutcome",
        "RiskGateOutcome",
        "DecisionMemoryRecord",
        "PacketWorkflowStatus",
    ]:
        if model_name not in openapi_schemas:
            errors.append(f"OpenAPI is missing canonical schema: {model_name}")
    if not (
        "DecisionPacket" in openapi_schemas
        or {"DecisionPacket-Input", "DecisionPacket-Output"} <= set(openapi_schemas)
    ):
        errors.append("OpenAPI is missing canonical DecisionPacket input/output schemas")
    for route in [
        "/packets/{packet_id}/selective-integrate",
        "/packets/{packet_id}/provenance/refresh",
        "/packets/{packet_id}/disconfirmation/run",
        "/packets/{packet_id}/risk-gate/run",
        "/packets/{packet_id}/decision",
        "/packets/{packet_id}/memory/resolve",
        "/packets/{packet_id}/audit-chain/verify",
    ]:
        if route not in openapi.get("paths", {}):
            errors.append(f"OpenAPI is missing governed route: {route}")

    selective_path = ROOT / "services" / "api" / "app" / "selective_integration.py"
    selective_text = selective_path.read_text(encoding="utf-8")
    for duplicated_model in [
        "class ProvenanceMetadata",
        "class DisconfirmationOutcome",
        "class RiskGateOutcome",
        "class DecisionMemoryRecord",
    ]:
        if duplicated_model in selective_text:
            errors.append(f"selective_integration.py redefines canonical model: {duplicated_model}")

    require_tokens(
        ROOT / "services" / "api" / "app" / "main.py",
        [
            '"/packets/{packet_id}/selective-integrate"',
            '"/packets/{packet_id}/provenance/refresh"',
            '"/packets/{packet_id}/disconfirmation/run"',
            '"/packets/{packet_id}/risk-gate/run"',
            '"/packets/{packet_id}/decision"',
            '"/packets/{packet_id}/memory/resolve"',
            '"/packets/{packet_id}/audit-chain/verify"',
            "packet_decision_blockers",
            "SELECTIVE_INTEGRATION_ENFORCED",
        ],
        errors,
    )
    require_tokens(
        ROOT / "infra" / "db" / "migrations" / "V0007__selective_integration_hardening.sql",
        ["packet_version", "decision_memory_record", "packet_audit_chain", "packet_audit_head"],
        errors,
    )
    require_tokens(
        ROOT / "apps" / "web" / "src" / "lib" / "types.ts",
        ["ProvenanceMetadata", "DisconfirmationOutcome", "RiskGateOutcome", "PacketWorkflowStatus"],
        errors,
    )
    require_tokens(
        ROOT / "apps" / "web" / "src" / "components" / "workbench.tsx",
        ["recordPacketDecision", "Next governed action", "Workflow blockers"],
        errors,
    )

    evaluation = run_evaluation()
    if evaluation["summary"]["releaseGate"] != "pass":
        errors.append("deterministic selective-integration evaluation gate failed")

    if errors:
        print("Selective integration readiness check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Selective integration readiness check passed.")
    print(f"- Contract: {fixture['contractVersion']}")
    print("- Database migration: v0007")
    print(f"- Deterministic evaluation: {evaluation['summary']['passed']}/{evaluation['summary']['total']}")
    print("- Workflow enforcement, memory, and audit-chain surfaces: present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
