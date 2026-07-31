import { expect, Page } from "@playwright/test";

export async function openWorkstation(page: Page) {
  await page.goto("/");
  await expect(page.getByTestId("app-shell")).toBeVisible();
}

export async function waitForStream(page: Page) {
  await expect(page.getByTestId("connection-status")).toContainText(/connected|reconnecting|disconnected/);
  await expect(page.getByTestId("watchlist-price").first()).not.toHaveText("--", { timeout: 15_000 });
}
