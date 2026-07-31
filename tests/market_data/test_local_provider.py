from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest

from packages.domain.market_data import AdjustmentMode, BarRequest, Instrument
from packages.market_data.errors import MarketDataError, ProviderErrorCategory
from packages.market_data.local_file import LocalFileProvider, LocalFileSource
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
        LocalFileSource(
            path=FIXTURES / "local_bars.csv",
            source_name="local_bars.csv",
            instrument=instrument,
            price_adjustment=AdjustmentMode.RAW,
            volume_adjustment=AdjustmentMode.RAW,
        ),
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
        LocalFileSource(
            path=FIXTURES / "local_bars.csv",
            source_name="local_bars.csv",
            instrument=instrument,
            price_adjustment=AdjustmentMode.RAW,
            volume_adjustment=AdjustmentMode.RAW,
        ),
        raw_store=FileRawStore(tmp_path / "raw"),
    )
    request = BarRequest(
        instrument=instrument,
        start=datetime(2024, 1, 1, tzinfo=UTC),
        end=datetime(2024, 1, 5, tzinfo=UTC),
        adjustment=AdjustmentMode.TOTAL_RETURN_ADJUSTED,
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
        LocalFileSource(
            path=parquet,
            source_name=parquet.name,
            instrument=instrument,
            price_adjustment=AdjustmentMode.RAW,
            volume_adjustment=AdjustmentMode.RAW,
        ),
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
        LocalFileSource(
            path=malformed,
            source_name=malformed.name,
            instrument=instrument,
            price_adjustment=AdjustmentMode.RAW,
            volume_adjustment=AdjustmentMode.RAW,
        ),
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
        LocalFileSource(
            path=fixture,
            source_name=fixture.name,
            instrument=instrument,
            price_adjustment=AdjustmentMode.RAW,
            volume_adjustment=AdjustmentMode.RAW,
        ),
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


def test_local_parquet_normalization_uses_captured_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.parquet"
    replacement = tmp_path / "replacement.parquet"
    original_frame = pl.read_csv(FIXTURES / "local_bars.csv", infer_schema=False)
    original_frame.write_parquet(source)
    original_frame.with_columns(pl.lit("999.00").alias("open")).write_parquet(replacement)
    instrument = Instrument(
        instrument_id="US:XNAS:AAPL",
        symbol="AAPL",
        exchange="XNAS",
        currency="USD",
        timezone="America/New_York",
    )
    provider = LocalFileProvider(
        LocalFileSource(
            path=source,
            source_name=source.name,
            instrument=instrument,
            price_adjustment=AdjustmentMode.RAW,
            volume_adjustment=AdjustmentMode.RAW,
        ),
        raw_store=FileRawStore(tmp_path / "raw"),
    )
    request = BarRequest(
        instrument=instrument,
        start=datetime(2024, 1, 1, tzinfo=UTC),
        end=datetime(2024, 1, 5, tzinfo=UTC),
        adjustment=AdjustmentMode.RAW,
    )
    original_read_bytes = Path.read_bytes
    replaced = False

    def read_then_replace(path: Path) -> bytes:
        nonlocal replaced
        payload = original_read_bytes(path)
        if path == source and not replaced:
            replaced = True
            _ = source.write_bytes(original_read_bytes(replacement))
        return payload

    monkeypatch.setattr(Path, "read_bytes", read_then_replace)

    result = provider.get_bars(request)

    assert result.items[0].open == Decimal("100.10")
