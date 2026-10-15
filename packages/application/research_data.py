from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.application.datasets import DatasetSnapshotService
from packages.application.simulation_models import SimulationRequest
from packages.domain.market_data import (
    AdjustmentMode,
    Bar,
    BarRequest,
    Instrument,
    MarketDataResult,
)
from packages.market_data.provider_support import lineage
from packages.market_data.raw_store import FileRawStore, FileRequestCache
from packages.market_data.snapshots import FileSnapshotStore, SnapshotManifest
from packages.market_data.symbols import EffectiveProviderSymbol, StaticProviderSymbolResolver
from packages.market_data.yfinance_provider import YFinanceProvider

DEMO_HALF_CYCLE = 30
SATURDAY = 5
SESSION_CLOSE_HOUR = 16


def nasdaq_instrument(symbol: str) -> Instrument:
    return Instrument(
        instrument_id=f"NASDAQ:{symbol}",
        symbol=symbol,
        exchange="NASDAQ",
        currency="USD",
        timezone="America/New_York",
    )


def acquire_research_data(root: Path, request: SimulationRequest) -> SnapshotManifest:
    store = FileSnapshotStore(root / "published")
    service = DatasetSnapshotService(store)
    if request.source == "snapshot":
        return service.get(request.snapshot_id or "")
    if request.source == "demo":
        return _demo(root, request, service)
    if request.start is None or request.end is None:
        msg = "기간을 선택하세요."
        raise ValueError(msg)
    raw = FileRawStore(root / "raw")
    provider = YFinanceProvider(
        raw_store=raw,
        request_cache=FileRequestCache(root / "cache", store=raw),
        symbol_resolver=StaticProviderSymbolResolver(
            (
                EffectiveProviderSymbol(
                    provider="yfinance",
                    instrument_id=f"NASDAQ:{request.symbol}",
                    symbol=request.symbol,
                    valid_from=request.start,
                ),
            )
        ),
    )
    return service.create_from_provider(
        provider,
        BarRequest(
            instrument=nasdaq_instrument(request.symbol),
            start=request.start,
            end=request.end,
            adjustment=AdjustmentMode.TOTAL_RETURN_ADJUSTED,
        ),
    )


def _demo(
    root: Path, request: SimulationRequest, service: DatasetSnapshotService
) -> SnapshotManifest:
    interval = request.strategy.timeframe
    start = datetime(2024, 1, 2, 9, 31, tzinfo=ZoneInfo("America/New_York"))
    if interval == "1d":
        start = start.replace(hour=0, minute=0)
    elif interval == "5m":
        start = start.replace(minute=35)
    bars: list[Bar] = []
    timestamp = start
    for index in range(120):
        price = (
            Decimal(100)
            + Decimal(index) / 10
            + Decimal((index % 30) if index % 60 < DEMO_HALF_CYCLE else 30 - index % 30) / 2
        )
        close = price + Decimal("0.2")
        bars.append(
            Bar(
                instrument_id=f"NASDAQ:{request.symbol}",
                timestamp=timestamp,
                open=price,
                high=close + 1,
                low=price - 1,
                close=close,
                volume=10000 + index * 10,
                price_adjustment=AdjustmentMode.RAW,
                volume_adjustment=AdjustmentMode.RAW,
            )
        )
        timestamp += (
            timedelta(days=1)
            if interval == "1d"
            else timedelta(minutes=1 if interval == "1m" else 5)
        )
        if interval == "1d":
            while timestamp.weekday() >= SATURDAY:
                timestamp += timedelta(days=1)
        elif timestamp.hour >= SESSION_CLOSE_HOUR:
            timestamp = (timestamp + timedelta(days=1)).replace(
                hour=9, minute=31 if interval == "1m" else 35
            )
    payload = ("[" + ",".join(bar.model_dump_json() for bar in bars) + "]").encode()
    raw = FileRawStore(root / "raw", clock=lambda: datetime(2024, 1, 1, tzinfo=UTC))
    artifact = raw.capture(
        provider="synthetic_demo",
        provider_version="1",
        request={
            "interval": interval,
            "provider_symbol": request.symbol,
            "synthetic": True,
            "timestamp_label": "close" if interval != "1d" else "session_date",
        },
        payload=payload,
        media_type="application/json",
    )
    return service.create_from_result(
        BarRequest(
            instrument=nasdaq_instrument(request.symbol),
            start=start,
            end=timestamp,
            interval=interval,
            adjustment=AdjustmentMode.RAW,
        ),
        MarketDataResult(items=tuple(bars), lineage=lineage(artifact)),
    )
