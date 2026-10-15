import itertools
import math
from collections.abc import Callable
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from statistics import correlation
from time import monotonic
from zoneinfo import ZoneInfo

from pydantic import TypeAdapter

from packages.application.datasets import DatasetInvalidError, SnapshotNotFoundError
from packages.application.research_data import acquire_research_data
from packages.application.research_experiment_models import (
    Correlation,
    Experiment,
    ExperimentRow,
    GridExperiment,
    GridRequest,
    PortfolioComponentResult,
    PortfolioExperiment,
    PortfolioPoint,
    PortfolioRequest,
    WalkFold,
    WalkForwardExperiment,
    WalkForwardRequest,
)
from packages.application.research_parameters import combinations, parameterize, validate_axes
from packages.application.research_store import ResearchStore
from packages.application.simulation_models import (
    MAX_SIMULATION_BARS,
    SimulationReport,
    SimulationRequest,
)
from packages.application.simulations import SimulationService
from packages.market_data.errors import MarketDataError
from packages.market_data.snapshots import FileSnapshotStore

EXPERIMENT_SECONDS = 30
MIN_CORRELATION_RETURNS = 2
WARNINGS = [
    "Research only; parameter search can overfit. No live orders.",
    "30s cooperative engine budget; external provider I/O has separate bounded timeouts.",
]


class ResearchExperiments:
    def __init__(
        self, root: Path, simulations: SimulationService, clock: Callable[[], float] = monotonic
    ) -> None:
        """Execute real isolated engine runs with a shared cooperative deadline."""
        self._root = root
        self._simulations = simulations
        self._store = ResearchStore(root)
        self._clock = clock

    def _freeze(self, base: SimulationRequest) -> SimulationRequest:
        manifest = acquire_research_data(self._root, base)
        if manifest.row_count > MAX_SIMULATION_BARS:
            msg = f"연구 실험은 {MAX_SIMULATION_BARS}개 bar까지 지원합니다."
            raise ValueError(msg)
        return SimulationRequest.model_validate(
            {
                **base.model_dump(mode="json"),
                "source": "snapshot",
                "snapshot_id": manifest.snapshot_id,
            }
        )

    def _execute(
        self,
        base: SimulationRequest,
        parameters: dict[str, Decimal],
        deadline: float,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> ExperimentRow:
        if self._clock() >= deadline:
            return ExperimentRow(
                parameters=parameters, status="not_run", error="30s experiment budget exhausted"
            )
        try:
            request = parameterize(base, parameters)
            report = self._simulations.run(
                request, trade_start=start, trade_end=end, deadline=deadline
            )
        except (ValueError, MarketDataError, SnapshotNotFoundError, DatasetInvalidError) as error:
            return ExperimentRow(parameters=parameters, status="failed", error=str(error)[:500])
        if report.result.status != "succeeded":
            return ExperimentRow(
                parameters=parameters,
                run_id=report.run_id,
                status=report.result.status,
                error=report.result.failure_reason or "run did not succeed",
            )
        return ExperimentRow(
            parameters=parameters,
            run_id=report.run_id,
            status="succeeded",
            total_return=report.result.summary.total_return,
            max_drawdown=report.metrics.max_drawdown,
            net_profit=report.metrics.net_profit,
        )

    def _save(self, experiment: Experiment) -> Experiment:
        payload = self._store.save("experiments", experiment, "experiment_id")
        return TypeAdapter(Experiment).validate_python(payload)

    def get(self, identity: str) -> Experiment:
        payload = self._store.get("experiments", identity, "experiment_id")
        if payload is None:
            raise LookupError(identity)
        return TypeAdapter(Experiment).validate_python(payload)

    def grid(self, body: GridRequest) -> Experiment:
        validate_axes(body.base, body.axes)
        deadline = self._clock() + EXPERIMENT_SECONDS
        base = self._freeze(body.base)
        rows = [self._execute(base, p, deadline) for p in combinations(body.axes)]
        return self._save(
            GridExperiment(
                request=body,
                rows=rows,
                warnings=WARNINGS,
                baseline_snapshot_id=base.snapshot_id or "",
            )
        )

    def walk_forward(self, body: WalkForwardRequest) -> Experiment:
        validate_axes(body.base, body.axes)
        deadline = self._clock() + EXPERIMENT_SECONDS
        base = self._freeze(body.base)
        loaded = FileSnapshotStore(self._root / "published").read_bars(base.snapshot_id or "")
        if loaded is None:
            raise LookupError(base.snapshot_id)
        _, bars = loaded
        folds: list[WalkFold] = []
        for number in range(body.folds):
            offset = number * body.test_bars
            test_start = offset + body.train_bars
            stop = test_start + body.test_bars
            if stop > len(bars):
                folds.append(
                    WalkFold(
                        fold=number + 1,
                        status="not_run",
                        error="insufficient bars for complete fold",
                    )
                )
                continue
            training = [
                self._execute(
                    base,
                    parameters,
                    deadline,
                    start=bars[offset].timestamp,
                    end=bars[test_start].timestamp,
                )
                for parameters in combinations(body.axes)
            ]
            eligible = [
                r for r in training if r.status == "succeeded" and r.total_return is not None
            ]
            selected = (
                max(
                    eligible,
                    key=lambda r: (
                        r.total_return if r.total_return is not None else Decimal("-Infinity")
                    ),
                )
                if eligible
                else None
            )
            test = (
                self._execute(
                    base,
                    selected.parameters,
                    deadline,
                    start=bars[test_start].timestamp,
                    end=bars[stop - 1].timestamp + timedelta(microseconds=1),
                )
                if selected
                else None
            )
            folds.append(
                WalkFold(
                    fold=number + 1,
                    train_start=bars[offset].timestamp,
                    train_end=bars[test_start - 1].timestamp,
                    test_start=bars[test_start].timestamp,
                    test_end=bars[stop - 1].timestamp,
                    training=training,
                    train_run_ids=[r.run_id for r in training if r.run_id is not None],
                    selected_parameters=selected.parameters if selected else {},
                    test=test,
                    test_run_id=test.run_id if test else None,
                    status=test.status if test else "not_run",
                    error=None if test else "no successful training candidate",
                )
            )
        return self._save(
            WalkForwardExperiment(
                request=body,
                baseline_snapshot_id=base.snapshot_id or "",
                folds=folds,
                warnings=[
                    *WARNINGS,
                    "Rolling chronological windows. Train-only total-return selection; "
                    "ties use first candidate.",
                    "Each test starts fresh cash/evaluator; historical bars warm indicators only. "
                    "No pooled OOS CAGR.",
                ],
            )
        )

    def portfolio(self, body: PortfolioRequest) -> Experiment:
        deadline = self._clock() + EXPERIMENT_SECONDS
        components: list[PortfolioComponentResult] = []
        reports: list[SimulationReport] = []
        for index, component in enumerate(body.components):
            budget = body.initial_cash * component.weight
            request = SimulationRequest.model_validate(
                {**component.request.model_dump(mode="json"), "initial_cash": str(budget)}
            )
            row = self._execute(request, {}, deadline)
            components.append(
                PortfolioComponentResult(
                    index=index,
                    weight=component.weight,
                    budget=budget,
                    run_id=row.run_id,
                    status=row.status,
                    error=row.error,
                )
            )
            if row.status == "succeeded" and row.run_id:
                report = self._simulations.get(row.run_id)
                if report is not None:
                    reports.append(report)
        reserve = body.initial_cash - sum((c.budget for c in components), Decimal(0))
        curves = [{p.timestamp: p.equity for p in r.result.portfolio} for r in reports]
        common = (
            sorted(set.intersection(*(set(c) for c in curves)))
            if curves and len(reports) == len(components)
            else []
        )
        curve = [
            PortfolioPoint(timestamp=t, equity=reserve + sum((c[t] for c in curves), Decimal(0)))
            for t in common
        ]
        correlations = _correlations(curves, common) if len(reports) == len(components) else []
        warnings = [
            *WARNINGS,
            "Fixed independent budgets, no rebalancing or cross-component cash sharing.",
            "Common timestamps only, no forward fill. "
            "Correlations use daily equity returns between the last common timestamps "
            "per America/New_York date; observations count common daily returns.",
        ]
        if any(r.manifest.provider == "synthetic_demo" for r in reports):
            warnings.append(
                "synthetic_demo components share the same demo price pattern; "
                "correlation is not market diversification evidence."
            )
        if len(reports) != len(components):
            warnings.append(
                "Incomplete components: aggregate curve withheld, "
                "no assumed zero or cash-only success."
            )
        return self._save(
            PortfolioExperiment(
                request=body,
                components=components,
                reserve_cash=reserve,
                curve=curve,
                correlations=correlations,
                excluded_timestamps={
                    r.run_id: len(r.result.portfolio) - len(common) for r in reports
                },
                warnings=warnings,
            )
        )


def _correlations(
    curves: list[dict[datetime, Decimal]], common: list[datetime]
) -> list[Correlation]:
    daily_marks: dict[date, datetime] = {}
    zone = ZoneInfo("America/New_York")
    for timestamp in sorted(common):
        daily_marks[timestamp.astimezone(zone).date()] = timestamp
    returns = [
        [float(curve[b] / curve[a] - 1) for a, b in itertools.pairwise(daily_marks.values())]
        for curve in curves
    ]
    results: list[Correlation] = []
    for left in range(len(returns)):
        for right in range(left + 1, len(returns)):
            value = None
            reason = "fewer than 2 common daily returns or zero variance"
            finite = all(
                math.isfinite(value)
                for series in (returns[left], returns[right])
                for value in series
            )
            if not finite:
                reason = "non-finite common daily returns"
            elif (
                len(returns[left]) >= MIN_CORRELATION_RETURNS
                and len(set(returns[left])) > 1
                and len(set(returns[right])) > 1
            ):
                coefficient = correlation(returns[left], returns[right])
                if math.isfinite(coefficient):
                    value = Decimal(str(coefficient))
                else:
                    reason = "non-finite daily correlation"
            results.append(
                Correlation(
                    left=left,
                    right=right,
                    value=value,
                    reason=reason if value is None else None,
                    observations=max(0, len(daily_marks) - 1),
                )
            )
    return results
