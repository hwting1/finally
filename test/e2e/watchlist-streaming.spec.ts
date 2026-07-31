import { expect, test } from '@playwright/test';
import { openWorkstation, readNumeric, watchlistRow } from './helpers';

test.describe('watchlist streaming', () => {
  test('shows connected state and updates watchlist prices from SSE', async ({ page }) => {
    await openWorkstation(page);

    const status = page.getByTestId('connection-status');
    await expect(status).toHaveAttribute('data-state', 'connected');

    const priceCell = watchlistRow(page, 'AAPL').getByTestId('watchlist-price');
    const firstPrice = await readNumeric(priceCell);

    await expect
      .poll(async () => readNumeric(priceCell), {
        message: 'AAPL price should change as simulator SSE updates arrive',
        timeout: 15_000,
      })
      .not.toBe(firstPrice);
  });

  test('surfaces reconnecting or disconnected state after the stream is interrupted', async ({ page }) => {
    await page.route('**/api/stream/prices', (route) => route.abort());

    await openWorkstation(page);

    await expect(page.getByTestId('connection-status')).toHaveAttribute(
      'data-state',
      /reconnecting|disconnected/,
    );
  });
});
