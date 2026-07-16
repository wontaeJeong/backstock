import base64
from datetime import UTC, datetime
from pathlib import Path
from typing import override

import pytest
from pydantic import BaseModel

from packages.domain.market_data import (
    AdjustmentMode,
    BarRequest,
    Instrument,
    InstrumentSearchRequest,
)
from packages.market_data.errors import MarketDataError, ProviderErrorCategory
from packages.market_data.finance_datareader_provider import (
    WORK_DATE_PATH,
    DefaultFinanceDataReaderClient,
    FinanceDataReaderClient,
    FinanceDataReaderFetch,
    FinanceDataReaderProvider,
    HttpsKrxTransport,
    KrxHttpTransport,
)
from packages.market_data.raw_store import FileRawStore

FIXTURES = Path(__file__).parents[1] / "fixtures" / "market_data"


class FixtureListingClient(FinanceDataReaderClient):
    @override
    def listing_data(self, market: str) -> FinanceDataReaderFetch:
        return DefaultFinanceDataReaderClient(FixtureKrxTransport()).listing_data(market)


class FixtureKrxTransport(KrxHttpTransport):
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, bytes | None]] = []

    @override
    def request(self, method: str, path: str, *, body: bytes | None = None) -> bytes:
        self.calls.append((method, path, body))
        if method == "GET":
            return (FIXTURES / "krx_work_date.json").read_bytes()
        return (FIXTURES / "krx_listing_response.json").read_bytes()


class RawEnvelope(BaseModel):
    work_date: str
    work_date_response_base64: str
    listing_response_base64: str


class FixtureResponse:
    status: int = 200

    def read(self) -> bytes:
        return b"response"


class FixtureConnection:
    requested: tuple[str, str, bytes | None, dict[str, str]] | None = None
    closed: bool = False

    def request(self, method: str, url: str, body: bytes | None, headers: dict[str, str]) -> None:
        self.requested = (method, url, body, headers)

    def getresponse(self) -> FixtureResponse:
        return FixtureResponse()

    def close(self) -> None:
        self.closed = True


def test_current_krx_listing_is_searchable_and_traceable(tmp_path: Path) -> None:
    provider = FinanceDataReaderProvider(
        client=FixtureListingClient(), raw_store=FileRawStore(tmp_path / "raw")
    )

    result = provider.search_instruments(InstrumentSearchRequest(query="삼성", market="KRX"))

    assert [item.instrument_id for item in result.items] == ["KRX:005930"]
    assert result.items[0].currency == "KRW"
    assert dict(result.lineage.request_options)["listing_scope"] == "current"


def test_default_krx_client_preserves_both_http_bodies_offline() -> None:
    transport = FixtureKrxTransport()
    client = DefaultFinanceDataReaderClient(transport)

    fetched = client.listing_data("KRX")

    assert fetched.work_date == "20240104"
    envelope = RawEnvelope.model_validate_json(fetched.raw_payload)
    assert (
        base64.b64decode(envelope.work_date_response_base64)
        == (FIXTURES / "krx_work_date.json").read_bytes()
    )
    assert (
        base64.b64decode(envelope.listing_response_base64)
        == (FIXTURES / "krx_listing_response.json").read_bytes()
    )
    assert [call[0] for call in transport.calls] == ["GET", "POST"]
    assert transport.calls[0][1] == WORK_DATE_PATH
    assert transport.calls[1][1] == "/comm/bldAttendant/getJsonData.cmd"
    assert transport.calls[1][2] is not None
    assert b"trdDd=20240104" in transport.calls[1][2]


def test_https_transport_applies_timeout_to_connection_factory() -> None:
    connection = FixtureConnection()
    factory_call: tuple[str, float] | None = None

    def connection_factory(host: str, timeout: float) -> FixtureConnection:
        nonlocal factory_call
        factory_call = (host, timeout)
        return connection

    transport = HttpsKrxTransport(connection_factory)

    payload = transport.request("GET", "/fixture")

    assert payload == b"response"
    assert factory_call == ("data.krx.co.kr", 10.0)
    assert connection.requested is not None
    assert connection.requested[:2] == ("GET", "/fixture")
    assert connection.closed is True


def test_listing_provider_does_not_claim_historical_bars(tmp_path: Path) -> None:
    provider = FinanceDataReaderProvider(
        client=FixtureListingClient(), raw_store=FileRawStore(tmp_path / "raw")
    )

    instrument = Instrument(
        instrument_id="KRX:005930",
        symbol="005930",
        exchange="KOSPI",
        currency="KRW",
        timezone="Asia/Seoul",
    )
    request = BarRequest(
        instrument=instrument,
        start=datetime(2024, 1, 1, tzinfo=UTC),
        end=datetime(2024, 1, 2, tzinfo=UTC),
        adjustment=AdjustmentMode.RAW,
    )
    with pytest.raises(MarketDataError) as captured:
        _ = provider.get_bars(request)

    assert captured.value.category is ProviderErrorCategory.NOT_SUPPORTED
