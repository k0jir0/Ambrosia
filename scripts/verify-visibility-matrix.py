from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "apps" / "web" / "src" / "app"
BACKEND_FILES = [
    ROOT / "services" / "api" / "app" / "main.py",
    ROOT / "services" / "api" / "app" / "feedback_api.py",
]
REGISTRY_PATH = ROOT / "docs" / "visibility" / "function-registry.json"
MATRIX_PATH = ROOT / "docs" / "visibility" / "frontend-visibility-matrix.md"

ROUTE_PATTERN = re.compile(r'@(app|feedback_router)\.(get|post|patch|delete)\("([^"]+)"')
ROUTER_PREFIX_PATTERN = re.compile(r'feedback_router\s*=\s*APIRouter\(prefix="([^"]+)"')

EXPOSURE_ORDER = ["user", "advanced", "team", "admin", "internal-only"]
REQUIRED_SURFACES = {
    "advanced": "/advanced",
    "team": "/team",
    "admin": "/admin",
}


def collect_backend_routes(files: Iterable[Path]) -> list[dict[str, str]]:
    entries: dict[tuple[str, str], dict[str, str]] = {}
    for file_path in files:
        content = file_path.read_text(encoding="utf-8")
        router_prefix = ""
        prefix_match = ROUTER_PREFIX_PATTERN.search(content)
        if prefix_match:
            router_prefix = prefix_match.group(1)

        for router_name, method, path in ROUTE_PATTERN.findall(content):
            full_path = f"{router_prefix}{path}" if router_name == "feedback_router" else path
            entries[(method.upper(), full_path)] = {"method": method.upper(), "path": full_path}
    return sorted(entries.values(), key=lambda item: (item["path"], item["method"]))


def collect_frontend_routes(app_dir: Path) -> set[str]:
    routes: set[str] = set()
    for page_file in app_dir.rglob("page.tsx"):
        rel = page_file.relative_to(app_dir)
        route_parts = list(rel.parts[:-1])
        if not route_parts:
            routes.add("/")
            continue
        normalized_parts: list[str] = []
        for part in route_parts:
            if part.startswith("[") and part.endswith("]"):
                normalized_parts.append(f":{part[1:-1]}")
            else:
                normalized_parts.append(part)
        routes.add("/" + "/".join(normalized_parts))
    return routes


def classify_endpoint(path: str) -> tuple[str, str]:
    if path.startswith("/sandbox/"):
        return "advanced", "/advanced"
    if "/attribution/" in path:
        return "advanced", "/advanced"
    if path.startswith("/webhooks/"):
        return "internal-only", "internal"
    if path.startswith("/admin/"):
        return "admin", "/admin"
    if path.startswith("/workflows/templates"):
        return "admin", "/admin"
    if path.startswith("/workspaces") or path.endswith("/comments") or path.endswith("/approval"):
        return "team", "/team"
    if (
        path.startswith("/feedback/")
        or path.startswith("/providers/")
        or path.startswith("/tools/")
        or path.startswith("/alerts/")
        or path.startswith("/jobs")
        or path.startswith("/scanner/")
        or path.startswith("/visibility/")
        or path in {"/health", "/health/detailed", "/metrics", "/scorecard", "/market/providers/status"}
    ):
        return "advanced", "/advanced"
    return "user", infer_user_surface(path)


def infer_user_surface(path: str) -> str:
    if path.startswith("/market/") or path.startswith("/sentiment/"):
        return "/markets/:ticker"
    if path.startswith("/reviews"):
        return "/review/new"
    if path.startswith("/packets/"):
        return "/review/:id"
    return "/"


def generate_registry(routes: list[dict[str, str]]) -> list[dict[str, str]]:
    registry: list[dict[str, str]] = []
    for entry in routes:
        exposure, frontend_route = classify_endpoint(entry["path"])
        required_role = infer_required_role(entry["method"], entry["path"], exposure)
        audit_event = infer_audit_event(entry["method"], entry["path"])
        registry.append(
            {
                "method": entry["method"],
                "path": entry["path"],
                "exposure": exposure,
                "frontendRoute": frontend_route,
                "requiredRole": required_role,
                "auditEvent": audit_event,
            }
        )
    return sorted(registry, key=lambda item: (item["exposure"], item["path"], item["method"]))


def infer_required_role(method: str, path: str, exposure: str) -> str:
    if exposure == "internal-only":
        return "system"
    if exposure == "admin":
        return "admin"
    if exposure == "team":
        if path.endswith("/approval"):
            return "reviewer"
        if method == "GET":
            return "viewer"
        return "analyst"
    if exposure == "advanced":
        return "analyst"
    return "user"


def infer_audit_event(method: str, path: str) -> str:
    action_by_method = {
        "GET": "read",
        "POST": "write",
        "PATCH": "update",
        "DELETE": "delete",
    }
    action = action_by_method.get(method, "access")
    resource_segments = [
        segment for segment in path.strip("/").split("/") if segment and not segment.startswith("{")
    ]
    resource = ".".join(resource_segments[:3]) if resource_segments else "root"
    return f"{resource}.{action}"


def generate_matrix_markdown(registry: list[dict[str, str]], frontend_routes: set[str]) -> str:
    by_exposure: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in registry:
        by_exposure[row["exposure"]].append(row)

    lines: list[str] = []
    lines.append("# Frontend Visibility Matrix")
    lines.append("")
    lines.append("This file is generated by scripts/verify-visibility-matrix.py.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    for exposure in EXPOSURE_ORDER:
        count = len(by_exposure.get(exposure, []))
        lines.append(f"- {exposure}: {count} backend functions")

    lines.append("")
    lines.append("## Frontend Routes Detected")
    lines.append("")
    for route in sorted(frontend_routes):
        lines.append(f"- {route}")

    for exposure in EXPOSURE_ORDER:
        rows = by_exposure.get(exposure, [])
        if not rows:
            continue
        lines.append("")
        lines.append(f"## Exposure: {exposure}")
        lines.append("")
        lines.append("| Method | Path | Frontend Route | Required Role | Audit Event |")
        lines.append("| --- | --- | --- | --- | --- |")
        for row in rows:
            lines.append(
                f"| {row['method']} | {row['path']} | {row['frontendRoute']} | {row['requiredRole']} | {row['auditEvent']} |"
            )

    lines.append("")
    lines.append("## Policy")
    lines.append("")
    lines.append("- Non-internal functions must map to a visible frontend surface.")
    lines.append("- Every function includes required role and audit event metadata.")
    lines.append("- Team and Admin routes are boundary surfaces for privileged features.")
    lines.append("- Advanced route is the boundary surface for power-user operator functions.")
    lines.append("")
    return "\n".join(lines) + "\n"


def validate(registry: list[dict[str, str]], frontend_routes: set[str]) -> list[str]:
    errors: list[str] = []

    for exposure, required_route in REQUIRED_SURFACES.items():
        if required_route not in frontend_routes:
            errors.append(
                f"Missing required frontend surface {required_route} for exposure class '{exposure}'."
            )

    for row in registry:
        exposure = row["exposure"]
        frontend_route = row["frontendRoute"]
        if exposure == "internal-only":
            continue
        if not row.get("requiredRole"):
            errors.append(
                f"Missing requiredRole metadata: {row['method']} {row['path']}"
            )
        if not row.get("auditEvent"):
            errors.append(
                f"Missing auditEvent metadata: {row['method']} {row['path']}"
            )
        if frontend_route not in frontend_routes:
            errors.append(
                f"Unmapped visibility: {row['method']} {row['path']} -> {frontend_route} (route not found)."
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify frontend visibility matrix coverage.")
    parser.add_argument(
        "--write-artifacts",
        action="store_true",
        help="Write generated registry and matrix artifacts to docs/visibility.",
    )
    args = parser.parse_args()

    backend_routes = collect_backend_routes(BACKEND_FILES)
    frontend_routes = collect_frontend_routes(APP_DIR)
    registry = generate_registry(backend_routes)

    registry_json = json.dumps(registry, indent=2) + "\n"
    matrix_md = generate_matrix_markdown(registry, frontend_routes)

    errors = validate(registry, frontend_routes)
    if errors:
        print("Visibility validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    if args.write_artifacts:
        REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
        REGISTRY_PATH.write_text(registry_json, encoding="utf-8")
        MATRIX_PATH.write_text(matrix_md, encoding="utf-8")
        print(f"Wrote {REGISTRY_PATH.relative_to(ROOT)}")
        print(f"Wrote {MATRIX_PATH.relative_to(ROOT)}")
        return 0

    missing_artifacts = [
        str(path.relative_to(ROOT))
        for path in (REGISTRY_PATH, MATRIX_PATH)
        if not path.exists()
    ]
    if missing_artifacts:
        print("Missing visibility artifacts:")
        for path in missing_artifacts:
            print(f"- {path}")
        print("Run: python scripts/verify-visibility-matrix.py --write-artifacts")
        return 1

    if REGISTRY_PATH.read_text(encoding="utf-8") != registry_json:
        print("function-registry.json is out of date.")
        print("Run: python scripts/verify-visibility-matrix.py --write-artifacts")
        return 1

    if MATRIX_PATH.read_text(encoding="utf-8") != matrix_md:
        print("frontend-visibility-matrix.md is out of date.")
        print("Run: python scripts/verify-visibility-matrix.py --write-artifacts")
        return 1

    print("Visibility matrix verification passed.")
    print(f"Backend functions analyzed: {len(registry)}")
    print(f"Frontend routes analyzed: {len(frontend_routes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
