"""Portfolio REST routes."""

from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.schemas import PortfolioHistoryResponse, PortfolioResponse, TradeRequest, TradeResponse
from app.services.portfolio import PortfolioService

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


def get_portfolio_service(request: Request) -> PortfolioService:
    return request.app.state.portfolio_service


@router.get("", response_model=PortfolioResponse)
async def get_portfolio(request: Request) -> dict:
    return await get_portfolio_service(request).portfolio()


@router.post("/trade", response_model=TradeResponse)
async def execute_trade(payload: TradeRequest, request: Request) -> dict:
    return await get_portfolio_service(request).trade(
        payload.ticker,
        payload.side,
        payload.quantity,
    )


@router.get("/history", response_model=PortfolioHistoryResponse)
async def get_portfolio_history(request: Request, limit: int = 200) -> dict:
    return await get_portfolio_service(request).history(limit=limit)
