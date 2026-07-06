#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED = {
    "artifacts/financebench-relay-trace.json": "benchmark-trace.v1",
    "artifacts/finqa-relay-trace.json": "finqa-relay-trace.v1",
    "artifacts/tatqa-relay-trace.json": "tatqa-relay-trace.v1",
    "artifacts/open-finllm-routing-map.json": "open-finllm-routing-map.v1",
}
STALE_AFTER_DAYS = 14


def main() -> int:
    errors: list[str] = []
    cutoff = datetime.now(UTC) - timedelta(days=STALE_AFTER_DAYS)

    for rel_path, schema in REQUIRED.items():
        path = ROOT / rel_path
        if not path.exists():
            errors.append(f"Missing benchmark artifact: {rel_path}")
            continue

        payload = json.loads(path.read_text(encoding="utf-8"))
        if rel_path == "artifacts/financebench-relay-trace.json":
            trace_schema = payload.get("schemaVersion")
            if trace_schema is None and payload.get("traces"):
                trace_schema = payload["traces"][0].get("schemaVersion")
            if trace_schema != schema:
                errors.append(f"{rel_path} schemaVersion must be {schema}")
        elif payload.get("schemaVersion") != schema:
            errors.append(f"{rel_path} schemaVersion must be {schema}")

        generated_at = payload.get("generatedAt")
        if not isinstance(generated_at, str):
            if rel_path == "artifacts/financebench-relay-trace.json":
                generated = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            else:
                errors.append(f"{rel_path} missing generatedAt")
                continue
        else:
            stamp = generated_at.replace("Z", "+00:00")
            try:
                generated = datetime.fromisoformat(stamp)
            except ValueError:
                errors.append(f"{rel_path} generatedAt is not ISO-8601")
                continue

        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=UTC)
        if generated < cutoff:
            errors.append(f"{rel_path} is stale (older than {STALE_AFTER_DAYS} days)")

    if errors:
        print("Index85 benchmark verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Index85 benchmark verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
