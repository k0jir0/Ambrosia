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
            "sdk:check",
            "evals:financebench",
            "evals:finqa",
            "evals:tatqa",
            "evals:decision-memory",
            "routing-map:open-finllm",
            "enterprise:execution:check",
            "index84:literal:check",
            "index85:benchmarks:check",
            "schemas:index84:check",
            "web:control-plane:check",
            "release:evidence",
            "release:readiness:check",
            "production:evidence:check",
            "docs:consistency:check",
            "roadmap:completion:check",
        ]:
            self.assertIn(script, scripts)

        self.assertIn("pnpm --filter @ambrosia/web", scripts["dev:web"])
        self.assertIn("uvicorn app.main:app", scripts["dev:api"])
        self.assertIn("python -m unittest discover -s tests", scripts["test:stack"])
        self.assertIn("python scripts/verify-sdk-cli.py", scripts["sdk:check"])
        self.assertIn("python packages/evals/run_financebench_relay.py", scripts["evals:financebench"])
        self.assertIn("python packages/evals/run_finqa_relay.py", scripts["evals:finqa"])
        self.assertIn("python packages/evals/run_tatqa_relay.py", scripts["evals:tatqa"])
        self.assertIn("python scripts/generate-open-finllm-routing-map.py", scripts["routing-map:open-finllm"])
        self.assertIn("python packages/evals/run_decision_memory_fixture.py", scripts["evals:decision-memory"])
        self.assertIn("python scripts/verify-enterprise-execution.py", scripts["enterprise:execution:check"])
        self.assertIn("python scripts/verify-index84-literal.py", scripts["index84:literal:check"])
        self.assertIn("python scripts/verify-index85-benchmarks.py", scripts["index85:benchmarks:check"])
        self.assertIn("python scripts/verify-index84-schemas.py", scripts["schemas:index84:check"])
        self.assertIn("python scripts/verify-web-control-plane.py", scripts["web:control-plane:check"])
        self.assertIn("python scripts/generate-release-evidence.py", scripts["release:evidence"])
        self.assertIn("python scripts/verify-release-readiness.py", scripts["release:readiness:check"])
        self.assertIn("python scripts/verify-production-evidence.py", scripts["production:evidence:check"])
        self.assertIn("python scripts/verify-docs-consistency.py", scripts["docs:consistency:check"])
        self.assertIn("python scripts/verify-index84-completion.py", scripts["roadmap:completion:check"])

    def test_index84_sdk_cli_safe_read_surface_exists(self) -> None:
        sdk_client = read_text("packages/sdk-python/ambrosia_sdk/client.py")
        cli_main = read_text("packages/cli/ambrosia_cli/main.py")
        verifier = read_text("scripts/verify-sdk-cli.py")

        for expected in [
            "class AmbrosiaClient",
            "def health_detailed",
            "def create_review",
            "def scanner_run",
            "def relay_evaluate",
            "def create_signal",
            "def run_backtest",
            "def create_paper_trade",
            "def create_service_account",
            "def rotate_service_account",
            "def revoke_service_account",
            "def configure_sso",
            "def get_sso_config",
            "def get_offline_bundle_manifest",
            "def list_reviews",
            "def get_packet",
            "def market_snapshot",
            "def list_plans",
        ]:
            self.assertIn(expected, sdk_client)

        for expected in [
            "--json",
            "--yaml",
            "--table",
            "auth",
            "config",
            "--profile",
            "health",
            "reviews",
            "packets",
            "market",
            "scanner",
            "relay",
            "signals",
            "backtests",
            "paper-trades",
            "enterprise",
            "service-account-rotate",
            "service-account-revoke",
            "sso-config",
            "offline-bundle",
            "plans",
        ]:
            self.assertIn(expected, cli_main)

        self.assertIn("sdk-cli-transcript.json", verifier)

    def test_index84_schema_and_benchmark_evidence_exists(self) -> None:
        alpha_schema = read_text("packages/schemas/alpha-signal.v1.json")
        trace_schema = read_text("packages/schemas/benchmark-trace.v1.json")
        paper_schema = read_text("packages/schemas/paper-decision-loop.v1.json")
        relay = read_text("packages/evals/run_financebench_relay.py")
        verifier = read_text("scripts/verify-index84-schemas.py")

        for expected in ["costModel", "factorExposures", "validationGates", "decisionLinks"]:
            self.assertIn(expected, alpha_schema)

        for expected in ["retrievalEvents", "tableExtractions", "calculations", "verification", "grounding", "abstention"]:
            self.assertIn(expected, trace_schema)

        for expected in ["paper_only", "riskControls", "outcomePlan", "auditEvents"]:
            self.assertIn(expected, paper_schema + read_text("packages/schemas/fixtures/paper-decision-loop.fixture.json"))

        self.assertIn("financebench-relay-trace.json", relay)
        self.assertIn("benchmark-trace.v1.json", verifier)

    def test_index84_decision_memory_and_enterprise_evidence_exists(self) -> None:
        decision_memory = read_text("packages/evals/run_decision_memory_fixture.py")
        enterprise = read_text("scripts/verify-enterprise-execution.py")
        migration = read_text("infra/db/migrations/V0003__execution_enterprise_readiness.sql")
        full_platform_migration = read_text("infra/db/migrations/V0004__index84_full_platform.sql")
        literal = read_text("scripts/verify-index84-literal.py")

        for expected in ["decision-memory-attribution.json", "paperTradeId", "attribution", "priorityDelta"]:
            self.assertIn(expected, decision_memory)

        for expected in ["implementationShortfallBps", "latencyFitness", "serviceAccount", "auditExport"]:
            self.assertIn(expected, enterprise)

        for table in ["paper_trade", "execution_fill", "service_account", "audit_export_job"]:
            self.assertIn(table, migration)

        for expected in [
            "relay_run",
            "point_in_time_feature",
            "signal_definition",
            "backtest_run",
            "market_replay_run",
            "release_evidence_packet",
        ]:
            self.assertIn(expected, full_platform_migration)

        for route in [
            "/v1/chat/completions",
            "/relay/evaluate",
            "/features",
            "/signals",
            "/backtests/run",
            "/paper-trades",
            "/execution/fills",
            "/enterprise/service-accounts",
            "/enterprise/audit-exports",
        ]:
            self.assertIn(route, literal)

    def test_index84_web_control_plane_evidence_exists(self) -> None:
        verifier = read_text("scripts/verify-web-control-plane.py")

        for expected in [
            "frontend-control-plane-matrix.md",
            "web-control-plane-evidence.json",
            "/review/new",
            "/review/[id]",
            "/governance/team-management",
            "STATE_TERMS",
            "baselineTests",
        ]:
            self.assertIn(expected, verifier)

    def test_index84_completion_checker_maps_all_plans(self) -> None:
        checker = read_text("scripts/verify-index84-completion.py")

        for plan_id in [f"P-{i:03d}" for i in range(1, 13)]:
            self.assertIn(plan_id, checker)

        for expected in [
            "index84-completion.json",
            "completionPercent",
            "dbSchemaVersion",
            "v0004",
            "index84-literal-completion.json",
            "release-evidence.json",
            "rollout-evidence-packet.json",
            "memoryUpdate",
        ]:
            self.assertIn(expected, checker)

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

        self.assertIn("@/modules/adversarial-review", new_review_page)
        self.assertIn("NewReviewFlow", new_review_page)

    def test_sellable_navigation_separates_product_from_labs(self) -> None:
        app_shell = read_text("apps/web/src/components/app-shell.tsx")
        advanced_page = read_text("apps/web/src/app/advanced/page.tsx")
        dashboard = read_text("apps/web/src/components/dashboard-page.tsx")
        manifest = read_text("apps/web/src/lib/route-availability.ts")

        for href, label in [
            ("/review/new", "Intake"),
            ("/app", "Decision Packets"),
            ("/review", "Review Queue"),
            ("/history", "Outcomes & Memory"),
            ("/team", "Team"),
            ("/admin", "Admin"),
        ]:
            self.assertIn(f'{{ href: "{href}", label: "{label}"', app_shell)

        for expected in [
            "getRouteAvailability",
            "routeAvailability.unavailableRedirect",
            "getAccountSession()",
            "profile.organization.name",
            "logoutAccount()",
        ]:
            self.assertIn(expected, app_shell)

        self.assertIn('"/advanced"', manifest)
        self.assertIn('process.env.NEXT_PUBLIC_ENABLE_LABS === "true"', manifest)

        self.assertIn('redirect("/operations")', advanced_page)

        for expected in [
            "Run five-minute guided case",
            "Human decision authority",
            "One visible loop, no black-box approval",
            "Tenant database",
            "Local fallback",
        ]:
            self.assertIn(expected, dashboard)

    def test_route_manifest_has_dedicated_typed_policy_and_production_labs_gate(self) -> None:
        manifest = read_text("apps/web/src/lib/route-availability.ts")

        for field in [
            "label:",
            "owningWorkflow:",
            "buildSwitch:",
            "runtimePolicy:",
            "dedicatedSwitch:",
            "minimumRole:",
            "environments:",
            "dataModes:",
            "releaseStatus:",
            "evidenceArtifactId:",
            "unavailableRedirect:",
        ]:
            self.assertIn(field, manifest)

        self.assertIn("Duplicate route prefix", manifest)
        self.assertIn("has an invalid role declaration", manifest)
        self.assertIn("must use a dedicated exposure switch", manifest)
        self.assertIn("NEXT_PUBLIC_ENABLE_LABS=true is forbidden in production", manifest)
        self.assertNotIn('"/discovery",', manifest)
        self.assertNotIn('"/platform",', manifest)
        self.assertNotIn('"/enterprise",', manifest)
        self.assertNotIn('"/governance",', manifest)

    def test_legacy_product_routes_redirect_to_guarded_owners(self) -> None:
        redirects = {
            "apps/web/src/app/discovery/page.tsx": "/market-scanner",
            "apps/web/src/app/platform/page.tsx": "/operations",
            "apps/web/src/app/governance/page.tsx": "/team",
            "apps/web/src/app/governance/team-management/page.tsx": "/team",
            "apps/web/src/app/enterprise/page.tsx": "/admin",
            "apps/web/src/app/reports/page.tsx": "/review",
            "apps/web/src/app/advanced/page.tsx": "/operations",
        }
        for path, target in redirects.items():
            page = read_text(path)
            self.assertIn('from "next/navigation"', page)
            self.assertIn(f'redirect("{target}")', page)

        palette = read_text("apps/web/src/components/command-palette.tsx")
        for retired in ["/discovery", "/platform", "/enterprise", "/advanced", "/governance/team-management"]:
            self.assertNotIn(f'href: "{retired}"', palette)
        for owner in ["/market-scanner", "/operations", "/team", "/admin"]:
            self.assertIn(f'href: "{owner}"', palette)

    def test_backend_contracts_cover_operational_routes(self) -> None:
        pyproject = tomllib.loads(read_text("services/api/pyproject.toml"))
        dependencies = "\n".join(pyproject["project"]["dependencies"])
        for dependency in ["fastapi", "uvicorn", "pydantic", "aiohttp"]:
            self.assertIn(dependency, dependencies)

        main = read_text("services/api/app/main.py")
        models = read_text("services/api/app/models.py")
        store = read_text("services/api/app/store.py")
        index84_platform = read_text("services/api/app/index84_platform.py")

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

        for route in [
            '@router.post("/v1/chat/completions")',
            '@router.post("/relay/evaluate")',
            '@router.post("/features"',
            '@router.post("/signals"',
            '@router.post("/backtests/run")',
            '@router.post("/paper-trades"',
            '@router.post("/execution/fills"',
            '@router.post("/enterprise/service-accounts"',
            '@router.post("/enterprise/service-accounts/{service_account_id}/rotate")',
            '@router.post("/enterprise/service-accounts/{service_account_id}/revoke")',
            '@router.post("/enterprise/sso/config")',
            '@router.get("/enterprise/deployment-bundles/offline")',
        ]:
            self.assertIn(route, index84_platform)

    def test_render_blueprint_matches_free_tier_staging_contract(self) -> None:
        render = read_text("render.yaml")
        validator = read_text("scripts/validate-schema.py")

        self.assertNotIn("preDeployCommand:", render)
        self.assertNotIn("healthCheckStartFailureThreshold:", render)
        self.assertIn("repo: https://github.com/k0jir0/Ambrosia", render)
        self.assertIn("--timeout-graceful-shutdown 30", render)
        self.assertIn("ambrosia-api-staging", render)
        self.assertIn("ambrosia-web-staging", render)
        for safe_default in [
            "NEXT_PUBLIC_ENABLE_LABS",
            "NEXT_PUBLIC_ENABLE_MARKET_SCANNER_PROMOTION",
            "NEXT_PUBLIC_ENABLE_CALIBRATION_DEMO",
            "NEXT_PUBLIC_ENABLE_REVIEW_EXPORT",
            "ALPHA_LAB_DEMO_SEED_ENABLED",
            "SIGNALS_VALIDATION_ENABLED",
            "SIGNALS_EXECUTION_HANDOFF_ENABLED",
            "REPORT_EXPORT_ENABLED",
        ]:
            self.assertIn(safe_default, render)
        self.assertIn("cwd=api_dir", validator)
        self.assertIn('"-p", "test_stack_contract.py"', validator)

    def test_release_targets_propagate_dedicated_flags_and_reject_global_labs(self) -> None:
        readiness = read_text("scripts/verify-release-readiness.py")
        aws_release = read_text(".github/workflows/aws-release.yml")
        terraform = read_text("infra/aws/main.tf")

        self.assertIn("NEXT_PUBLIC_ENABLE_LABS=true is forbidden by production readiness", readiness)
        for dedicated_flag in [
            "NEXT_PUBLIC_ENABLE_MARKET_SCANNER",
            "NEXT_PUBLIC_ENABLE_OPERATIONS",
            "NEXT_PUBLIC_ENABLE_CALIBRATION",
            "NEXT_PUBLIC_ENABLE_REVIEW_EXPORT",
            "NEXT_PUBLIC_ENABLE_ALPHA_LAB",
            "NEXT_PUBLIC_ENABLE_SIGNALS_LAB",
            "NEXT_PUBLIC_ENABLE_CLI_DESIGN",
        ]:
            self.assertIn(dedicated_flag, aws_release)
        for disabled_flag in [
            "NEXT_PUBLIC_ENABLE_LABS",
            "NEXT_PUBLIC_ENABLE_MARKET_SCANNER_PROMOTION",
            "NEXT_PUBLIC_ENABLE_CALIBRATION_DEMO",
            "NEXT_PUBLIC_ENABLE_REVIEW_EXPORT",
            "NEXT_PUBLIC_ENABLE_ALPHA_LAB",
            "NEXT_PUBLIC_ENABLE_SIGNALS_LAB",
        ]:
            self.assertIn(disabled_flag, terraform)


if __name__ == "__main__":
    unittest.main()
