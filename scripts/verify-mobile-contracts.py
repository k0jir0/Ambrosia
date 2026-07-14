#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = ROOT / "packages" / "schemas" / "fixtures" / "mobile-control-plane.fixture.json"
MOBILE_API_PATH = ROOT / "apps" / "mobile" / "src" / "api.ts"
ARTIFACT_PATH = ROOT / "artifacts" / "mobile-api-contract.json"
GENERATED_TYPES_PATH = ROOT / "apps" / "mobile" / "src" / "generated" / "mobile-contract.ts"

BACKEND_FILES = [
    ROOT / "services" / "api" / "app" / "main.py",
    ROOT / "services" / "api" / "app" / "index84_platform.py",
    ROOT / "services" / "api" / "app" / "mobile_api.py",
]

MUTATING_METHODS = {"POST", "PATCH", "PUT", "DELETE"}
ALLOWED_METHODS = {"GET", "POST", "PATCH", "PUT", "DELETE"}
DECORATOR_PATTERN = re.compile(r"@(app|router)\.(get|post|patch|put|delete)\(\s*[\"']([^\"']+)[\"']")
ROUTER_PREFIX_PATTERN = re.compile(r"router\s*=\s*APIRouter\((?P<args>.*?)\)", re.DOTALL)
PREFIX_PATTERN = re.compile(r"prefix\s*=\s*[\"']([^\"']+)[\"']")
CLIENT_PATH_PATTERN = re.compile(r"([\"`])(/[^\"`]+)\1")
CLIENT_FUNCTION_PATTERN = re.compile(r"export\s+async\s+function\s+([A-Za-z0-9_]+)\s*\(")


def normalize_path(path: str) -> str:
    path = re.sub(r"\$\{[^}]+\}", "{param}", path)
    return re.sub(r"\{[^/{}]+\}", "{param}", path)


def load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def router_prefix(content: str) -> str:
    match = ROUTER_PREFIX_PATTERN.search(content)
    if not match:
        return ""
    prefix_match = PREFIX_PATTERN.search(match.group("args"))
    return prefix_match.group(1) if prefix_match else ""


def collect_backend_routes() -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    for file_path in BACKEND_FILES:
        content = file_path.read_text(encoding="utf-8")
        prefix = router_prefix(content)
        for router_name, method, path in DECORATOR_PATTERN.findall(content):
            full_path = f"{prefix}{path}" if router_name == "router" else path
            routes.add((method.upper(), normalize_path(full_path)))
    return routes


def collect_client_paths() -> set[str]:
    content = MOBILE_API_PATH.read_text(encoding="utf-8")
    return {
        normalize_path(path)
        for _, path in CLIENT_PATH_PATTERN.findall(content)
        if path.startswith("/")
    }


def collect_client_functions() -> set[str]:
    content = MOBILE_API_PATH.read_text(encoding="utf-8")
    return set(CLIENT_FUNCTION_PATTERN.findall(content))


def validate_contract(contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if contract.get("schemaVersion") != "mobile-control-plane.v1":
        errors.append("schemaVersion must be mobile-control-plane.v1")

    governance = contract.get("governance", {})
    expected_governance = {
        "backendSystemOfRecord": True,
        "humanDecisionAuthority": True,
        "llmInLiveOrderLoop": False,
        "finalDecisionsRequireServerConfirmation": True,
    }
    for key, expected in expected_governance.items():
        if governance.get(key) is not expected:
            errors.append(f"governance.{key} must be {expected}")

    routes = contract.get("routes", [])
    if not isinstance(routes, list) or not routes:
        errors.append("routes must be a non-empty list")
        return errors

    seen: set[tuple[str, str]] = set()
    for index, route in enumerate(routes):
        label = f"routes[{index}]"
        method = route.get("method")
        path = route.get("path")
        if method not in ALLOWED_METHODS:
            errors.append(f"{label}.method must be one of {sorted(ALLOWED_METHODS)}")
            continue
        if not isinstance(path, str) or not path.startswith("/"):
            errors.append(f"{label}.path must start with /")
            continue

        key = (method, normalize_path(path))
        if key in seen:
            errors.append(f"duplicate mobile route contract: {method} {path}")
        seen.add(key)

        mutating = route.get("mutating")
        requires_confirmation = route.get("requiresServerConfirmation")
        if mutating != (method in MUTATING_METHODS):
            errors.append(f"{method} {path} mutating must match method semantics")
        if method in MUTATING_METHODS and requires_confirmation is not True:
            errors.append(f"{method} {path} must require server confirmation")
        for field in ["mobileModule", "clientFunction", "sourceOfTruth", "purpose"]:
            if not route.get(field):
                errors.append(f"{method} {path} missing {field}")
        if route.get("sourceOfTruth") != "fastapi":
            errors.append(f"{method} {path} sourceOfTruth must be fastapi")

    return errors


def build_artifact(contract: dict[str, Any]) -> dict[str, Any]:
    routes = contract["routes"]
    by_module: dict[str, int] = {}
    mutating_routes = 0
    for route in routes:
        by_module[route["mobileModule"]] = by_module.get(route["mobileModule"], 0) + 1
        if route["mutating"]:
            mutating_routes += 1
    return {
        "schemaVersion": "mobile-api-contract-artifact.v1",
        "contract": str(CONTRACT_PATH.relative_to(ROOT)).replace("\\", "/"),
        "mobileClient": str(MOBILE_API_PATH.relative_to(ROOT)).replace("\\", "/"),
        "routeCount": len(routes),
        "mutatingRouteCount": mutating_routes,
        "readRouteCount": len(routes) - mutating_routes,
        "byModule": by_module,
        "governance": contract["governance"],
        "routes": routes,
    }

def expected_generated_types(contract: dict[str, Any]) -> str:
    lines = [
        "// Generated by scripts/generate-mobile-contract-types.py. Do not edit manually.",
        "",
        'export const mobileContractVersion = "mobile-control-plane.v1" as const;',
        "",
        "export type MobileContractRoute = {",
        '  method: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";',
        "  path: string;",
        "  mobileModule: string;",
        "  clientFunction: string;",
        '  sourceOfTruth: "fastapi";',
        "  purpose: string;",
        "  mutating: boolean;",
        "  requiresServerConfirmation: boolean;",
        "};",
        "",
        "export const mobileContractRoutes = [",
    ]
    for route in contract["routes"]:
        lines.extend(
            [
                "  {",
                f"    method: {json.dumps(route['method'])},",
                f"    path: {json.dumps(route['path'])},",
                f"    mobileModule: {json.dumps(route['mobileModule'])},",
                f"    clientFunction: {json.dumps(route['clientFunction'])},",
                '    sourceOfTruth: "fastapi",',
                f"    purpose: {json.dumps(route['purpose'])},",
                f"    mutating: {str(route['mutating']).lower()},",
                f"    requiresServerConfirmation: {str(route['requiresServerConfirmation']).lower()}",
                "  },",
            ]
        )
    lines.extend(
        [
            "] as const satisfies readonly MobileContractRoute[];",
            "",
            "export const mobileContractRouteCount = mobileContractRoutes.length;",
            "",
        ]
    )
    return "\n".join(lines)


def verify() -> tuple[dict[str, Any], list[str]]:
    contract = load_contract()
    errors = validate_contract(contract)
    backend_routes = collect_backend_routes()
    client_paths = collect_client_paths()
    client_functions = collect_client_functions()

    contract_routes = {
        (route["method"], normalize_path(route["path"]))
        for route in contract.get("routes", [])
        if route.get("method") in ALLOWED_METHODS and isinstance(route.get("path"), str)
    }
    contract_paths = {path for _, path in contract_routes}

    for method, path in sorted(contract_routes):
        if (method, path) not in backend_routes:
            errors.append(f"Contract route missing from backend decorators: {method} {path}")

    for path in sorted(client_paths):
        if path not in contract_paths:
            errors.append(f"Mobile API client path missing from contract: {path}")

    for route in contract.get("routes", []):
        client_function = route.get("clientFunction")
        if client_function not in client_functions:
            errors.append(f"Contract clientFunction missing from api.ts: {client_function}")

    expected_types = expected_generated_types(contract)
    if not GENERATED_TYPES_PATH.exists():
        errors.append(f"Missing generated mobile contract types: {GENERATED_TYPES_PATH.relative_to(ROOT)}")
    elif GENERATED_TYPES_PATH.read_text(encoding="utf-8") != expected_types:
        errors.append(
            f"{GENERATED_TYPES_PATH.relative_to(ROOT)} is stale. Run scripts/generate-mobile-contract-types.py"
        )

    return build_artifact(contract), errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Ambrosia mobile API contract coverage.")
    parser.add_argument("--write", action="store_true", help="Write artifacts/mobile-api-contract.json")
    parser.add_argument("--check", action="store_true", help="Fail if the artifact is missing or stale")
    args = parser.parse_args()

    artifact, errors = verify()
    if errors:
        print("Mobile contract verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    serialized = json.dumps(artifact, indent=2) + "\n"
    if args.write:
        ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
        ARTIFACT_PATH.write_text(serialized, encoding="utf-8")
        print(f"Wrote {ARTIFACT_PATH.relative_to(ROOT)} with {artifact['routeCount']} routes.")

    if args.check:
        if not ARTIFACT_PATH.exists():
            print(f"Missing {ARTIFACT_PATH.relative_to(ROOT)}. Run with --write.")
            return 1
        if ARTIFACT_PATH.read_text(encoding="utf-8") != serialized:
            print(f"{ARTIFACT_PATH.relative_to(ROOT)} is stale. Run with --write.")
            return 1
        print(f"Mobile contract check passed with {artifact['routeCount']} routes.")

    if not args.write and not args.check:
        print(serialized)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
