from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from packages.application.simulations import (
    SimulationRequest,
    SimulationService,
    _validate_intraday,
)
from packages.strategy.schema import StrategyDefinition
from tests.backtest.test_engine_golden import _bar


def definition(timeframe: str = "1d") -> StrategyDefinition:
    return StrategyDefinition.model_validate(
        {
            "name": "매수 후 보유",
            "universe": ["NASDAQ:AAPL"],
            "timeframe": timeframe,
            "entry": {
                "condition": {
                    "op": "gt",
                    "left": {"type": "bar_field", "field": "close"},
                    "right": {"type": "constant", "value": "0"},
                }
            },
            "position_sizing": {"method": "fixed_quantity", "quantity": 2},
        }
    )


def test_demo_runs_real_engine_and_is_immutable(tmp_path: Path) -> None:
    service = SimulationService(tmp_path, code_revision="test-revision")
    request = SimulationRequest(
        source="demo", symbol="AAPL", strategy=definition(), initial_cash=Decimal(1000)
    )
    first = service.run(request)
    second = service.run(request)
    assert first.run_id == second.run_id
    assert service.get(first.run_id) == first
    assert first.result.status == "succeeded"
    assert first.result.fills[0].timestamp > first.result.orders[0].intent.submitted_at
    assert first.metrics.net_profit == first.result.summary.final_equity - Decimal(1000)
    assert first.metrics.max_drawdown >= 0
    assert first.manifest.provider == "synthetic_demo"
    assert any("합성" in warning for warning in first.warnings)
    assert first.config.initial_cash == Decimal(1000)


def test_rejects_universe_and_interval_mismatch(tmp_path: Path) -> None:
    service = SimulationService(tmp_path, code_revision="test")
    with pytest.raises(ValueError, match="종목"):
        service.run(
            SimulationRequest(
                source="demo", symbol="MSFT", strategy=definition(), initial_cash=Decimal(1000)
            )
        )
    with pytest.raises(ValueError, match="분봉"):
        service.run(
            SimulationRequest(
                source="yfinance",
                symbol="AAPL",
                strategy=definition("1m"),
                initial_cash=Decimal(1000),
                start=datetime(2024, 1, 1, tzinfo=UTC),
                end=datetime(2024, 1, 3, tzinfo=UTC),
            )
        )


def test_costs_reduce_net_return_without_double_subtracting_slippage(tmp_path: Path) -> None:
    service = SimulationService(tmp_path, code_revision="test")
    free = service.run(
        SimulationRequest(
            source="demo",
            symbol="AAPL",
            strategy=definition(),
            initial_cash=Decimal(1000),
            commission_bps=Decimal(0),
            slippage_bps=Decimal(0),
        )
    )
    costly = service.run(
        SimulationRequest(
            source="demo",
            symbol="AAPL",
            strategy=definition(),
            initial_cash=Decimal(1000),
            commission_bps=Decimal(10),
            slippage_bps=Decimal(10),
        )
    )
    assert costly.metrics.net_profit < free.metrics.net_profit
    assert costly.metrics.net_profit == costly.result.summary.final_equity - Decimal(1000)


def test_intraday_demo_fills_after_bar_close_at_next_open(tmp_path: Path) -> None:
    report = SimulationService(tmp_path, code_revision="test").run(
        SimulationRequest(
            source="demo", symbol="AAPL", strategy=definition("1m"), initial_cash=Decimal(1000)
        )
    )
    intent = report.result.orders[0].intent
    fill = report.result.fills[0]
    assert intent.submitted_at == datetime(2024, 1, 2, 14, 31, tzinfo=UTC)
    assert fill.timestamp == intent.submitted_at
    assert fill.execution_price != Decimal(100)
    assert any("호가" in warning for warning in report.warnings)


def test_missing_run_and_invalid_id_cannot_read_arbitrary_paths(tmp_path: Path) -> None:
    service = SimulationService(tmp_path, code_revision="test")
    assert service.get("../anything") is None
    assert service.get("a" * 64) is None


def test_negated_unavailable_indicator_does_not_trade(tmp_path: Path) -> None:
    strategy = definition().model_dump(mode="json")
    strategy["entry"] = {
        "condition": {
            "op": "not",
            "condition": {
                "op": "gt",
                "left": {"type": "indicator", "indicator": "sma", "period": 5000},
                "right": {"type": "constant", "value": "1"},
            },
        }
    }
    report = SimulationService(tmp_path, code_revision="test").run(
        SimulationRequest(
            source="demo",
            symbol="AAPL",
            strategy=StrategyDefinition.model_validate(strategy),
            initial_cash=Decimal(1000),
        )
    )
    assert report.result.fills == ()


def test_saved_result_tampering_is_detected(tmp_path: Path) -> None:
    service = SimulationService(tmp_path, code_revision="test")
    report = service.run(
        SimulationRequest(
            source="demo", symbol="AAPL", strategy=definition(), initial_cash=Decimal(1000)
        )
    )
    path = tmp_path / "runs" / f"{report.run_id}.json"
    payload = path.read_text().replace('"net_profit":"', '"net_profit":"9')
    path.write_text(payload)
    with pytest.raises(ValueError, match="무결성"):
        service.get(report.run_id)


def test_daily_label_cannot_hide_minute_data() -> None:
    bar = _bar("AAA", 1, open_="100", close="100")
    bars = (bar, bar.model_copy(update={"timestamp": bar.timestamp.replace(minute=1)}))
    with pytest.raises(ValueError, match="일봉"):
        _validate_intraday(bars, "1d")


def test_strategy_expression_size_is_bounded() -> None:
    strategy = definition().model_dump(mode="json")
    leaf = strategy["entry"]["condition"]
    strategy["entry"] = {
        "condition": {"op": "all", "conditions": [{"op": "all", "conditions": [leaf] * 8}] * 8}
    }
    with pytest.raises(ValueError, match="node"):
        StrategyDefinition.model_validate(strategy)
