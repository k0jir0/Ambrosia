import type { Route } from "@playwright/test";

export const LOCAL_API_ROUTE = "http://localhost:8000/**";
export const SAME_ORIGIN_API_ROUTE = "**/api/**";

export async function fulfillAuthenticatedAccount(route: Route): Promise<boolean> {
  const url = new URL(route.request().url());
  const pathname = url.pathname.replace(/^\/api(?=\/)/, "");
  if (pathname !== "/auth/me") return false;
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      user: {
        id: "user-e2e-owner",
        email: "owner@example.com",
        displayName: "Avery Chen",
        professionalRole: "portfolio_manager",
      },
      organization: { id: "org-e2e", name: "Northstar Capital", role: "owner" },
      session: { id: "session-e2e" },
    }),
  });
  return true;
}
