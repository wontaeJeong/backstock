from datetime import datetime
from decimal import Decimal
from typing import ClassVar

from pydantic import BaseModel, ConfigDict

from packages.backtest.events import BacktestEvent
from packages.backtest.models import Fill, Order, PortfolioSnapshot, RunStatus, SnapshotReference


class _FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)


class BenchmarkPoint(_FrozenModel):
    timestamp: datetime
    value: Decimal


class BacktestSummary(_FrozenModel):
    initial_cash: Decimal
    final_equity: Decimal
    total_return: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    commission: Decimal
    tax: Decimal
    slippage: Decimal


class ReproducibilityMetadata(_FrozenModel):
    snapshot: SnapshotReference
    strategy_version: str
    code_revision: str
    engine_version: str
    seed: int


class BacktestResult(_FrozenModel):
    status: RunStatus
    summary: BacktestSummary
    orders: tuple[Order, ...]
    fills: tuple[Fill, ...]
    portfolio: tuple[PortfolioSnapshot, ...]
    benchmark: tuple[BenchmarkPoint, ...]
    events: tuple[BacktestEvent, ...]
    metadata: ReproducibilityMetadata
    failure_reason: str | None = None
