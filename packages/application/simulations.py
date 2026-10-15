import hashlib
import json
import re
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from time import monotonic
from zoneinfo import ZoneInfo

from packages.application.research_data import acquire_research_data
from packages.application.research_store import verified_payload
from packages.application.simulation_history import HistoryEvaluator
from packages.application.simulation_models import (
    MAX_SIMULATION_BARS,
    SimulationMetrics,
    SimulationReport,
    SimulationRequest,
)
from packages.backtest.analytics import maximum_drawdown
from packages.backtest.engine import BacktestEngine
from packages.backtest.models import BacktestConfig, BacktestInput, CostConfig, SnapshotReference
from packages.domain.market_data import Bar
from packages.market_data.snapshots import FileSnapshotStore, SnapshotManifest, _write_once
from packages.strategy.evaluator import DslStrategyEvaluator
from packages.strategy.validation import create_strategy_version

__all__ = ["SimulationRequest", "SimulationService"]
MIN_BARS = 2
SATURDAY = 5
SESSION_OPEN_MINUTES = 570
SESSION_CLOSE_MINUTES = 960
MAX_RUN_SECONDS = 15


class RunDeadline:
    def __init__(
        self, clock: Callable[[], float] = monotonic, deadline: float | None = None
    ) -> None:
        """Bound engine work cooperatively between bars, not external I/O."""
        self._clock = clock
        self._deadline = (
            min(clock() + MAX_RUN_SECONDS, deadline)
            if deadline is not None
            else clock() + MAX_RUN_SECONDS
        )

    def should_cancel(self, processed_events: int) -> bool:
        del processed_events
        return self._clock() >= self._deadline


class SimulationService:
    def __init__(self, root: Path, *, code_revision: str) -> None:
        """Bind a local research store and reproducible source revision."""
        self._root = root
        self._revision = code_revision

    def run(
        self,
        request: SimulationRequest,
        *,
        trade_start: datetime | None = None,
        trade_end: datetime | None = None,
        deadline: float | None = None,
    ) -> SimulationReport:
        manifest = acquire_research_data(self._root, request)
        if manifest.row_count > MAX_SIMULATION_BARS:
            msg = f"MVP는 실행당 {MAX_SIMULATION_BARS}개 bar까지 지원합니다."
            raise ValueError(msg)
        loaded = FileSnapshotStore(self._root / "published").read_bars(manifest.snapshot_id)
        if loaded is None:
            msg = "snapshot을 찾을 수 없습니다."
            raise ValueError(msg)
        manifest, bars = loaded
        _validate_manifest(manifest, request)
        if len(bars) < MIN_BARS:
            msg = "시뮬레이션에는 최소 2개 bar가 필요합니다."
            raise ValueError(msg)
        _validate_intraday(bars, manifest.interval)
        history = tuple(
            bar for bar in bars if trade_start is not None and bar.timestamp < trade_start
        )
        bars = tuple(
            bar
            for bar in bars
            if (trade_start is None or bar.timestamp >= trade_start)
            and (trade_end is None or bar.timestamp < trade_end)
        )
        if len(bars) < MIN_BARS:
            msg = "평가 구간에는 최소 2개 bar가 필요합니다."
            raise ValueError(msg)
        version = create_strategy_version(request.strategy)
        config = BacktestConfig(
            initial_cash=request.initial_cash,
            bar_interval=request.strategy.timeframe,
            spread_bps=request.spread_bps,
            latency_ms=request.latency_ms,
            volume_participation=request.volume_participation,
            costs=CostConfig(
                commission_rate=request.commission_bps / 10000,
                sell_tax_rate=request.sell_tax_bps / 10000,
                slippage_bps=request.slippage_bps,
            ),
            benchmark_instrument_id=manifest.instrument_id,
        )
        result = BacktestEngine().run(
            BacktestInput(
                snapshot=SnapshotReference(
                    snapshot_id=manifest.snapshot_id,
                    normalized_checksum=manifest.normalized_checksum,
                    price_adjustment=manifest.price_adjustment,
                    volume_adjustment=manifest.volume_adjustment,
                ),
                bars=bars,
                config=config,
                strategy_version=version.version_id,
                code_revision=self._revision,
            ),
            HistoryEvaluator(DslStrategyEvaluator(request.strategy, version.version_id), history),
            cancellation=RunDeadline(deadline=deadline),
        )
        warnings = [
            "체결 가정: spread/latency 시나리오이며 실제 queue·충격·부분 체결을 재현하지 않습니다. "
            "volume_participation=null은 유동성 보장이 아닌 무제한 가정입니다. "
            "bar 지연은 다음 eligible open까지 올림하며 OHLC 내부 경로는 알 수 없습니다.",
            "과거 수익률은 미래 수익을 보장하지 않습니다. 실주문 기능은 없습니다.",
            "종가 확정 후 판단하고 다음 bar 시가부터 체결합니다. "
            "손절·익절은 종가 조건이며 보호 주문이 아닙니다.",
            "미청산 포지션은 마지막 종가로 평가합니다. 최종 평가금액은 현금 잔액이 아닙니다.",
            "단순보유 비교는 같은 종목의 첫/마지막 종가 기준이며 "
            "비용·정수 수량 제약이 없는 참고값입니다.",
            "거래소 휴장·조기폐장 calendar가 없어 데이터 완전성을 보장하지 않습니다. "
            "누락을 채우지 않습니다.",
        ]
        warnings.extend(_session_warnings(request))
        if trade_start is not None or trade_end is not None:
            warnings.append(
                f"Evaluation range: {bars[0].timestamp.isoformat()} .. "
                f"{bars[-1].timestamp.isoformat()}; warmup bars={len(history)}; fresh capital."
            )
        if manifest.provider == "synthetic_demo":
            warnings.insert(
                0, "합성 데모 데이터입니다. 실제 나스닥 과거 시세나 투자 성과가 아닙니다."
            )
        if manifest.interval != "1d":
            warnings.insert(
                0,
                "분봉 기반 근사 실험입니다. 호가·스프레드·실제 지연·부분 체결을 검증하지 않아 "
                "초단타 실전 유효성을 입증하지 못합니다.",
            )
        else:
            warnings.append("일봉으로 초단타 전략의 유효성을 판단할 수 없습니다.")
        if manifest.price_adjustment != "raw":
            warnings.append(
                "소급 보정 가격 연구입니다. "
                "당시 이용 가능했던 가격이나 배당 현금원장을 재현하지 않습니다."
            )
        else:
            warnings.append(
                "raw 가격의 분할·배당은 원장에 반영하지 않습니다. "
                "해당 이벤트를 포함한 손익은 완전하지 않습니다."
            )
        if not result.fills:
            warnings.append(
                "체결이 없습니다. 조건·지표 준비 기간·투자 금액과 거절 사유를 확인하세요."
            )
        report = SimulationReport(
            run_id="",
            request=request,
            config=config,
            manifest=manifest,
            result=result,
            metrics=SimulationMetrics(
                net_profit=result.summary.final_equity - request.initial_cash,
                max_drawdown=maximum_drawdown(request.initial_cash, result.portfolio),
                fill_count=len(result.fills),
                closed_trade_count=sum(fill.side == "sell" for fill in result.fills),
                benchmark_return=bars[-1].close / bars[0].close - 1,
            ),
            warnings=tuple(warnings),
        )
        report = report.model_copy(update={"run_id": _report_hash(report)})
        directory = self._root / "runs"
        directory.mkdir(parents=True, exist_ok=True)
        _write_once(directory / f"{report.run_id}.json", report.model_dump_json().encode())
        return report

    def get(self, run_id: str) -> SimulationReport | None:
        if re.fullmatch(r"[0-9a-f]{64}", run_id) is None:
            return None
        path = self._root / "runs" / f"{run_id}.json"
        if not path.is_file():
            return None
        payload = verified_payload(path, run_id, "run_id")
        return SimulationReport.model_validate(payload)


def _report_hash(report: SimulationReport) -> str:
    payload = json.dumps(
        report.model_dump(mode="json", exclude={"run_id"}), sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def _session_warnings(request: SimulationRequest) -> list[str]:
    if request.strategy.session is not None and request.strategy.session.flatten_at is not None:
        return [
            "마감 청산은 종가 기반 신호입니다. 다음 이벤트 부재·지연으로 미체결/보유가 "
            "남을 수 있으며 강제 종가 체결하지 않습니다."
        ]
    return []


def _validate_manifest(manifest: SnapshotManifest, request: SimulationRequest) -> None:
    if manifest.currency != "USD" or manifest.timezone != "America/New_York":
        message = (
            "연구 MVP는 USD·America/New_York metadata가 있는 snapshot만 지원합니다. "
            "다시 업로드하세요."
        )
        raise ValueError(message)
    if manifest.instrument_id != request.strategy.universe[0]:
        message = "snapshot 종목과 전략 종목이 다릅니다."
        raise ValueError(message)
    if manifest.interval != request.strategy.timeframe:
        message = "snapshot 주기와 전략 주기가 다릅니다."
        raise ValueError(message)


def _validate_intraday(bars: tuple[Bar, ...], interval: str) -> None:
    if interval == "tick":
        previous_tick: datetime | None = None
        for bar in bars:
            local = bar.timestamp.astimezone(ZoneInfo("America/New_York"))
            minute = local.hour * 60 + local.minute
            if (
                bar.price_adjustment != "raw"
                or bar.volume_adjustment != "raw"
                or bar.timestamp_provenance != "explicit_offset"
                or local.weekday() >= SATURDAY
                or not SESSION_OPEN_MINUTES <= minute < SESSION_CLOSE_MINUTES
                or (previous_tick is not None and bar.timestamp <= previous_tick)
                or not bar.open == bar.high == bar.low == bar.close
            ):
                message = "tick requires raw, unique ordered aware regular-session point events"
                raise ValueError(message)
            previous_tick = bar.timestamp
        return
    if interval == "1d":
        dates = {bar.timestamp.astimezone(ZoneInfo("America/New_York")).date() for bar in bars}
        if len(dates) != len(bars):
            message = (
                "일봉에는 종목별 하루 한 개의 bar만 사용할 수 있습니다. 분봉 주기를 선택하세요."
            )
            raise ValueError(message)
        return
    duration = timedelta(minutes=1 if interval == "1m" else 5)
    previous: Bar | None = None
    for bar in bars:
        local = bar.timestamp.astimezone(ZoneInfo("America/New_York"))
        minutes = local.hour * 60 + local.minute
        if (
            local.weekday() >= SATURDAY
            or not SESSION_OPEN_MINUTES < minutes <= SESSION_CLOSE_MINUTES
            or local.second != 0
            or (interval == "5m" and local.minute % 5 != 0)
        ):
            msg = "분봉은 미국 정규장 bar 종료 시각(명시적 UTC offset)으로 제공해야 합니다."
            raise ValueError(msg)
        if previous is not None:
            delta = bar.timestamp - previous.timestamp
            same_day = (
                local.date() == previous.timestamp.astimezone(ZoneInfo("America/New_York")).date()
            )
            if delta <= timedelta(0) or (same_day and delta != duration):
                msg = "분봉 간격이 다르거나 누락되었습니다. 자동 보간하지 않습니다."
                raise ValueError(msg)
        previous = bar
