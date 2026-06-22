from __future__ import annotations

import json
import re
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def read_json(relative_path: str) -> dict:
    return json.loads(read_text(relative_path))


class StackContractTests(unittest.TestCase):
    def test_root_monorepo_scripts_match_current_stack(self) -> None:
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
            "evals",
            "test:stack",
        ]:
            self.assertIn(script, scripts)

        self.assertIn("pnpm --filter @ambrosia/web", scripts["dev:web"])
        self.assertIn("uvicorn app.main:app", scripts["dev:api"])
        self.assertIn("python -m unittest discover -s tests", scripts["test:stack"])

    def test_frontend_stack_is_pinned_and_workbench_oriented(self) -> None:
        package = read_json("apps/web/package.json")

        self.assertEqual(package["dependencies"]["next"], "15.1.0")
        self.assertEqual(package["dependencies"]["react"], "19.0.0")
        self.assertEqual(package["dependencies"]["react-dom"], "19.0.0")
        self.assertEqual(package["devDependencies"]["eslint-config-next"], "15.1.0")

        for dependency in [
            "@tanstack/react-query",
            "@tanstack/react-table",
            "react-hook-form",
            "zod",
            "recharts",
            "lucide-react",
            "tailwind-merge",
        ]:
            self.assertIn(dependency, package["dependencies"])

        self.assertIn("@playwright/test", package["devDependencies"])
        self.assertEqual(package["scripts"]["dev"], "node scripts/dev.mjs")

        dev_script = read_text("apps/web/scripts/dev.mjs")
        self.assertIn("rmSync", dev_script)
        self.assertIn(".next", dev_script)
        self.assertIn('"node_modules", "next", "dist", "bin", "next"', dev_script)
        self.assertIn('spawn(process.execPath, [nextCli, "dev", "--port", "3000"]', dev_script)
        self.assertIn('process.on("SIGTERM"', dev_script)

    def test_workbench_exposes_finished_mvp_frontend_surfaces(self) -> None:
        workbench = read_text("apps/web/src/components/workbench.tsx")

        for expected in [
            "Generate thesis",
            "createReview",
            "listReviews",
            "recordDecision",
            "DecisionMemoryPanel",
            "CalibrationPanel",
            "SourceLibraryPanel",
            "computeDashboardMetrics",
            "buildDecisionChartData",
            "collectSources",
            "mergeReviews",
            "Enter a decision-relevant thesis.",
        ]:
            self.assertIn(expected, workbench)

        self.assertIn("API-backed", workbench)
        self.assertIn("Local fallback", workbench)
        self.assertIn("Generated thesis candidates are review inputs, not recommendations", workbench)

    def test_frontend_api_client_covers_review_lifecycle(self) -> None:
        api_client = read_text("apps/web/src/lib/api.ts")

        self.assertIn("/reviews", api_client)
        self.assertIn("createReview", api_client)
        self.assertIn("listReviews", api_client)
        self.assertIn("recordDecision", api_client)
        self.assertIn("/decision", api_client)
        self.assertIn("NEXT_PUBLIC_API_BASE_URL", api_client)

    def test_backend_stack_and_endpoint_surface(self) -> None:
        pyproject = tomllib.loads(read_text("services/api/pyproject.toml"))
        dependencies = "\n".join(pyproject["project"]["dependencies"])
        dev_dependencies = "\n".join(pyproject["dependency-groups"]["dev"])

        for dependency in ["fastapi", "uvicorn", "pydantic", "sqlalchemy", "psycopg"]:
            self.assertIn(dependency, dependencies)
        for dependency in ["pytest", "ruff", "httpx"]:
            self.assertIn(dependency, dev_dependencies)

        main = read_text("services/api/app/main.py")
        for route in [
            '@app.get("/health")',
            '@app.get("/reviews"',
            '@app.post("/reviews"',
            '@app.get("/reviews/{review_id}"',
            '@app.patch("/reviews/{review_id}/decision"',
            '@app.post("/reviews/{review_id}/outcome"',
            '@app.post("/webhooks/tradingview"',
            '@app.get("/metrics"',
        ]:
            self.assertIn(route, main)

    def test_database_schema_targets_decision_memory_and_retrieval(self) -> None:
        schema = read_text("infra/db/init.sql")

        for expected in [
            "CREATE EXTENSION IF NOT EXISTS vector",
            "CREATE TABLE IF NOT EXISTS workspaces",
            "CREATE TABLE IF NOT EXISTS reviews",
            "CREATE TABLE IF NOT EXISTS source_pointers",
            "CREATE TABLE IF NOT EXISTS audit_events",
            "CREATE TABLE IF NOT EXISTS workflow_runs",
            "CREATE TABLE IF NOT EXISTS review_embeddings",
            "embedding vector(1536)",
            "search_text tsvector",
            "decision_state TEXT CHECK",
            "idempotency_key TEXT UNIQUE",
        ]:
            self.assertIn(expected, schema)

    def test_eval_fixtures_cover_core_failure_modes(self) -> None:
        fixture_rows = [json.loads(line) for line in read_text("packages/evals/fixtures.jsonl").splitlines() if line.strip()]
        categories = {row["category"] for row in fixture_rows}

        self.assertSetEqual(
            categories,
            {
                "invalid_validation",
                "prompt_injection",
                "tradeability_missing_data",
                "disconfirming_test",
            },
        )

        runner = read_text("packages/evals/run_evals.py")
        self.assertIn("Ambrosia eval fixture gate", runner)

    def test_playwright_suite_covers_current_frontend_todos(self) -> None:
        spec = read_text("apps/web/tests/workbench.spec.ts")

        for expected in [
            "workbench opens directly into Trade Review",
            "generated thesis can seed and create a review",
            "navigation panels switch to memory calibration and sources",
            "empty form shows validation instead of silent submit",
            "Generate thesis",
            "Captured review decisions",
            "Decision discipline dashboard",
            "User-owned evidence and source pointers",
        ]:
            self.assertIn(expected, spec)

    def test_readme_describes_current_mvp_state(self) -> None:
        readme = read_text("README.md")

        for expected in [
            "Current State",
            "Generate thesis",
            "API-first review creation",
            "Local deterministic fallback",
            "Functional left navigation",
            "Live dashboard metrics",
            "Visible form validation errors",
            "pnpm test:stack",
            "https://github.com/k0jir0/Ambrosia",
        ]:
            self.assertIn(expected, readme)

        verification_commands = re.findall(r"pnpm [a-z0-9:]+", readme)
        self.assertIn("pnpm test:e2e", verification_commands)


if __name__ == "__main__":
    unittest.main()
