import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.application.simulation_models import SimulationRequest
from packages.application.simulations import SimulationService
from packages.shared.settings import Settings
from tests.application.test_simulations import definition


def request() -> SimulationRequest:
    return SimulationRequest(
        source="demo", symbol="AAPL", strategy=definition(), initial_cash=Decimal(1000)
    )


def client(root: Path) -> TestClient:
    return TestClient(create_app(Settings(data_storage_path=root)))


def test_library_immutable_archive_search_and_pagination(tmp_path: Path) -> None:
    api = client(tmp_path)
    body = {"definition": definition().model_dump(mode="json"), "tags": ["demo"]}
    saved = api.post("/research/library/strategies", json=body)
    assert saved.status_code == 201, saved.text
    record = saved.json()
    assert record["version_id"].startswith("sha256:")
    assert len(record["strategy_id"]) == 64
    original = api.get(f"/research/library/strategies/{record['strategy_id']}").json()
    page = api.get("/research/library/strategies?q=demo&page_size=1").json()
    assert page["total"] == 1
    assert page["items"][0] == original
    assert api.get("/research/library/strategies?page=2&page_size=1").json()["items"] == []
    url = f"/research/library/strategies/{record['strategy_id']}/archive"
    assert api.post(url, json={"archived": True}).status_code == 200
    assert api.get("/research/library/strategies").json()["total"] == 0
    assert api.get("/research/library/strategies?archived=true").json()["total"] == 1
    assert api.get(f"/research/library/strategies/{record['strategy_id']}").json() == original
    assert api.get("/research/library/strategies/bad").status_code == 404
    assert api.get("/research/library/runs?page_size=101").status_code == 422


def test_legacy_hash_verified_before_injecting_defaults(tmp_path: Path) -> None:
    service = SimulationService(tmp_path, code_revision="test")
    report = service.run(request())
    payload = report.model_dump(mode="json")
    del payload["config"]["bar_interval"]
    payload.pop("run_id")
    run_id = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    payload["run_id"] = run_id
    path = tmp_path / "runs" / f"{run_id}.json"
    path.write_text(json.dumps(payload))
    loaded = service.get(run_id)
    assert loaded is not None
    assert loaded.config.bar_interval == "1d"
    payload["metrics"]["net_profit"] = "999"
    path.write_text(json.dumps(payload))
    with pytest.raises(ValueError, match="무결성"):
        service.get(run_id)


def test_analysis_csv_compare_and_real_separate_benchmark(tmp_path: Path) -> None:
    service = SimulationService(tmp_path, code_revision="test")
    first = service.run(request())
    second = service.run(request().model_copy(update={"commission_bps": Decimal(10)}))
    api = client(tmp_path)
    response = api.get(f"/research/runs/{first.run_id}/analysis")
    assert response.status_code == 200, response.text
    analysis = response.json()
    assert Decimal(analysis["statistics"]["net_profit"]["value"]) == first.metrics.net_profit
    assert analysis["statistics"]["win_rate"]["value"] is None
    assert analysis["statistics"]["win_rate"]["reason"]
    assert len(analysis["daily_returns"]) == 120
    assert len(analysis["drawdown"]) == 120
    assert analysis["round_trips"] == []
    for kind in ("fills", "equity", "orders"):
        export = api.get(f"/research/runs/{first.run_id}/export.csv?kind={kind}")
        assert export.status_code == 200
        assert export.headers["content-type"].startswith("text/csv")
        assert len(export.text.splitlines()) >= 2
    comparison = api.post("/research/compare", json={"run_ids": [first.run_id, second.run_id]})
    assert comparison.status_code == 200, comparison.text
    assert comparison.json()["comparable"] is True
    benchmark = api.post("/research/benchmark", json={"run_id": first.run_id})
    assert benchmark.status_code == 200, benchmark.text
    data = benchmark.json()
    assert data["benchmark_symbol"] == "QQQ"
    assert data["snapshot_id"] != first.manifest.snapshot_id
    assert data["provider"] == "synthetic_demo"
    assert len(data["points"]) == 120
    assert data["warnings"]


def test_grid_freezes_snapshot_and_persists_real_runs(tmp_path: Path) -> None:
    api = client(tmp_path)
    response = api.post(
        "/research/experiments/grid",
        json={
            "base": request().model_dump(mode="json"),
            "axes": [
                {"path": "commission_bps", "values": [0, 10]},
                {"path": "strategy.position_sizing.quantity", "values": [1, 2]},
            ],
        },
    )
    assert response.status_code == 201, response.text
    experiment = response.json()
    assert len(experiment["rows"]) == 4
    service = SimulationService(tmp_path, code_revision="test")
    for row in experiment["rows"]:
        assert row["status"] == "succeeded"
        run = service.get(row["run_id"])
        assert run is not None
        assert run.manifest.snapshot_id == experiment["baseline_snapshot_id"]
    assert api.get(f"/research/experiments/{experiment['experiment_id']}").json() == experiment
    for path in ("strategy.name", "strategy.entry.condition.left.shift", "initial_cash"):
        invalid = api.post(
            "/research/experiments/grid",
            json={
                "base": request().model_dump(mode="json"),
                "axes": [{"path": path, "values": [1, 2]}],
            },
        )
        assert invalid.status_code == 422, invalid.text


def test_walk_forward_test_capital_and_warmup_exclude_training(tmp_path: Path) -> None:
    api = client(tmp_path)
    response = api.post(
        "/research/experiments/walk-forward",
        json={
            "base": request().model_dump(mode="json"),
            "train_bars": 30,
            "test_bars": 10,
            "folds": 2,
            "axes": [{"path": "commission_bps", "values": [0, 10]}],
        },
    )
    assert response.status_code == 201, response.text
    result = response.json()
    assert len(result["folds"]) == 2
    service = SimulationService(tmp_path, code_revision="test")
    for fold in result["folds"]:
        assert fold["train_end"] < fold["test_start"]
        assert len(fold["train_run_ids"]) == 2
        run = service.get(fold["test_run_id"])
        assert run is not None
        assert len(run.result.portfolio) == 10
        assert run.result.summary.initial_cash == Decimal(1000)
        assert run.result.portfolio[0].equity == Decimal(1000)
        assert all(p.timestamp.isoformat() >= fold["test_start"] for p in run.result.portfolio)
        assert all(f.timestamp.isoformat() > fold["test_start"] for f in run.result.fills)
        assert run.result.benchmark[0].value == Decimal(1000)


def test_fixed_budget_portfolio_cash_reserve_and_correlation(tmp_path: Path) -> None:
    api = client(tmp_path)
    body = {
        "initial_cash": "1000",
        "components": [
            {"weight": "0.25", "request": request().model_dump(mode="json")},
            {"weight": "0.5", "request": request().model_dump(mode="json")},
        ],
    }
    response = api.post("/research/experiments/portfolio", json=body)
    assert response.status_code == 201, response.text
    result = response.json()
    assert Decimal(result["reserve_cash"]) == Decimal(250)
    assert [Decimal(c["budget"]) for c in result["components"]] == [Decimal(250), Decimal(500)]
    assert Decimal(result["curve"][0]["equity"]) == Decimal(1000)
    assert result["correlations"][0]["value"] is not None
    assert any("demo" in w for w in result["warnings"])
    invalid = {
        "initial_cash": "1000",
        "components": [
            {"weight": "0.75", "request": request().model_dump(mode="json")},
            {"weight": "0.5", "request": request().model_dump(mode="json")},
        ],
    }
    assert api.post("/research/experiments/portfolio", json=invalid).status_code == 422
