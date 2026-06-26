#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = ROOT / "artifacts"
VISIBILITY_DIR = ROOT / "docs" / "visibility"
PERMISSION_FOCUS_HISTORY_PATH = ARTIFACTS_DIR / "permission-boundary-focus-history.json"
FOCUS_PERMISSION_CHECKS = [
    "advanced_registry_denies_missing_role",
    "advanced_registry_allows_analyst",
    "advanced_frontend_matrix_denies_missing_role",
    "advanced_frontend_matrix_allows_analyst",
    "admin_policies_denies_analyst",
    "admin_policies_allows_admin",
    "admin_boundary_rules_denies_analyst",
    "admin_boundary_rules_allows_admin",
]


def read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def age_days(ts: datetime | None) -> int | None:
    if ts is None:
        return None
    now = datetime.now(UTC)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    delta = now - ts.astimezone(UTC)
    return max(0, delta.days)


def bool_status(ok: bool) -> str:
    return "pass" if ok else "fail"


def summarize_permission_focus(permission_boundary: dict[str, Any] | None) -> dict[str, Any]:
    if not permission_boundary:
        return {
            "required": len(FOCUS_PERMISSION_CHECKS),
            "present": 0,
            "passed": 0,
            "missing": FOCUS_PERMISSION_CHECKS,
            "failed": [],
            "passRatePct": 0,
            "healthy": False,
            "detail": "permission boundary artifact missing",
        }

    checks = permission_boundary.get("checks")
    if not isinstance(checks, list):
        return {
            "required": len(FOCUS_PERMISSION_CHECKS),
            "present": 0,
            "passed": 0,
            "missing": FOCUS_PERMISSION_CHECKS,
            "failed": [],
            "passRatePct": 0,
            "healthy": False,
            "detail": "permission boundary artifact malformed",
        }

    by_name = {
        item.get("name"): item
        for item in checks
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    }

    missing = [name for name in FOCUS_PERMISSION_CHECKS if name not in by_name]
    failed = [
        name
        for name in FOCUS_PERMISSION_CHECKS
        if name in by_name and not bool(by_name[name].get("passed", False))
    ]
    present = len(FOCUS_PERMISSION_CHECKS) - len(missing)
    passed = present - len(failed)
    pass_rate = int(round((passed / len(FOCUS_PERMISSION_CHECKS)) * 100)) if FOCUS_PERMISSION_CHECKS else 100
    healthy = len(missing) == 0 and len(failed) == 0

    detail = (
        "all focused permission checks passed"
        if healthy
        else f"missing={len(missing)} failed={len(failed)}"
    )

    return {
        "required": len(FOCUS_PERMISSION_CHECKS),
        "present": present,
        "passed": passed,
        "missing": missing,
        "failed": failed,
        "passRatePct": pass_rate,
        "healthy": healthy,
        "detail": detail,
    }


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load_permission_focus_history() -> list[dict[str, Any]]:
    if not PERMISSION_FOCUS_HISTORY_PATH.exists():
        return []
    try:
        raw = json.loads(PERMISSION_FOCUS_HISTORY_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        generated_at = item.get("generatedAt")
        if not isinstance(generated_at, str):
            continue
        normalized.append(
            {
                "generatedAt": generated_at,
                "passRatePct": _coerce_int(item.get("passRatePct"), 0),
                "passed": _coerce_int(item.get("passed"), 0),
                "required": _coerce_int(item.get("required"), len(FOCUS_PERMISSION_CHECKS)),
                "healthy": bool(item.get("healthy", False)),
            }
        )
    return normalized


def update_permission_focus_history(generated_at: str, focus: dict[str, Any]) -> list[dict[str, Any]]:
    history = load_permission_focus_history()
    history.append(
        {
            "generatedAt": generated_at,
            "passRatePct": _coerce_int(focus.get("passRatePct"), 0),
            "passed": _coerce_int(focus.get("passed"), 0),
            "required": _coerce_int(focus.get("required"), len(FOCUS_PERMISSION_CHECKS)),
            "healthy": bool(focus.get("healthy", False)),
        }
    )

    # Deduplicate by timestamp, keeping latest occurrence.
    dedup: dict[str, dict[str, Any]] = {}
    for item in history:
        dedup[item["generatedAt"]] = item

    ordered = sorted(dedup.values(), key=lambda item: item["generatedAt"])
    trimmed = ordered[-20:]
    PERMISSION_FOCUS_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    PERMISSION_FOCUS_HISTORY_PATH.write_text(json.dumps(trimmed, indent=2) + "\n", encoding="utf-8")
    return trimmed


def summarize_permission_focus_trend(history: list[dict[str, Any]]) -> dict[str, Any]:
    if not history:
        return {
            "window": 0,
            "latestPassRatePct": 0,
            "previousPassRatePct": None,
            "deltaPassRatePct": None,
            "healthyRuns": 0,
            "degradedRuns": 0,
            "direction": "flat",
            "detail": "no history available",
        }

    latest = history[-1]
    previous = history[-2] if len(history) >= 2 else None
    latest_rate = _coerce_int(latest.get("passRatePct"), 0)
    previous_rate = _coerce_int(previous.get("passRatePct"), latest_rate) if previous else None
    delta = latest_rate - previous_rate if previous_rate is not None else None
    healthy_runs = sum(1 for item in history if bool(item.get("healthy", False)))
    degraded_runs = len(history) - healthy_runs

    if delta is None:
        direction = "flat"
        detail = "first recorded run"
    elif delta > 0:
        direction = "improving"
        detail = f"+{delta}pp vs previous run"
    elif delta < 0:
        direction = "degrading"
        detail = f"{delta}pp vs previous run"
    else:
        direction = "flat"
        detail = "no change vs previous run"

    return {
        "window": len(history),
        "latestPassRatePct": latest_rate,
        "previousPassRatePct": previous_rate,
        "deltaPassRatePct": delta,
        "healthyRuns": healthy_runs,
        "degradedRuns": degraded_runs,
        "direction": direction,
        "detail": detail,
    }


def phase_status(
    *,
    milestones: dict[str, Any],
    checklist: dict[str, Any],
    registry: list[dict[str, Any]],
    scanner_artifact_present: bool,
) -> dict[str, dict[str, str]]:
    def _state(green: bool, yellow: bool) -> str:
        if green:
            return "green"
        if yellow:
            return "yellow"
        return "red"

    m1_ready = bool(milestones.get("M1_85", {}).get("ready"))
    m2_ready = bool(milestones.get("M2_91", {}).get("ready"))
    m3_ready = bool(milestones.get("M3_96", {}).get("ready"))

    phase_a_green = m1_ready
    phase_a_yellow = bool(checklist["metricsSnapshot"]["passed"] and checklist["retrievalQualityDrift"]["passed"])

    phase_b_green = m2_ready
    phase_b_yellow = bool(checklist["visibilityCoverage"]["passed"] or checklist["releaseEvidenceComplete"]["passed"])

    phase_c_green = m3_ready
    phase_c_yellow = scanner_artifact_present

    phase_d_green = bool(
        checklist["permissionBoundaries"]["passed"]
        and checklist["permissionBoundaryFocus"]["passed"]
        and checklist["visibilityCoverage"]["passed"]
    )
    phase_d_yellow = bool(checklist["permissionBoundaries"]["passed"] or checklist["visibilityCoverage"]["passed"])

    registry_paths = {str(item.get("path", "")) for item in registry if isinstance(item, dict)}
    e_required = {
        "/sandbox/orders/simulate",
        "/packets/{packet_id}/attribution/compute",
        "/alerts/mobile",
    }
    e_present = len(registry_paths.intersection(e_required))
    phase_e_green = e_present == len(e_required)
    phase_e_yellow = e_present >= 2

    return {
        "PhaseA_TruthLayer": {
            "status": _state(phase_a_green, phase_a_yellow),
            "detail": "M1 readiness and truth-layer checks",
        },
        "PhaseB_EvalCI": {
            "status": _state(phase_b_green, phase_b_yellow),
            "detail": "M2 evidence gates and visibility proof",
        },
        "PhaseC_Discovery": {
            "status": _state(phase_c_green, phase_c_yellow),
            "detail": "Scanner/discovery benchmark evidence",
        },
        "PhaseD_Governance": {
            "status": _state(phase_d_green, phase_d_yellow),
            "detail": "RBAC, boundary, and visibility governance checks",
        },
        "PhaseE_ExecutionLoop": {
            "status": _state(phase_e_green, phase_e_yellow),
            "detail": f"Execution loop endpoints present ({e_present}/{len(e_required)})",
        },
    }


def build_blockers(report: dict[str, Any]) -> list[dict[str, str]]:
    blockers: list[dict[str, str]] = []

    if not report["checklist"]["runtimeEvidenceFresh"]["passed"]:
        blockers.append(
            {
                "id": "B1",
                "title": "Runtime evidence is missing or stale",
                "owner": "platform",
                "mitigation": "Regenerate scorecard/retrieval/scanner artifacts before milestone review.",
            }
        )

    if not report["checklist"]["retrievalQualityDrift"]["passed"]:
        blockers.append(
            {
                "id": "B5",
                "title": "Retrieval quality drift exceeds allowed thresholds",
                "owner": "api + data engineering",
                "mitigation": "Re-run retrieval benchmark, inspect driftErrors, and update retrieval tuning or fixtures before promotion.",
            }
        )

    if not report["checklist"]["visibilityCoverage"]["passed"]:
        blockers.append(
            {
                "id": "B2",
                "title": "Visibility matrix coverage contract is incomplete",
                "owner": "frontend + api",
                "mitigation": "Run visibility sync and ensure every non-internal function has frontend route, role, and audit metadata.",
            }
        )

    if not report["checklist"]["permissionBoundaries"]["passed"]:
        blockers.append(
            {
                "id": "B3",
                "title": "Permission boundary metadata is not enforceable",
                "owner": "security + operations",
                "mitigation": "Require non-user roles for team/admin surfaces and verify runtime boundary artifact in CI.",
            }
        )

    if not report["checklist"]["permissionBoundaryFocus"]["passed"]:
        blockers.append(
            {
                "id": "B6",
                "title": "Focused permission boundary checks regressed",
                "owner": "security + platform",
                "mitigation": "Repair focused advanced/admin boundary checks and regenerate permission-boundary artifact before promotion.",
            }
        )

    if not report["milestones"]["M2_91"]["ready"]:
        blockers.append(
            {
                "id": "B4",
                "title": "M2 release evidence package is incomplete",
                "owner": "platform + eval",
                "mitigation": "Generate provider ablation and synthetic monitor artifacts for full M2 proof set.",
            }
        )

    return blockers[:3]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate weekly roadmap delta artifact.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when blockers exist.")
    args = parser.parse_args()

    m1 = read_json_if_exists(ARTIFACTS_DIR / "m1-readiness.json")
    retrieval = read_json_if_exists(ARTIFACTS_DIR / "retrieval-benchmark.json")
    scorecard = read_json_if_exists(ARTIFACTS_DIR / "scorecard-runtime.json")
    scanner = read_json_if_exists(ARTIFACTS_DIR / "scanner-benchmark.json")
    synthetic = read_json_if_exists(ARTIFACTS_DIR / "synthetic-monitor.json")
    provider_ablation = read_json_if_exists(ARTIFACTS_DIR / "provider-ablation.json")
    permission_boundary = read_json_if_exists(ARTIFACTS_DIR / "permission-boundary.json")

    registry = read_json_if_exists(VISIBILITY_DIR / "function-registry.json")

    runtime_timestamps = [
        parse_timestamp((scorecard or {}).get("generatedAt")),
        parse_timestamp((retrieval or {}).get("generatedAt")),
        parse_timestamp((scanner or {}).get("generatedAt")),
    ]
    freshest_runtime = max((ts for ts in runtime_timestamps if ts is not None), default=None)
    runtime_age = age_days(freshest_runtime)
    runtime_fresh = freshest_runtime is not None and runtime_age is not None and runtime_age <= 7

    visibility_ok = isinstance(registry, list) and len(registry) > 0
    non_internal = [entry for entry in (registry or []) if entry.get("exposure") != "internal-only"]
    mapped_ok = all(entry.get("frontendRoute") for entry in non_internal)
    role_ok = all(entry.get("requiredRole") for entry in non_internal)
    audit_ok = all(entry.get("auditEvent") for entry in non_internal)

    team_admin = [
        entry
        for entry in non_internal
        if entry.get("exposure") in {"team", "admin"}
    ]
    permission_ok = all(entry.get("requiredRole") not in {"", "user"} for entry in team_admin)
    permission_runtime_ok = bool(permission_boundary) and (permission_boundary or {}).get("summary", {}).get("failed", 1) == 0
    permission_focus = summarize_permission_focus(permission_boundary)
    retrieval_drift_ok = bool(retrieval) and (retrieval or {}).get("summary", {}).get("failedCases", 1) == 0 and len((retrieval or {}).get("driftErrors", [])) == 0

    async_paths = {
        "/packets/{packet_id}/backtest/run/async",
        "/packets/{packet_id}/report/async",
        "/scanner/run/async",
    }
    async_ok = {entry.get("path") for entry in (registry or [])}.issuperset(async_paths)
    synthetic_ok = bool(synthetic) and (synthetic or {}).get("summary", {}).get("failed", 1) == 0
    provider_ablation_ok = bool(provider_ablation) and len((provider_ablation or {}).get("modes", [])) > 0

    checklist = {
        "runtimeEvidenceFresh": {
            "passed": runtime_fresh,
            "detail": "Latest runtime evidence within 7 days" if runtime_fresh else "Runtime evidence missing or stale",
        },
        "metricsSnapshot": {
            "passed": bool((scorecard or {}).get("passed")),
            "detail": f"scorecard passed={bool((scorecard or {}).get('passed'))}",
        },
        "retrievalQualityDrift": {
            "passed": retrieval_drift_ok,
            "detail": (
                "retrieval benchmark cases pass and driftErrors is empty"
                if retrieval_drift_ok
                else "retrieval benchmark failed cases or driftErrors present"
            ),
        },
        "visibilityCoverage": {
            "passed": visibility_ok and mapped_ok and role_ok and audit_ok,
            "detail": "non-internal mappings include frontendRoute + requiredRole + auditEvent",
        },
        "nonInternalDiscoverability": {
            "passed": visibility_ok and mapped_ok,
            "detail": "all non-internal entries have visible frontend route",
        },
        "highestRiskCaptured": {
            "passed": True,
            "detail": "Top blockers generated automatically from failed checks",
        },
        "asyncWorkflowsObservable": {
            "passed": async_ok,
            "detail": "required async endpoints present in function registry",
        },
        "weeklyDeltaRecorded": {
            "passed": True,
            "detail": "weekly roadmap delta artifact generated",
        },
        "permissionBoundaries": {
            "passed": permission_ok and permission_runtime_ok,
            "detail": "team/admin metadata uses non-user role and runtime permission checks pass",
        },
        "permissionBoundaryFocus": {
            "passed": permission_focus["healthy"],
            "detail": permission_focus["detail"],
        },
        "releaseEvidenceComplete": {
            "passed": synthetic_ok and provider_ablation_ok,
            "detail": "synthetic monitor and provider ablation artifacts are present and valid",
        },
    }

    milestones = {
        "M1_85": {
            "ready": bool((m1 or {}).get("ready")),
            "evidence": "artifacts/m1-readiness.json",
        },
        "M2_91": {
            "ready": provider_ablation_ok and synthetic_ok and bool(checklist["visibilityCoverage"]["passed"]),
            "evidence": "provider ablation + synthetic monitor + visibility coverage",
        },
        "M3_96": {
            "ready": bool((scanner or {}).get("summary", {}).get("failedCases", 1) == 0),
            "evidence": "artifacts/scanner-benchmark.json",
        },
    }

    generated_at = datetime.now(UTC).isoformat()
    permission_focus_history = update_permission_focus_history(generated_at, permission_focus)
    permission_focus_trend = summarize_permission_focus_trend(permission_focus_history)

    report: dict[str, Any] = {
        "generatedAt": generated_at,
        "window": "weekly",
        "summary": {
            "runtimeEvidenceAgeDays": runtime_age,
            "checklistPassCount": sum(1 for item in checklist.values() if item["passed"]),
            "checklistTotal": len(checklist),
        },
        "checklist": checklist,
        "milestones": milestones,
        "phaseStatus": phase_status(
            milestones=milestones,
            checklist=checklist,
            registry=registry or [],
            scanner_artifact_present=bool(scanner),
        ),
        "evidence": {
            "m1Readiness": bool(m1),
            "retrievalBenchmark": bool(retrieval),
            "scorecardRuntime": bool(scorecard),
            "scannerBenchmark": bool(scanner),
            "syntheticMonitor": bool(synthetic),
            "syntheticMonitorHealthy": synthetic_ok,
            "providerAblation": bool(provider_ablation),
            "providerAblationHealthy": provider_ablation_ok,
            "permissionBoundary": bool(permission_boundary),
            "permissionBoundaryHealthy": permission_runtime_ok,
            "permissionBoundaryFocus": permission_focus,
            "permissionBoundaryFocusTrend": permission_focus_trend,
            "visibilityRegistry": visibility_ok,
        },
    }

    blockers = build_blockers(report)
    report["blockers"] = blockers

    report["nextSlice"] = (
        "Repair focused permission boundary checks and regenerate runtime boundary evidence."
        if not checklist["permissionBoundaryFocus"]["passed"]
        else (
            "Generate synthetic monitor and provider ablation artifacts, then re-run roadmap delta for M2 evidence closure."
            if blockers
            else "Advance to next milestone gate with current evidence package."
        )
    )

    md_lines: list[str] = []
    md_lines.append("# Weekly Roadmap Delta")
    md_lines.append("")
    md_lines.append(f"Generated: {report['generatedAt']}")
    md_lines.append("")
    md_lines.append("## Weekly Checklist")
    md_lines.append("")
    for key, item in checklist.items():
        md_lines.append(f"- {key}: {bool_status(item['passed']).upper()} ({item['detail']})")

    md_lines.append("")
    md_lines.append("## Permission Boundary Focus")
    md_lines.append("")
    md_lines.append(
        f"- passRate: {permission_focus['passRatePct']}% ({permission_focus['passed']}/{permission_focus['required']})"
    )
    md_lines.append(f"- status: {'HEALTHY' if permission_focus['healthy'] else 'DEGRADED'}")
    if permission_focus["missing"]:
        md_lines.append(f"- missingChecks: {', '.join(permission_focus['missing'])}")
    else:
        md_lines.append("- missingChecks: none")
    if permission_focus["failed"]:
        md_lines.append(f"- failedChecks: {', '.join(permission_focus['failed'])}")
    else:
        md_lines.append("- failedChecks: none")

    md_lines.append("")
    md_lines.append("## Permission Boundary Trend")
    md_lines.append("")
    md_lines.append(
        f"- latestPassRate: {permission_focus_trend['latestPassRatePct']}% ({permission_focus['passed']}/{permission_focus['required']})"
    )
    md_lines.append(f"- direction: {permission_focus_trend['direction']} ({permission_focus_trend['detail']})")
    md_lines.append(
        f"- runWindow: {permission_focus_trend['window']} (healthy={permission_focus_trend['healthyRuns']}, degraded={permission_focus_trend['degradedRuns']})"
    )

    md_lines.append("")
    md_lines.append("## Milestone Snapshot")
    md_lines.append("")
    for key, item in milestones.items():
        md_lines.append(f"- {key}: {'READY' if item['ready'] else 'NOT READY'} ({item['evidence']})")

    md_lines.append("")
    md_lines.append("## Phase Status")
    md_lines.append("")
    for phase, info in report["phaseStatus"].items():
        md_lines.append(f"- {phase}: {str(info['status']).upper()} ({info['detail']})")

    md_lines.append("")
    md_lines.append("## Top Blockers")
    md_lines.append("")
    if blockers:
        for blocker in blockers:
            md_lines.append(
                f"- {blocker['id']} {blocker['title']} | owner: {blocker['owner']} | mitigation: {blocker['mitigation']}"
            )
    else:
        md_lines.append("- None")

    md_lines.append("")
    md_lines.append("## Next Smallest Slice")
    md_lines.append("")
    md_lines.append(f"- {report['nextSlice']}")
    md_lines.append("")

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = ARTIFACTS_DIR / "weekly-roadmap-delta.json"
    md_path = ARTIFACTS_DIR / "weekly-roadmap-delta.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    if blockers:
        print("Top blockers:")
        for blocker in blockers:
            print(f"- {blocker['id']} {blocker['title']}")
    else:
        print("Top blockers: none")

    if args.strict and blockers:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
