"""Server-sent market data streams."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.market.serialization import quote_to_payload, utc_iso
from app.market.service import MarketDataService


router = APIRouter(prefix="/api/stream", tags=["stream"])


@router.get("/prices")
async def stream_prices(request: Request) -> StreamingResponse:
    service: MarketDataService = request.app.state.market_service

    async def events():
        while not await request.is_disconnected():
            snapshot = await service.cache.snapshot()
            if snapshot:
                payload = {
                    "type": "prices",
                    "timestamp": utc_iso(datetime.now(timezone.utc)),
                    "prices": [quote_to_payload(quote) for quote in snapshot.values()],
                }
                yield f"event: prices\ndata: {json.dumps(payload)}\n\n"
            else:
                payload = {
                    "type": "heartbeat",
                    "timestamp": utc_iso(datetime.now(timezone.utc)),
                }
                yield f"event: heartbeat\ndata: {json.dumps(payload)}\n\n"
            await asyncio.sleep(service.poll_interval_seconds)

    return StreamingResponse(events(), media_type="text/event-stream")
