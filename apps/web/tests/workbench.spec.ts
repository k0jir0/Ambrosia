import { expect, test, type Page, type Route } from "@playwright/test";

const LOCAL_API_ROUTE = "http://localhost:8000/**";

test.beforeEach(async ({ page }) => {
  await page.route(LOCAL_API_ROUTE, (route) => route.abort());
});

test("dashboard is the default entry point", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Ambrosia", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Good morning\./i })).toBeVisible();
  await expect(page.getByText("Needs Your Attention")).toBeVisible();
  await expect(page.getByText("Recent Reviews", { exact: true })).toBeVisible();
});

test("new review creates an archive record and can be reopened", async ({ page }) => {
  await page.goto("/review/new");
  await expect(page.getByRole("heading", { name: "Thesis intake workflow" })).toBeVisible();
  await page.getByLabel("Ticker / instrument").fill("NVDA");
  await page.getByRole("button", { name: /Continue/i }).first().click();
  await page.getByPlaceholder("State why this instrument is actionable.").fill("NVDA may be actionable if datacenter demand keeps beating expectations while margins remain resilient.");
  await page.getByRole("button", { name: /Continue/i }).first().click();
  await Promise.all([
    page.waitForURL(/\/review\/atr-/, { timeout: 20000 }),
    page.getByRole("button", { name: /Create review/i }).click()
  ]);
  await expect(page.getByRole("heading", { name: /NVDA adversarial review/i })).toBeVisible();

  await page.goto("/");
  await expect(page.getByText("NVDA adversarial review", { exact: true })).toBeVisible();
  await expect(page.getByText("Agentic AI for Investments:")).toBeVisible();
  await expect(page.getByText("Investment Trading Decisions:")).toBeVisible();
  await expect(page.getByText("Swarm Intelligence:")).toBeVisible();
  await expect(page.getByText("Agentic Swarm:")).toBeVisible();

  await page.goto("/history");
  await page.getByRole("textbox", { name: "Search", exact: true }).fill("NVDA");
  await expect(page.getByRole("table").getByText("NVDA")).toBeVisible();
  await page.getByRole("link", { name: "Open" }).first().click();
  await expect(page.getByRole("heading", { name: /NVDA adversarial review/i })).toBeVisible();
});

test("markets route renders ticker-bound charting workspace", async ({ page }) => {
  await page.goto("/markets/MSFT");
  await expect(page.getByRole("heading", { name: /MSFT intelligence/i })).toBeVisible();
  await expect(page.getByText("Line, Candlestick, and OHLC")).toBeVisible();
  await page.getByRole("button", { name: "Analytics" }).click();
  await expect(page.getByText("Efficient Frontier")).toBeVisible();
});

test("review route uses focused decision workbench", async ({ page }) => {
  await page.goto("/review/atr-003");
  await expect(page.getByRole("heading", { name: /Curve steepener after policy shift/i })).toBeVisible();
  await expect(page.getByText("Thesis and sources")).toBeVisible();
  await expect(page.getByText("Live workflow feed")).toBeVisible();
  await expect(page.getByText("TLT market dock")).toBeVisible();
  await expect(page.getByText("Decision controls")).toBeVisible();
  await expect(page.getByText("Signal Decision Proposal")).toBeVisible();
  await expect(page.getByText("Signal will be created")).toBeVisible();
  await expect(page.locator("section").filter({ hasText: "Decision controls" })).toHaveCSS("position", "static");
  await expect(page.getByText("Core Actions")).toHaveCount(0);
  await expect(page.getByText("Run a thesis through Ambrosia")).toHaveCount(0);
  const exportButton = page.getByRole("button", { name: "Generate / export report" });
  await expect(exportButton).toBeEnabled();
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    exportButton.click()
  ]);
  expect(download.suggestedFilename()).toBe("tlt-investment-decision-report.md");
  await expect(page.getByText("Report exported from local fallback").first()).toBeVisible();
});

test("governed decisions fail closed when the API is unavailable", async ({ page }) => {
  await page.goto("/review/atr-003");
  await page.getByRole("button", { name: "Watch" }).click();

  await expect(page.getByText(/Decision blocked:/)).toBeVisible();
  await expect(page.getByText("Human decision: Watch.")).toHaveCount(0);
  await expect(page.getByText("Decision pending", { exact: true })).toBeVisible();
});

test("soft-policy advisories do not lock watch and reject decisions", async ({ page }) => {
  const governedPackets = new Map<string, JsonRecord>();
  await page.unroute(LOCAL_API_ROUTE);
  await page.route(LOCAL_API_ROUTE, async (route) => {
    if (await fulfillGovernedPacketRequest(route, governedPackets)) return;
    if (route.request().url().endsWith("/signals/signal-e2e-alpha-decay/alpha-decay")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ decayDetected: true, recommendedAction: "downgrade_or_recalibrate" })
      });
      return;
    }
    await route.abort();
  });
  await page.addInitScript(() => {
    window.localStorage.setItem(
      "ambrosia.review-alpha-links.v1",
      JSON.stringify({
        "atr-003": {
          source: "alpha",
          objectType: "signal",
          signalId: "signal-e2e-alpha-decay",
          signalVersion: 1,
          title: "QA signal",
          signalFamily: "quality-momentum",
          ticker: "TLT",
          createdAt: "2026-07-06T00:00:00.000Z"
        }
      })
    );
  });

  await page.goto("/review/atr-003");
  await expect(page.getByText(/Alpha decay detected for linked signal signal-e2e-alpha-decay/)).toBeVisible();
  await expect(page.getByText("Resolve soft-policy decay/hygiene advisories first.")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Watch" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Reject" })).toBeEnabled();
  await page.getByRole("button", { name: "Watch" }).click();
  await expect(page.getByText("Human decision: Watch.").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Write HOLD to Signal" })).toBeEnabled();
});

test("signal proposal recreates stale linked signal before writeback", async ({ page }) => {
  let staleLinkAttempted = false;
  let replacementSignalCreated = false;
  let writebackDecisionAction = "";
  const governedPackets = new Map<string, JsonRecord>();

  await page.unroute(LOCAL_API_ROUTE);
  await page.route(LOCAL_API_ROUTE, async (route) => {
    const request = route.request();
    const url = request.url();

    if (await fulfillGovernedPacketRequest(route, governedPackets)) return;

    if (url.endsWith("/signals/stale-signal/link-review")) {
      staleLinkAttempted = true;
      await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "signal not found" }) });
      return;
    }
    if (url.endsWith("/alpha/hypotheses") && request.method() === "POST") {
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ hypothesisId: "alpha-replacement" }) });
      return;
    }
    if (url.endsWith("/signals") && request.method() === "POST") {
      replacementSignalCreated = true;
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ signalId: "signal-replacement", activeVersion: 1, version: 1 }) });
      return;
    }
    if (url.endsWith("/alpha/hypotheses/alpha-replacement/link-signal")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ hypothesisId: "alpha-replacement", signalId: "signal-replacement", signalVersion: 1 }) });
      return;
    }
    if (url.endsWith("/signals/signal-replacement/link-review")) {
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ signalId: "signal-replacement", reviewId: "atr-003" }) });
      return;
    }
    if (url.endsWith("/signals/signal-replacement/writeback-decision")) {
      const payload = request.postDataJSON() as { decisionAction?: string };
      writebackDecisionAction = payload.decisionAction ?? "";
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ signalId: "signal-replacement", reviewId: "atr-003", latestDecisionAction: payload.decisionAction, executionReadiness: "execution_blocked" })
      });
      return;
    }
    if (url.endsWith("/signals/signal-replacement/alpha-decay") || url.endsWith("/signals/stale-signal/alpha-decay")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ decayDetected: false, recommendedAction: "maintain" }) });
      return;
    }
    await route.abort();
  });

  await page.addInitScript(() => {
    window.localStorage.setItem(
      "ambrosia.review-alpha-links.v1",
      JSON.stringify({
        "atr-003": {
          source: "alpha",
          objectType: "signal",
          signalId: "stale-signal",
          signalVersion: 1,
          title: "Stale QA signal",
          signalFamily: "macro",
          ticker: "TLT",
          createdAt: "2026-07-06T00:00:00.000Z"
        }
      })
    );
  });

  await page.goto("/review/atr-003");
  await page.getByRole("button", { name: "Watch" }).click();
  await page.getByRole("button", { name: "Write HOLD to Signal" }).click();
  await expect(page.getByText("Signal updated: HOLD / execution_blocked.")).toBeVisible();
  expect(staleLinkAttempted).toBe(true);
  expect(replacementSignalCreated).toBe(true);
  expect(writebackDecisionAction).toBe("HOLD");
});

test("signal proposal sanitizes short generated signal fields", async ({ page }) => {
  let createdSignalFormula = "";
  const governedPackets = new Map<string, JsonRecord>();

  await page.unroute(LOCAL_API_ROUTE);
  await page.route(LOCAL_API_ROUTE, async (route) => {
    const request = route.request();
    const url = request.url();

    if (await fulfillGovernedPacketRequest(route, governedPackets)) return;

    if (url.endsWith("/alpha/hypotheses") && request.method() === "POST") {
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ hypothesisId: "alpha-sanitized" }) });
      return;
    }
    if (url.endsWith("/signals") && request.method() === "POST") {
      const payload = request.postDataJSON() as { formula?: string };
      createdSignalFormula = payload.formula ?? "";
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ signalId: "signal-sanitized", activeVersion: 1, version: 1 }) });
      return;
    }
    if (url.endsWith("/alpha/hypotheses/alpha-sanitized/link-signal")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ hypothesisId: "alpha-sanitized", signalId: "signal-sanitized", signalVersion: 1 }) });
      return;
    }
    if (url.endsWith("/signals/signal-sanitized/link-review")) {
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ signalId: "signal-sanitized", reviewId: "atr-short-fields" }) });
      return;
    }
    if (url.endsWith("/signals/signal-sanitized/writeback-decision")) {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ signalId: "signal-sanitized", reviewId: "atr-short-fields", latestDecisionAction: "HOLD", executionReadiness: "execution_blocked" })
      });
      return;
    }
    if (url.endsWith("/signals/signal-sanitized/alpha-decay")) {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ decayDetected: false, recommendedAction: "maintain" }) });
      return;
    }
    await route.abort();
  });

  await page.addInitScript(() => {
    window.localStorage.setItem(
      "ambrosia.reviews.v1",
      JSON.stringify([
        {
          id: "atr-short-fields",
          schemaVersion: "review.v1",
          workflowVersion: "adversarial-review.v1",
          title: "Short field review",
          thesis: "Short fields should still create a valid signal.",
          ticker: "TS",
          assetClass: "Equity",
          timeHorizon: " ",
          intendedExpression: " ",
          status: "synthesis",
          decisionState: "watch",
          confidence: 61,
          trialCountImpact: 1,
          followUpDate: "2026-07-14",
          createdAt: "2026-07-06T00:00:00.000Z",
          claims: [],
          strongestCritique: "Costs may dominate the signal.",
          disconfirmingTest: " ",
          historicalAnalogue: { title: "n/a", similarity: "n/a", differences: "n/a", resolution: "n/a" },
          validation: {
            status: "refused",
            hypothesis: "n/a",
            nullHypothesis: " ",
            dataRequirements: [],
            protocol: "n/a",
            refusalReason: "fixture"
          },
          tradeability: [],
          sources: [],
          audit: []
        }
      ])
    );
  });

  await page.goto("/review/atr-short-fields");
  await page.getByRole("button", { name: "Create Signal + Write HOLD" }).click();
  await expect(page.getByText("Signal updated: HOLD / execution_blocked.")).toBeVisible();
  expect(createdSignalFormula).toBe("review_expression:TS");
});

test("sidebar navigation reaches core routes", async ({ page }) => {
  test.slow();
  await page.goto("/");
  await openSidebarRoute(page, "Decision History", "/history");
  await expect(page.getByRole("heading", { name: /^Archive \(\d+ total\)$/ })).toBeVisible();

  await openSidebarRoute(page, "Calibration", "/calibration");
  await expect(page.getByRole("heading", { name: "Model outcome calibration" })).toBeVisible();
});

test("index89 routes are accessible from sidebar navigation", async ({ page }) => {
  test.slow();
  await page.goto("/");

  await openSidebarRoute(page, "Platform", "/platform");
  await expect(page.getByRole("heading", { name: "Platform", exact: true })).toBeVisible();

  await openSidebarRoute(page, "Alpha Lab", "/alpha");
  await expect(page.getByRole("heading", { name: "Alpha Lab", exact: true })).toBeVisible();

  await openSidebarRoute(page, "Execution Intelligence", "/execution-intelligence");
  await expect(page.getByRole("heading", { name: "Execution Intelligence", exact: true })).toBeVisible();

  await openSidebarRoute(page, "Relay + Benchmarks", "/relay-benchmarks");
  await expect(page.getByRole("heading", { name: "Relay + Benchmarks", exact: true })).toBeVisible();

  await openSidebarRoute(page, "CLI Design", "/cli-design");
  await expect(page.getByRole("heading", { name: "CLI Design", exact: true })).toBeVisible();

  await openSidebarRoute(page, "Enterprise", "/enterprise");
  await expect(page.getByRole("heading", { name: "Enterprise", exact: true })).toBeVisible();
});

test("command palette opens and routes ticker jump", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Control+k");
  const input = page.getByPlaceholder("Search actions or type ticker (AAPL)");
  await expect(input).toBeVisible();
  await input.fill("AAPL");
  await page.getByRole("button", { name: /Open AAPL intelligence/i }).click();
  await expect(page).toHaveURL(/\/markets\/AAPL/);
});

test("markets compare mode displays peer symbols", async ({ page }) => {
  await page.goto("/markets/AAPL?compare=MSFT,QQQ");
  await expect(page.getByRole("heading", { name: /AAPL intelligence/i })).toBeVisible();
  await expect(page.getByText("Compare: MSFT · QQQ")).toBeVisible();
});

test("dark mode is the default visual mode", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("html")).toHaveCSS("color-scheme", "dark");
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(16, 24, 32)");
});

async function openSidebarRoute(page: Page, label: string, path: string) {
  const link = page.locator("aside").getByRole("link", { name: label });
  await expect(link).toHaveAttribute("href", path);
  await expect(link).toBeVisible();
  await Promise.all([
    page.waitForURL(new RegExp(`${escapeRegExp(path)}(?:$|[?#])`), { timeout: 20000 }),
    link.click()
  ]);
}

type JsonRecord = Record<string, unknown>;

async function fulfillGovernedPacketRequest(
  route: Route,
  packets: Map<string, JsonRecord>
): Promise<boolean> {
  const request = route.request();
  const url = new URL(request.url());

  if (request.method() === "POST" && url.pathname === "/packets") {
    const input = request.postDataJSON() as JsonRecord;
    const packetId = String(input.id);
    const governed = {
      ...input,
      provenance: [
        {
          envelopeId: `env-${packetId}`,
          source: "playwright-governed-fixture",
          sourceType: "review",
          timestamp: "2026-08-02T00:00:00Z",
          retrievedAt: "2026-08-02T00:00:00Z",
          asOf: "2026-08-02T00:00:00Z",
          stale: false,
          coverageStatus: "full",
          dataMode: "demo",
          pointInTime: true,
          confidence: "verified"
        }
      ],
      disconfirmationResult: {
        status: "pass",
        requiresHumanReview: false,
        summary: "Playwright governed fixture passed.",
        reasons: [],
        evaluator: "playwright-fixture",
        policyVersion: "disconfirmation.v1",
        packetVersion: 1
      },
      riskGateResult: {
        status: "pass",
        reasons: [],
        warnings: [],
        hardBlocks: [],
        missingInputs: [],
        evaluator: "playwright-fixture",
        policyVersion: "risk-policy.v1",
        packetVersion: 1
      },
      integrationStatus: {
        state: "promotable",
        completedStages: ["provenance", "disconfirmation", "risk_gate"],
        staleStages: [],
        blockers: [],
        nextAction: "Record the human decision.",
        policyVersion: "selective-integration.v1",
        updatedAt: "2026-08-02T00:00:00Z"
      }
    };
    packets.set(packetId, governed);
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(governed) });
    return true;
  }

  const packetMatch = url.pathname.match(/^\/packets\/([^/]+)$/);
  if (request.method() === "GET" && packetMatch) {
    const packet = packets.get(decodeURIComponent(packetMatch[1]));
    await route.fulfill({
      status: packet ? 200 : 404,
      contentType: "application/json",
      body: JSON.stringify(packet ?? { detail: "Packet not found" })
    });
    return true;
  }

  const decisionMatch = url.pathname.match(/^\/packets\/([^/]+)\/decision$/);
  if (request.method() === "POST" && decisionMatch) {
    const packetId = decodeURIComponent(decisionMatch[1]);
    const packet = packets.get(packetId);
    if (!packet) {
      await route.fulfill({ status: 404, contentType: "application/json", body: JSON.stringify({ detail: "Packet not found" }) });
      return true;
    }
    const decision = request.postDataJSON() as { decision_state: string };
    const decided = {
      ...packet,
      decisionState: decision.decision_state,
      status: "decision_recorded",
      integrationStatus: {
        ...(packet.integrationStatus as JsonRecord),
        state: "decided",
        completedStages: ["provenance", "disconfirmation", "risk_gate", "human_decision"],
        nextAction: "Observe the forward outcome and resolve decision memory."
      }
    };
    packets.set(packetId, decided);
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(decided) });
    return true;
  }

  return false;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
