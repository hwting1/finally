import { expect, test } from "@playwright/test";
import { openWorkstation, waitForStream } from "./helpers";

test.describe("watchlist streaming", () => {
  test("shows connected state and updates watchlist prices from SSE", async ({ page }) => {
    await openWorkstation(page);
    await waitForStream(page);

    await expect(page.getByTestId("connection-status")).toContainText("connected");
    await expect(page.getByTestId("watchlist-row-AAPL")).toContainText("$");
  });

  test("surfaces reconnecting or disconnected state after the stream is interrupted", async ({ page }) => {
    await openWorkstation(page);
    await waitForStream(page);
    await page.route("**/api/stream/prices", (route) => route.abort());
    await page.reload();
    await expect(page.getByTestId("connection-status")).toContainText(/connecting|reconnecting|disconnected/);
  });
});
