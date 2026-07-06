import { expect, test, type Page } from "@playwright/test";

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
  await expect(page.getByText("Sticky decision strip")).toBeVisible();
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

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
