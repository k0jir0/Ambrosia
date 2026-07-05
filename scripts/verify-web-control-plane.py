#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "apps" / "web" / "src" / "app"
MATRIX_PATH = ROOT / "docs" / "roadmap" / "frontend-control-plane-matrix.md"
PLAYWRIGHT_SPEC = ROOT / "apps" / "web" / "tests" / "workbench.spec.ts"
ARTIFACT_PATH = ROOT / "artifacts" / "web-control-plane-evidence.json"

ROUTES = {
    "/": "page.tsx",
    "/review/new": "review/new/page.tsx",
    "/review/[id]": "review/[id]/page.tsx",
    "/history": "history/page.tsx",
    "/markets/[ticker]": "markets/[ticker]/page.tsx",
    "/calibration": "calibration/page.tsx",
    "/advanced": "advanced/page.tsx",
    "/admin": "admin/page.tsx",
    "/governance/team-management": "governance/team-management/page.tsx",
    "/discovery": "discovery/page.tsx",
    "/reports/export": "reports/export/page.tsx",
}

STATE_TERMS = ["loading", "empty", "stale", "degraded", "fallback", "forbidden", "success"]
UX_TERMS = ["Primary Action", "Required States", "Evidence", "keyboard-only", "Web Vitals", "audit"]


def main() -> int:
    matrix = MATRIX_PATH.read_text(encoding="utf-8")
    spec = PLAYWRIGHT_SPEC.read_text(encoding="utf-8")
    route_results = []
    errors: list[str] = []

    for route, page in ROUTES.items():
        page_path = APP_DIR / page
        matrix_present = f"| `{route}` |" in matrix
        page_present = page_path.exists()
        if not matrix_present:
            errors.append(f"Missing frontend matrix entry for {route}")
        if not page_present:
            errors.append(f"Missing page file for {route}: {page}")
        route_results.append(
            {
                "route": route,
                "page": str(page_path.relative_to(ROOT)),
                "pagePresent": page_present,
                "matrixPresent": matrix_present,
            }
        )

    missing_state_terms = [term for term in STATE_TERMS if term not in matrix]
    missing_ux_terms = [term for term in UX_TERMS if term not in matrix]
    if missing_state_terms:
        errors.append(f"Matrix missing state terms: {', '.join(missing_state_terms)}")
    if missing_ux_terms:
        errors.append(f"Matrix missing UX terms: {', '.join(missing_ux_terms)}")

    baseline_tests = {
        "dashboard": "dashboard is the default entry point" in spec,
        "reviewCreation": "new review creates an archive record" in spec,
        "workbench": "review route uses focused decision workbench" in spec,
        "history": "history" in spec and "Open" in spec,
        "markets": "markets route renders ticker-bound charting workspace" in spec,
        "commandPalette": "command palette opens" in spec,
        "darkMode": "dark mode is the default visual mode" in spec,
    }
    for name, present in baseline_tests.items():
        if not present:
            errors.append(f"Missing Playwright baseline marker: {name}")

    artifact = {
        "status": "failed" if errors else "passed",
        "routeCount": len(route_results),
        "routes": route_results,
        "stateTerms": {term: term in matrix for term in STATE_TERMS},
        "uxTerms": {term: term in matrix for term in UX_TERMS},
        "baselineTests": baseline_tests,
        "errors": errors,
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")

    if errors:
        print("Web control-plane verification failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"Web control-plane verification passed. Wrote {ARTIFACT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())