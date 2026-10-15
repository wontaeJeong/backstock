from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from packages.application.simulation_models import SimulationRequest
from packages.application.simulations import SimulationService
from packages.backtest.engine import BacktestEngine
from packages.backtest.models import BacktestConfig
from packages.strategy.evaluator import DslStrategyEvaluator
from packages.strategy.indicators import compute_indicator, minimum_lookback
from packages.strategy.metadata import INDICATORS
from packages.strategy.schema import IndicatorRef, StrategyDefinition
from tests.application.test_simulations import definition
from tests.backtest.test_engine_golden import _input
from tests.research.test_execution_features import event

D = Decimal


def test_vwap_uses_typical_price_and_zero_volume_is_unavailable() -> None:
    bars = [
        event(price="10", high="14", low="9", volume=1),
        event(price="20", high="25", low="18", volume=3),
    ]
    assert compute_indicator("vwap", 2, bars) == D("18.5")
    assert compute_indicator("vwap", 2, [event(volume=0), event(volume=0)]) is None


def test_bollinger_population_std_golden() -> None:
    bars = [event(price="2"), event(price="4")]
    assert compute_indicator("bollinger_upper", 2, bars) == D(5)
    assert compute_indicator("bollinger_lower", 2, bars) == D(1)
    assert compute_indicator("bollinger_middle", 2, bars) == D(3)


def test_macd_explicit_parameters_warmup_and_golden() -> None:
    bars = [event(price=str(n)) for n in (1, 2, 3, 4, 5)]
    assert minimum_lookback("macd_signal", 3, fast_period=2, slow_period=3, signal_period=2) == 4
    assert compute_indicator("macd", 3, bars, fast_period=2, slow_period=3, signal_period=2) == D(
        "0.5"
    )
    assert compute_indicator(
        "macd_signal", 3, bars, fast_period=2, slow_period=3, signal_period=2
    ) == D("0.5")
    assert (
        compute_indicator("macd_histogram", 3, bars, fast_period=2, slow_period=3, signal_period=2)
        == 0
    )
    assert (
        compute_indicator("macd_signal", 3, bars[:3], fast_period=2, slow_period=3, signal_period=2)
        is None
    )
    with pytest.raises(ValidationError):
        IndicatorRef.model_validate(
            {"indicator": "macd", "period": 3, "fast_period": 3, "slow_period": 2}
        )


@pytest.mark.parametrize(
    "indicator", ["vwap", "bollinger_upper", "bollinger_lower", "macd", "macd_signal"]
)
def test_indicator_shift_cannot_see_future(tmp_path: Path, indicator: str) -> None:
    payload = definition("1m").model_dump(mode="json")
    payload["entry"]["condition"]["left"] = {
        "type": "indicator",
        "indicator": indicator,
        "period": 2,
        "shift": 1,
        "fast_period": 2,
        "slow_period": 3,
        "signal_period": 2,
    }
    report = SimulationService(tmp_path, code_revision="test").run(
        SimulationRequest(
            source="demo",
            symbol="AAPL",
            strategy=StrategyDefinition.model_validate(payload),
            initial_cash=D(1000),
        )
    )
    assert report.result.orders[0].intent.submitted_at > datetime(2024, 1, 2, 14, 32, tzinfo=UTC)


def test_session_entry_clock_signal_time_and_flatten_next_bar(tmp_path: Path) -> None:
    payload = definition("1m").model_dump(mode="json")
    payload["session"] = {
        "entry_start": "09:35",
        "entry_end": "09:40",
        "weekdays": [1],
        "flatten_at": "09:42",
    }
    report = SimulationService(tmp_path, code_revision="test").run(
        SimulationRequest(
            source="demo",
            symbol="AAPL",
            strategy=StrategyDefinition.model_validate(payload),
            initial_cash=D(1000),
        )
    )
    buy, sell = report.result.fills
    assert report.result.orders[0].intent.submitted_at.astimezone(UTC).hour == 14
    assert report.result.orders[0].intent.submitted_at.minute == 35
    assert buy.timestamp.minute == 35
    assert sell.timestamp.minute == 42
    assert report.result.orders[1].intent.rule_path == "session/flatten"


def test_daily_rejects_intraday_clock_controls() -> None:
    payload = definition().model_dump(mode="json")
    payload["session"] = {"flatten_at": "15:55"}
    with pytest.raises(ValidationError, match="daily"):
        StrategyDefinition.model_validate(payload)


def test_execution_fields_reach_config_and_cost_once(tmp_path: Path) -> None:
    service = SimulationService(tmp_path, code_revision="test")
    req = SimulationRequest.model_validate(
        {
            "source": "demo",
            "symbol": "AAPL",
            "strategy": definition("1m"),
            "initial_cash": "1000",
            "spread_bps": "100",
            "latency_ms": 1000,
            "volume_participation": "0.1",
        }
    )
    report = service.run(req)
    assert report.config.spread_bps == 100
    assert report.config.latency_ms == 1000
    assert report.config.volume_participation == D("0.1")
    fill = report.result.fills[0]
    assert fill.timestamp >= report.result.orders[0].intent.submitted_at + timedelta(seconds=1)
    assert report.result.summary.spread == fill.spread > 0
    assert (
        report.result.portfolio[-1].cash
        == D(1000) - fill.quantity * fill.execution_price - fill.commission
    )
    assert service.get(report.run_id) == report


def test_indicator_metadata_exposes_new_parameters_and_warmup() -> None:
    metadata = {item.name: item for item in INDICATORS}
    assert metadata["vwap"].minimum_lookback == "period bars"
    assert "stddev_multiplier" in metadata["bollinger_upper"].parameters
    assert metadata["macd_signal"].minimum_lookback == "slow_period + signal_period - 1 bars"


def test_late_flatten_is_unfilled_not_same_close_liquidation(tmp_path: Path) -> None:
    payload = definition("1m").model_dump(mode="json")
    payload["session"] = {"flatten_at": "11:30"}
    report = SimulationService(tmp_path, code_revision="test").run(
        SimulationRequest(
            source="demo",
            symbol="AAPL",
            strategy=StrategyDefinition.model_validate(payload),
            initial_cash=D(1000),
        )
    )
    assert len(report.result.fills) == 1
    flatten = report.result.orders[-1]
    assert flatten.intent.rule_path == "session/flatten"
    assert flatten.state == "expired"
    assert report.result.portfolio[-1].positions[0].quantity == 2
    assert any("미체결" in warning for warning in report.warnings)


@pytest.mark.parametrize(
    "indicator",
    [
        "vwap",
        "bollinger_middle",
        "bollinger_upper",
        "bollinger_lower",
        "macd",
        "macd_signal",
        "macd_histogram",
    ],
)
def test_future_price_mutation_cannot_change_indicator_order_prefix(indicator: str) -> None:
    payload = definition("tick").model_dump(mode="json")
    payload["entry"]["condition"]["left"] = {
        "type": "indicator",
        "indicator": indicator,
        "period": 2,
        "fast_period": 2,
        "slow_period": 3,
        "signal_period": 2,
    }
    strategy = StrategyDefinition.model_validate(payload)
    start = datetime(2024, 1, 2, 15, tzinfo=UTC)
    history = tuple(
        event(price=str(n + 1), timestamp=start + timedelta(seconds=n)) for n in range(6)
    )
    cutoff = history[-1].timestamp
    future_time = cutoff + timedelta(seconds=1)
    config = BacktestConfig(initial_cash=D(1000), bar_interval="tick")
    first = BacktestEngine().run(
        _input((*history, event(price="1", timestamp=future_time)), config),
        DslStrategyEvaluator(strategy),
    )
    second = BacktestEngine().run(
        _input((*history, event(price="10000", timestamp=future_time)), config),
        DslStrategyEvaluator(strategy),
    )
    assert [e for e in first.events if e.timestamp <= cutoff] == [
        e for e in second.events if e.timestamp <= cutoff
    ]
