import { expect, type Locator, type Page } from '@playwright/test';

export const DEFAULT_TICKERS = [
  'AAPL',
  'GOOGL',
  'MSFT',
  'AMZN',
  'TSLA',
  'NVDA',
  'META',
  'JPM',
  'V',
  'NFLX',
] as const;

export async function openWorkstation(page: Page): Promise<void> {
  await page.goto('/');
  await expect(page.getByTestId('app-shell')).toBeVisible();
}

export function watchlistRow(page: Page, ticker: string): Locator {
  return page.getByTestId(`watchlist-row-${ticker}`);
}

export async function readMoney(locator: Locator): Promise<number> {
  const text = (await locator.innerText()).replace(/,/g, '');
  const match = text.match(/-?\$?\s*([0-9]+(?:\.[0-9]+)?)/);
  expect(match, `Expected money text in "${text}"`).not.toBeNull();
  return Number(match?.[1]);
}

export async function readNumeric(locator: Locator): Promise<number> {
  const text = (await locator.innerText()).replace(/,/g, '');
  const match = text.match(/-?[0-9]+(?:\.[0-9]+)?/);
  expect(match, `Expected numeric text in "${text}"`).not.toBeNull();
  return Number(match?.[0]);
}

export async function submitTrade(
  page: Page,
  side: 'buy' | 'sell',
  ticker: string,
  quantity: string,
): Promise<void> {
  await page.getByTestId('trade-ticker-input').fill(ticker);
  await page.getByTestId('trade-quantity-input').fill(quantity);
  await page.getByTestId(`${side}-button`).click();
}
