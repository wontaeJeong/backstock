from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest

from packages.domain.market_data import AdjustmentMode, BarRequest, Instrument
from packages.market_data.errors import MarketDataError, ProviderErrorCategory
from packages.market_data.local_file import LocalFileProvider
from packages.market_data.raw_store import FileRawStore

FIXTURES = Path(__file__).parents[1] / "fixtures" / "market_data"


def test_local_csv_normalizes_decimal_bars_without_network(tmp_path: Path) -> None:
    instrument = Instrument(
        instrument_id="US:XNAS:AAPL",
        symbol="AAPL",
        exchange="XNAS",
        currency="USD",
        timezone="America/New_York",
    )
    provider = LocalFileProvider(
        path=FIXTURES / "local_bars.csv",
        instrument=instrument,
        price_adjustment=AdjustmentMode.RAW,
        volume_adjustment=AdjustmentMode.RAW,
        raw_store=FileRawStore(tmp_path / "raw"),
    )
    request = BarRequest(
        instrument=instrument,
        start=datetime(2024, 1, 3, tzinfo=UTC),
        end=datetime(2024, 1, 5, tzinfo=UTC),
        adjustment=AdjustmentMode.RAW,
    )

    result = provider.get_bars(request)

    assert len(result.items) == 2
    assert result.items[0].open == Decimal("101.50")
    assert result.items[0].volume == 23456
    assert result.lineage.raw_checksum.startswith("sha256:")


def test_local_provider_rejects_adjustment_mismatch(tmp_path: Path) -> None:
    instrument = Instrument(
        instrument_id="US:XNAS:AAPL",
        symbol="AAPL",
        exchange="XNAS",
        currency="USD",
        timezone="America/New_York",
    )
    provider = LocalFileProvider(
        path=FIXTURES / "local_bars.csv",
        instrument=instrument,
        price_adjustment=AdjustmentMode.RAW,
        volume_adjustment=AdjustmentMode.RAW,
        raw_store=FileRawStore(tmp_path / "raw"),
    )
    request = BarRequest(
        instrument=instrument,
        start=datetime(2024, 1, 1, tzinfo=UTC),
        end=datetime(2024, 1, 5, tzinfo=UTC),
        adjustment=AdjustmentMode.ADJUSTED,
    )

    with pytest.raises(MarketDataError) as captured:
        _ = provider.get_bars(request)

    assert captured.value.category is ProviderErrorCategory.INVALID_REQUEST


def test_local_parquet_uses_same_normalization_contract(tmp_path: Path) -> None:
    parquet = tmp_path / "bars.parquet"
    frame = pl.read_csv(FIXTURES / "local_bars.csv", infer_schema=False)
    frame.write_parquet(parquet)
    instrument = Instrument(
        instrument_id="US:XNAS:AAPL",
        symbol="AAPL",
        exchange="XNAS",
        currency="USD",
        timezone="America/New_York",
    )
    provider = LocalFileProvider(
        path=parquet,
        instrument=instrument,
        price_adjustment=AdjustmentMode.RAW,
        volume_adjustment=AdjustmentMode.RAW,
        raw_store=FileRawStore(tmp_path / "raw"),
    )
    request = BarRequest(
        instrument=instrument,
        start=datetime(2024, 1, 1, tzinfo=UTC),
        end=datetime(2024, 1, 5, tzinfo=UTC),
        adjustment=AdjustmentMode.RAW,
    )

    result = provider.get_bars(request)

    assert len(result.items) == 3
    assert result.lineage.raw_payload_path.endswith(".payload")


def test_local_schema_drift_is_a_non_retryable_parse_error(tmp_path: Path) -> None:
    malformed = tmp_path / "malformed.csv"
    _ = malformed.write_text("timestamp,open,high,low,close\n2024-01-02,1,2,1,2\n")
    instrument = Instrument(
        instrument_id="KRX:005930",
        symbol="005930",
        exchange="KOSPI",
        currency="KRW",
        timezone="Asia/Seoul",
    )
    provider = LocalFileProvider(
        path=malformed,
        instrument=instrument,
        price_adjustment=AdjustmentMode.RAW,
        volume_adjustment=AdjustmentMode.RAW,
        raw_store=FileRawStore(tmp_path / "raw"),
    )
    request = BarRequest(
        instrument=instrument,
        start=datetime(2024, 1, 1, tzinfo=UTC),
        end=datetime(2024, 1, 5, tzinfo=UTC),
        adjustment=AdjustmentMode.RAW,
    )

    with pytest.raises(MarketDataError) as captured:
        _ = provider.get_bars(request)

    assert captured.value.category is ProviderErrorCategory.PARSE
    assert captured.value.retryable is False


def test_naive_krx_daily_timestamp_uses_seoul_timezone(tmp_path: Path) -> None:
    fixture = tmp_path / "krx.csv"
    _ = fixture.write_text("timestamp,open,high,low,close,volume\n2024-01-02,100,110,90,105,1234\n")
    instrument = Instrument(
        instrument_id="KRX:005930",
        symbol="005930",
        exchange="KOSPI",
        currency="KRW",
        timezone="Asia/Seoul",
    )
    provider = LocalFileProvider(
        path=fixture,
        instrument=instrument,
        price_adjustment=AdjustmentMode.RAW,
        volume_adjustment=AdjustmentMode.RAW,
        raw_store=FileRawStore(tmp_path / "raw"),
    )
    request = BarRequest(
        instrument=instrument,
        start=datetime(2024, 1, 1, 15, tzinfo=UTC),
        end=datetime(2024, 1, 2, 15, tzinfo=UTC),
        adjustment=AdjustmentMode.RAW,
    )

    result = provider.get_bars(request)

    assert len(result.items) == 1
    assert result.items[0].timestamp.utcoffset() == timedelta(hours=9)
    assert result.items[0].timestamp.astimezone(UTC) == request.start
