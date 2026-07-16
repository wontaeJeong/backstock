from typing import Protocol

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


class MarketDataProvider(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def capabilities(self) -> ProviderCapabilities: ...

    def get_bars(self, request: BarRequest) -> MarketDataResult[Bar]: ...

    def get_corporate_actions(self, request: BarRequest) -> MarketDataResult[CorporateAction]: ...

    def search_instruments(
        self, request: InstrumentSearchRequest
    ) -> MarketDataResult[Instrument]: ...

    def get_exchange_calendar(
        self, request: ExchangeCalendarRequest
    ) -> MarketDataResult[ExchangeSession]: ...
