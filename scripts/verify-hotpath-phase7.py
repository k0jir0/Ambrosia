#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DECISION_PATH = ROOT / "docs" / "roadmap" / "index95-phase7-governance-decision.json"
ARTIFACT_PATH = ROOT / "artifacts" / "hotpath-phase7-governance.json"
MAIN_PATH = ROOT / "services" / "hotpath-rs" / "src" / "main.rs"
README_PATH = ROOT / "services" / "hotpath-rs" / "README.md"

REQUIRED_MAIN_TERMS = [
    "llm_origin_rejected",
    "price_collar_exceeded",
    "risk_checks_passed",
    "kill_switch_active",
]

REQUIRED_README_TERMS = [
    "deterministic",
    "no",
    "LLM",
    "price collar",
]


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    errors: list[str] = []

    if not DECISION_PATH.exists():
        errors.append(f"missing governance decision: {DECISION_PATH.relative_to(ROOT).as_posix()}")
    if not MAIN_PATH.exists():
        errors.append(f"missing hotpath source: {MAIN_PATH.relative_to(ROOT).as_posix()}")
    if not README_PATH.exists():
        errors.append(f"missing hotpath readme: {README_PATH.relative_to(ROOT).as_posix()}")

    decision_data: dict = {}
    if not errors:
        decision_data = _load_json(DECISION_PATH)

        if decision_data.get("schemaVersion") != "phase7-hotpath-governance.v1":
            errors.append("invalid governance schemaVersion")

        if decision_data.get("program", {}).get("separateRuntime") is not True:
            errors.append("program.separateRuntime must be true")

        if decision_data.get("businessCase", {}).get("approved") is not True:
            errors.append("businessCase.approved must be true")

        if decision_data.get("regulatoryReadiness", {}).get("approved") is not True:
            errors.append("regulatoryReadiness.approved must be true")

        controls = decision_data.get("regulatoryReadiness", {}).get("controls", {})
        for key in ["noLlmInPath", "deterministicRiskChecks", "killSwitch", "auditArtifacts", "separationOfDuties"]:
            if controls.get(key) is not True:
                errors.append(f"regulatoryReadiness.controls.{key} must be true")

        go_no_go = decision_data.get("goNoGoDecision", {})
        if go_no_go.get("approved") is not True:
            errors.append("goNoGoDecision.approved must be true")
        if str(go_no_go.get("decision", "")).upper() != "GO":
            errors.append("goNoGoDecision.decision must be GO")

    if MAIN_PATH.exists():
        main_text = MAIN_PATH.read_text(encoding="utf-8")
        for term in REQUIRED_MAIN_TERMS:
            if term not in main_text:
                errors.append(f"main.rs missing required term: {term}")

    if README_PATH.exists():
        readme_text = README_PATH.read_text(encoding="utf-8")
        for term in REQUIRED_README_TERMS:
            if term not in readme_text:
                errors.append(f"hotpath README missing required term: {term}")

    artifact = {
        "status": "failed" if errors else "passed",
        "schemaVersion": "hotpath-phase7-governance.v1",
        "phase": "phase7_optional_hotpath_program",
        "decisionSource": "docs/roadmap/index95-phase7-governance-decision.json",
        "hotpathService": "services/hotpath-rs",
        "errors": errors,
    }

    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    if errors:
        print("Phase 7 hotpath verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Phase 7 hotpath verification passed. Wrote {ARTIFACT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
