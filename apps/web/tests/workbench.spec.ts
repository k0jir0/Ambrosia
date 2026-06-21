import { expect, test } from "@playwright/test";

test("workbench opens directly into Trade Review", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText("Ambrosia", { exact: true })).toBeVisible();
  await expect(page.getByText("Pre-trade adversarial review")).toBeVisible();
  await expect(page.getByText("Strongest critique")).toBeVisible();
  await expect(page.getByText("Decision state")).toBeVisible();
});

test("generated thesis can seed and create a review", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "Generate thesis" }).click();
  await expect(page.getByRole("textbox", { name: "Ticker / basket" })).not.toHaveValue("");
  await page.getByRole("button", { name: "Generate review" }).click();
  await expect(page.getByRole("heading", { name: /adversarial review/i })).toBeVisible();
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