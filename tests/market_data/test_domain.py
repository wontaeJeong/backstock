from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from packages.domain.market_data import AdjustmentMode, Bar, BarRequest, Instrument


def instrument() -> Instrument:
    return Instrument(
        instrument_id="US:XNAS:AAPL",
        symbol="AAPL",
        exchange="XNAS",
        currency="USD",
        timezone="America/New_York",
        name="Apple Inc.",
    )


def test_bar_rejects_impossible_ohlc_values() -> None:
    with pytest.raises(ValidationError):
        _ = Bar(
            instrument_id="US:XNAS:AAPL",
            timestamp=datetime(2024, 1, 2, tzinfo=UTC),
            open=Decimal(100),
            high=Decimal(99),
            low=Decimal(98),
            close=Decimal(99),
            volume=100,
            price_adjustment=AdjustmentMode.RAW,
            volume_adjustment=AdjustmentMode.RAW,
        )


def test_request_requires_aware_half_open_interval() -> None:
    with pytest.raises(ValidationError):
        _ = BarRequest(
            instrument=instrument(),
            start=datetime(2024, 1, 1, tzinfo=UTC).replace(tzinfo=None),
            end=datetime(2024, 1, 2, tzinfo=UTC).replace(tzinfo=None),
            adjustment=AdjustmentMode.RAW,
        )

    with pytest.raises(ValidationError):
        _ = BarRequest(
            instrument=instrument(),
            start=datetime(2024, 1, 2, tzinfo=UTC),
            end=datetime(2024, 1, 2, tzinfo=UTC),
            adjustment=AdjustmentMode.RAW,
        )
