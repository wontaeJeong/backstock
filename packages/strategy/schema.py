"""JSON AST models for condition-order strategies. No arbitrary code execution."""

from decimal import Decimal
from typing import Annotated, ClassVar, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_EXPRESSION_DEPTH: Final = 8
MAX_EXPRESSION_NODES: Final = 64
EXCESSIVE_NODES: Final = "condition tree exceeds the maximum node count"
MAX_SIZING_FRACTION: Final = Decimal(1)
EXCESSIVE_DEPTH: Final = "condition tree exceeds the maximum expression depth"
MARKET_LIMIT_OFFSET: Final = "market orders cannot define a limit offset"
MISSING_LIMIT_OFFSET: Final = "limit orders require a limit offset"
EMPTY_UNIVERSE: Final = "universe must reference at least one instrument"
EXCESSIVE_PERCENT_LOSS: Final = "a percent-mode loss trigger cannot exceed 100%"
MAX_PERCENT_VALUE: Final = Decimal(100)


class _FrozenModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)


class ConstantValue(_FrozenModel):
    type: Literal["constant"] = "constant"
    value: Decimal


class BarField(_FrozenModel):
    type: Literal["bar_field"] = "bar_field"
    field: Literal["open", "high", "low", "close", "volume"]
    shift: int = Field(default=0, ge=0, le=5000)


class IndicatorRef(_FrozenModel):
    type: Literal["indicator"] = "indicator"
    indicator: Literal[
        "sma",
        "ema",
        "rsi",
        "atr",
        "rolling_high",
        "rolling_low",
        "volume_average",
        "volume_ratio",
        "return",
    ]
    period: int = Field(gt=0, le=5000)
    shift: int = Field(default=0, ge=0, le=5000)


class PositionField(_FrozenModel):
    type: Literal["position"] = "position"
    field: Literal["quantity", "average_cost", "unrealized_pnl_percent", "holding_bars"]


class PortfolioField(_FrozenModel):
    type: Literal["portfolio"] = "portfolio"
    field: Literal["cash", "equity"]


class CalendarField(_FrozenModel):
    type: Literal["calendar"] = "calendar"
    field: Literal["day_of_week", "day_of_month", "month"]


Value = Annotated[
    ConstantValue | BarField | IndicatorRef | PositionField | PortfolioField | CalendarField,
    Field(discriminator="type"),
]


class AllCondition(_FrozenModel):
    op: Literal["all"] = "all"
    conditions: tuple["Condition", ...] = Field(min_length=1, max_length=8)


class AnyCondition(_FrozenModel):
    op: Literal["any"] = "any"
    conditions: tuple["Condition", ...] = Field(min_length=1, max_length=8)


class NotCondition(_FrozenModel):
    op: Literal["not"] = "not"
    condition: "Condition"


class CompareCondition(_FrozenModel):
    op: Literal["gt", "gte", "lt", "lte", "eq"]
    left: Value
    right: Value


class CrossCondition(_FrozenModel):
    op: Literal["crosses_above", "crosses_below"]
    left: Value
    right: Value


Condition = Annotated[
    AllCondition | AnyCondition | NotCondition | CompareCondition | CrossCondition,
    Field(discriminator="op"),
]

AllCondition.model_rebuild()
AnyCondition.model_rebuild()
NotCondition.model_rebuild()


def condition_depth(condition: object) -> int:
    match condition:
        case AllCondition(conditions=conditions) | AnyCondition(conditions=conditions):
            return 1 + max((condition_depth(item) for item in conditions), default=0)
        case NotCondition(condition=inner):
            return 1 + condition_depth(inner)
        case CompareCondition() | CrossCondition():
            return 1
        case _:
            return 0


def condition_nodes(condition: object) -> int:
    match condition:
        case AllCondition(conditions=items) | AnyCondition(conditions=items):
            return 1 + sum(condition_nodes(item) for item in items)
        case NotCondition(condition=inner):
            return 1 + condition_nodes(inner)
        case _:
            return 1


class EntryRule(_FrozenModel):
    condition: Condition


class ExitRule(_FrozenModel):
    condition: Condition | None = None


class StopLossRule(_FrozenModel):
    mode: Literal["percent", "atr_multiple"]
    value: Decimal = Field(gt=0)
    atr_period: int = Field(default=14, gt=0)

    @model_validator(mode="after")
    def percent_loss_is_bounded(self) -> "StopLossRule":
        if self.mode == "percent" and self.value > MAX_PERCENT_VALUE:
            raise ValueError(EXCESSIVE_PERCENT_LOSS)
        return self


class TakeProfitRule(_FrozenModel):
    mode: Literal["percent", "atr_multiple"]
    value: Decimal = Field(gt=0)
    atr_period: int = Field(default=14, gt=0)


class TrailingStopRule(_FrozenModel):
    mode: Literal["percent", "atr_multiple"]
    value: Decimal = Field(gt=0)
    atr_period: int = Field(default=14, gt=0)

    @model_validator(mode="after")
    def percent_loss_is_bounded(self) -> "TrailingStopRule":
        if self.mode == "percent" and self.value > MAX_PERCENT_VALUE:
            raise ValueError(EXCESSIVE_PERCENT_LOSS)
        return self


class RiskRules(_FrozenModel):
    stop_loss: StopLossRule | None = None
    take_profit: TakeProfitRule | None = None
    trailing_stop: TrailingStopRule | None = None
    max_holding_bars: int | None = Field(default=None, gt=0)


class FixedQuantitySizing(_FrozenModel):
    method: Literal["fixed_quantity"] = "fixed_quantity"
    quantity: int = Field(gt=0)


class FixedNotionalSizing(_FrozenModel):
    method: Literal["fixed_notional"] = "fixed_notional"
    notional: Decimal = Field(gt=0)


class PercentEquitySizing(_FrozenModel):
    method: Literal["percent_equity"] = "percent_equity"
    percent: Decimal = Field(gt=0, le=MAX_SIZING_FRACTION)


class AtrRiskSizing(_FrozenModel):
    method: Literal["atr_risk"] = "atr_risk"
    risk_percent: Decimal = Field(gt=0, le=MAX_SIZING_FRACTION)
    atr_period: int = Field(gt=0)
    atr_multiple: Decimal = Field(gt=0)


PositionSizing = Annotated[
    FixedQuantitySizing | FixedNotionalSizing | PercentEquitySizing | AtrRiskSizing,
    Field(discriminator="method"),
]


class OrderRule(_FrozenModel):
    order_type: Literal["market", "limit"] = "market"
    limit_offset_bps: Decimal | None = Field(default=None, ge=0)
    time_in_force: Literal["day", "gtc"] = "day"

    @model_validator(mode="after")
    def limit_offset_matches_order_type(self) -> "OrderRule":
        if self.order_type == "market" and self.limit_offset_bps is not None:
            raise ValueError(MARKET_LIMIT_OFFSET)
        if self.order_type == "limit" and self.limit_offset_bps is None:
            raise ValueError(MISSING_LIMIT_OFFSET)
        return self


class StrategyDefinition(_FrozenModel):
    schema_version: Literal["1"] = "1"
    name: str = Field(min_length=1, max_length=200)
    universe: tuple[str, ...] = Field(min_length=1, max_length=50)
    timeframe: Literal["1d", "1m", "5m"] = "1d"
    entry: EntryRule
    exit: ExitRule = Field(default_factory=ExitRule)
    position_sizing: PositionSizing
    risk: RiskRules = Field(default_factory=RiskRules)
    order: OrderRule = Field(default_factory=OrderRule)

    @model_validator(mode="after")
    def universe_is_not_empty(self) -> "StrategyDefinition":
        if not all(instrument_id.strip() for instrument_id in self.universe):
            raise ValueError(EMPTY_UNIVERSE)
        return self

    @model_validator(mode="after")
    def expression_depth_is_bounded(self) -> "StrategyDefinition":
        depth = condition_depth(self.entry.condition)
        if self.exit.condition is not None:
            depth = max(depth, condition_depth(self.exit.condition))
        if depth > MAX_EXPRESSION_DEPTH:
            raise ValueError(EXCESSIVE_DEPTH)
        nodes = condition_nodes(self.entry.condition)
        if self.exit.condition is not None:
            nodes += condition_nodes(self.exit.condition)
        if nodes > MAX_EXPRESSION_NODES:
            raise ValueError(EXCESSIVE_NODES)
        return self
