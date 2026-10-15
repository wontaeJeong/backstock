from datetime import datetime
from decimal import Decimal
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.backtest.models import BacktestConfig
from packages.backtest.results import BacktestResult
from packages.market_data.snapshots import SnapshotManifest
from packages.strategy.schema import StrategyDefinition

SYMBOLS = ("AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "QQQ")
MAX_SIMULATION_BARS = 3000
MAX_RANGE_DAYS = 3650


class SimulationRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    source: Literal["demo", "yfinance", "snapshot"]
    symbol: Literal["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "QQQ"]
    strategy: StrategyDefinition
    initial_cash: Decimal = Field(gt=0, le=1_000_000_000, allow_inf_nan=False)
    commission_bps: Decimal = Field(default=Decimal(1), ge=0, le=100, allow_inf_nan=False)
    sell_tax_bps: Decimal = Field(default=Decimal(0), ge=0, le=100, allow_inf_nan=False)
    slippage_bps: Decimal = Field(default=Decimal(5), ge=0, le=100, allow_inf_nan=False)
    snapshot_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    start: datetime | None = None
    end: datetime | None = None

    @model_validator(mode="after")
    def validate_source(self) -> "SimulationRequest":
        if self.source == "snapshot" and self.snapshot_id is None:
            msg = "업로드 snapshot을 선택하세요."
            raise ValueError(msg)
        if self.source == "yfinance":
            if self.strategy.timeframe != "1d":
                msg = "Yahoo 분봉 수집은 지원하지 않습니다. 분봉 파일을 업로드하세요."
                raise ValueError(msg)
            if self.start is None or self.end is None:
                msg = "시작일과 종료일이 필요합니다."
                raise ValueError(msg)
            if any(value.tzinfo is None for value in (self.start, self.end)):
                msg = "날짜에는 시간대가 필요합니다."
                raise ValueError(msg)
            if self.end <= self.start or (self.end - self.start).days > MAX_RANGE_DAYS:
                msg = "기간은 0일 초과, 10년 이하여야 합니다."
                raise ValueError(msg)
        if self.strategy.universe != (f"NASDAQ:{self.symbol}",):
            msg = "전략 종목과 선택 종목이 일치해야 합니다."
            raise ValueError(msg)
        return self


class SimulationMetrics(BaseModel):
    net_profit: Decimal
    max_drawdown: Decimal
    fill_count: int
    closed_trade_count: int
    benchmark_return: Decimal
    metric_version: str = "research.v1"


class SimulationReport(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    run_id: str
    request: SimulationRequest
    config: BacktestConfig
    manifest: SnapshotManifest
    result: BacktestResult
    metrics: SimulationMetrics
    warnings: tuple[str, ...]
