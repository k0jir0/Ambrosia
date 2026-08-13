from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI_PATH = ROOT / "packages" / "cli"
SDK_PATH = ROOT / "packages" / "sdk-python"

sys.path.insert(0, str(CLI_PATH))
sys.path.insert(0, str(SDK_PATH))

from ambrosia_cli.main import build_parser  # noqa: E402


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class Index90StackTests(unittest.TestCase):
    def test_frontend_routes_use_dedicated_owners_and_retired_aliases(self) -> None:
        app_shell = read_text("apps/web/src/components/app-shell.tsx")
        palette = read_text("apps/web/src/components/command-palette.tsx")

        for route in ['/alpha', '/cli-design', '/operations']:
            self.assertIn(route, app_shell)
            self.assertIn(route, palette)

        for internal_route in ['/execution-intelligence', '/relay-benchmarks']:
            self.assertIn(internal_route, palette)

        for label in [
            'Alpha Lab',
            'Execution Intelligence',
            'Relay + Benchmarks',
            'CLI Guide',
            'Operations',
        ]:
            self.assertIn(label, palette)

        sellable_navigation = app_shell.split("const NAV_ITEMS = [", 1)[1].split("] as const;", 1)[0]
        for route in ['/platform', '/execution-intelligence', '/relay-benchmarks', '/enterprise']:
            self.assertNotIn(route, sellable_navigation)
        for retired in ['/platform', '/enterprise', '/advanced', '/discovery', '/governance/team-management']:
            self.assertNotIn(f'href: "{retired}"', palette)

    def test_index89_pages_have_route_state_boundaries(self) -> None:
        for page in [
            "platform",
            "alpha",
            "execution-intelligence",
            "relay-benchmarks",
            "enterprise",
            "cli-design",
        ]:
            page_file = ROOT / "apps" / "web" / "src" / "app" / page / "page.tsx"
            self.assertTrue(page_file.exists(), f"Missing page: {page_file}")

        for page in ["alpha", "execution-intelligence", "relay-benchmarks", "cli-design"]:
            loading_file = ROOT / "apps" / "web" / "src" / "app" / page / "loading.tsx"
            error_file = ROOT / "apps" / "web" / "src" / "app" / page / "error.tsx"
            self.assertTrue(loading_file.exists(), f"Missing loading boundary: {loading_file}")
            self.assertTrue(error_file.exists(), f"Missing error boundary: {error_file}")

        self.assertIn('redirect("/operations")', read_text("apps/web/src/app/platform/page.tsx"))
        self.assertIn('redirect("/admin")', read_text("apps/web/src/app/enterprise/page.tsx"))

        state_component = read_text("apps/web/src/components/route-state.tsx")
        error_component = read_text("apps/web/src/components/route-error.tsx")
        self.assertIn("RouteLoading", state_component)
        self.assertIn("RouteNotice", state_component)
        self.assertIn("RouteStatusBadge", state_component)
        self.assertIn("RouteErrorView", error_component)

    def test_cli_design_page_uses_generated_truthful_registry(self) -> None:
        page = read_text("apps/web/src/app/cli-design/page.tsx")

        for expected in [
            "cli-guide-registry.json",
            "Implemented means the command parses",
            "tested means a focused CLI contract test exists",
            "qualified means a read command",
            "there is no in-browser terminal",
            "no public package publication is claimed",
            "Write commands are listed for contract accuracy",
        ]:
            self.assertIn(expected, page)

        registry = read_text("apps/web/src/generated/cli-guide-registry.json")
        self.assertIn('"command": "ambrosia health"', registry)
        self.assertIn('"qualificationStatus": "qualified"', registry)

    def test_cli_design_page_has_evidence_based_status_sections(self) -> None:
        page = read_text("apps/web/src/app/cli-design/page.tsx")

        for expected in [
            "Capability statement",
            "Current status",
            "What exists today",
            "What has been validated",
            "Remaining release gates",
            "Evidence and ownership",
            "implemented and locally validated",
            "release-gated",
        ]:
            self.assertIn(expected, page)

    def test_adversarial_review_flow_isolated_in_module_boundary(self) -> None:
        module_index = read_text("apps/web/src/modules/adversarial-review/index.ts")
        intake = read_text("apps/web/src/modules/adversarial-review/intake/new-review-flow.tsx")
        workbench = read_text("apps/web/src/modules/adversarial-review/workbench/review-workbench-route.tsx")
        review_new_route = read_text("apps/web/src/app/review/new/page.tsx")
        review_id_route = read_text("apps/web/src/app/review/[id]/page.tsx")

        self.assertIn("NewReviewFlow", module_index)
        self.assertIn("ReviewWorkbenchRoute", module_index)
        self.assertIn("createReviewRecord", intake)
        self.assertIn("Workbench", workbench)
        self.assertIn("@/modules/adversarial-review", review_new_route)
        self.assertIn("@/modules/adversarial-review", review_id_route)

    def test_backend_routes_for_new_control_plane_modules_exist(self) -> None:
        index84_platform = read_text("services/api/app/index84_platform.py")

        for route in [
            '/alpha/hypotheses',
            '/signals',
            '/signals/{signal_id}/alpha-decay',
            '/backtests/run',
            '/execution/warm-path/events',
            '/relay/scorecard',
            '/enterprise/readiness',
            '/enterprise/support/security-packet',
        ]:
            self.assertIn(route, index84_platform)

    def test_cli_parser_covers_full_index84_command_surface(self) -> None:
        parser = build_parser()

        parse_cases = [
            ["--json", "health", "--detailed"],
            ["--json", "reviews", "create", "--thesis", "Alpha thesis", "--ticker", "SOXX"],
            ["--json", "relay", "evaluate", "--question", "What supports margin expansion?"],
            ["--json", "signals", "create", "--name", "Momentum", "--formula", "close/close_20d-1"],
            ["--json", "alpha", "create", "--title", "Hypothesis", "--signal-family", "momentum", "--thesis", "Continuation"],
            ["--json", "backtests", "run", "--signal-id", "signal-1"],
            ["--json", "paper-trades", "create", "--decision-id", "dec-1", "--ticker", "SOXX", "--quantity", "1"],
            ["--json", "warm-path", "ingest", "--event-type", "fill", "--ticker", "SOXX", "--latency-ms", "120", "--notional-usd", "10000"],
            ["--json", "enterprise", "service-account", "--name", "ci-bot"],
            ["--json", "enterprise", "security-packet"],
        ]

        for case in parse_cases:
            parsed = parser.parse_args(case)
            self.assertIsNotNone(parsed)


if __name__ == "__main__":
    unittest.main()
