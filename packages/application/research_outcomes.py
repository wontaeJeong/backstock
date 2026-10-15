"""Read-only presentation bridges over verified research artifacts."""

from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel

from packages.application.research_analysis import Statistic
from packages.application.research_experiment_models import PortfolioExperiment
from packages.application.simulation_models import MAX_SIMULATION_BARS
from packages.domain.market_data import Bar
from packages.market_data.snapshots import FileSnapshotStore


class BarPage(BaseModel):
    snapshot_id: str
    interval: str
    items: list[Bar]
    total: int
    page: int
    page_size: int


def preview_bars(root: Path, identity: str, page: int, page_size: int) -> BarPage:
    store = FileSnapshotStore(root / "published")
    manifest = store.load(identity)
    if manifest is None:
        raise LookupError(identity)
    if manifest.row_count > MAX_SIMULATION_BARS:
        message = "연구 snapshot은 최대 3000개 bar까지 미리 볼 수 있습니다."
        raise ValueError(message)
    loaded = store.read_bars(identity)
    if loaded is None:
        raise LookupError(identity)
    _, bars = loaded
    start = (page - 1) * page_size
    return BarPage(
        snapshot_id=identity,
        interval=manifest.interval,
        items=list(bars[start : start + page_size]),
        total=len(bars),
        page=page,
        page_size=page_size,
    )


class PortfolioAnalysis(BaseModel):
    experiment_id: str
    statistics: dict[str, Statistic]


def portfolio_analysis(experiment: PortfolioExperiment) -> PortfolioAnalysis:
    complete = (
        bool(experiment.curve)
        and not any(experiment.excluded_timestamps.values())
        and all(c.status == "succeeded" for c in experiment.components)
    )
    initial = experiment.request.initial_cash
    final = experiment.curve[-1].equity if complete else initial
    peak = initial
    drawdown = Decimal(0)
    for point in experiment.curve:
        peak = max(peak, point.equity)
        drawdown = max(drawdown, (peak - point.equity) / peak)
    values = {
        "initial_cash": initial,
        "final_equity": final,
        "net_profit": final - initial,
        "total_return": final / initial - 1,
        "max_drawdown": drawdown,
    }
    definitions = {
        "initial_cash": "fixed total initial budget USD",
        "final_equity": "last common timestamp aggregate equity USD",
        "net_profit": "final_equity - initial_cash USD",
        "total_return": "final_equity / initial_cash - 1",
        "max_drawdown": "max (peak - equity) / peak; initial cash included",
    }
    return PortfolioAnalysis(
        experiment_id=experiment.experiment_id,
        statistics={
            key: Statistic(
                value=value if complete else None,
                definition=definitions[key],
                reason=None if complete else "incomplete aggregate curve or unsuccessful component",
            )
            for key, value in values.items()
        },
    )
