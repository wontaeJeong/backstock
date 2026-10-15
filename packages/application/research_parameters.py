"""Numeric DSL allowlist; never sweep identity, metadata, symbols or time offsets."""

from decimal import Decimal
from itertools import product
from typing import cast

from pydantic import JsonValue

from packages.application.research_experiment_models import Axis
from packages.application.simulation_models import SimulationRequest

COST_FIELDS = {"commission_bps", "sell_tax_bps", "slippage_bps"}
SIZING_FIELDS = {"quantity", "notional", "percent", "risk_percent", "atr_period", "atr_multiple"}
RISK_RULES = {"stop_loss", "take_profit", "trailing_stop"}


def _parent(payload: JsonValue, path: str) -> tuple[dict[str, JsonValue], str]:
    parts = path.split(".")
    node = payload
    for part in parts[:-1]:
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            msg = f"존재하지 않는 숫자 path: {path}"
            raise ValueError(msg)
    if not isinstance(node, dict) or parts[-1] not in node:
        msg = f"존재하지 않는 숫자 path: {path}"
        raise ValueError(msg)
    return node, parts[-1]


def validate_axes(base: SimulationRequest, axes: tuple[Axis, ...]) -> None:
    payload = base.model_dump(mode="json")
    for axis in axes:
        path = axis.path
        parent, leaf = _parent(payload, path)
        allowed = path in COST_FIELDS
        allowed |= path.rsplit(".", 1)[0] == "strategy.position_sizing" and leaf in SIZING_FIELDS
        allowed |= path == "strategy.risk.max_holding_bars"
        allowed |= path.rsplit(".", 1)[0] in {
            f"strategy.risk.{rule}" for rule in RISK_RULES
        } and leaf in {"value", "atr_period"}
        allowed |= path == "strategy.order.limit_offset_bps"
        condition_path = path.startswith(("strategy.entry.condition.", "strategy.exit.condition."))
        allowed |= condition_path and (
            (parent.get("type") == "constant" and leaf == "value")
            or (parent.get("type") == "indicator" and leaf == "period")
        )
        if not allowed or parent[leaf] is None or isinstance(parent[leaf], bool):
            msg = f"허용되지 않는 숫자 path: {path}"
            raise ValueError(msg)


def combinations(axes: tuple[Axis, ...]) -> list[dict[str, Decimal]]:
    return [
        dict(zip((a.path for a in axes), values, strict=True))
        for values in product(*(a.values for a in axes))
    ]


def parameterize(base: SimulationRequest, parameters: dict[str, Decimal]) -> SimulationRequest:
    payload = base.model_dump(mode="json")
    for path, value in parameters.items():
        parent, leaf = _parent(payload, path)
        parent[leaf] = cast("JsonValue", str(value))
    return SimulationRequest.model_validate(payload)
