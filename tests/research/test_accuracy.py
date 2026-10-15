import csv
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest

from packages.application.datasets import DatasetSnapshotService
from packages.application.research_analysis import analyze, export_csv, round_trips, safe_cell
from packages.application.research_data import nasdaq_instrument
from packages.application.research_experiment_models import Axis, GridRequest, WalkForwardRequest
from packages.application.research_experiments import ResearchExperiments
from packages.application.simulation_models import SimulationRequest
from packages.application.simulations import SimulationService
from packages.backtest.models import Fill, Side
from packages.domain.market_data import AdjustmentMode, Bar, BarRequest, MarketDataResult
from packages.market_data.provider_support import lineage
from packages.market_data.raw_store import FileRawStore
from packages.market_data.snapshots import FileSnapshotStore
from tests.research.test_features import client, request


def snapshot(root: Path, prices: list[int], symbol: str = "AAPL") -> str:
    start = datetime(2024, 1, 2, 21, tzinfo=UTC)
    bars = tuple(
        Bar(
            instrument_id=f"NASDAQ:{symbol}",
            timestamp=start + timedelta(days=i),
            open=Decimal(p),
            close=Decimal(p),
            high=Decimal(p),
            low=Decimal(p),
            volume=1000,
            price_adjustment=AdjustmentMode.RAW,
            volume_adjustment=AdjustmentMode.RAW,
        )
        for i, p in enumerate(prices)
    )
    raw = FileRawStore(root / "raw", clock=lambda: start)
    artifact = raw.capture(
        provider="offline_fixture",
        provider_version="1",
        request={"provider_symbol": symbol, "interval": "1d"},
        payload=json.dumps(prices).encode(),
        media_type="application/json",
    )
    return (
        DatasetSnapshotService(FileSnapshotStore(root / "published"))
        .create_from_result(
            BarRequest(
                instrument=nasdaq_instrument(symbol),
                start=start,
                end=bars[-1].timestamp + timedelta(days=1),
                adjustment=AdjustmentMode.RAW,
            ),
            MarketDataResult(items=bars, lineage=lineage(artifact)),
        )
        .snapshot_id
    )


def test_hand_calculated_engine_fees_roundtrip_returns_and_drawdown(tmp_path: Path) -> None:
    strategy = request().strategy.model_dump(mode="json")
    strategy["risk"] = {"max_holding_bars": 1}
    base = SimulationRequest.model_validate(
        {
            **request().model_dump(mode="json"),
            "source": "snapshot",
            "snapshot_id": snapshot(tmp_path, [100, 100, 110, 90]),
            "strategy": strategy,
            "commission_bps": "10",
            "sell_tax_bps": "20",
            "slippage_bps": "10",
        }
    )
    report = SimulationService(tmp_path, code_revision="test").run(base)
    analysis = analyze(report)
    # Buy 2 at 100.1, fee .2002; sell 2 at 89.91, fee .17982, tax .35964.
    assert len(report.result.fills) == 2
    expected = (
        Decimal("179.82")
        - Decimal("0.17982")
        - Decimal("0.35964")
        - Decimal("200.2")
        - Decimal("0.2002")
    )
    assert len(analysis.round_trips) == 1
    trip = analysis.round_trips[0]
    assert trip.net_profit == expected
    assert trip.fees == Decimal("0.73966")
    assert report.result.summary.final_equity == Decimal(1000) + expected
    assert analysis.statistics["net_profit"].value == expected
    assert analysis.statistics["commission"].value == Decimal("0.38002")
    assert analysis.statistics["tax"].value == Decimal("0.35964")
    assert analysis.statistics["slippage"].value == Decimal("0.38")
    assert analysis.statistics["win_rate"].value == 0
    assert analysis.statistics["profit_factor"].value == 0
    assert analysis.statistics["expectancy"].value == expected
    peak = Decimal("1019.5998")
    assert analysis.statistics["max_drawdown"].value == (peak - (1000 + expected)) / peak
    compounded = Decimal(1)
    for point in analysis.daily_returns:
        compounded *= 1 + point.value
    assert abs(compounded - report.result.summary.final_equity / 1000) < Decimal("1e-25")


def test_fifo_partial_lots_allocate_fees_without_double_slippage() -> None:
    start = datetime(2024, 1, 2, tzinfo=UTC)
    buy = Fill(
        fill_id="1",
        order_id="1",
        instrument_id="A",
        timestamp=start,
        side=Side.BUY,
        quantity=4,
        reference_price=Decimal(99),
        execution_price=Decimal(100),
        commission=Decimal(4),
        tax=Decimal(0),
        slippage=Decimal(4),
    )
    sell = Fill(
        fill_id="2",
        order_id="2",
        instrument_id="A",
        timestamp=start + timedelta(days=1),
        side=Side.SELL,
        quantity=2,
        reference_price=Decimal(111),
        execution_price=Decimal(110),
        commission=Decimal(2),
        tax=Decimal(1),
        slippage=Decimal(2),
    )
    trips = round_trips((buy, sell))
    assert len(trips) == 1
    assert trips[0].quantity == 2
    assert trips[0].fees == 5
    assert trips[0].net_profit == 15
    assert trips[0].return_on_cost == Decimal(15) / 202
    assert trips[0].holding_seconds == 86400


@pytest.mark.parametrize("text", ["=1+1", "+SUM(1)", "-cmd", "@SUM(1)", "\t=1", "  =1"])
def test_csv_escapes_text_cells_only(text: str) -> None:
    assert safe_cell(text).startswith("'")
    assert safe_cell(Decimal("-1.25")) == "-1.25"


def test_csv_exports_every_fill_and_injection_reason(tmp_path: Path) -> None:
    report = SimulationService(tmp_path, code_revision="test").run(request())
    order = report.result.orders[0]
    modified = order.model_copy(
        update={"intent": order.intent.model_copy(update={"reason": "=HYPERLINK(1)"})}
    )
    report = report.model_copy(
        update={"result": report.result.model_copy(update={"orders": (modified,)})}
    )
    rows = list(csv.DictReader(StringIO(export_csv(report, "orders"))))
    assert rows[0]["reason"] == "'=HYPERLINK(1)"
    assert len(list(csv.DictReader(StringIO(export_csv(report, "fills"))))) == len(
        report.result.fills
    )


def test_corrupt_json_returns_integrity_conflict(tmp_path: Path) -> None:
    report = SimulationService(tmp_path, code_revision="test").run(request())
    (tmp_path / "runs" / f"{report.run_id}.json").write_text("{")
    assert client(tmp_path).get(f"/research/runs/{report.run_id}/analysis").status_code == 409


def test_warmup_available_without_training_fills_or_annualization(tmp_path: Path) -> None:
    service = SimulationService(tmp_path, code_revision="test")
    strategy = request().strategy.model_dump(mode="json")
    strategy["entry"]["condition"]["left"] = {"type": "indicator", "indicator": "sma", "period": 30}
    base = SimulationRequest.model_validate(
        {**request().model_dump(mode="json"), "strategy": strategy}
    )
    full = service.run(base)
    loaded = FileSnapshotStore(tmp_path / "published").read_bars(full.manifest.snapshot_id)
    assert loaded is not None
    _, bars = loaded
    test = service.run(base, trade_start=bars[30].timestamp, trade_end=bars[40].timestamp)
    assert len(test.result.portfolio) == 10
    assert test.result.orders[0].intent.submitted_at == bars[30].timestamp
    assert test.result.fills[0].timestamp == bars[31].timestamp
    assert test.result.portfolio[0].cash == 1000
    assert len(test.result.benchmark) == 10
    assert len(analyze(test).daily_returns) == 10


def test_walk_forward_selection_cannot_see_perturbed_test_prices(tmp_path: Path) -> None:
    service = SimulationService(tmp_path, code_revision="test")
    experiments = ResearchExperiments(tmp_path, service)
    results = []
    for prices in ([100, 101, 102, 103, 104, 105, 106, 107], [100, 101, 102, 103, 104, 1, 1, 1]):
        base = request().model_copy(
            update={"source": "snapshot", "snapshot_id": snapshot(tmp_path, prices)}
        )
        experiment = experiments.walk_forward(
            WalkForwardRequest(
                base=base,
                train_bars=4,
                test_bars=4,
                folds=1,
                axes=(
                    Axis(path="strategy.position_sizing.quantity", values=(Decimal(1), Decimal(2))),
                ),
            )
        )
        assert experiment.kind == "walk_forward"
        results.append(experiment)
    assert results[0].folds[0].selected_parameters == results[1].folds[0].selected_parameters
    assert [r.net_profit for r in results[0].folds[0].training] == [
        r.net_profit for r in results[1].folds[0].training
    ]
    assert results[0].folds[0].test != results[1].folds[0].test


def test_invalid_grid_value_preserves_failed_row_and_null_metrics(tmp_path: Path) -> None:
    result = ResearchExperiments(tmp_path, SimulationService(tmp_path, code_revision="test")).grid(
        GridRequest(
            base=request(),
            axes=(Axis(path="strategy.position_sizing.quantity", values=(Decimal(0), Decimal(2))),),
        )
    )
    assert result.kind == "grid"
    assert result.rows[0].status == "failed"
    assert result.rows[0].run_id is None
    assert result.rows[0].total_return is None
    assert result.rows[0].net_profit is None
    assert result.rows[0].error
    assert result.rows[1].status == "succeeded"


def test_experiment_budget_marks_not_run_without_fabricated_success(tmp_path: Path) -> None:
    ticks = iter([0.0, 31.0, 32.0])
    result = ResearchExperiments(
        tmp_path, SimulationService(tmp_path, code_revision="test"), clock=lambda: next(ticks)
    ).grid(
        GridRequest(
            base=request(), axes=(Axis(path="commission_bps", values=(Decimal(0), Decimal(1))),)
        )
    )
    assert result.kind == "grid"
    assert all(
        row.status == "not_run" and row.run_id is None and row.total_return is None
        for row in result.rows
    )


def test_upload_benchmark_needs_separate_qqq_snapshot(tmp_path: Path) -> None:
    base = request().model_copy(
        update={"source": "snapshot", "snapshot_id": snapshot(tmp_path, [100, 101, 102])}
    )
    report = SimulationService(tmp_path, code_revision="test").run(base)
    api = client(tmp_path)
    assert api.post("/research/benchmark", json={"run_id": report.run_id}).status_code == 422
    assert (
        api.post(
            "/research/benchmark",
            json={"run_id": report.run_id, "snapshot_id": report.manifest.snapshot_id},
        ).status_code
        == 422
    )


def test_request_limits_and_invalid_ids(tmp_path: Path) -> None:
    api = client(tmp_path)
    for url in (
        "/research/runs/bad/analysis",
        "/research/experiments/bad",
        "/research/runs/bad/export.csv",
    ):
        assert api.get(url).status_code == 404
    assert api.post("/research/compare", json={"run_ids": ["bad"]}).status_code == 422
    assert api.post("/research/library/strategies", content=b" " * 65537).status_code == 413
    assert (
        api.post(
            "/research/experiments/walk-forward",
            json={
                "base": request().model_dump(mode="json"),
                "train_bars": 30,
                "test_bars": 10,
                "folds": 4,
                "axes": [{"path": "commission_bps", "values": list(range(8))}],
            },
        ).status_code
        == 422
    )


def test_library_existing_run_and_dataset_archive_does_not_remove_artifact(tmp_path: Path) -> None:
    report = SimulationService(tmp_path, code_revision="test").run(request())
    api = client(tmp_path)
    for kind, identity in (("runs", report.run_id), ("datasets", report.manifest.snapshot_id)):
        assert api.get(f"/research/library/{kind}").json()["total"] == 1
        assert (
            api.post(
                f"/research/library/{kind}/{identity}/archive", json={"archived": True}
            ).status_code
            == 200
        )
        assert api.get(f"/research/library/{kind}").json()["total"] == 0
        assert (
            api.post(
                f"/research/library/{kind}/{identity}/archive", json={"archived": False}
            ).status_code
            == 200
        )
    assert api.get(f"/simulations/{report.run_id}").status_code == 200


def test_partial_portfolio_withholds_correlations_and_total_curve(tmp_path: Path) -> None:
    api = client(tmp_path)
    good = request().model_dump(mode="json")
    missing = {**good, "source": "snapshot", "snapshot_id": "a" * 64}
    result = api.post(
        "/research/experiments/portfolio",
        json={
            "initial_cash": "1000",
            "components": [
                {"weight": "0.2", "request": missing},
                {"weight": "0.2", "request": good},
                {"weight": "0.2", "request": good},
            ],
        },
    )
    assert result.status_code == 201, result.text
    payload = result.json()
    assert payload["components"][0]["status"] == "failed"
    assert payload["components"][0]["run_id"] is None
    assert payload["components"][1]["status"] == "succeeded"
    assert payload["curve"] == []
    assert payload["correlations"] == []


def test_no_fill_metrics_have_explicit_null_reasons(tmp_path: Path) -> None:
    strategy = request().strategy.model_dump(mode="json")
    strategy["entry"]["condition"]["right"]["value"] = "1000000"
    base = SimulationRequest.model_validate(
        {**request().model_dump(mode="json"), "strategy": strategy}
    )
    stats = analyze(SimulationService(tmp_path, code_revision="test").run(base)).statistics
    for name in ("sharpe", "sortino", "win_rate", "profit_factor", "expectancy", "holding_seconds"):
        assert stats[name].value is None
        assert stats[name].reason
    assert stats["net_profit"].value == 0
    assert stats["exposure"].value == 0


def test_intraday_cagr_is_not_annualized_from_minutes(tmp_path: Path) -> None:
    strategy = request().strategy.model_dump(mode="json")
    strategy["timeframe"] = "1m"
    base = SimulationRequest.model_validate(
        {**request().model_dump(mode="json"), "strategy": strategy}
    )
    stats = analyze(SimulationService(tmp_path, code_revision="test").run(base)).statistics
    assert stats["cagr"].value is None
    assert stats["cagr"].reason
    assert stats["volatility"].value is None


def test_experiment_artifact_tamper_is_rejected(tmp_path: Path) -> None:
    api = client(tmp_path)
    result = api.post(
        "/research/experiments/grid",
        json={
            "base": request().model_dump(mode="json"),
            "axes": [{"path": "commission_bps", "values": [0]}],
        },
    ).json()
    path = tmp_path / "experiments" / f"{result['experiment_id']}.json"
    result["rows"][0]["total_return"] = "9999"
    path.write_text(json.dumps(result))
    assert api.get(f"/research/experiments/{result['experiment_id']}").status_code == 409


def test_grid_rejects_oversized_baseline_before_decoding_for_runs(tmp_path: Path) -> None:
    base = {
        **request().model_dump(mode="json"),
        "source": "snapshot",
        "snapshot_id": snapshot(tmp_path, [100] * 3001),
    }
    response = client(tmp_path).post(
        "/research/experiments/grid",
        json={"base": base, "axes": [{"path": "commission_bps", "values": [0]}]},
    )
    assert response.status_code == 422, response.text
    assert list((tmp_path / "runs").glob("*.json")) == []


def test_benchmark_rejects_oversized_separate_qqq(tmp_path: Path) -> None:
    report = SimulationService(tmp_path, code_revision="test").run(request())
    oversized = snapshot(tmp_path, [100] * 3001, "QQQ")
    response = client(tmp_path).post(
        "/research/benchmark", json={"run_id": report.run_id, "snapshot_id": oversized}
    )
    assert response.status_code == 422, response.text


def test_explicit_qqq_uses_its_prices_not_the_run_symbol(tmp_path: Path) -> None:
    base = request().model_copy(
        update={"source": "snapshot", "snapshot_id": snapshot(tmp_path, [100, 110, 120])}
    )
    report = SimulationService(tmp_path, code_revision="test").run(base)
    qqq = snapshot(tmp_path, [200, 100, 220], "QQQ")
    response = client(tmp_path).post(
        "/research/benchmark", json={"run_id": report.run_id, "snapshot_id": qqq}
    )
    assert response.status_code == 200, response.text
    benchmark = response.json()
    assert benchmark["snapshot_id"] == qqq
    assert benchmark["provider"] == "offline_fixture"
    assert Decimal(benchmark["benchmark_return"]) == Decimal("0.1")
    assert [Decimal(p["benchmark_value"]) for p in benchmark["points"]] == [1000, 500, 1100]
    assert benchmark["excluded_run_timestamps"] == 0
