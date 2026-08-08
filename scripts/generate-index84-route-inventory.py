#!/usr/bin/env python3
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
API_ROOT = ROOT / "services" / "api"
ARTIFACT_PATH = ROOT / "artifacts" / "index84-route-inventory.json"
OPENAPI_DIR = ROOT / "artifacts" / "openapi"

if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from fastapi.routing import APIRoute  # noqa: E402
from app.main import app  # noqa: E402

EXPOSURE_ORDER = ["public", "advanced", "team", "admin", "internal-only"]
OPENAPI_EXPOSURES = {
    "public": {"public"},
    "advanced": {"public", "advanced"},
    "team": {"public", "advanced", "team"},
    "admin": {"public", "advanced", "team", "admin"},
    "internal": {"public", "advanced", "team", "admin", "internal-only"},
}
MUTATING_METHODS = {"POST", "PATCH", "PUT", "DELETE"}
PUBLIC_BOOTSTRAP_PATHS = {
    "/",
    "/health",
    "/live",
    "/ready",
    "/auth/signup",
    "/auth/login",
    "/auth/verify-email",
    "/auth/resend-verification",
    "/auth/accept-invite",
    "/auth/forgot-password",
    "/auth/reset-password",
}


def classify_path(path: str) -> str:
    if path.startswith("/webhooks/"):
        return "internal-only"
    if path.startswith("/local-worker/"):
        return "internal-only"
    if path in PUBLIC_BOOTSTRAP_PATHS:
        return "public"
    if path.startswith("/admin/"):
        return "admin"
    if path == "/analytics/activation" or path.startswith("/llm/workers"):
        return "admin"
    if path.startswith(("/analytics/", "/artifacts", "/llm/")):
        return "team"
    if path.startswith("/governance/") or path.startswith("/ci-cd/"):
        return "admin"
    if path.startswith(("/auth/", "/team")):
        return "team"
    if path.startswith("/workspaces") or path.endswith("/comments") or path.endswith("/approval"):
        return "team"
    if path.startswith("/alerts/") or path.startswith("/workflow") or path.startswith("/workflows/"):
        return "team"
    if path.startswith("/sandbox/") or path.startswith("/execution/") or path.startswith("/market/sandbox/"):
        return "advanced"
    if any(segment in path for segment in ["/agents/", "/retrieve", "/backtest/", "/risk/"]):
        return "advanced"
    if path.startswith("/scanner/") or path.startswith("/discovery") or path.startswith("/jobs"):
        return "advanced"
    if path.startswith("/visibility/") or path.startswith("/tools/") or path.startswith("/providers/"):
        return "advanced"
    if path in {"/health/detailed", "/metrics", "/scorecard", "/market/providers/status"}:
        return "advanced"
    # The production request boundary authenticates every route that is not in
    # the exact bootstrap allowlist above. Keep generated OpenAPI exposure in
    # sync: product routes are tenant-scoped, never anonymously public merely
    # because they do not belong to an advanced module.
    return "team"


def frontend_route_for(path: str, exposure: str) -> str:
    if exposure == "internal-only":
        return "internal"
    if exposure == "admin":
        return "/admin"
    if exposure == "team":
        return "/team"
    if path.startswith("/market/") or path.startswith("/sentiment/"):
        return "/markets/[ticker]"
    if path.startswith("/reviews"):
        return "/review/new"
    if path.startswith("/packets"):
        return "/review/[id]"
    if path.startswith("/roadmap"):
        return "/advanced"
    if exposure == "advanced":
        return "/advanced"
    return "/"


def required_scope(method: str, exposure: str) -> str:
    if exposure == "internal-only":
        return "system"
    if exposure == "admin":
        return "admin:write" if method in MUTATING_METHODS else "admin:read"
    if exposure == "team":
        return "team:write" if method in MUTATING_METHODS else "team:read"
    if exposure == "advanced":
        return "advanced:write" if method in MUTATING_METHODS else "advanced:read"
    return "public:write" if method in MUTATING_METHODS else "public:read"


def audit_event_for(method: str, path: str) -> str:
    action = {
        "GET": "read",
        "POST": "write",
        "PATCH": "update",
        "PUT": "replace",
        "DELETE": "delete",
    }.get(method, "access")
    resource = ".".join(
        segment for segment in path.strip("/").split("/")[:3] if segment and not segment.startswith("{")
    )
    return f"{resource or 'root'}.{action}"


def idempotency_policy(method: str, path: str, exposure: str) -> str:
    if method not in MUTATING_METHODS:
        return "not_applicable"
    if exposure == "internal-only":
        return "integration_signature_required"
    if path.startswith(("/reviews", "/packets", "/roadmap", "/workspaces", "/admin", "/sandbox")):
        return "required"
    return "planned"


def response_model_name(route: APIRoute) -> str:
    model = route.response_model
    if model is None:
        return "dict"
    return getattr(model, "__name__", str(model).replace("typing.", ""))


def route_record(route: APIRoute, method: str) -> dict[str, Any]:
    exposure = classify_path(route.path)
    idempotency = idempotency_policy(method, route.path, exposure)
    sdk_candidate = exposure in {"public", "advanced", "team"} and exposure != "internal-only"
    cli_candidate = method == "GET" and exposure in {"public", "advanced", "team"}
    return {
        "method": method,
        "path": route.path,
        "name": route.name,
        "exposure": exposure,
        "authScope": required_scope(method, exposure),
        "responseModel": response_model_name(route),
        "errorShape": "standard_error_envelope_planned",
        "auditEvent": audit_event_for(method, route.path),
        "idempotencyPolicy": idempotency,
        "frontendRoute": frontend_route_for(route.path, exposure),
        "sdkCandidate": sdk_candidate,
        "cliCandidate": cli_candidate,
    }


def build_inventory() -> dict[str, Any]:
    routes: list[dict[str, Any]] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in sorted(route.methods or []):
            if method in {"HEAD", "OPTIONS"}:
                continue
            routes.append(route_record(route, method))

    routes.sort(key=lambda item: (EXPOSURE_ORDER.index(item["exposure"]), item["path"], item["method"]))
    summary = {exposure: 0 for exposure in EXPOSURE_ORDER}
    for route in routes:
        summary[route["exposure"]] += 1

    return {
        "version": "index84-route-inventory.v1",
        "routeCount": len(routes),
        "summary": summary,
        "routes": routes,
    }


def build_openapi_documents(inventory: dict[str, Any]) -> dict[str, dict[str, Any]]:
    base_schema = app.openapi()
    operation_index = {
        (route["path"], route["method"].lower()): route for route in inventory["routes"]
    }
    documents: dict[str, dict[str, Any]] = {}

    for exposure_name, allowed_exposures in OPENAPI_EXPOSURES.items():
        schema = deepcopy(base_schema)
        schema["info"] = {
            **schema.get("info", {}),
            "title": f"Ambrosia Trade Review API ({exposure_name})",
            "x-ambrosia-exposure": exposure_name,
        }
        filtered_paths: dict[str, Any] = {}
        for path, operations in schema.get("paths", {}).items():
            kept_operations: dict[str, Any] = {}
            for method, operation in operations.items():
                route = operation_index.get((path, method.lower()))
                if route is None or route["exposure"] not in allowed_exposures:
                    continue
                operation["x-ambrosia-exposure"] = route["exposure"]
                operation["x-ambrosia-auth-scope"] = route["authScope"]
                operation["x-ambrosia-audit-event"] = route["auditEvent"]
                operation["x-ambrosia-idempotency-policy"] = route["idempotencyPolicy"]
                kept_operations[method] = operation
            if kept_operations:
                filtered_paths[path] = kept_operations
        schema["paths"] = filtered_paths
        schema["x-ambrosia-route-count"] = sum(len(operations) for operations in filtered_paths.values())
        documents[exposure_name] = schema

    return documents


def write_openapi_documents(documents: dict[str, dict[str, Any]]) -> None:
    OPENAPI_DIR.mkdir(parents=True, exist_ok=True)
    for exposure_name, schema in documents.items():
        path = OPENAPI_DIR / f"{exposure_name}.json"
        path.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")


def check_openapi_documents(documents: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for exposure_name, schema in documents.items():
        path = OPENAPI_DIR / f"{exposure_name}.json"
        serialized = json.dumps(schema, indent=2) + "\n"
        if not path.exists():
            errors.append(f"Missing {path.relative_to(ROOT)}. Run with --write-openapi.")
        elif path.read_text(encoding="utf-8") != serialized:
            errors.append(f"{path.relative_to(ROOT)} is stale. Run with --write-openapi.")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the Index84 route inventory artifact.")
    parser.add_argument("--write", action="store_true", help="Write artifacts/index84-route-inventory.json")
    parser.add_argument("--check", action="store_true", help="Fail if the committed artifact is missing or stale")
    parser.add_argument("--write-openapi", action="store_true", help="Write exposure-filtered OpenAPI artifacts")
    parser.add_argument("--check-openapi", action="store_true", help="Fail if OpenAPI artifacts are missing or stale")
    args = parser.parse_args()

    inventory = build_inventory()
    serialized = json.dumps(inventory, indent=2) + "\n"
    openapi_documents = build_openapi_documents(inventory)

    if args.write:
        ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
        ARTIFACT_PATH.write_text(serialized, encoding="utf-8")
        print(f"Wrote {ARTIFACT_PATH.relative_to(ROOT)} with {inventory['routeCount']} routes.")

    if args.write_openapi:
        write_openapi_documents(openapi_documents)
        print(f"Wrote {len(openapi_documents)} OpenAPI exposure artifacts to {OPENAPI_DIR.relative_to(ROOT)}.")

    if args.check:
        if not ARTIFACT_PATH.exists():
            print(f"Missing {ARTIFACT_PATH.relative_to(ROOT)}. Run with --write.")
            return 1
        if ARTIFACT_PATH.read_text(encoding="utf-8") != serialized:
            print(f"{ARTIFACT_PATH.relative_to(ROOT)} is stale. Run with --write.")
            return 1
        print(f"Route inventory check passed with {inventory['routeCount']} routes.")

    if args.check_openapi:
        errors = check_openapi_documents(openapi_documents)
        if errors:
            for error in errors:
                print(error)
            return 1
        print(f"OpenAPI exposure artifact check passed for {len(openapi_documents)} documents.")

    if args.write or args.write_openapi or args.check or args.check_openapi:
        return 0

    print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
