from dataclasses import dataclass
from typing import Protocol

from packages.backtest.models import PortfolioSnapshot, StrategyDecision
from packages.domain.market_data import Bar


@dataclass(frozen=True, slots=True)
class EvaluationContext:
    current_bar: Bar
    history: tuple[Bar, ...]
    portfolio: PortfolioSnapshot


class StrategyEvaluator(Protocol):
    def evaluate(self, context: EvaluationContext) -> tuple[StrategyDecision, ...]: ...


class CancellationProbe(Protocol):
    def should_cancel(self, processed_events: int) -> bool: ...


class StrategyEvaluationError(Exception):
    reason: str

    def __init__(self, reason: str) -> None:
        """Preserve a safe strategy failure reason for the run event log."""
        self.reason = reason
        super().__init__(reason)
