import { expect, test } from "@playwright/test";

test("workbench opens directly into Trade Review", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Ambrosia", { exact: true })).toBeVisible();
  await expect(page.getByText("Pre-trade adversarial review")).toBeVisible();
  await expect(page.getByText("Strongest critique")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Decision state" })).toBeVisible();
});

test("generated thesis can seed and create a review", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Generate thesis" }).click();
  const tickerInput = page.getByRole("textbox", { name: "Ticker / basket" });
  await expect(tickerInput).not.toHaveValue("");
  await expect(tickerInput).toHaveValue(/^(MARA|IWM|SPCX|TLT)$/);
  await page.getByRole("button", { name: "Generate review" }).click();
  await expect(page.getByRole("heading", { name: /adversarial review/i })).toBeVisible();
  await expect(page.getByText(/signal is aborted/i)).toHaveCount(0);
});

test("market intelligence panel surfaces data provenance before actions", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Price · technicals · sentiment" })).toBeVisible();
  await expect(page.getByText("Every metric shows its data source, timestamp, and mode")).toBeVisible();
  await expect(page.getByRole("button", { name: "Refresh Metrics" })).toBeVisible();
  await expect(page.getByRole("button", { name: "View Technicals" })).toBeVisible();
  await expect(page.getByRole("button", { name: "View Sentiment" })).toBeVisible();
});

test("navigation panels switch to memory calibration and sources", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Decision memory" }).click();
  await expect(page.getByRole("heading", { name: "Captured review decisions" })).toBeVisible();
  await page.getByRole("button", { name: "Calibration" }).click();
  await expect(page.getByRole("heading", { name: "Decision discipline dashboard" })).toBeVisible();
  await page.getByRole("button", { name: "Source library" }).click();
  await expect(page.getByRole("heading", { name: "User-owned evidence and source pointers" })).toBeVisible();
});

test("empty form shows validation instead of silent submit", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Generate review" }).click();
  await expect(page.getByText("Enter a decision-relevant thesis.")).toBeVisible();
});

test("decision buttons update the active review state", async ({ page }) => {
  await page.goto("/");
  const pursueButton = page.locator("aside").getByRole("button", { name: "Pursue" });
  const rejectButton = page.locator("aside").getByRole("button", { name: "Reject" });

  await pursueButton.click();
  await expect(page.getByText("Decision recorded", { exact: true })).toBeVisible();
  await expect(pursueButton).toHaveClass(/bg-teal/);

  await rejectButton.click();
  await expect(rejectButton).toHaveClass(/bg-teal/);
});

test("source library entries navigate back to their review", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Source library" }).click();
  await page.getByRole("button", { name: /User watchlist: BTC miners relative strength/ }).click();
  await expect(page.getByRole("heading", { name: "BTC miners lagging spot Bitcoin" })).toBeVisible();
  await expect(page.getByText("Strongest critique")).toBeVisible();
});

test("dark mode is the default visual mode", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator("html")).toHaveCSS("color-scheme", "dark");
  await expect(page.locator("body")).toHaveCSS("background-color", "rgb(16, 24, 32)");
});
