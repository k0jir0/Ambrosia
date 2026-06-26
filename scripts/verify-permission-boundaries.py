#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = ROOT / "docs" / "visibility" / "function-registry.json"


@dataclass
class BoundaryCheck:
    name: str
    method: str
    endpoint: str
    role: str
    expectedStatus: int
    actualStatus: int
    passed: bool
    detail: str


def request_json(
    base_url: str,
    method: str,
    endpoint: str,
    *,
    role: str | None = None,
    body: dict | None = None,
) -> tuple[int, str, dict | list | None]:
    url = f"{base_url.rstrip('/')}{endpoint}"
    headers: dict[str, str] = {"Accept": "application/json"}
    payload: bytes | None = None

    if role:
        headers["X-Ambrosia-Role"] = role

    if body is not None:
        headers["Content-Type"] = "application/json"
        payload = json.dumps(body).encode("utf-8")

    req = Request(url, headers=headers, data=payload, method=method)

    try:
        with urlopen(req, timeout=20) as response:
            status = int(response.status)
            raw = response.read().decode("utf-8")
            parsed = json.loads(raw) if raw else None
            return status, f"HTTP {status}", parsed
    except HTTPError as exc:
        parsed: dict | list | None = None
        try:
            raw = exc.read().decode("utf-8")
            parsed = json.loads(raw) if raw else None
        except Exception:
            parsed = None
        return int(exc.code), f"HTTPError {exc.code}", parsed
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        return 0, f"request failed: {exc}", None


def request_status(
    base_url: str,
    method: str,
    endpoint: str,
    *,
    role: str | None = None,
    body: dict | None = None,
) -> tuple[int, str]:
    status, detail, _payload = request_json(
        base_url,
        method,
        endpoint,
        role=role,
        body=body,
    )
    return status, detail


def _minimal_packet_payload(packet_id: str) -> dict:
    return {
        "id": packet_id,
        "title": "Boundary Packet",
        "thesis": "Boundary verification packet",
        "ticker": "SPY",
        "assetClass": "ETF",
        "timeHorizon": "2-6 weeks",
        "intendedExpression": "Long ETF",
        "status": "synthesis",
        "decisionState": "watch",
        "confidence": 65,
        "trialCountImpact": 1,
        "followUpDate": "2026-07-15",
        "createdAt": "2026-06-25T10:00:00Z",
        "claims": [{"id": "c1", "kind": "sourced", "text": "boundary claim", "confidence": 70}],
        "strongestCritique": "macro headwinds",
        "disconfirmingTest": "underperform for 10 sessions",
        "historicalAnalogue": {
            "title": "early cycle",
            "similarity": "breadth",
            "differences": "rates",
            "resolution": "stop",
        },
        "validation": {
            "status": "specified",
            "hypothesis": "SPY outperforms",
            "nullHypothesis": "no alpha",
            "dataRequirements": ["returns"],
            "protocol": "20-day rolling",
            "refusalReason": None,
        },
        "tradeability": [{"topic": "liquidity", "question": "enough?", "severity": "low"}],
        "sources": [{
            "id": "s1",
            "title": "boundary source",
            "sourceType": "internal",
            "timestamp": "2026-06-25T09:00:00Z",
            "permission": "user_owned",
            "relevance": 0.9,
        }],
        "audit": [{"id": "a1", "timestamp": "10:00:00", "eventType": "packet.created", "detail": "boundary"}],
    }


def _seed_context(base_url: str, unique: str) -> dict[str, str]:
    context: dict[str, str] = {
        "packet_id": f"boundary-pkt-{unique}",
        "workspace_id": "ws-missing",
        "template_id": "tpl-missing",
        "profile_id": "grp-balanced-default",
        "feedback_id": "fb-missing",
        "job_id": "job-missing",
    }

    request_json(base_url, "POST", "/packets", body=_minimal_packet_payload(context["packet_id"]))

    ws_status, _ws_detail, ws_payload = request_json(
        base_url,
        "POST",
        "/workspaces",
        role="analyst",
        body={"name": f"Boundary Workspace {unique}", "ownerId": "boundary-analyst"},
    )
    if ws_status == 200 and isinstance(ws_payload, dict) and ws_payload.get("id"):
        context["workspace_id"] = str(ws_payload["id"])

    tpl_status, _tpl_detail, tpl_payload = request_json(
        base_url,
        "POST",
        "/workflows/templates",
        role="admin",
        body={
            "name": f"Boundary Template {unique}",
            "version": "1.0.0",
            "description": "Boundary test template",
            "category": "custom",
            "steps": [],
            "authorId": "boundary-admin",
        },
    )
    if tpl_status == 200 and isinstance(tpl_payload, dict) and tpl_payload.get("id"):
        context["template_id"] = str(tpl_payload["id"])

    profile_status, _profile_detail, profile_payload = request_json(
        base_url,
        "POST",
        "/admin/policies",
        role="admin",
        body={
            "name": f"Boundary Policy {unique}",
            "description": "Boundary test profile",
            "riskTolerance": "balanced",
            "maxPositionSizePct": 10,
            "maxPortfolioDrawdownPct": 12,
            "refusalSensitivity": 65,
            "allowLiveMutation": False,
            "requiresTwoPersonApproval": True,
            "updatedBy": "boundary-admin",
        },
    )
    if profile_status == 200 and isinstance(profile_payload, dict) and profile_payload.get("id"):
        context["profile_id"] = str(profile_payload["id"])

    return context


def _load_registry_entries() -> list[dict]:
    if not REGISTRY_PATH.exists():
        return []
    raw = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        return []
    return [entry for entry in raw if isinstance(entry, dict)]


def _materialize_path(path: str, context: dict[str, str]) -> str:
    return (
        path.replace("{packet_id}", context["packet_id"])
        .replace("{workspace_id}", context["workspace_id"])
        .replace("{template_id}", context["template_id"])
        .replace("{profile_id}", context["profile_id"])
        .replace("{feedback_id}", context["feedback_id"])
        .replace("{job_id}", context["job_id"])
    )


def _request_body(method: str, path: str, context: dict[str, str], unique: str) -> dict | None:
    if method == "POST" and path == "/workspaces":
        return {"name": f"Boundary Workspace Op {unique}", "ownerId": "boundary-analyst"}
    if method == "POST" and path == "/workspaces/{workspace_id}/packets":
        return {"packetId": context["packet_id"]}
    if method == "POST" and path == "/packets/{packet_id}/comments":
        return {"authorId": "boundary-analyst", "content": "boundary comment", "commentType": "general"}
    if method == "POST" and path == "/packets/{packet_id}/approval":
        return {"reviewerId": "boundary-reviewer", "decision": "approved", "note": "boundary approval"}
    if method == "POST" and path == "/workflows/templates":
        return {
            "name": f"Boundary Template Op {unique}",
            "version": "1.0.0",
            "description": "Boundary operation template",
            "category": "custom",
            "steps": [],
            "authorId": "boundary-admin",
        }
    if method == "POST" and path == "/admin/policies":
        return {
            "name": f"Boundary Policy Op {unique}",
            "description": "Boundary operation profile",
            "riskTolerance": "balanced",
            "maxPositionSizePct": 10,
            "maxPortfolioDrawdownPct": 12,
            "refusalSensitivity": 65,
            "allowLiveMutation": False,
            "requiresTwoPersonApproval": True,
            "updatedBy": "boundary-admin",
        }
    if method == "PATCH" and path == "/admin/policies/{profile_id}/activate":
        return {"updatedBy": "boundary-admin"}
    return None


def _role_for_denied(exposure: str) -> str:
    return "analyst" if exposure == "admin" else "user"


def _check_allowed_status(status: int) -> bool:
    return status not in {0, 401, 403}


def _slug(path: str) -> str:
    cleaned = path.strip("/").replace("/", "_").replace("{", "").replace("}", "")
    return cleaned or "root"


def _build_registry_coverage_checks(base_url: str, unique: str) -> list[BoundaryCheck]:
    context = _seed_context(base_url, unique)
    entries = [
        entry
        for entry in _load_registry_entries()
        if entry.get("exposure") in {"team", "admin"}
    ]

    checks: list[BoundaryCheck] = []
    for entry in entries:
        method = str(entry.get("method", "GET")).upper()
        raw_path = str(entry.get("path", ""))
        exposure = str(entry.get("exposure", ""))
        required_role = str(entry.get("requiredRole", ""))
        endpoint = _materialize_path(raw_path, context)
        body = _request_body(method, raw_path, context, unique)
        slug = _slug(raw_path)

        denied_role = _role_for_denied(exposure)
        denied_status, denied_detail = request_status(
            base_url,
            method,
            endpoint,
            role=denied_role,
            body=body,
        )
        checks.append(
            BoundaryCheck(
                name=f"registry_{exposure}_{method.lower()}_{slug}_denied",
                method=method,
                endpoint=endpoint,
                role=denied_role,
                expectedStatus=403,
                actualStatus=denied_status,
                passed=denied_status == 403,
                detail=f"{denied_detail} | requiredRole={required_role}",
            )
        )

        allowed_status, allowed_detail = request_status(
            base_url,
            method,
            endpoint,
            role=required_role,
            body=body,
        )
        checks.append(
            BoundaryCheck(
                name=f"registry_{exposure}_{method.lower()}_{slug}_allowed",
                method=method,
                endpoint=endpoint,
                role=required_role,
                expectedStatus=200,
                actualStatus=allowed_status,
                passed=_check_allowed_status(allowed_status),
                detail=f"{allowed_detail} | allowed if not 401/403",
            )
        )

    return checks


def build_checks(base_url: str) -> list[BoundaryCheck]:
    unique = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    checks_spec = [
        {
            "name": "advanced_registry_denies_missing_role",
            "method": "GET",
            "endpoint": "/visibility/function-registry",
            "role": None,
            "expected": 403,
            "body": None,
        },
        {
            "name": "advanced_registry_allows_analyst",
            "method": "GET",
            "endpoint": "/visibility/function-registry",
            "role": "analyst",
            "expected": 200,
            "body": None,
        },
        {
            "name": "advanced_frontend_matrix_denies_missing_role",
            "method": "GET",
            "endpoint": "/visibility/frontend-matrix",
            "role": None,
            "expected": 403,
            "body": None,
        },
        {
            "name": "advanced_frontend_matrix_allows_analyst",
            "method": "GET",
            "endpoint": "/visibility/frontend-matrix",
            "role": "analyst",
            "expected": 200,
            "body": None,
        },
        {
            "name": "sandbox_positions_denies_viewer",
            "method": "GET",
            "endpoint": "/sandbox/positions",
            "role": "viewer",
            "expected": 403,
            "body": None,
        },
        {
            "name": "sandbox_positions_allows_analyst",
            "method": "GET",
            "endpoint": "/sandbox/positions",
            "role": "analyst",
            "expected": 200,
            "body": None,
        },
        {
            "name": "workspaces_list_denies_missing_role",
            "method": "GET",
            "endpoint": "/workspaces",
            "role": None,
            "expected": 403,
            "body": None,
        },
        {
            "name": "workspaces_list_allows_viewer",
            "method": "GET",
            "endpoint": "/workspaces",
            "role": "viewer",
            "expected": 200,
            "body": None,
        },
        {
            "name": "workspaces_create_denies_viewer",
            "method": "POST",
            "endpoint": "/workspaces",
            "role": "viewer",
            "expected": 403,
            "body": {
                "name": f"Boundary Viewer Denied {unique}",
                "ownerId": "boundary-viewer",
            },
        },
        {
            "name": "workspaces_create_allows_analyst",
            "method": "POST",
            "endpoint": "/workspaces",
            "role": "analyst",
            "expected": 200,
            "body": {
                "name": f"Boundary Analyst Allowed {unique}",
                "ownerId": "boundary-analyst",
            },
        },
        {
            "name": "admin_policies_denies_analyst",
            "method": "GET",
            "endpoint": "/admin/policies",
            "role": "analyst",
            "expected": 403,
            "body": None,
        },
        {
            "name": "admin_policies_allows_admin",
            "method": "GET",
            "endpoint": "/admin/policies",
            "role": "admin",
            "expected": 200,
            "body": None,
        },
        {
            "name": "admin_audit_denies_analyst",
            "method": "GET",
            "endpoint": "/admin/audit",
            "role": "analyst",
            "expected": 403,
            "body": None,
        },
        {
            "name": "admin_audit_allows_admin",
            "method": "GET",
            "endpoint": "/admin/audit",
            "role": "admin",
            "expected": 200,
            "body": None,
        },
        {
            "name": "admin_boundary_rules_denies_analyst",
            "method": "GET",
            "endpoint": "/admin/boundary-rules",
            "role": "analyst",
            "expected": 403,
            "body": None,
        },
        {
            "name": "admin_boundary_rules_allows_admin",
            "method": "GET",
            "endpoint": "/admin/boundary-rules",
            "role": "admin",
            "expected": 200,
            "body": None,
        },
    ]

    checks: list[BoundaryCheck] = []
    for spec in checks_spec:
        status, detail = request_status(
            base_url,
            spec["method"],
            spec["endpoint"],
            role=spec["role"],
            body=spec["body"],
        )
        checks.append(
            BoundaryCheck(
                name=spec["name"],
                method=spec["method"],
                endpoint=spec["endpoint"],
                role=spec["role"] or "missing",
                expectedStatus=spec["expected"],
                actualStatus=status,
                passed=status == spec["expected"],
                detail=detail,
            )
        )

    checks.extend(_build_registry_coverage_checks(base_url, unique))

    return checks


def build_markdown(base_url: str, checks: list[BoundaryCheck]) -> str:
    passed = sum(1 for check in checks if check.passed)
    lines: list[str] = []
    lines.append("# Permission Boundary Verification")
    lines.append("")
    lines.append(f"Generated: {datetime.now(UTC).isoformat()}")
    lines.append(f"Base URL: {base_url}")
    lines.append(f"Passed checks: {passed}/{len(checks)}")
    lines.append("")
    lines.append("| Check | Method | Endpoint | Role | Expected | Actual | Status | Detail |")
    lines.append("| --- | --- | --- | --- | ---: | ---: | --- | --- |")
    for check in checks:
        lines.append(
            f"| {check.name} | {check.method} | {check.endpoint} | {check.role} | {check.expectedStatus} | {check.actualStatus} | {'PASS' if check.passed else 'FAIL'} | {check.detail} |"
        )
    lines.append("")
    lines.append("## Policy")
    lines.append("")
    lines.append("- Advanced surfaces require analyst-or-higher role headers.")
    lines.append("- Team write actions deny viewer and allow analyst-or-higher.")
    lines.append("- Admin surfaces deny non-admin roles and allow admin.")
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Team/Admin permission boundaries against runtime API.")
    parser.add_argument(
        "--base-url",
        default=os.getenv("AMBROSIA_API_BASE_URL", ""),
        help="Base API URL to probe, e.g. http://127.0.0.1:8000",
    )
    parser.add_argument(
        "--output-json",
        default="artifacts/permission-boundary.json",
        help="Path to JSON report artifact",
    )
    parser.add_argument(
        "--output-md",
        default="artifacts/permission-boundary.md",
        help="Path to markdown report artifact",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = args.base_url.strip()
    if not base_url:
        print("Missing --base-url or AMBROSIA_API_BASE_URL", file=sys.stderr)
        return 2

    checks = build_checks(base_url)
    passed = sum(1 for check in checks if check.passed)
    failed = len(checks) - passed

    output_json = Path(args.output_json)
    output_md = Path(args.output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)

    output_json.write_text(
        json.dumps(
            {
                "generatedAt": datetime.now(UTC).isoformat(),
                "baseUrl": base_url,
                "summary": {
                    "passed": passed,
                    "failed": failed,
                    "total": len(checks),
                    "registryCoverageChecks": len([c for c in checks if c.name.startswith("registry_")]),
                },
                "checks": [asdict(check) for check in checks],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    output_md.write_text(build_markdown(base_url, checks), encoding="utf-8")

    print(f"Wrote {output_json}")
    print(f"Wrote {output_md}")
    for check in checks:
        state = "PASS" if check.passed else "FAIL"
        print(
            f"- {state} {check.name} role={check.role} expected={check.expectedStatus} actual={check.actualStatus}"
        )

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
