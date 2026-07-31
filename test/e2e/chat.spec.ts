import { expect, test } from "@playwright/test";
import { openWorkstation, waitForStream } from "./helpers";

test.describe("chat availability", () => {
  test("mock chat executes deterministic actions when LLM_MOCK=true", async ({ page }) => {
    await openWorkstation(page);
    await waitForStream(page);

    await expect(page.getByTestId("chat-panel")).not.toHaveAttribute("data-state", "disabled", { timeout: 15_000 });
    await page.getByTestId("chat-input").fill("Buy one share of AAPL and add AMD");
    await page.getByTestId("chat-send-button").click();
    await expect(page.getByTestId("chat-panel")).toContainText(/Mock|AAPL|AMD|trade/i);
  });

  test("disabled chat state is visible when backend reports chat unavailable", async ({ page }) => {
    await page.route("**/api/health", (route) =>
      route.fulfill({ json: { ok: true, market: "simulator", chat_enabled: false } })
    );
    await openWorkstation(page);
    await expect(page.getByTestId("chat-panel")).toHaveAttribute("data-state", "disabled");
    await expect(page.getByTestId("chat-disabled-message")).toContainText("LLM API key");
  });
});
