import { expect, test } from '@playwright/test';
import { openWorkstation } from './helpers';

test.describe('chat availability', () => {
  test('disables chat when no LLM key is configured and mock mode is off', async ({ page }) => {
    test.skip(
      process.env.LLM_MOCK === 'true' || !!process.env.LLM_API_KEY,
      'Run without LLM_API_KEY and with LLM_MOCK=false to verify disabled chat state.',
    );

    await openWorkstation(page);

    await expect(page.getByTestId('chat-panel')).toHaveAttribute('data-state', 'disabled');
    await expect(page.getByTestId('chat-disabled-message')).toContainText(/LLM.*key|required|configured/i);
    await expect(page.getByTestId('chat-input')).toBeDisabled();
    await expect(page.getByTestId('chat-send-button')).toBeDisabled();
  });

  test('mock chat executes deterministic actions when LLM_MOCK=true', async ({ page }) => {
    test.skip(process.env.LLM_MOCK !== 'true', 'Run with LLM_MOCK=true to verify mock chat actions.');

    await openWorkstation(page);

    await expect(page.getByTestId('chat-panel')).toHaveAttribute('data-state', /ready|enabled/);
    await page.getByTestId('chat-input').fill('Use mock mode to buy one share of AAPL.');
    await page.getByTestId('chat-send-button').click();

    await expect(page.getByTestId('chat-message-assistant').last()).toBeVisible();
    await expect(page.getByTestId('chat-action-result').last()).toContainText(/AAPL|buy|executed/i);
    await expect(page.getByTestId('position-row-AAPL')).toBeVisible();
  });
});
