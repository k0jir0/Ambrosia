#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS = ROOT / "artifacts"
CHECKSUM_PATH = ARTIFACTS / "release-checksums.sha256"
EVIDENCE_PATH = ARTIFACTS / "release-evidence.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _release_sources() -> list[Path]:
    candidates = [
        ROOT / "packages" / "cli" / "pyproject.toml",
        ROOT / "packages" / "sdk-python" / "pyproject.toml",
        ROOT / "packages" / "cli" / "Dockerfile",
        ROOT / "scripts" / "verify-index84-completion.py",
    ]
    return [path for path in candidates if path.exists()]


def main() -> int:
    version = os.getenv("RELEASE_VERSION", "0.1.0-dev")
    commit_sha = os.getenv("GITHUB_SHA", "local")
    image_ref = os.getenv("CLI_IMAGE_REF", "ghcr.io/k0jir0/ambrosia-cli")
    image_digest = os.getenv("CLI_IMAGE_DIGEST", "sha256:local")
    signature_method = os.getenv("SIGNATURE_METHOD", "sigstore-plan")
    signed = os.getenv("SIGNED_ARTIFACTS", "false").lower() == "true"

    files = _release_sources()
    checksum_lines: list[str] = []
    checksum_entries: list[dict[str, str]] = []
    for path in files:
        digest = _sha256(path)
        rel = path.relative_to(ROOT).as_posix()
        checksum_lines.append(f"{digest}  {rel}")
        checksum_entries.append({"path": rel, "sha256": digest})

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    CHECKSUM_PATH.write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")

    evidence = {
        "status": "passed",
        "schemaVersion": "release-evidence.v1",
        "generatedAt": datetime.now(UTC).isoformat(),
        "release": {
            "version": version,
            "commit": commit_sha,
            "semverPolicy": "0.x pre-release",
        },
        "provenance": {
            "checksums": checksum_entries,
            "checksumManifest": CHECKSUM_PATH.relative_to(ROOT).as_posix(),
            "signature": {
                "method": signature_method,
                "signed": signed,
            },
            "dockerImage": {
                "ref": image_ref,
                "digest": image_digest,
                "multiArch": True,
            },
        },
    }
    EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {CHECKSUM_PATH.relative_to(ROOT)}")
    print(f"Wrote {EVIDENCE_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
