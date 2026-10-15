"""Pure analysis of verified engine artifacts; execution prices already include slippage."""

import csv
import math
from collections import deque
from datetime import datetime
from decimal import Decimal
from io import StringIO
from statistics import stdev
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from packages.application.simulation_models import SimulationReport
from packages.backtest.models import Fill

ZERO = Decimal(0)
TRADING_DAYS = 252
SECONDS_PER_DAY = 86400


class Statistic(BaseModel):
    value: Decimal | None
    reason: str | None = None
    definition: str


class ReturnPoint(BaseModel):
    period: str
    value: Decimal


class DrawdownPoint(BaseModel):
    timestamp: datetime
    value: Decimal


class RoundTrip(BaseModel):
    instrument_id: str
    entry_at: datetime
    exit_at: datetime
    quantity: int
    entry_price: Decimal
    exit_price: Decimal
    fees: Decimal
    net_profit: Decimal
    return_on_cost: Decimal
    holding_seconds: Decimal


class Analysis(BaseModel):
    run_id: str
    statistics: dict[str, Statistic]
    daily_returns: list[ReturnPoint]
    monthly_returns: list[ReturnPoint]
    drawdown: list[DrawdownPoint]
    round_trips: list[RoundTrip]
    distributions: dict[str, list[Decimal]]
    warnings: list[str]


def round_trips(fills: tuple[Fill, ...]) -> list[RoundTrip]:
    """FIFO matched lots, allocating both sides' fees by matched quantity."""
    lots: dict[str, deque[tuple[Fill, int]]] = {}
    trips: list[RoundTrip] = []
    for fill in fills:
        queue = lots.setdefault(fill.instrument_id, deque())
        if fill.side == "buy":
            queue.append((fill, fill.quantity))
            continue
        remaining = fill.quantity
        while remaining and queue:
            entry, available = queue.popleft()
            quantity = min(available, remaining)
            entry_fees = (entry.commission + entry.tax) * quantity / entry.quantity
            exit_fees = (fill.commission + fill.tax) * quantity / fill.quantity
            cost = entry.execution_price * quantity + entry_fees
            pnl = fill.execution_price * quantity - exit_fees - cost
            trips.append(
                RoundTrip(
                    instrument_id=fill.instrument_id,
                    entry_at=entry.timestamp,
                    exit_at=fill.timestamp,
                    quantity=quantity,
                    entry_price=entry.execution_price,
                    exit_price=fill.execution_price,
                    fees=entry_fees + exit_fees,
                    net_profit=pnl,
                    return_on_cost=pnl / cost,
                    holding_seconds=Decimal(
                        str((fill.timestamp - entry.timestamp).total_seconds())
                    ),
                )
            )
            remaining -= quantity
            if available > quantity:
                queue.appendleft((entry, available - quantity))
    return trips


def _returns(values: dict[str, Decimal], initial: Decimal) -> list[ReturnPoint]:
    previous = initial
    points: list[ReturnPoint] = []
    for period, equity in values.items():
        points.append(ReturnPoint(period=period, value=equity / previous - 1))
        previous = equity
    return points


def _finite(value: float) -> Decimal | None:
    return Decimal(str(value)) if math.isfinite(value) else None


def analyze(report: SimulationReport) -> Analysis:
    initial = report.config.initial_cash
    portfolio = report.result.portfolio
    trips = round_trips(report.result.fills)
    daily: dict[str, Decimal] = {}
    monthly: dict[str, Decimal] = {}
    drawdown: list[DrawdownPoint] = []
    peak = initial
    for point in portfolio:
        day = point.timestamp.astimezone(ZoneInfo(report.manifest.timezone)).date().isoformat()
        daily[day] = point.equity
        monthly[day[:7]] = point.equity
        peak = max(peak, point.equity)
        drawdown.append(
            DrawdownPoint(timestamp=point.timestamp, value=(peak - point.equity) / peak)
        )
    daily_returns = _returns(daily, initial)
    returns = [float(p.value) for p in daily_returns]
    count = len(returns)
    average = sum(returns) / count if count else 0.0
    deviation = stdev(returns) if count > 1 else 0.0
    downside = math.sqrt(sum(min(r, 0) ** 2 for r in returns) / count) if count else 0.0
    gains = sum((t.net_profit for t in trips if t.net_profit > 0), ZERO)
    losses = -sum((t.net_profit for t in trips if t.net_profit < 0), ZERO)
    stats: dict[str, Statistic] = {}

    def metric(name: str, value: Decimal | None, definition: str, reason: str) -> None:
        stats[name] = Statistic(
            value=value, definition=definition, reason=reason if value is None else None
        )

    summary = report.result.summary
    metric("commission", summary.commission, "sum actual fill commissions in USD", "")
    metric("tax", summary.tax, "sum actual fill taxes in USD", "")
    metric(
        "spread",
        summary.spread,
        "half-spread adverse cost in USD; included in execution price, separate from slippage",
        "",
    )
    metric(
        "slippage",
        summary.slippage,
        "adverse price slippage in USD; already included in execution price, not subtracted again",
        "",
    )
    metric(
        "net_profit",
        summary.final_equity - initial,
        "final_equity - initial_cash; includes unrealized PnL, fees and price slippage once",
        "",
    )
    metric("total_return", summary.total_return, "final_equity / initial_cash - 1", "")
    metric(
        "max_drawdown",
        max((p.value for p in drawdown), default=ZERO),
        "maximum (peak - equity) / peak; peak includes initial cash",
        "",
    )
    elapsed = (
        (portfolio[-1].timestamp - portfolio[0].timestamp).total_seconds()
        if len(portfolio) > 1
        else 0
    )
    annual: Decimal | None = None
    if elapsed >= SECONDS_PER_DAY and summary.final_equity > 0:
        try:
            annual = _finite(
                math.expm1(
                    math.log(float(summary.final_equity / initial)) * 365.25 * 86400 / elapsed
                )
            )
        except OverflowError:
            annual = None
    metric(
        "cagr",
        annual,
        "(final/initial)^(365.25 / elapsed calendar days) - 1",
        "requires >=1 elapsed day, positive equity and finite annualization",
    )
    metric(
        "volatility",
        _finite(deviation * math.sqrt(TRADING_DAYS)) if count > 1 else None,
        "sample standard deviation of NY daily returns * sqrt(252)",
        "fewer than 2 daily returns",
    )
    metric(
        "sharpe",
        _finite(average / deviation * math.sqrt(TRADING_DAYS)) if deviation else None,
        "mean daily return / sample deviation * sqrt(252); risk-free=0",
        "zero daily variance or fewer than 2 daily returns",
    )
    metric(
        "sortino",
        _finite(average / downside * math.sqrt(TRADING_DAYS)) if downside else None,
        "mean daily return / sqrt(mean(min(return,0)^2)) * sqrt(252); target=0",
        "no downside observations",
    )
    metric(
        "win_rate",
        Decimal(sum(t.net_profit > 0 for t in trips)) / len(trips) if trips else None,
        "positive FIFO matched lots / all closed FIFO matched lots; open lots excluded",
        "no closed matched lots",
    )
    metric(
        "profit_factor",
        gains / losses if losses else None,
        "sum positive closed net PnL / absolute sum negative closed net PnL",
        "no losing closed matched lots",
    )
    winners, losers = (sum(t.net_profit > 0 for t in trips), sum(t.net_profit < 0 for t in trips))
    metric(
        "payoff_ratio",
        (gains / winners) / (losses / losers) if winners and losers else None,
        "mean positive closed net PnL / absolute mean negative closed net PnL",
        "requires both winning and losing closed matched lots",
    )
    metric(
        "expectancy",
        sum((t.net_profit for t in trips), ZERO) / len(trips) if trips else None,
        "mean net PnL per closed FIFO matched lot in USD",
        "no closed matched lots",
    )
    metric(
        "exposure",
        Decimal(sum(p.market_value > 0 for p in portfolio)) / len(portfolio) if portfolio else None,
        "observed bars with market_value > 0 / observed bars; not time weighted",
        "no portfolio bars",
    )
    metric(
        "turnover",
        sum((f.execution_price * f.quantity for f in report.result.fills), ZERO) / initial,
        "gross traded execution notional (both sides) / initial cash; not annualized",
        "",
    )
    metric(
        "holding_seconds",
        sum((t.holding_seconds for t in trips), ZERO) / len(trips) if trips else None,
        "unweighted mean seconds per closed FIFO matched lot",
        "no closed matched lots",
    )
    return Analysis(
        run_id=report.run_id,
        statistics=stats,
        daily_returns=daily_returns,
        monthly_returns=_returns(monthly, initial),
        drawdown=drawdown,
        round_trips=trips,
        distributions={
            "closed_net_profit": [t.net_profit for t in trips],
            "closed_return": [t.return_on_cost for t in trips],
            "holding_seconds": [t.holding_seconds for t in trips],
        },
        warnings=[
            "252-day annualization is a research convention; no exchange calendar.",
            "Open positions are excluded from closed-lot statistics.",
        ]
        + (
            ["Partial/failed run: statistics describe only observed results."]
            if report.result.status != "succeeded"
            else []
        ),
    )


def safe_cell(value: object) -> str:
    text = str(value)
    dangerous = isinstance(value, str) and (
        text.lstrip().startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n"))
    )
    return "'" + text if dangerous else text


def export_csv(report: SimulationReport, kind: Literal["fills", "equity", "orders"]) -> str:
    records: list[dict[str, object]]
    if kind == "fills":
        records = [f.model_dump() for f in report.result.fills]
        headers = list(Fill.model_fields)
    elif kind == "equity":
        records = [p.model_dump() for p in report.result.portfolio]
        headers = [
            "timestamp",
            "cash",
            "market_value",
            "equity",
            "realized_pnl",
            "unrealized_pnl",
            "positions",
        ]
    else:
        records = [
            {**o.model_dump(exclude={"intent"}), **o.intent.model_dump()}
            for o in report.result.orders
        ]
        headers = [
            "order_id",
            "state",
            "filled_quantity",
            "state_reason",
            "triggered_at",
            "instrument_id",
            "submitted_at",
            "side",
            "quantity",
            "order_type",
            "limit_price",
            "stop_price",
            "time_in_force",
            "reason",
            "strategy_version",
            "rule_path",
        ]
    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(headers)
    for record in records:
        writer.writerow([safe_cell(record.get(h, "")) for h in headers])
    return output.getvalue()
