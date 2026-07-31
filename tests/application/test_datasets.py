from datetime import UTC, datetime
from pathlib import Path
from typing import override

import pytest

from packages.application.datasets import DatasetInvalidError, DatasetSnapshotService
from packages.domain.market_data import AdjustmentMode, BarRequest, Instrument
from packages.market_data.local_file import LocalFileProvider, LocalFileSource
from packages.market_data.raw_store import FileRawStore
from packages.market_data.snapshots import FileSnapshotStore
from packages.market_data.symbols import EffectiveProviderSymbol, StaticProviderSymbolResolver
from packages.market_data.yfinance_provider import YFinanceClient, YFinanceProvider

FIXTURES = Path(__file__).parents[1] / "fixtures" / "market_data"


class ChangingYahooClient(YFinanceClient):
    calls: int

    def __init__(self) -> None:
        self.calls = 0

    @override
    def history_csv(
        self, *, symbol: str, start: datetime, end: datetime, auto_adjust: bool
    ) -> bytes:
        del symbol, start, end, auto_adjust
        self.calls += 1
        payload = (FIXTURES / "yahoo_history.csv").read_bytes()
        return payload if self.calls == 1 else payload.replace(b"185.64", b"999.99", 1)


def _request() -> BarRequest:
    return BarRequest(
        instrument=Instrument(
            instrument_id="US:XNAS:AAPL",
            symbol="AAPL",
            exchange="XNAS",
            currency="USD",
            timezone="America/New_York",
        ),
        start=datetime(2024, 1, 2, tzinfo=UTC),
        end=datetime(2024, 1, 5, tzinfo=UTC),
        adjustment=AdjustmentMode.RAW,
    )


def test_provider_result_flows_through_validation_to_snapshot(tmp_path: Path) -> None:
    # Given
    request = _request()
    provider = LocalFileProvider(
        LocalFileSource(
            path=FIXTURES / "local_bars.csv",
            source_name="local_bars.csv",
            instrument=request.instrument,
            price_adjustment=AdjustmentMode.RAW,
            volume_adjustment=AdjustmentMode.RAW,
        ),
        raw_store=FileRawStore(tmp_path / "raw"),
    )
    service = DatasetSnapshotService(FileSnapshotStore(tmp_path / "published"))

    # When
    created = service.create_from_provider(provider, request)
    retrieved = service.get(created.snapshot_id)

    # Then
    assert retrieved == created
    assert created.raw_checksum.startswith("sha256:")
    assert created.row_count == 3


def test_invalid_provider_result_is_not_published(tmp_path: Path) -> None:
    # Given
    invalid = tmp_path / "invalid.csv"
    _ = invalid.write_text(
        "timestamp,open,high,low,close,volume\n2024-01-02T00:00:00-05:00,0,1,0,2,-1\n"
    )
    request = _request()
    provider = LocalFileProvider(
        LocalFileSource(
            path=invalid,
            source_name=invalid.name,
            instrument=request.instrument,
            price_adjustment=AdjustmentMode.RAW,
            volume_adjustment=AdjustmentMode.RAW,
        ),
        raw_store=FileRawStore(tmp_path / "raw"),
    )
    service = DatasetSnapshotService(FileSnapshotStore(tmp_path / "published"))

    # When / Then
    with pytest.raises(DatasetInvalidError):
        _ = service.create_from_provider(provider, request)
    assert not (tmp_path / "published" / "snapshots").exists()


def test_snapshot_rejects_actions_from_a_different_acquisition(tmp_path: Path) -> None:
    request = _request()
    provider = YFinanceProvider(
        client=ChangingYahooClient(),
        raw_store=FileRawStore(tmp_path / "raw"),
        symbol_resolver=StaticProviderSymbolResolver(
            (
                EffectiveProviderSymbol(
                    provider="yfinance",
                    instrument_id=request.instrument.instrument_id,
                    symbol="AAPL",
                    valid_from=datetime(2000, 1, 1, tzinfo=UTC),
                ),
            )
        ),
    )
    service = DatasetSnapshotService(FileSnapshotStore(tmp_path / "published"))

    with pytest.raises(DatasetInvalidError) as captured:
        _ = service.create_from_provider(provider, request)

    assert captured.value.report.status.value == "invalid"
    assert {issue.code.value for issue in captured.value.report.issues} == {"lineage_mismatch"}
