"""Watchlist REST routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.schemas import TickerRequest, WatchlistResponse
from app.services.portfolio import WatchlistService

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


def get_watchlist_service(request: Request) -> WatchlistService:
    return request.app.state.watchlist_service


@router.get("", response_model=WatchlistResponse)
async def get_watchlist(request: Request) -> dict:
    return await get_watchlist_service(request).watchlist()


@router.post("")
async def add_watchlist_ticker(payload: TickerRequest, request: Request) -> dict:
    return await get_watchlist_service(request).add(payload.ticker)


@router.delete("/{ticker}")
async def remove_watchlist_ticker(ticker: str, request: Request) -> dict:
    return await get_watchlist_service(request).remove(ticker)
