from datetime import UTC, datetime

import pytest

from packages.market_data.errors import MarketDataError, ProviderErrorCategory
from packages.market_data.symbols import EffectiveProviderSymbol, StaticProviderSymbolResolver


def mapping(
    *,
    instrument_id: str = "KRX:005930",
    symbol: str = "005930.KS",
    valid_from: datetime | None = None,
    valid_to: datetime | None = None,
) -> EffectiveProviderSymbol:
    return EffectiveProviderSymbol(
        provider="yfinance",
        instrument_id=instrument_id,
        symbol=symbol,
        valid_from=valid_from or datetime(2020, 1, 1, tzinfo=UTC),
        valid_to=valid_to,
    )


def test_resolver_returns_provider_symbol_for_entire_request_window() -> None:
    resolver = StaticProviderSymbolResolver((mapping(),))

    symbol = resolver.resolve(
        provider="yfinance",
        instrument_id="KRX:005930",
        start=datetime(2024, 1, 1, tzinfo=UTC),
        end=datetime(2024, 2, 1, tzinfo=UTC),
    )

    assert symbol == "005930.KS"


def test_resolver_rejects_overlaps_and_transition_crossing() -> None:
    transition = datetime(2024, 1, 15, tzinfo=UTC)
    first = mapping(valid_to=transition)
    second = mapping(symbol="005930.NEW", valid_from=transition)
    resolver = StaticProviderSymbolResolver((first, second))

    with pytest.raises(MarketDataError) as captured:
        _ = resolver.resolve(
            provider="yfinance",
            instrument_id="KRX:005930",
            start=datetime(2024, 1, 1, tzinfo=UTC),
            end=datetime(2024, 2, 1, tzinfo=UTC),
        )
    assert captured.value.category is ProviderErrorCategory.INVALID_REQUEST

    with pytest.raises(ValueError, match="must not overlap"):
        _ = StaticProviderSymbolResolver((mapping(), mapping(symbol="005930.NEW")))
