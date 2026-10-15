"""Indicator-only history: warmup bars never enter execution or return denominators."""

from packages.backtest.models import StrategyDecision
from packages.backtest.ports import EvaluationContext, StrategyEvaluator
from packages.domain.market_data import Bar


class HistoryEvaluator:
    def __init__(self, evaluator: StrategyEvaluator, history: tuple[Bar, ...]) -> None:
        """Supply read-only pre-trade history to a fresh evaluator."""
        self._evaluator = evaluator
        self._history = history

    def evaluate(self, context: EvaluationContext) -> tuple[StrategyDecision, ...]:
        return self._evaluator.evaluate(
            EvaluationContext(
                current_bar=context.current_bar,
                history=self._history + context.history,
                portfolio=context.portfolio,
            )
        )
