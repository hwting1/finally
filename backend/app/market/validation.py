"""Shared ticker normalization and validation helpers."""

from __future__ import annotations

import re


TICKER_PATTERN = re.compile(r"^[A-Z]{1,5}$")


def normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper()


def is_valid_ticker(ticker: str) -> bool:
    return bool(TICKER_PATTERN.fullmatch(ticker))


def normalize_ticker_set(tickers: set[str]) -> set[str]:
    normalized = {normalize_ticker(ticker) for ticker in tickers if normalize_ticker(ticker)}
    return {ticker for ticker in normalized if is_valid_ticker(ticker)}
