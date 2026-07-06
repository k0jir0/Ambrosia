#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIRED = [
    "artifacts/index84-completion.json",
    "artifacts/index84-literal-completion.json",
    "artifacts/finqa-relay-trace.json",
    "artifacts/tatqa-relay-trace.json",
    "artifacts/open-finllm-routing-map.json",
    "artifacts/release-evidence.json",
    "artifacts/release-checksums.sha256",
    "artifacts/rollout-evidence-packet.json",
    "artifacts/enterprise-execution-readiness.json",
    "artifacts/frontend-quality-evidence.json",
    "artifacts/alpha-decay-alerts.json",
    "artifacts/hotpath-readiness.json",
    "artifacts/hotpath-phase7-governance.json",
]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []
    for rel in REQUIRED:
        if not (ROOT / rel).exists():
            errors.append(f"Missing required artifact: {rel}")

    if not errors:
        index84 = _read_json(ROOT / "artifacts/index84-completion.json")
        literal = _read_json(ROOT / "artifacts/index84-literal-completion.json")
        rollout = _read_json(ROOT / "artifacts/rollout-evidence-packet.json")
        frontend = _read_json(ROOT / "artifacts/frontend-quality-evidence.json")
        alpha_decay = _read_json(ROOT / "artifacts/alpha-decay-alerts.json")
        hotpath = _read_json(ROOT / "artifacts/hotpath-readiness.json")
        hotpath_phase7 = _read_json(ROOT / "artifacts/hotpath-phase7-governance.json")

        if index84.get("status") != "passed":
            errors.append("index84 completion status must be passed")
        if literal.get("status") != "passed":
            errors.append("index84 literal status must be passed")
        if rollout.get("status") != "passed":
            errors.append("rollout evidence status must be passed")
        if frontend.get("status") != "passed":
            errors.append("frontend quality evidence status must be passed")
        if alpha_decay.get("status") != "passed":
            errors.append("alpha decay evidence status must be passed")
        if hotpath.get("status") != "passed":
            errors.append("hotpath readiness status must be passed")
        if hotpath_phase7.get("status") != "passed":
            errors.append("hotpath phase7 governance status must be passed")

    if errors:
        print("Index86 closure verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Index86 closure verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
