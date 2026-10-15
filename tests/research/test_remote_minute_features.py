import hashlib
from datetime import UTC, datetime, timedelta
from importlib import import_module
from pathlib import Path

import pytest

from packages.application.research_data import nasdaq_instrument
from packages.domain.market_data import AdjustmentMode, BarRequest
from packages.market_data.errors import MarketDataError
from packages.market_data.raw_store import FileRawStore
from packages.market_data.symbols import EffectiveProviderSymbol, StaticProviderSymbolResolver
from packages.market_data.yfinance_provider import DefaultYFinanceClient, YFinanceProvider

ACQUIRED = datetime(2026, 10, 16, 14, 32, 30, tzinfo=UTC)
CSV = (
    b"Datetime,Open,High,Low,Close,Volume,Dividends,Stock Splits\n"
    b"2026-10-16T10:30:00-04:00,100,102,99,101,50,0,0\n"
    b"2026-10-16T10:31:00-04:00,101,103,100,102,60,0,0\n"
    b"2026-10-16T10:32:00-04:00,102,104,101,103,70,0,0\n"
)


class MinuteClient:
    def __init__(self) -> None:
        self.intervals: list[str] = []

    def history_csv(
        self,
        *,
        symbol: str,
        start: datetime,
        end: datetime,
        auto_adjust: bool,
        interval: str = "1d",
    ) -> bytes:
        assert symbol == "AAPL"
        assert start < end
        assert auto_adjust
        self.intervals.append(interval)
        return CSV


def make_provider(root: Path, client: MinuteClient) -> YFinanceProvider:
    return YFinanceProvider(
        raw_store=FileRawStore(root / "raw", clock=lambda: ACQUIRED),
        symbol_resolver=StaticProviderSymbolResolver(
            (
                EffectiveProviderSymbol(
                    provider="yfinance",
                    instrument_id="NASDAQ:AAPL",
                    symbol="AAPL",
                    valid_from=ACQUIRED - timedelta(days=365),
                ),
            )
        ),
        client=client,
        clock=lambda: ACQUIRED,
    )


def request(interval: str = "1m", days: int = 0) -> BarRequest:
    return BarRequest.model_validate(
        {
            "instrument": nasdaq_instrument("AAPL"),
            "start": datetime(2026, 10, 16, 14, 30, tzinfo=UTC) - timedelta(days=days),
            "end": ACQUIRED,
            "adjustment": (
                AdjustmentMode.RAW if interval == "tick" else AdjustmentMode.TOTAL_RETURN_ADJUSTED
            ),
            "interval": interval,
        }
    )


def test_minute_provider_uses_explicit_interval_closes_and_only_finalized(tmp_path: Path) -> None:
    client = MinuteClient()
    data = make_provider(tmp_path, client).get_bars(request())
    assert client.intervals == ["1m"]
    assert [b.timestamp for b in data.items] == [
        datetime(2026, 10, 16, 14, minute, tzinfo=UTC) for minute in (31, 32)
    ]
    assert data.items[0].price_adjustment is AdjustmentMode.TOTAL_RETURN_ADJUSTED
    assert data.items[0].volume_adjustment is AdjustmentMode.RAW
    notes = dict(data.lineage.request_options)
    assert notes["upstream_timestamp_label"] == "open"
    assert notes["timestamp_label"] == "close"
    assert notes["prepost"] is False
    assert data.lineage.raw_checksum == f"sha256:{hashlib.sha256(CSV).hexdigest()}"


@pytest.mark.parametrize(("interval", "days"), [("1m", 8), ("5m", 61), ("tick", 0)])
def test_remote_bounds_and_tick_reject_without_provider_call(
    tmp_path: Path, interval: str, days: int
) -> None:
    client = MinuteClient()
    with pytest.raises(MarketDataError):
        make_provider(tmp_path, client).get_bars(request(interval, days))
    assert client.intervals == []


def test_five_minute_contract_and_finalization(tmp_path: Path) -> None:
    client = MinuteClient()
    data = make_provider(tmp_path, client).get_bars(request("5m"))
    assert client.intervals == ["5m"]
    assert data.items == ()  # the 10:30 open candle has not closed at acquisition


def test_pinned_default_client_sdk_options_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    options: dict[str, object] = {}

    class Frame:
        def reset_index(self) -> "Frame":
            return self

        def to_csv(self, *, index: bool) -> str:
            assert index is False
            return CSV.decode()

    class Ticker:
        def history(self, **kwargs: object) -> Frame:
            options.update(kwargs)
            return Frame()

    def ticker(symbol: str) -> Ticker:
        assert symbol == "AAPL"
        return Ticker()

    monkeypatch.setattr(import_module("yfinance"), "Ticker", ticker)
    assert YFinanceProvider.version == "1.5.1"
    payload = DefaultYFinanceClient().history_csv(
        symbol="AAPL", start=request().start, end=request().end, auto_adjust=False, interval="5m"
    )
    assert payload == CSV
    assert options["interval"] == "5m"
    assert options["prepost"] is False
    assert options["auto_adjust"] is False
    assert options["back_adjust"] is False
    assert options["repair"] is False
    assert options["actions"] is True
