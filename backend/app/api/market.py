"""Market data REST diagnostics."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.market.serialization import health_to_payload, quote_to_payload
from app.market.service import MarketDataService
from app.market.validation import is_valid_ticker, normalize_ticker


router = APIRouter(prefix="/api/market", tags=["market"])


def get_market_service(request: Request) -> MarketDataService:
    return request.app.state.market_service


@router.get("/prices")
async def get_prices(request: Request) -> dict:
    service = get_market_service(request)
    snapshot = await service.cache.snapshot()
    return {"prices": [quote_to_payload(quote) for quote in snapshot.values()]}


@router.get("/prices/{ticker}")
async def get_price(ticker: str, request: Request) -> dict:
    symbol = normalize_ticker(ticker)
    if not is_valid_ticker(symbol):
        raise HTTPException(status_code=400, detail={"code": "INVALID_TICKER"})
    service = get_market_service(request)
    quote = await service.cache.get(symbol)
    if quote is None:
        await service.add_tracked_ticker(symbol)
        await service.refresh_once()
        quote = await service.cache.get(symbol)
    if quote is None:
        raise HTTPException(status_code=404, detail={"code": "MARKET_DATA_UNAVAILABLE"})
    return {"price": quote_to_payload(quote)}


@router.get("/health")
async def market_health(request: Request) -> dict:
    service = get_market_service(request)
    return {"market": health_to_payload(service.health())}
