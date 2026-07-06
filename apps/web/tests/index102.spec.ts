import { expect, test } from "@playwright/test";

const LOCAL_API_ROUTE = "http://localhost:8000/**";

const teamMembers = [
  { user_id: "usr-001", name: "Owner", role: "owner", active: true },
  { user_id: "usr-002", name: "Admin", role: "admin", active: true },
  { user_id: "usr-003", name: "Reviewer", role: "reviewer", active: true },
];

test.beforeEach(async ({ page }) => {
  await page.route(LOCAL_API_ROUTE, (route) => route.abort());
});

test("reports export uses query review id and email recipient contract", async ({ page }) => {
  await page.unroute(LOCAL_API_ROUTE);
  await page.addInitScript(() => {
    window.open = () => null;
  });
  const requests: string[] = [];

  await page.route(LOCAL_API_ROUTE, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    requests.push(`${request.method()} ${url.pathname}${url.search}`);

    if (url.pathname === "/discovery/reports/atr-query-001/email") {
      expect(url.searchParams.get("recipient")).toBe("analyst@example.com");
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "sent" }) });
      return;
    }

    if (url.pathname === "/discovery/reports/atr-query-001/export") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ url: "about:blank" }) });
      return;
    }

    await route.abort();
  });

  await page.goto("/reports/export?id=atr-query-001");
  await expect(page.getByText("Review ID: atr-query-001")).toBeVisible();
  await page.getByText("HTML", { exact: true }).click();
  await page.getByRole("button", { name: "Export as HTML" }).click();
  await expect(page.getByText("Export successful")).toBeVisible();
  expect(requests).toContain("POST /discovery/reports/atr-query-001/export?format=html");

  await page.getByText("Email", { exact: true }).click();
  await page.getByPlaceholder("recipient@example.com").fill("analyst@example.com");
  await page.getByRole("button", { name: "Export as EMAIL" }).click();
  await expect(page.getByText("Export successful")).toBeVisible();
  expect(requests).toContain("POST /discovery/reports/atr-query-001/email?recipient=analyst%40example.com");
});

test("calibration route does not emit browser page errors", async ({ page }) => {
  const pageErrors: string[] = [];
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.goto("/calibration");
  await expect(page.getByRole("heading", { name: "Model outcome calibration" })).toBeVisible();
  await expect(page.getByText("Seeded fixture").or(page.getByText("Live API data"))).toBeVisible();
  expect(pageErrors).toEqual([]);
});

test.describe("mobile navigation", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("More opens the full module drawer", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /More/i }).click();

    for (const label of [
      "Market Scanner",
      "Signals",
      "Alpha Lab",
      "Team",
      "Enterprise",
      "CLI Design",
      "Admin",
      "Advanced",
      "Platform",
    ]) {
      await expect(page.getByRole("link", { name: label, exact: true })).toBeVisible();
    }
  });
});

test("command palette covers secondary modules", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Control+k");
  const input = page.getByPlaceholder("Search actions or type ticker (AAPL)");
  await expect(input).toBeVisible();

  for (const label of ["Signals", "Team", "Admin", "Advanced", "Reports Export", "Discovery", "Governance Team Management"]) {
    await input.fill(label);
    await expect(page.getByRole("button").filter({ hasText: new RegExp(`^${escapeRegExp(label)}`) }).first()).toBeVisible();
  }
});

test("market scanner presents Alpha as a hypothesis workflow", async ({ page }) => {
  await page.unroute(LOCAL_API_ROUTE);
  await page.route(LOCAL_API_ROUTE, async (route) => {
    const request = route.request();
    const url = new URL(request.url());

    if (request.method() === "POST" && url.pathname === "/scanner/run") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          candidates: [
            {
              ticker: "AAPL",
              signal: "momentum_up",
              thesisSuggestion: "AAPL momentum is improving after a constructive base.",
              score: 0.82,
              price: 221.34,
              trend: "uptrend",
              rsi: 61,
              volume24h: 32400000,
              dataSource: "test-fixture",
              dataMode: "demo",
              scannedAt: "2026-07-06T00:00:00.000Z"
            }
          ],
          scannedAt: "2026-07-06T00:00:00.000Z",
          universe: ["AAPL"],
          totalScanned: 1,
          dataMode: "demo"
        })
      });
      return;
    }

    if (request.method() === "GET" && url.pathname === "/jobs") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
      return;
    }

    if (request.method() === "GET" && url.pathname === "/scanner/candidates/promotions") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
      return;
    }

    await route.abort();
  });

  await page.goto("/market-scanner");
  await expect(page.getByRole("heading", { name: "Market Scanner" })).toBeVisible();
  await expect(page.getByText("formalize the strongest setups as Alpha Lab hypotheses")).toBeVisible();
  await expect(page.getByRole("button", { name: "Create Alpha Hypothesis" })).toBeVisible();
  await expect(page.getByText("Promote to Alpha")).toHaveCount(0);
});

test("market intelligence labels fallback provenance", async ({ page }) => {
  await page.goto("/markets/AAPL");
  await expect(page.getByRole("heading", { name: /AAPL intelligence/i })).toBeVisible();
  await expect(page.getByText("Fallback", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Fallback deterministic").first()).toBeVisible();
  await expect(page.getByText("Fallback simulated").first()).toBeVisible();
});

test("history can seed demo archive records", async ({ page }) => {
  await page.unroute(LOCAL_API_ROUTE);
  let seeded = false;

  await page.route(LOCAL_API_ROUTE, async (route) => {
    const request = route.request();
    const url = new URL(request.url());

    if (request.method() === "GET" && url.pathname === "/reviews") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(
          seeded
            ? [
                {
                  id: "review-index97-aapl-momo-01",
                  schemaVersion: "review.v1",
                  workflowVersion: "adversarial-review.v1",
                  title: "Demo Lifecycle: AAPL Momentum 1D",
                  thesis: "AAPL short-horizon continuation is strongest when positive five-day return is confirmed by relative volume.",
                  ticker: "AAPL",
                  assetClass: "Equities",
                  timeHorizon: "1d",
                  intendedExpression: "Long AAPL",
                  status: "decision_recorded",
                  decisionState: "pursue",
                  confidence: 72,
                  trialCountImpact: 1,
                  followUpDate: "2026-07-13",
                  createdAt: "2026-07-06T18:00:00Z",
                  claims: [],
                  strongestCritique: "Demo critique",
                  disconfirmingTest: "Demo disconfirming test",
                  historicalAnalogue: { title: "Demo", similarity: "Demo", differences: "Demo", resolution: "Demo" },
                  validation: { status: "specified", hypothesis: "Demo", nullHypothesis: "Demo", dataRequirements: [], protocol: "Demo" },
                  tradeability: [],
                  sources: [],
                  audit: [],
                },
              ]
            : []
        ),
      });
      return;
    }

    if (request.method() === "POST" && url.pathname === "/reviews/seed-index97") {
      seeded = true;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ status: "ok", reviewsSeeded: 1, reviewIds: ["review-index97-aapl-momo-01"] }),
      });
      return;
    }

    await route.abort();
  });

  await page.goto("/history");
  await expect(page.getByRole("heading", { name: "Archive (0 total)" })).toBeVisible();
  await page.getByRole("button", { name: "Seed demo archive" }).click();
  await expect(page.getByText("Seeded 1 demo reviews into the archive.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Archive (1 total)" })).toBeVisible();
  await expect(page.getByRole("table").getByText("AAPL")).toBeVisible();
});

test("discovery create thesis opens real review intake prefill", async ({ page }) => {
  await page.unroute(LOCAL_API_ROUTE);

  await page.route(LOCAL_API_ROUTE, async (route) => {
    const request = route.request();
    const url = new URL(request.url());

    if (request.method() === "POST" && url.pathname === "/discovery/scan") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "sig-qa-001",
            ticker: "SPY",
            signal_type: "momentum",
            conviction: 0.85,
            description: "Relative strength improving vs broad market",
            data_sources: ["polygon"],
          },
        ]),
      });
      return;
    }

    if (request.method() === "POST" && url.pathname === "/discovery/signal/sig-qa-001/create-thesis") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ review_id: "rev-from-sig-qa-001", thesis: "Thesis created from signal sig-qa-001" }),
      });
      return;
    }

    await route.abort();
  });

  await page.goto("/discovery");
  await expect(page.getByText("SPY").first()).toBeVisible();
  await Promise.all([
    page.waitForURL(/\/review\/new\?/, { timeout: 20000 }),
    page.getByRole("button", { name: "Create Thesis" }).first().click(),
  ]);
  await expect(page.getByText("Prefilled from Market Scanner candidate")).toBeVisible();
  await expect(page.getByLabel("Ticker / instrument")).toHaveValue("SPY");
});

test("governance team management edits and removes members", async ({ page }) => {
  await page.unroute(LOCAL_API_ROUTE);

  await page.route(LOCAL_API_ROUTE, async (route) => {
    const request = route.request();
    const url = new URL(request.url());

    if (request.method() === "GET" && url.pathname === "/governance/team/members") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ team: teamMembers, total_members: teamMembers.length, active_members: teamMembers.length }),
      });
      return;
    }

    if (request.method() === "PATCH" && url.pathname === "/governance/team/usr-003") {
      const payload = JSON.parse(request.postData() ?? "{}");
      expect(payload.role).toBe("admin");
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ member: { ...teamMembers[2], role: "admin" }, status: "updated" }),
      });
      return;
    }

    if (request.method() === "DELETE" && url.pathname === "/governance/team/usr-003") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "removed" }) });
      return;
    }

    await route.abort();
  });

  await page.goto("/governance/team-management");
  const reviewerCard = page.getByTestId("team-member-usr-003");
  await expect(reviewerCard).toBeVisible();
  await reviewerCard.getByRole("button", { name: "Edit" }).click();
  await reviewerCard.locator("select").selectOption("admin");
  await reviewerCard.getByRole("button", { name: "Save" }).click();
  await expect(page.getByText("Reviewer updated to admin.")).toBeVisible();

  await reviewerCard.getByRole("button", { name: "Remove" }).click();
  await expect(page.getByText("Reviewer removed from the team.")).toBeVisible();
});

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
