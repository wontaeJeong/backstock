from datetime import UTC, datetime, timedelta
from importlib import import_module
from importlib.metadata import version
from typing import TYPE_CHECKING, ClassVar, Final, Protocol, cast

if TYPE_CHECKING:
    from collections.abc import Callable

from packages.domain.market_data import (
    AdjustmentMode,
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
from packages.market_data.normalization import actions_from_yahoo_csv, bars_from_csv
from packages.market_data.provider_support import lineage, not_supported
from packages.market_data.raw_store import (
    FileRawStore,
    FileRequestCache,
    RawArtifact,
    RequestInput,
)
from packages.market_data.retry import RetryPolicy, retry_call
from packages.market_data.symbols import ProviderSymbolResolver

DEFAULT_CACHE_TTL: Final = timedelta(hours=12)


class YFinanceClient(Protocol):
    def history_csv(
        self, *, symbol: str, start: datetime, end: datetime, auto_adjust: bool
    ) -> bytes: ...


class _Frame(Protocol):
    def reset_index(self) -> "_Frame": ...

    def to_csv(self, *, index: bool) -> str: ...


class _Ticker(Protocol):
    def history(self, **kwargs: object) -> _Frame: ...


class DefaultYFinanceClient:
    def history_csv(
        self, *, symbol: str, start: datetime, end: datetime, auto_adjust: bool
    ) -> bytes:
        module = import_module("yfinance")
        ticker_factory = cast("Callable[[str], _Ticker]", vars(module)["Ticker"])
        frame = ticker_factory(symbol).history(
            start=start,
            end=end,
            interval="1d",
            auto_adjust=auto_adjust,
            back_adjust=False,
            actions=True,
            repair=False,
            keepna=False,
            raise_errors=True,
        )
        return frame.reset_index().to_csv(index=False).encode()


class YFinanceProvider:
    name: ClassVar[str] = "yfinance"
    version: ClassVar[str] = version("yfinance")

    _client: YFinanceClient
    _raw_store: FileRawStore
    _request_cache: FileRequestCache | None
    _cache_ttl: timedelta
    _retry_policy: RetryPolicy
    _symbol_resolver: ProviderSymbolResolver

    def __init__(
        self,
        *,
        raw_store: FileRawStore,
        symbol_resolver: ProviderSymbolResolver,
        client: YFinanceClient | None = None,
        request_cache: FileRequestCache | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        """Create a Yahoo daily-bar adapter with optional persistent request caching."""
        self._client = client or DefaultYFinanceClient()
        self._raw_store = raw_store
        self._request_cache = request_cache
        self._cache_ttl = DEFAULT_CACHE_TTL
        self._retry_policy = retry_policy or RetryPolicy()
        self._symbol_resolver = symbol_resolver

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            daily_bars=True,
            corporate_actions=True,
            instrument_search=False,
            exchange_calendar=False,
        )

    def get_bars(self, request: BarRequest) -> MarketDataResult[Bar]:
        artifact = self._artifact(request)
        bars = bars_from_csv(
            artifact.payload_path.read_bytes(),
            instrument=request.instrument,
            price_adjustment=request.adjustment,
            volume_adjustment=AdjustmentMode.RAW,
            provider=self.name,
        )
        start = request.start.astimezone(UTC)
        end = request.end.astimezone(UTC)
        selected = tuple(bar for bar in bars if start <= bar.timestamp.astimezone(UTC) < end)
        return MarketDataResult(items=selected, lineage=lineage(artifact))

    def get_corporate_actions(self, request: BarRequest) -> MarketDataResult[CorporateAction]:
        artifact = self._artifact(request)
        actions = actions_from_yahoo_csv(
            artifact.payload_path.read_bytes(), instrument=request.instrument, provider=self.name
        )
        start = request.start.astimezone(UTC)
        end = request.end.astimezone(UTC)
        selected = tuple(
            action for action in actions if start <= action.effective_at.astimezone(UTC) < end
        )
        return MarketDataResult(items=selected, lineage=lineage(artifact))

    def search_instruments(self, request: InstrumentSearchRequest) -> MarketDataResult[Instrument]:
        del request
        raise not_supported(self.name, "instrument search")

    def get_exchange_calendar(
        self, request: ExchangeCalendarRequest
    ) -> MarketDataResult[ExchangeSession]:
        del request
        raise not_supported(self.name, "exchange calendars")

    def _artifact(self, request: BarRequest) -> RawArtifact:
        provider_symbol = self._symbol_resolver.resolve(
            provider=self.name,
            instrument_id=request.instrument.instrument_id,
            start=request.start,
            end=request.end,
        )
        options = self._request_options(request, provider_symbol)
        if self._request_cache is not None:
            cached = self._request_cache.get(self.name, options)
            if cached is not None:
                return cached

        def fetch() -> bytes:
            try:
                return self._client.history_csv(
                    symbol=provider_symbol,
                    start=request.start,
                    end=request.end,
                    auto_adjust=request.adjustment.value == "adjusted",
                )
            except MarketDataError:
                raise
            except (ConnectionError, OSError, TimeoutError) as error:
                raise MarketDataError(
                    provider=self.name,
                    category=ProviderErrorCategory.NETWORK,
                    message="Yahoo Finance history request failed",
                    retryable=True,
                ) from error
            except Exception as error:
                if type(error).__name__ == "YFRateLimitError":
                    raise MarketDataError(
                        provider=self.name,
                        category=ProviderErrorCategory.QUOTA,
                        message="Yahoo Finance rate limit was reached",
                        retryable=True,
                    ) from error
                raise MarketDataError(
                    provider=self.name,
                    category=ProviderErrorCategory.PROVIDER,
                    message="Yahoo Finance could not produce a history payload",
                    retryable=False,
                ) from error

        payload = retry_call(fetch, policy=self._retry_policy)
        artifact = self._raw_store.capture(
            provider=self.name,
            provider_version=self.version,
            request=options,
            payload=payload,
            media_type="text/csv; profile=yfinance-history",
        )
        if self._request_cache is not None:
            self._request_cache.put(self.name, options, artifact, ttl=self._cache_ttl)
        return artifact

    @staticmethod
    def _request_options(request: BarRequest, provider_symbol: str) -> RequestInput:
        return {
            "operation": "history",
            "instrument_id": request.instrument.instrument_id,
            "provider_symbol": provider_symbol,
            "timezone": request.instrument.timezone,
            "start": request.start.isoformat(),
            "end": request.end.isoformat(),
            "interval": "1d",
            "price_adjustment": request.adjustment.value,
            "volume_adjustment": AdjustmentMode.RAW.value,
            "adjustment_vintage": "retrospective_at_acquisition",
            "actions": True,
        }
