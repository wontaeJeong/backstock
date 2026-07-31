from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar, Final

from pydantic import BaseModel, ConfigDict, Field, model_validator

from packages.domain.market_data import AdjustmentMode, Bar

MARKET_LIMIT_PRICE: Final = "market orders cannot define a limit price"
MISSING_LIMIT_PRICE: Final = "limit orders require a limit price"
EXCESS_FILL_QUANTITY: Final = "filled quantity exceeds requested quantity"
ADJUSTMENT_MISMATCH: Final = "bar adjustments do not match the snapshot reference"
DUPLICATE_BAR_IDENTITY: Final = "backtest bars contain duplicate instrument timestamps"
EXCESS_SELL_DEDUCTIONS: Final = "sell commission and tax cannot exceed proceeds"


class _FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"


class TimeInForce(StrEnum):
    DAY = "day"
    GTC = "gtc"


class OrderState(StrEnum):
    ACCEPTED = "accepted"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    REJECTED = "rejected"


class EndOrderPolicy(StrEnum):
    EXPIRE = "expire"
    CANCEL = "cancel"


class EndPositionPolicy(StrEnum):
    MARK_TO_LAST_CLOSE = "mark_to_last_close"
    LIQUIDATE_AT_LAST_CLOSE = "liquidate_at_last_close"


class RunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    CANCELLED = "cancelled"
    FAILED = "failed"


class SnapshotReference(_FrozenModel):
    snapshot_id: str = Field(min_length=64, max_length=64)
    normalized_checksum: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    price_adjustment: AdjustmentMode
    volume_adjustment: AdjustmentMode


class CostConfig(_FrozenModel):
    commission_rate: Decimal = Field(default=Decimal(0), ge=0)
    sell_tax_rate: Decimal = Field(default=Decimal(0), ge=0)
    slippage_bps: Decimal = Field(default=Decimal(0), ge=0, lt=10_000)

    @model_validator(mode="after")
    def sell_deductions_do_not_exceed_proceeds(self) -> "CostConfig":
        if self.commission_rate + self.sell_tax_rate > Decimal(1):
            raise ValueError(EXCESS_SELL_DEDUCTIONS)
        return self


class BacktestConfig(_FrozenModel):
    initial_cash: Decimal = Field(gt=0)
    costs: CostConfig = Field(default_factory=CostConfig)
    seed: int = 0
    end_order_policy: EndOrderPolicy = EndOrderPolicy.EXPIRE
    end_position_policy: EndPositionPolicy = EndPositionPolicy.MARK_TO_LAST_CLOSE
    benchmark_instrument_id: str | None = None


class OrderIntent(_FrozenModel):
    instrument_id: str = Field(min_length=1)
    submitted_at: datetime
    side: Side
    quantity: int = Field(gt=0)
    order_type: OrderType
    limit_price: Decimal | None = Field(default=None, gt=0)
    time_in_force: TimeInForce = TimeInForce.DAY
    reason: str = Field(min_length=1)
    strategy_version: str = Field(default="fixture", min_length=1)
    rule_path: str = Field(default="fixture", min_length=1)

    @model_validator(mode="after")
    def limit_price_matches_order_type(self) -> "OrderIntent":
        match self.order_type:
            case OrderType.MARKET:
                if self.limit_price is not None:
                    raise ValueError(MARKET_LIMIT_PRICE)
            case OrderType.LIMIT:
                if self.limit_price is None:
                    raise ValueError(MISSING_LIMIT_PRICE)
        return self


class CancelIntent(_FrozenModel):
    order_id: str = Field(min_length=1)
    submitted_at: datetime
    reason: str = Field(min_length=1)


StrategyDecision = OrderIntent | CancelIntent


class Order(_FrozenModel):
    order_id: str = Field(min_length=1)
    intent: OrderIntent
    state: OrderState = OrderState.ACCEPTED
    filled_quantity: int = Field(default=0, ge=0)
    state_reason: str = "accepted"

    @model_validator(mode="after")
    def filled_quantity_does_not_exceed_request(self) -> "Order":
        if self.filled_quantity > self.intent.quantity:
            raise ValueError(EXCESS_FILL_QUANTITY)
        return self

    @property
    def remaining_quantity(self) -> int:
        return self.intent.quantity - self.filled_quantity


class Fill(_FrozenModel):
    fill_id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    instrument_id: str = Field(min_length=1)
    timestamp: datetime
    side: Side
    quantity: int = Field(gt=0)
    reference_price: Decimal = Field(gt=0)
    execution_price: Decimal = Field(gt=0)
    commission: Decimal = Field(ge=0)
    tax: Decimal = Field(ge=0)
    slippage: Decimal = Field(ge=0)


class Position(_FrozenModel):
    instrument_id: str = Field(min_length=1)
    quantity: int = Field(ge=0)
    average_cost: Decimal = Field(ge=0)


class PortfolioState(_FrozenModel):
    cash: Decimal = Field(ge=0)
    positions: tuple[Position, ...] = ()
    realized_pnl: Decimal = Decimal(0)
    total_commission: Decimal = Field(default=Decimal(0), ge=0)
    total_tax: Decimal = Field(default=Decimal(0), ge=0)
    total_slippage: Decimal = Field(default=Decimal(0), ge=0)


class PriceMark(_FrozenModel):
    instrument_id: str = Field(min_length=1)
    price: Decimal = Field(gt=0)


class PortfolioSnapshot(_FrozenModel):
    timestamp: datetime
    cash: Decimal
    market_value: Decimal
    equity: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    positions: tuple[Position, ...]


class BacktestInput(_FrozenModel):
    snapshot: SnapshotReference
    bars: tuple[Bar, ...] = Field(min_length=1)
    config: BacktestConfig
    strategy_version: str = Field(min_length=1)
    code_revision: str = Field(min_length=1)

    @model_validator(mode="after")
    def bars_match_snapshot_adjustments(self) -> "BacktestInput":
        if any(
            bar.price_adjustment is not self.snapshot.price_adjustment
            or bar.volume_adjustment is not self.snapshot.volume_adjustment
            for bar in self.bars
        ):
            raise ValueError(ADJUSTMENT_MISMATCH)
        identities = {(bar.instrument_id, bar.timestamp) for bar in self.bars}
        if len(identities) != len(self.bars):
            raise ValueError(DUPLICATE_BAR_IDENTITY)
        return self
