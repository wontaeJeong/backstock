from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import override

import pytest

from packages.domain.market_data import AdjustmentMode, BarRequest, Instrument
from packages.market_data.errors import MarketDataError, ProviderErrorCategory
from packages.market_data.raw_store import FileRawStore, FileRequestCache
from packages.market_data.retry import RetryPolicy
from packages.market_data.symbols import EffectiveProviderSymbol, StaticProviderSymbolResolver
from packages.market_data.yfinance_provider import YFinanceClient, YFinanceProvider

FIXTURES = Path(__file__).parents[1] / "fixtures" / "market_data"
INVALID_TICKER_RESPONSE = "invalid ticker response"
TRANSIENT_NETWORK_ERROR = "temporary network error"


class FixtureYahooClient(YFinanceClient):
    def __init__(self) -> None:
        self.calls: list[tuple[str, datetime, datetime, bool]] = []

    @override
    def history_csv(
        self, *, symbol: str, start: datetime, end: datetime, auto_adjust: bool
    ) -> bytes:
        self.calls.append((symbol, start, end, auto_adjust))
        fixture = "yahoo_adjusted_history.csv" if auto_adjust else "yahoo_history.csv"
        return (FIXTURES / fixture).read_bytes()


class InvalidYahooClient(YFinanceClient):
    calls: int

    def __init__(self) -> None:
        self.calls = 0

    @override
    def history_csv(
        self, *, symbol: str, start: datetime, end: datetime, auto_adjust: bool
    ) -> bytes:
        del symbol, start, end, auto_adjust
        self.calls += 1
        raise ValueError(INVALID_TICKER_RESPONSE)


class TransientYahooClient(YFinanceClient):
    calls: int

    def __init__(self) -> None:
        self.calls = 0

    @override
    def history_csv(
        self, *, symbol: str, start: datetime, end: datetime, auto_adjust: bool
    ) -> bytes:
        del symbol, start, end, auto_adjust
        self.calls += 1
        if self.calls == 1:
            raise OSError(TRANSIENT_NETWORK_ERROR)
        return (FIXTURES / "yahoo_history.csv").read_bytes()


def apple() -> Instrument:
    return Instrument(
        instrument_id="US:XNAS:AAPL",
        symbol="AAPL",
        exchange="XNAS",
        currency="USD",
        timezone="America/New_York",
    )


def request(adjustment: AdjustmentMode = AdjustmentMode.RAW) -> BarRequest:
    return BarRequest(
        instrument=apple(),
        start=datetime(2024, 1, 1, tzinfo=UTC),
        end=datetime(2024, 1, 5, tzinfo=UTC),
        adjustment=adjustment,
    )


def resolver(symbol: str = "AAPL-YAHOO") -> StaticProviderSymbolResolver:
    return StaticProviderSymbolResolver(
        (
            EffectiveProviderSymbol(
                provider="yfinance",
                instrument_id="US:XNAS:AAPL",
                symbol=symbol,
                valid_from=datetime(2000, 1, 1, tzinfo=UTC),
            ),
        )
    )


def test_yahoo_bars_and_actions_share_explicit_raw_lineage(tmp_path: Path) -> None:
    client = FixtureYahooClient()
    store = FileRawStore(tmp_path / "raw")
    provider = YFinanceProvider(
        client=client,
        raw_store=store,
        symbol_resolver=resolver(),
        request_cache=FileRequestCache(tmp_path / "cache", store=store),
    )

    bars = provider.get_bars(request())
    actions = provider.get_corporate_actions(request())
    cached_bars = provider.get_bars(request())

    assert len(client.calls) == 1
    assert client.calls[0][0] == "AAPL-YAHOO"
    assert client.calls[0][3] is False
    assert bars.items[0].close == Decimal("185.64")
    assert bars.items == cached_bars.items
    assert bars.lineage.raw_checksum == actions.lineage.raw_checksum
    assert {action.kind.value for action in actions.items} == {"cash_dividend", "split"}


def test_yahoo_adjusted_mode_is_forwarded_to_upstream(tmp_path: Path) -> None:
    client = FixtureYahooClient()
    provider = YFinanceProvider(
        client=client,
        raw_store=FileRawStore(tmp_path / "raw"),
        symbol_resolver=resolver(),
    )

    result = provider.get_bars(request(AdjustmentMode.ADJUSTED))

    assert client.calls[0][3] is True
    assert result.items[0].close == Decimal("184.73")
    assert result.items[0].price_adjustment is AdjustmentMode.ADJUSTED
    assert result.items[0].volume_adjustment is AdjustmentMode.RAW
    assert dict(result.lineage.request_options)["adjustment_vintage"] == (
        "retrospective_at_acquisition"
    )


def test_yahoo_unknown_provider_failure_is_not_retried(tmp_path: Path) -> None:
    client = InvalidYahooClient()
    provider = YFinanceProvider(
        client=client,
        raw_store=FileRawStore(tmp_path / "raw"),
        symbol_resolver=resolver(),
    )

    with pytest.raises(MarketDataError) as captured:
        _ = provider.get_bars(request())

    assert client.calls == 1
    assert captured.value.category is ProviderErrorCategory.PROVIDER
    assert captured.value.retryable is False


def test_yahoo_transport_failure_is_retried(tmp_path: Path) -> None:
    client = TransientYahooClient()
    provider = YFinanceProvider(
        client=client,
        raw_store=FileRawStore(tmp_path / "raw"),
        symbol_resolver=resolver(),
        retry_policy=RetryPolicy(
            max_attempts=2,
            initial_delay_seconds=0,
            jitter_seconds=0,
        ),
    )

    result = provider.get_bars(request())

    assert client.calls == 2
    assert len(result.items) == 3
