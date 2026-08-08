import { expect, test } from "@playwright/test";

import { fulfillAuthenticatedAccount, LOCAL_API_ROUTE } from "./helpers";

test("visitor can complete signup, verification, and onboarding choice", async ({ page }) => {
  const requests: string[] = [];
  await page.route(LOCAL_API_ROUTE, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    requests.push(`${request.method()} ${path}`);
    if (path === "/auth/signup") {
      const body = request.postDataJSON() as { email: string; acceptedTerms: boolean };
      expect(body.email).toBe("avery@example.com");
      expect(body.acceptedTerms).toBe(true);
      await route.fulfill({
        status: 201, contentType: "application/json",
        body: JSON.stringify({
          status: "pending_verification", message: "Check your email.",
          userId: "user-1", organizationId: "org-1", workspaceId: "workspace-1",
          developmentVerificationToken: "verification-token-that-is-long-enough",
        }),
      });
      return;
    }
    if (path === "/auth/verify-email") {
      await route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({
          user: { id: "user-1", email: "avery@example.com", displayName: "Avery Chen", professionalRole: "portfolio_manager" },
          organization: { id: "org-1", name: "Northstar Capital", role: "owner" },
          session: { id: "session-1" },
        }),
      });
      return;
    }
    if (await fulfillAuthenticatedAccount(route)) return;
    await route.abort();
  });

  await page.goto("/signup");
  await page.getByLabel("Work email").fill("avery@example.com");
  await page.getByLabel("Name").fill("Avery Chen");
  await page.getByLabel("Your role").selectOption("portfolio_manager");
  await page.getByLabel("Organization").fill("Northstar Capital");
  await page.getByLabel("Password", { exact: true }).fill("a careful portfolio passphrase 2026");
  await page.getByText(/I accept the/).click();
  await page.getByRole("button", { name: "Create private workspace" }).click();
  await expect(page.getByRole("heading", { name: "Verify this account" })).toBeVisible();
  await page.getByRole("link", { name: "Verify development account" }).click();
  await expect(page).toHaveURL(/\/onboarding$/, { timeout: 15000 });
  await expect(page.getByRole("heading", { name: /Make Ambrosia earn your trust/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /Start guided case/i })).toBeVisible();
  expect(requests).toContain("POST /auth/signup");
  expect(requests).toContain("POST /auth/verify-email");
});

test("protected workspace redirects an unauthenticated visitor to login", async ({ page }) => {
  await page.route(LOCAL_API_ROUTE, (route) => route.abort());
  await page.goto("/app");
  await page.waitForURL(/\/login\?returnTo=%2Fapp/);
  await expect(page.getByRole("heading", { name: /Return to the decisions/i })).toBeVisible();
});

test("password recovery reports unavailable delivery without claiming success", async ({ page }) => {
  await page.route(LOCAL_API_ROUTE, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path === "/auth/forgot-password" && request.method() === "POST") {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Password recovery is temporarily unavailable" }),
      });
      return;
    }
    await route.abort();
  });

  await page.goto("/forgot-password");
  await page.getByLabel("Email").fill("owner@example.com");
  await page.getByRole("button", { name: "Send reset link" }).click();
  await expect(page.getByText("Password recovery is temporarily unavailable. Please try again later.", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Send reset link" })).toBeVisible();
  await expect(page.getByText(/has been sent/i)).toHaveCount(0);
});

test("team surface renders only tenant-backed members and invitations", async ({ page }) => {
  let invitations = 0;
  await page.route(LOCAL_API_ROUTE, async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (await fulfillAuthenticatedAccount(route)) return;
    if (path === "/team" && request.method() === "GET") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({
        members: [{ id: "user-e2e-owner", email: "owner@example.com", display_name: "Avery Chen", professional_role: "portfolio_manager", role: "owner", status: "active" }],
        invitations: invitations ? [{ id: "invite-1", email: "analyst@example.com", role: "analyst" }] : [],
      }) });
      return;
    }
    if (path === "/team/invitations" && request.method() === "POST") {
      invitations += 1;
      await route.fulfill({ status: 201, contentType: "application/json", body: JSON.stringify({ id: "invite-1", email: "analyst@example.com", role: "analyst", developmentInvitationToken: "invitation-token-that-is-long-enough" }) });
      return;
    }
    await route.abort();
  });
  await page.goto("/team");
  await expect(page.getByText("Avery Chen")).toBeVisible();
  await expect(page.getByText("Risk Committee workspace")).toHaveCount(0);
  await page.getByLabel("Work email").fill("analyst@example.com");
  await page.getByRole("button", { name: "Send invitation" }).click();
  await expect(page.getByText(/Development invite:/)).toBeVisible();
  await expect(page.getByText("analyst@example.com")).toBeVisible();
});

test("company proof separates implemented evidence from external gates", async ({ page }) => {
  await page.goto("/company-proof");
  await expect(page.getByRole("heading", { name: /limitations left visible/i })).toBeVisible();
  await expect(page.getByText("Open evidence gates")).toBeVisible();
  await expect(page.getByText(/No paid design-partner retention/)).toBeVisible();
});
