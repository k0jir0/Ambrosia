#!/usr/bin/env python3
"""Fail closed when pnpm audit exceptions are undocumented or expired."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = ROOT / "package.json"
EXCEPTIONS_PATH = ROOT / "docs" / "security" / "dependency-audit-exceptions.json"


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    evidence = json.loads(EXCEPTIONS_PATH.read_text(encoding="utf-8"))
    ignored = set(
        manifest.get("pnpm", {})
        .get("auditConfig", {})
        .get("ignoreGhsas", [])
    )
    exceptions = evidence.get("exceptions", [])
    documented = {entry.get("advisory") for entry in exceptions}
    errors: list[str] = []

    if ignored != documented:
        errors.append(
            "package.json pnpm.auditConfig.ignoreGhsas must exactly match "
            "docs/security/dependency-audit-exceptions.json"
        )

    today = datetime.now(UTC).date()
    required_fields = {
        "advisory",
        "package",
        "severity",
        "status",
        "scope",
        "control",
        "owner",
        "approvedAt",
        "expiresAt",
        "removalCondition",
    }
    for entry in exceptions:
        advisory = entry.get("advisory", "<missing>")
        missing = sorted(required_fields - set(entry))
        if missing:
            errors.append(f"{advisory}: missing fields: {', '.join(missing)}")
            continue
        try:
            expiry = datetime.strptime(entry["expiresAt"], "%Y-%m-%d").date()
        except ValueError:
            errors.append(f"{advisory}: expiresAt must use YYYY-MM-DD")
            continue
        if expiry < today:
            errors.append(f"{advisory}: exception expired on {expiry.isoformat()}")
        if entry["status"] != "upstream_unfixed":
            errors.append(f"{advisory}: only upstream_unfixed advisories may be ignored")

    if errors:
        print("Dependency audit exception verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Verified {len(exceptions)} documented, unexpired audit exceptions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
