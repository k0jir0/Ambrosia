#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_PATH = ROOT / "artifacts" / "hotpath-readiness.json"

REQUIRED_FILES = [
    ROOT / "services" / "hotpath-rs" / "Cargo.toml",
    ROOT / "services" / "hotpath-rs" / "src" / "main.rs",
    ROOT / "services" / "hotpath-rs" / "README.md",
]

REQUIRED_MAIN_TERMS = [
    "KillSwitch",
    "NewOrder",
    "risk_checks_passed",
    "notional_limit_exceeded",
    "kill_switch_active",
]

REQUIRED_README_TERMS = [
    "deterministic",
    "no",
    "LLM",
    "Rust",
    "hot-path",
]


def main() -> int:
    errors: list[str] = []

    for path in REQUIRED_FILES:
        if not path.exists():
            errors.append(f"missing required file: {path.relative_to(ROOT).as_posix()}")

    main_path = ROOT / "services" / "hotpath-rs" / "src" / "main.rs"
    readme_path = ROOT / "services" / "hotpath-rs" / "README.md"

    if main_path.exists():
        text = main_path.read_text(encoding="utf-8")
        for term in REQUIRED_MAIN_TERMS:
            if term not in text:
                errors.append(f"main.rs missing term: {term}")

    if readme_path.exists():
        text = readme_path.read_text(encoding="utf-8")
        for term in REQUIRED_README_TERMS:
            if term not in text:
                errors.append(f"README missing term: {term}")

    artifact = {
        "status": "failed" if errors else "passed",
        "schemaVersion": "hotpath-readiness.v1",
        "language": "Rust",
        "servicePath": "services/hotpath-rs",
        "enforcedBoundaries": [
            "separate_service_boundary",
            "deterministic_pre_trade_risk_checks",
            "kill_switch",
            "no_llm_in_live_order_loop",
        ],
        "errors": errors,
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    if errors:
        print("Hot path design verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Hot path design verification passed. Wrote {ARTIFACT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
