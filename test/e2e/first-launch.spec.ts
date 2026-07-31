import { expect, test } from '@playwright/test';
import { DEFAULT_TICKERS, openWorkstation, readMoney, watchlistRow } from './helpers';

test.describe('first launch', () => {
  test('serves the workstation with seeded watchlist and virtual cash', async ({ page }) => {
    await openWorkstation(page);

    await expect(page.getByTestId('watchlist-panel')).toBeVisible();
    await expect(page.getByTestId('trade-bar')).toBeVisible();
    await expect(page.getByTestId('portfolio-summary')).toBeVisible();
    await expect(page.getByTestId('positions-table')).toBeVisible();
    await expect(page.getByTestId('chat-panel')).toBeVisible();

    for (const ticker of DEFAULT_TICKERS) {
      await expect(watchlistRow(page, ticker)).toBeVisible();
      await expect(watchlistRow(page, ticker).getByTestId('watchlist-price')).toContainText(/\d/);
    }

    await expect(page.getByTestId('portfolio-cash')).toContainText('$');
    expect(await readMoney(page.getByTestId('portfolio-cash'))).toBeCloseTo(10_000, 0);
  });

  test('refreshing a client route still serves the static app shell', async ({ page }) => {
    await page.goto('/portfolio');
    await expect(page.getByTestId('app-shell')).toBeVisible();
    await expect(page.getByTestId('portfolio-summary')).toBeVisible();
  });
});
