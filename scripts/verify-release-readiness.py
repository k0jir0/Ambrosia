#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE_PATH = ROOT / "packages" / "cli" / "Dockerfile"
CHECKSUM_PATH = ROOT / "artifacts" / "release-checksums.sha256"
EVIDENCE_PATH = ROOT / "artifacts" / "release-evidence.json"


def main() -> int:
    errors: list[str] = []

    if not DOCKERFILE_PATH.exists():
        errors.append("Missing CLI Dockerfile at packages/cli/Dockerfile")
    if not CHECKSUM_PATH.exists():
        errors.append("Missing checksum manifest artifacts/release-checksums.sha256")
    if not EVIDENCE_PATH.exists():
        errors.append("Missing release evidence artifacts/release-evidence.json")

    if EVIDENCE_PATH.exists():
        evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
        if evidence.get("schemaVersion") != "release-evidence.v1":
            errors.append("release-evidence schemaVersion must be release-evidence.v1")
        if evidence.get("status") != "passed":
            errors.append("release-evidence status must be passed")
        provenance = evidence.get("provenance", {})
        if not provenance.get("checksums"):
            errors.append("release-evidence must include checksum entries")
        docker = provenance.get("dockerImage", {})
        if not str(docker.get("digest", "")).startswith("sha256:"):
            errors.append("docker image digest must start with sha256:")

    if CHECKSUM_PATH.exists() and not CHECKSUM_PATH.read_text(encoding="utf-8").strip():
        errors.append("checksum manifest is empty")

    if errors:
        print("Release readiness verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Release readiness verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
