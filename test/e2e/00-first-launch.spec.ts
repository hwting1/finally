import { expect, test } from "@playwright/test";
import { openWorkstation, waitForStream } from "./helpers";

test.describe("first launch", () => {
  test("serves the workstation with seeded watchlist and virtual cash", async ({ page }) => {
    await openWorkstation(page);
    await waitForStream(page);

    await expect(page.getByText("Market Command")).toBeVisible();
    await expect(page.getByTestId("portfolio-cash")).toContainText("$10,000");

    for (const ticker of ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]) {
      await expect(page.getByTestId(`watchlist-row-${ticker}`)).toBeVisible();
    }
  });

  test("refreshing a client route still serves the static app shell", async ({ page }) => {
    await page.goto("/portfolio/deep-link");
    await expect(page.getByTestId("app-shell")).toBeVisible();
    await page.reload();
    await expect(page.getByTestId("app-shell")).toBeVisible();
  });
});
