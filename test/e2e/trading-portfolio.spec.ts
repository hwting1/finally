import { expect, test } from "@playwright/test";
import { openWorkstation, waitForStream } from "./helpers";

test.describe("manual trading and portfolio updates", () => {
  test("buying shares decreases cash and creates a position", async ({ page }) => {
    await openWorkstation(page);
    await waitForStream(page);

    await page.getByTestId("trade-ticker-input").fill("AAPL");
    await page.getByTestId("trade-quantity-input").fill("1");
    await page.getByTestId("buy-button").click();

    await expect(page.getByTestId("trade-status")).toContainText(/Bought|buy/i);
    await expect(page.getByTestId("positions-table")).toContainText("AAPL");
    await expect(page.getByTestId("portfolio-cash")).not.toContainText("$10,000");
  });

  test("selling shares increases cash and updates the existing position", async ({ page }) => {
    await openWorkstation(page);
    await waitForStream(page);

    await page.getByTestId("trade-ticker-input").fill("MSFT");
    await page.getByTestId("trade-quantity-input").fill("2");
    await page.getByTestId("buy-button").click();
    await expect(page.getByTestId("positions-table")).toContainText("MSFT");

    await page.getByTestId("trade-quantity-input").fill("1");
    await page.getByTestId("sell-button").click();
    await expect(page.getByTestId("trade-status")).toContainText(/Sold|sell/i);
  });
});
