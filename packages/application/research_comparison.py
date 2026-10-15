from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.application.research_data import acquire_research_data
from packages.application.simulation_models import (
    MAX_SIMULATION_BARS,
    SimulationReport,
    SimulationRequest,
)
from packages.application.simulations import SimulationService
from packages.market_data.snapshots import FileSnapshotStore
from packages.strategy.schema import StrategyDefinition


class CompareRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
    run_ids: tuple[str, ...] = Field(min_length=2, max_length=8)


class ComparedRun(BaseModel):
    run_id: str
    status: str
    snapshot_id: str
    symbol: str
    interval: str
    start: datetime | None
    end: datetime | None
    total_return: Decimal
    max_drawdown: Decimal
    net_profit: Decimal


class Comparison(BaseModel):
    comparable: bool
    rows: list[ComparedRun]
    differences: list[str]
    warnings: list[str]


class BenchmarkRequest(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")
    run_id: str
    benchmark_symbol: Literal["QQQ"] = "QQQ"
    snapshot_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class BenchmarkPoint(BaseModel):
    timestamp: datetime
    run_equity: Decimal
    benchmark_value: Decimal


class BenchmarkComparison(BaseModel):
    run_id: str
    benchmark_symbol: Literal["QQQ"] = "QQQ"
    snapshot_id: str
    provider: str
    points: list[BenchmarkPoint]
    benchmark_return: Decimal | None
    reason: str | None
    excluded_run_timestamps: int
    excluded_benchmark_timestamps: int
    warnings: list[str]


class ResearchComparison:
    def __init__(self, root: Path, simulations: SimulationService) -> None:
        """Read verified runs and independent benchmark snapshots from one store."""
        self._root = root
        self._simulations = simulations

    def run(self, run_id: str) -> SimulationReport:
        report = self._simulations.get(run_id)
        if report is None:
            raise LookupError(run_id)
        return report

    def compare(self, body: CompareRequest) -> Comparison:
        reports = [self.run(identity) for identity in body.run_ids]
        rows = [
            ComparedRun(
                run_id=r.run_id,
                status=r.result.status,
                snapshot_id=r.manifest.snapshot_id,
                symbol=r.request.symbol,
                interval=r.config.bar_interval,
                start=r.result.portfolio[0].timestamp if r.result.portfolio else None,
                end=r.result.portfolio[-1].timestamp if r.result.portfolio else None,
                total_return=r.result.summary.total_return,
                max_drawdown=r.metrics.max_drawdown,
                net_profit=r.metrics.net_profit,
            )
            for r in reports
        ]
        dimensions: dict[str, list[object]] = {
            "snapshot": [r.manifest.snapshot_id for r in reports],
            "symbol": [r.symbol for r in rows],
            "interval": [r.interval for r in rows],
            "start": [r.start for r in rows],
            "end": [r.end for r in rows],
            "initial_cash": [r.config.initial_cash for r in reports],
            "price_adjustment": [r.manifest.price_adjustment for r in reports],
            "volume_adjustment": [r.manifest.volume_adjustment for r in reports],
            "status": [r.status for r in rows],
        }
        differences = [key for key, values in dimensions.items() if len(set(values)) > 1]
        warnings = [
            f"Different {key}; not a controlled like-for-like comparison." for key in differences
        ]
        if any(r.result.status != "succeeded" for r in reports):
            warnings.append(
                "Failed/cancelled results are partial and must not be ranked as successes."
            )
        if any(r.manifest.provider == "synthetic_demo" for r in reports):
            warnings.append("Synthetic demo results are not actual market performance.")
        return Comparison(
            comparable=not differences and all(r.status == "succeeded" for r in rows),
            rows=rows,
            differences=differences,
            warnings=warnings,
        )

    def benchmark(self, body: BenchmarkRequest) -> BenchmarkComparison:
        report = self.run(body.run_id)
        if body.snapshot_id is None and report.request.source == "snapshot":
            msg = "업로드 실행의 QQQ 비교에는 별도 QQQ snapshot_id가 필요합니다."
            raise ValueError(msg)
        definition = report.request.strategy.model_dump(mode="json")
        definition["universe"] = ["NASDAQ:QQQ"]
        payload = report.request.model_dump(mode="json")
        payload.update(
            {
                "symbol": "QQQ",
                "strategy": StrategyDefinition.model_validate(definition),
                "source": "snapshot" if body.snapshot_id else report.request.source,
                "snapshot_id": body.snapshot_id,
                "start": report.manifest.range_start,
                "end": report.manifest.range_end,
            }
        )
        request = SimulationRequest.model_validate(payload)
        manifest = acquire_research_data(self._root, request)
        if manifest.row_count > MAX_SIMULATION_BARS:
            msg = f"QQQ 비교는 {MAX_SIMULATION_BARS}개 bar까지 지원합니다."
            raise ValueError(msg)
        loaded = FileSnapshotStore(self._root / "published").read_bars(manifest.snapshot_id)
        if loaded is None:
            raise LookupError(manifest.snapshot_id)
        manifest, bars = loaded
        if (
            manifest.instrument_id != "NASDAQ:QQQ"
            or manifest.interval != report.config.bar_interval
        ):
            msg = "별도 QQQ 데이터와 동일한 주기가 필요합니다."
            raise ValueError(msg)
        equity = {p.timestamp: p.equity for p in report.result.portfolio}
        prices = {b.timestamp: b.close for b in bars}
        common = sorted(equity.keys() & prices.keys())
        points = [
            BenchmarkPoint(
                timestamp=t,
                run_equity=equity[t],
                benchmark_value=report.config.initial_cash * prices[t] / prices[common[0]],
            )
            for t in common
        ]
        warnings = [
            "Common timestamp alignment only; no forward fill. "
            "Benchmark is cost-free fractional buy-and-hold."
        ]
        if manifest.provider == "synthetic_demo":
            warnings.append(
                "Explicit synthetic_demo QQQ; same demo pattern, "
                "not independent actual QQQ history."
            )
        if manifest.price_adjustment != report.manifest.price_adjustment:
            warnings.append("Price adjustment differs; not directly comparable.")
        return BenchmarkComparison(
            run_id=body.run_id,
            snapshot_id=manifest.snapshot_id,
            provider=manifest.provider,
            points=points,
            benchmark_return=prices[common[-1]] / prices[common[0]] - 1
            if len(common) > 1
            else None,
            reason=None if len(common) > 1 else "fewer than 2 common timestamps",
            excluded_run_timestamps=len(equity) - len(common),
            excluded_benchmark_timestamps=len(prices) - len(common),
            warnings=warnings,
        )
