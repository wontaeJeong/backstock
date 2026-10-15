from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import polars as pl
import pytest

from packages.application.datasets import DatasetSnapshotService
from packages.application.research_data import nasdaq_instrument
from packages.application.simulation_models import SimulationRequest
from packages.application.simulations import SimulationService
from packages.domain.market_data import AdjustmentMode, BarRequest
from packages.market_data.errors import MarketDataError
from packages.market_data.local_file import LocalFileProvider, LocalFileSource
from packages.market_data.raw_store import FileRawStore
from packages.market_data.snapshots import FileSnapshotStore, SnapshotIntegrityError
from tests.application.test_simulations import definition


def tick_request() -> BarRequest:
    return BarRequest(
        instrument=nasdaq_instrument("AAPL"),
        start=datetime(2024, 1, 2, 14, 30, tzinfo=UTC),
        end=datetime(2024, 1, 2, 15, tzinfo=UTC),
        adjustment=AdjustmentMode.RAW,
        interval="tick",
    )


def provider(path: Path, root: Path) -> LocalFileProvider:
    return LocalFileProvider(
        LocalFileSource(
            path=path,
            source_name="test",
            instrument=nasdaq_instrument("AAPL"),
            price_adjustment=AdjustmentMode.RAW,
            volume_adjustment=AdjustmentMode.RAW,
        ),
        raw_store=FileRawStore(root / "raw"),
    )


@pytest.mark.parametrize("extension", ["csv", "parquet"])
def test_tick_quotes_normalize_and_roundtrip_verified_parquet(
    tmp_path: Path, extension: str
) -> None:
    path = tmp_path / f"ticks.{extension}"
    frame = pl.DataFrame(
        {
            "timestamp": ["2024-01-02T09:30:00.001-05:00", "2024-01-02T09:30:00.002-05:00"],
            "price": ["100", "100.1"],
            "size": [0, 5],
            "bid": ["99.99", "100.09"],
            "ask": ["100.01", "100.11"],
        }
    )
    if extension == "csv":
        frame.write_csv(path)
    else:
        frame.write_parquet(path)
    store = FileSnapshotStore(tmp_path / "published")
    manifest = DatasetSnapshotService(store).create_from_provider(
        provider(path, tmp_path), tick_request()
    )
    loaded = store.read_bars(manifest.snapshot_id)
    assert loaded is not None
    _, bars = loaded
    assert bars[0].bid == Decimal("99.99")
    assert bars[0].volume == 0
    assert bars[1].open == bars[1].high == bars[1].low == bars[1].close == Decimal("100.1")
    assert dict(manifest.query_options)["timestamp_label"] == "event"
    normalized = (
        tmp_path / "published" / "normalized" / f"{manifest.normalized_checksum[7:]}.parquet"
    )
    normalized.write_bytes(normalized.read_bytes() + b"corrupt")
    with pytest.raises(SnapshotIntegrityError):
        store.read_bars(manifest.snapshot_id)


@pytest.mark.parametrize(
    "rows",
    [
        "2024-01-02T09:30:00,100,1\n",
        "2024-01-02T09:30:00-05:00,100,-1\n",
        "2024-01-02T09:30:00-05:00,0,1\n",
        "2024-01-02T09:30:00-05:00,100,1\n2024-01-02T09:30:00-05:00,100,1\n",
        "2024-01-02T09:30:01-05:00,100,1\n2024-01-02T09:30:00-05:00,100,1\n",
    ],
)
def test_tick_bad_input_rejected_before_raw_publication(tmp_path: Path, rows: str) -> None:
    path = tmp_path / "ticks.csv"
    path.write_text("timestamp,price,size\n" + rows)
    with pytest.raises(MarketDataError):
        provider(path, tmp_path).get_bars(tick_request())
    assert not list((tmp_path / "raw").rglob("*.csv"))


def test_tick_demo_real_next_event_and_latency(tmp_path: Path) -> None:
    report = SimulationService(tmp_path, code_revision="test").run(
        SimulationRequest(
            source="demo",
            symbol="AAPL",
            strategy=definition("tick"),
            initial_cash=Decimal(1000),
            latency_ms=1500,
        )
    )
    assert report.manifest.interval == "tick"
    assert report.manifest.price_adjustment is AdjustmentMode.RAW
    assert report.result.fills[0].timestamp == report.result.orders[
        0
    ].intent.submitted_at + timedelta(seconds=2)


def test_quote_decimal_precision_does_not_round_at_context_28(tmp_path: Path) -> None:
    path = tmp_path / "ticks.csv"
    bid = "99.99999999999999999999999999999"
    ask = "100.00000000000000000000000000001"
    path.write_text(f"timestamp,price,size,bid,ask\n2024-01-02T09:30:00-05:00,100,1,{bid},{ask}\n")
    store = FileSnapshotStore(tmp_path / "published")
    manifest = DatasetSnapshotService(store).create_from_provider(
        provider(path, tmp_path), tick_request()
    )
    loaded = store.read_bars(manifest.snapshot_id)
    assert loaded is not None
    assert loaded[1][0].bid == Decimal(bid)
    assert loaded[1][0].ask == Decimal(ask)
