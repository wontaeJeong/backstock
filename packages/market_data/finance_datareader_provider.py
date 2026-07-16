import base64
import json
from collections.abc import Callable
from dataclasses import dataclass
from http.client import HTTPSConnection
from importlib.metadata import version
from typing import ClassVar, Protocol
from urllib.parse import urlencode

from pydantic import BaseModel, Field

from packages.domain.market_data import (
    Bar,
    BarRequest,
    CorporateAction,
    ExchangeCalendarRequest,
    ExchangeSession,
    Instrument,
    InstrumentSearchRequest,
    MarketDataResult,
    ProviderCapabilities,
)
from packages.market_data.errors import MarketDataError, ProviderErrorCategory
from packages.market_data.provider_support import lineage, not_supported
from packages.market_data.raw_store import FileRawStore
from packages.market_data.retry import RetryPolicy, retry_call

HTTP_CLIENT_ERROR = 400
WORK_DATE_RESOURCE = "/comm/bldAttendant/executeForResourceBundle.cmd"
WORK_DATE_QUERY = "?baseName=krx.mdc.i18n.component&key=B128.bld"
WORK_DATE_PATH = f"{WORK_DATE_RESOURCE}{WORK_DATE_QUERY}"


class FinanceDataReaderClient(Protocol):
    def listing_data(self, market: str) -> "FinanceDataReaderFetch": ...


class KrxHttpTransport(Protocol):
    def request(self, method: str, path: str, *, body: bytes | None = None) -> bytes: ...


@dataclass(frozen=True)
class FinanceDataReaderFetch:
    raw_payload: bytes
    work_date: str


class _RawEnvelope(BaseModel):
    work_date: str
    work_date_response_base64: str
    listing_response_base64: str


class _WorkDateItem(BaseModel):
    max_work_dt: str


class _WorkDateResult(BaseModel):
    output: tuple[_WorkDateItem, ...]


class _WorkDateResponse(BaseModel):
    result: _WorkDateResult


class _ListingRow(BaseModel):
    code: str = Field(alias="ISU_SRT_CD")
    name: str = Field(alias="ISU_ABBRV")
    market: str = Field(alias="MKT_NM")


class _ListingResponse(BaseModel):
    rows: tuple[_ListingRow, ...] = Field(alias="OutBlock_1")


class _HttpResponse(Protocol):
    status: int

    def read(self) -> bytes: ...


class _HttpsConnection(Protocol):
    def request(
        self,
        method: str,
        url: str,
        body: bytes | None,
        headers: dict[str, str],
    ) -> None: ...

    def getresponse(self) -> _HttpResponse: ...

    def close(self) -> None: ...


ConnectionFactory = Callable[[str, float], _HttpsConnection]


class HttpsKrxTransport:
    timeout_seconds: ClassVar[float] = 10.0
    _host: ClassVar[str] = "data.krx.co.kr"
    _headers: ClassVar[dict[str, str]] = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://data.krx.co.kr/contents/MDC/MDI/outerLoader/index.cmd",
    }
    _connection_factory: ConnectionFactory

    def __init__(self, connection_factory: ConnectionFactory | None = None) -> None:
        """Create a KRX transport whose timeout is applied by its connection factory."""
        self._connection_factory = connection_factory or _new_https_connection

    def request(self, method: str, path: str, *, body: bytes | None = None) -> bytes:
        connection = self._connection_factory(self._host, self.timeout_seconds)
        headers = self._headers | {"Content-Type": "application/x-www-form-urlencoded"}
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            if response.status >= HTTP_CLIENT_ERROR:
                message = f"KRX returned HTTP {response.status}"
                raise ConnectionError(message)
            return response.read()
        finally:
            connection.close()


class DefaultFinanceDataReaderClient:
    _transport: KrxHttpTransport

    def __init__(self, transport: KrxHttpTransport | None = None) -> None:
        """Create a KRX client with injectable bounded HTTP transport."""
        self._transport = transport or HttpsKrxTransport()

    def listing_data(self, market: str) -> FinanceDataReaderFetch:
        market_ids = {"KRX": "ALL", "KOSPI": "STK", "KOSDAQ": "KSQ", "KONEX": "KNX"}
        work_date_payload = self._transport.request("GET", WORK_DATE_PATH)
        work_date = _WorkDateResponse.model_validate_json(work_date_payload)
        selected_date = work_date.result.output[0].max_work_dt
        form = urlencode(
            {
                "bld": "dbms/MDC/STAT/standard/MDCSTAT01501",
                "mktId": market_ids[market],
                "trdDd": selected_date,
                "share": "1",
                "money": "1",
                "csvxls_isNo": "false",
            }
        ).encode()
        listing_payload = self._transport.request(
            "POST", "/comm/bldAttendant/getJsonData.cmd", body=form
        )
        listing = _ListingResponse.model_validate_json(listing_payload)
        del listing
        envelope = json.dumps(
            {
                "work_date": selected_date,
                "work_date_response_base64": base64.b64encode(work_date_payload).decode(),
                "listing_response_base64": base64.b64encode(listing_payload).decode(),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return FinanceDataReaderFetch(
            raw_payload=envelope,
            work_date=selected_date,
        )


class FinanceDataReaderProvider:
    name: ClassVar[str] = "finance_datareader"
    version: ClassVar[str] = version("finance-datareader")

    _client: FinanceDataReaderClient
    _raw_store: FileRawStore
    _retry_policy: RetryPolicy

    def __init__(
        self,
        *,
        raw_store: FileRawStore,
        client: FinanceDataReaderClient | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        """Create a current KRX listing discovery adapter."""
        self._client = client or DefaultFinanceDataReaderClient()
        self._raw_store = raw_store
        self._retry_policy = retry_policy or RetryPolicy()

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            daily_bars=False,
            corporate_actions=False,
            instrument_search=True,
            exchange_calendar=False,
        )

    def get_bars(self, request: BarRequest) -> MarketDataResult[Bar]:
        del request
        raise not_supported(self.name, "historical bars")

    def get_corporate_actions(self, request: BarRequest) -> MarketDataResult[CorporateAction]:
        del request
        raise not_supported(self.name, "corporate actions")

    def search_instruments(self, request: InstrumentSearchRequest) -> MarketDataResult[Instrument]:
        if request.market.upper() != "KRX":
            raise MarketDataError(
                provider=self.name,
                category=ProviderErrorCategory.INVALID_REQUEST,
                message="FinanceDataReader discovery supports the KRX listing only",
                retryable=False,
            )

        def fetch() -> FinanceDataReaderFetch:
            try:
                return self._client.listing_data("KRX")
            except MarketDataError:
                raise
            except (ConnectionError, OSError, TimeoutError) as error:
                raise MarketDataError(
                    provider=self.name,
                    category=ProviderErrorCategory.NETWORK,
                    message="FinanceDataReader KRX listing request failed",
                    retryable=True,
                ) from error
            except Exception as error:
                raise MarketDataError(
                    provider=self.name,
                    category=ProviderErrorCategory.PROVIDER,
                    message="FinanceDataReader could not produce a KRX listing payload",
                    retryable=False,
                ) from error

        fetched = retry_call(fetch, policy=self._retry_policy)
        artifact = self._raw_store.capture(
            provider=self.name,
            provider_version=self.version,
            request={
                "operation": "stock_listing",
                "market": "KRX",
                "query": request.query,
                "listing_scope": "current",
                "adjustment_vintage": "retrospective_at_acquisition",
                "work_date": fetched.work_date,
            },
            payload=fetched.raw_payload,
            media_type="application/json; profile=finance-datareader-capture",
        )
        items = self._normalize_capture(artifact.payload_path.read_bytes(), request.query)
        return MarketDataResult(items=items, lineage=lineage(artifact))

    def get_exchange_calendar(
        self, request: ExchangeCalendarRequest
    ) -> MarketDataResult[ExchangeSession]:
        del request
        raise not_supported(self.name, "exchange calendars")

    def _normalize_capture(self, payload: bytes, query: str) -> tuple[Instrument, ...]:
        try:
            envelope = _RawEnvelope.model_validate_json(payload)
            listing_payload = base64.b64decode(envelope.listing_response_base64, validate=True)
            listing = _ListingResponse.model_validate_json(listing_payload)
            rows: list[Instrument] = []
            folded_query = query.casefold()
            for listing_row in listing.rows:
                code = listing_row.code.zfill(6)
                name = listing_row.name
                if folded_query not in code.casefold() and folded_query not in name.casefold():
                    continue
                rows.append(
                    Instrument(
                        instrument_id=f"KRX:{code}",
                        symbol=code,
                        exchange=listing_row.market,
                        currency="KRW",
                        timezone="Asia/Seoul",
                        name=name,
                    )
                )
            return tuple(rows)
        except Exception as error:
            raise MarketDataError(
                provider=self.name,
                category=ProviderErrorCategory.PARSE,
                message="FinanceDataReader listing could not be normalized",
                retryable=False,
            ) from error


def _new_https_connection(host: str, timeout: float) -> _HttpsConnection:
    return HTTPSConnection(host, timeout=timeout)
