from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field


class EventKind(StrEnum):
    CLOCK = "clock"
    MARKET = "market"
    STRATEGY_EVALUATION = "strategy_evaluation"
    SIGNAL = "signal"
    ORDER_INTENT = "order_intent"
    RISK_EVALUATION = "risk_evaluation"
    ORDER_ACCEPTED = "order_accepted"
    ORDER_REJECTED = "order_rejected"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_CANCEL_REJECTED = "order_cancel_rejected"
    ORDER_EXPIRED = "order_expired"
    ORDER_TRIGGERED = "order_triggered"
    FILL = "fill"
    LEDGER_UPDATE = "ledger_update"
    METRICS_UPDATE = "metrics_update"
    RUN_CANCELLED = "run_cancelled"
    RUN_FAILED = "run_failed"


class BacktestEvent(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", frozen=True)

    sequence: int = Field(ge=1)
    timestamp: datetime
    kind: EventKind
    instrument_id: str | None = None
    order_id: str | None = None
    reason: str
    quantity: int | None = Field(default=None, ge=0)
    reference_price: Decimal | None = Field(default=None, gt=0)
    execution_price: Decimal | None = Field(default=None, gt=0)
    commission: Decimal | None = Field(default=None, ge=0)
    tax: Decimal | None = Field(default=None, ge=0)
    slippage: Decimal | None = Field(default=None, ge=0)
    spread: Decimal | None = Field(default=None, ge=0)
    cash: Decimal | None = None
    equity: Decimal | None = None
