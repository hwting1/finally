import { expect, test } from '@playwright/test';
import { openWorkstation, readMoney, submitTrade } from './helpers';

test.describe('manual trading and portfolio updates', () => {
  test.beforeEach(async ({ page }) => {
    await openWorkstation(page);
  });

  test('buying shares decreases cash and creates a position', async ({ page }) => {
    const startingCash = await readMoney(page.getByTestId('portfolio-cash'));

    await submitTrade(page, 'buy', 'AAPL', '1');

    await expect(page.getByTestId('trade-status')).toContainText(/bought|filled|executed/i);
    await expect(page.getByTestId('position-row-AAPL')).toBeVisible();
    await expect(page.getByTestId('position-row-AAPL').getByTestId('position-quantity')).toContainText(
      /1(?:\.0+)?/,
    );

    await expect
      .poll(async () => readMoney(page.getByTestId('portfolio-cash')), {
        message: 'cash should decrease after a buy order',
      })
      .toBeLessThan(startingCash);

    await expect(page.getByTestId('portfolio-total')).toContainText('$');
    await expect(page.getByTestId('portfolio-heatmap')).toBeVisible();
    await expect(page.getByTestId('portfolio-pnl-chart')).toBeVisible();
  });

  test('selling shares increases cash and updates the existing position', async ({ page }) => {
    await submitTrade(page, 'buy', 'MSFT', '2');
    await expect(page.getByTestId('position-row-MSFT')).toBeVisible();

    const cashAfterBuy = await readMoney(page.getByTestId('portfolio-cash'));

    await submitTrade(page, 'sell', 'MSFT', '1');

    await expect(page.getByTestId('trade-status')).toContainText(/sold|filled|executed/i);
    await expect
      .poll(async () => readMoney(page.getByTestId('portfolio-cash')), {
        message: 'cash should increase after a sell order',
      })
      .toBeGreaterThan(cashAfterBuy);
    await expect(page.getByTestId('position-row-MSFT').getByTestId('position-quantity')).toContainText(
      /1(?:\.0+)?/,
    );
  });
});
