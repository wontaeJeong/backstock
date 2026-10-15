from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from packages.backtest.engine import BacktestEngine
from packages.backtest.models import BacktestConfig, BacktestInput, SnapshotReference
from packages.domain.market_data import AdjustmentMode, Bar
from packages.strategy.evaluator import DslStrategyEvaluator
from packages.strategy.templates import TEMPLATES
from packages.strategy.validation import create_strategy_version


def _bar(day: int, close: str) -> Bar:
    return Bar(
        instrument_id="AAA",
        timestamp=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(days=day),
        open=Decimal(close),
        high=Decimal(close),
        low=Decimal(close),
        close=Decimal(close),
        volume=1_000_000,
        price_adjustment=AdjustmentMode.RAW,
        volume_adjustment=AdjustmentMode.RAW,
    )


@pytest.mark.parametrize("name", sorted(TEMPLATES))
def test_template_is_valid_and_hashable(name: str) -> None:
    definition = TEMPLATES[name](("AAA",))

    version = create_strategy_version(definition)

    assert version.version_id.startswith("sha256:")
    assert version.definition.universe == ("AAA",)


@pytest.mark.parametrize("name", sorted(TEMPLATES))
def test_template_runs_through_the_backtest_engine_without_error(name: str) -> None:
    definition = TEMPLATES[name](("AAA",))
    evaluator = DslStrategyEvaluator(definition)
    bars = tuple(_bar(day, str(90 + (day % 20))) for day in range(1, 90))
    backtest_input = BacktestInput(
        snapshot=SnapshotReference(
            snapshot_id="a" * 64,
            normalized_checksum=f"sha256:{'b' * 64}",
            price_adjustment=AdjustmentMode.RAW,
            volume_adjustment=AdjustmentMode.RAW,
        ),
        bars=bars,
        config=BacktestConfig(initial_cash=Decimal(1_000_000)),
        strategy_version=create_strategy_version(definition).version_id,
        code_revision="test-revision",
    )

    result = BacktestEngine().run(backtest_input, evaluator)

    assert result.summary.final_equity > 0
