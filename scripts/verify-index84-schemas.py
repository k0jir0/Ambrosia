#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_FIXTURES = [
    (
        ROOT / "packages" / "schemas" / "alpha-signal.v1.json",
        ROOT / "packages" / "schemas" / "fixtures" / "alpha-signal.fixture.json",
    ),
    (
        ROOT / "packages" / "schemas" / "paper-decision-loop.v1.json",
        ROOT / "packages" / "schemas" / "fixtures" / "paper-decision-loop.fixture.json",
    ),
]
TRACE_SCHEMA = ROOT / "packages" / "schemas" / "benchmark-trace.v1.json"
TRACE_ARTIFACT = ROOT / "artifacts" / "financebench-relay-trace.json"


def main() -> int:
    errors: list[str] = []
    for schema_path, fixture_path in SCHEMA_FIXTURES:
        errors.extend(validate_required_fields(schema_path, fixture_path))

    if TRACE_ARTIFACT.exists():
        trace_payload = json.loads(TRACE_ARTIFACT.read_text(encoding="utf-8"))
        trace_schema = json.loads(TRACE_SCHEMA.read_text(encoding="utf-8"))
        for index, trace in enumerate(trace_payload.get("traces", [])):
            errors.extend(validate_payload(trace_schema, trace, f"{TRACE_ARTIFACT.name}:traces[{index}]"))

    if errors:
        print("Index84 schema verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Index84 schema verification passed.")
    return 0


def validate_required_fields(schema_path: Path, fixture_path: Path) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    return validate_payload(schema, fixture, fixture_path.name)


def validate_payload(schema: dict, payload: dict, label: str) -> list[str]:
    errors: list[str] = []
    for field in schema.get("required", []):
        if field not in payload:
            errors.append(f"{label} missing required field '{field}'")
    schema_version = schema.get("properties", {}).get("schemaVersion", {}).get("const")
    if schema_version and payload.get("schemaVersion") != schema_version:
        errors.append(f"{label} schemaVersion must be {schema_version}")
    return errors


if __name__ == "__main__":
    raise SystemExit(main())