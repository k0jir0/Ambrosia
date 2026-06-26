from __future__ import annotations

import json
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def read_json(relative_path: str) -> dict:
    return json.loads(read_text(relative_path))


class StackContractTests(unittest.TestCase):
    def test_root_scripts_match_current_stack(self) -> None:
        package = read_json("package.json")

        self.assertEqual(package["packageManager"], "pnpm@9.12.0")
        self.assertEqual(package["engines"]["node"], ">=20.0.0")

        scripts = package["scripts"]
        for script in [
            "dev:web",
            "build:web",
            "lint:web",
            "test:e2e",
            "dev:api",
            "test:api",
            "lint:api",
            "test:stack",
        ]:
            self.assertIn(script, scripts)

        self.assertIn("pnpm --filter @ambrosia/web", scripts["dev:web"])
        self.assertIn("uvicorn app.main:app", scripts["dev:api"])
        self.assertIn("python -m unittest discover -s tests", scripts["test:stack"])

    def test_frontend_review_lifecycle_and_agentic_workflow_are_wired(self) -> None:
        api_client = read_text("apps/web/src/lib/api.ts")
        review_store = read_text("apps/web/src/lib/review-store.ts")
        workbench = read_text("apps/web/src/components/workbench.tsx")
        new_review_page = read_text("apps/web/src/app/review/new/page.tsx")

        for expected in [
            "NEXT_PUBLIC_API_BASE_URL",
            "NEXT_PUBLIC_API_URL",
            "createReview",
            "listReviews",
            "getReview",
            "runPacketAgents",
            "/packets",
            "/agents/run",
        ]:
            self.assertIn(expected, api_client)

        for expected in ["loadReviewArchive", "createReviewRecord", "resolveReview", "upsertLocalReview"]:
            self.assertIn(expected, review_store)

        for expected in [
            "Run analysis",
            "buildPacketShell",
            "ensurePacketForReview",
            "DecisionStrip",
            "MarketAndRiskPanel",
            "RunbookStrip",
            "ProviderProvenancePanel",
            "expectedAgentRoles",
        ]:
            self.assertIn(expected, workbench)

        self.assertIn("createReviewRecord", new_review_page)
        self.assertIn("router.push(`/review/${encodeURIComponent(review.id)}`)", new_review_page)

    def test_operating_model_copy_is_global_sidebar_content(self) -> None:
        app_shell = read_text("apps/web/src/components/app-shell.tsx")
        advanced_page = read_text("apps/web/src/app/advanced/page.tsx")
        dashboard = read_text("apps/web/src/components/dashboard-page.tsx")

        self.assertIn("<OperatingModelPanel />", app_shell)
        self.assertIn('href: "/advanced"', app_shell)
        self.assertIn("Operator and instrumentation surface", advanced_page)
        self.assertLess(app_shell.index('href: "/admin"'), app_shell.index('href: "/advanced"'))
        self.assertLess(app_shell.index("NavSection items={bottom}"), app_shell.index("<OperatingModelPanel />"))
        for expected in [
            "Agentic AI for Investments",
            "Investment Trading Decisions",
            "Swarm Intelligence",
            "Agentic Swarm",
        ]:
            self.assertIn(expected, app_shell)
            self.assertIn(expected, dashboard)

        for expected in [
            "PROOF_CARDS",
            "Proof",
            "Endpoint",
            "Known limitation",
        ]:
            self.assertIn(expected, dashboard)

        for expected in [
            "Admin & Monitoring",
            "defaultOpen: true",
            "25 panels / 6 groups",
            "Provider path is visible",
        ]:
            self.assertIn(expected, advanced_page)

    def test_backend_contracts_cover_operational_routes(self) -> None:
        pyproject = tomllib.loads(read_text("services/api/pyproject.toml"))
        dependencies = "\n".join(pyproject["project"]["dependencies"])
        for dependency in ["fastapi", "uvicorn", "pydantic", "aiohttp"]:
            self.assertIn(dependency, dependencies)

        main = read_text("services/api/app/main.py")
        models = read_text("services/api/app/models.py")
        store = read_text("services/api/app/store.py")

        self.assertEqual(main.count('@app.get("/health/detailed")'), 1)
        self.assertIn('@app.get("/health/phases")', main)
        for route in [
            '@app.post("/reviews"',
            '@app.get("/reviews/{review_id}"',
            '@app.post("/sandbox/orders/simulate"',
            '@app.post("/packets/{packet_id}/attribution/compute"',
            '@app.get("/alerts/mobile"',
            '@app.get("/admin/audit"',
        ]:
            self.assertIn(route, main)

        for model in ["BrokerSandboxOrderRequest", "AttributionRequest", "MobileAlertSubscriptionCreate"]:
            self.assertIn(f"class {model}", models)

        for method in [
            "simulate_sandbox_order",
            "compute_attribution_report",
            "emit_mobile_alert",
            "add_admin_audit_event",
            "create_guardrail_profile",
        ]:
            self.assertIn(f"def {method}", store)

    def test_render_predeploy_runs_repo_level_validator_from_api_root(self) -> None:
        render = read_text("render.yaml")
        validator = read_text("scripts/validate-schema.py")

        self.assertIn("preDeployCommand: cd ../.. && python scripts/validate-schema.py", render)
        self.assertIn("cwd=api_dir", validator)
        self.assertIn('"-p", "test_stack_contract.py"', validator)


if __name__ == "__main__":
    unittest.main()
