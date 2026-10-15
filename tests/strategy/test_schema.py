from decimal import Decimal

import pytest

from packages.strategy.schema import (
    CompareCondition,
    Condition,
    ConstantValue,
    EntryRule,
    IndicatorRef,
    NotCondition,
    OrderRule,
    PercentEquitySizing,
    StopLossRule,
    StrategyDefinition,
)
from packages.strategy.validation import StrategyValidationError, validate_definition


def _base_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "1",
        "name": "sample",
        "universe": ["AAA"],
        "timeframe": "1d",
        "entry": {
            "condition": {
                "op": "gt",
                "left": {"type": "constant", "value": 2},
                "right": {"type": "constant", "value": 1},
            }
        },
        "position_sizing": {"method": "fixed_quantity", "quantity": 1},
    }
    payload.update(overrides)
    return payload


def test_valid_payload_parses() -> None:
    definition = validate_definition(_base_payload())

    assert definition.name == "sample"


def test_unknown_operator_is_rejected() -> None:
    payload = _base_payload(
        entry={
            "condition": {
                "op": "xor",
                "left": {"type": "constant", "value": 1},
                "right": {"type": "constant", "value": 1},
            }
        }
    )

    with pytest.raises(StrategyValidationError):
        validate_definition(payload)


def test_non_positive_indicator_period_is_rejected() -> None:
    payload = _base_payload(
        entry={
            "condition": {
                "op": "gt",
                "left": {"type": "indicator", "indicator": "sma", "period": 0},
                "right": {"type": "constant", "value": 1},
            }
        }
    )

    with pytest.raises(StrategyValidationError):
        validate_definition(payload)


def test_negative_shift_is_rejected_as_a_future_reference() -> None:
    payload = _base_payload(
        entry={
            "condition": {
                "op": "gt",
                "left": {"type": "bar_field", "field": "close", "shift": -1},
                "right": {"type": "constant", "value": 1},
            }
        }
    )

    with pytest.raises(StrategyValidationError):
        validate_definition(payload)


def test_unsupported_timeframe_is_rejected() -> None:
    payload = _base_payload(timeframe="1h")

    with pytest.raises(StrategyValidationError):
        validate_definition(payload)


def test_dangerous_percent_equity_sizing_is_rejected() -> None:
    payload = _base_payload(position_sizing={"method": "percent_equity", "percent": 1.5})

    with pytest.raises(StrategyValidationError):
        validate_definition(payload)


def test_percent_stop_loss_over_100_percent_is_rejected() -> None:
    with pytest.raises(ValueError, match="100"):
        StopLossRule(mode="percent", value=Decimal(150))


def test_empty_universe_is_rejected() -> None:
    payload = _base_payload(universe=[])

    with pytest.raises(StrategyValidationError):
        validate_definition(payload)


def test_market_order_rejects_a_limit_offset() -> None:
    with pytest.raises(ValueError, match="market"):
        OrderRule(order_type="market", limit_offset_bps=Decimal(10))


def test_limit_order_requires_a_limit_offset() -> None:
    with pytest.raises(ValueError, match="limit"):
        OrderRule(order_type="limit")


def test_expression_depth_at_the_limit_is_accepted() -> None:
    condition: Condition = CompareCondition(
        op="gt", left=ConstantValue(value=Decimal(1)), right=ConstantValue(value=Decimal(0))
    )
    for _ in range(7):
        condition = NotCondition(condition=condition)

    definition = StrategyDefinition(
        name="deep-but-allowed",
        universe=("AAA",),
        entry=EntryRule(condition=condition),
        position_sizing=PercentEquitySizing(percent=Decimal("0.1")),
    )
    assert definition.name == "deep-but-allowed"


def test_expression_depth_beyond_the_limit_is_rejected() -> None:
    condition: Condition = CompareCondition(
        op="gt", left=ConstantValue(value=Decimal(1)), right=ConstantValue(value=Decimal(0))
    )
    for _ in range(8):
        condition = NotCondition(condition=condition)

    with pytest.raises(ValueError, match="depth"):
        StrategyDefinition(
            name="too-deep",
            universe=("AAA",),
            entry=EntryRule(condition=condition),
            position_sizing=PercentEquitySizing(percent=Decimal("0.1")),
        )


def test_indicator_ref_is_reusable_as_a_condition_operand() -> None:
    ref = IndicatorRef(indicator="rsi", period=14)
    assert ref.shift == 0
