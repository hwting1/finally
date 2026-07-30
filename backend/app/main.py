"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import market, stream
from app.core.config import Settings, settings
from app.market.cache import PriceCache
from app.market.provider import create_market_provider, default_poll_interval_seconds
from app.market.service import MarketDataService, default_ticker_loader


def create_app(app_settings: Settings = settings) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        provider = create_market_provider(app_settings)
        cache = PriceCache(stale_after_seconds=app_settings.market_stale_after_seconds)
        service = MarketDataService(
            provider=provider,
            cache=cache,
            ticker_loader=default_ticker_loader,
            poll_interval_seconds=default_poll_interval_seconds(app_settings),
        )
        app.state.market_cache = cache
        app.state.market_service = service
        await service.start()
        try:
            yield
        finally:
            await service.stop()

    fastapi_app = FastAPI(title="FinAlly Backend", lifespan=lifespan)
    fastapi_app.include_router(market.router)
    fastapi_app.include_router(stream.router)

    @fastapi_app.get("/api/health")
    async def health() -> dict:
        return {"ok": True}

    return fastapi_app


app = create_app()
