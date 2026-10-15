from datetime import datetime
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from packages.domain.market_data import AdjustmentMode, BarRequest, Instrument

UNAWARE_UPLOAD_START = "start must be timezone-aware"
INVALID_UPLOAD_END = "end must be timezone-aware and after start"


class HealthResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    status: str


class ErrorResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    code: str
    message: str
    details: dict[str, JsonValue] = Field(default_factory=dict)
    request_id: str


class DatasetUploadRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    instrument_id: str = Field(min_length=1, max_length=100)
    symbol: str = Field(min_length=1, max_length=50)
    exchange: str = Field(min_length=1, max_length=50)
    currency: str = Field(min_length=3, max_length=3)
    timezone: str = Field(min_length=1, max_length=100)
    start: datetime
    end: datetime
    price_adjustment: AdjustmentMode
    volume_adjustment: AdjustmentMode
    interval: Literal["1d", "1m", "5m", "tick"] = "1d"

    @model_validator(mode="after")
    def bounds_are_aware_and_ordered(self) -> "DatasetUploadRequest":
        if self.start.tzinfo is None or self.start.utcoffset() is None:
            raise ValueError(UNAWARE_UPLOAD_START)
        if self.end.tzinfo is None or self.end.utcoffset() is None or self.end <= self.start:
            raise ValueError(INVALID_UPLOAD_END)
        return self

    def to_bar_request(self) -> BarRequest:
        return BarRequest(
            instrument=Instrument(
                instrument_id=self.instrument_id,
                symbol=self.symbol,
                exchange=self.exchange,
                currency=self.currency,
                timezone=self.timezone,
            ),
            start=self.start,
            end=self.end,
            adjustment=self.price_adjustment,
            interval=self.interval,
        )


class OperatorMetadataResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    name: str
    category: str
    arity: str
    description: str


class IndicatorMetadataResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    name: str
    parameters: tuple[str, ...]
    minimum_lookback: str
    output_type: str
    availability: str
    description: str


class StrategyMetadataResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    json_schema: dict[str, JsonValue]
    operators: tuple[OperatorMetadataResponse, ...]
    indicators: tuple[IndicatorMetadataResponse, ...]
    templates: dict[str, JsonValue]
