from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from apps.api.app import create_app
from packages.application.research_analysis import analyze
from packages.application.research_experiment_models import PortfolioExperiment
from packages.application.research_outcomes import portfolio_analysis
from packages.application.simulations import SimulationService
from packages.shared.settings import Settings
from tests.research.test_accuracy import snapshot
from tests.research.test_features import client, request


def test_route_contracts_built_before_parallel_serving(tmp_path: Path) -> None:
    app = create_app(Settings(data_storage_path=tmp_path))
    assert app.openapi_schema is not None
    paths = app.openapi_schema["paths"]
    assert "/research/datasets/{identity}/bars" in paths
    assert "/research/experiments/{identity}/analysis" in paths
    assert "/paper/accounts/{identity}/orders/{order_id}/{action}" in paths


def test_verified_bar_pages_and_bounds(tmp_path: Path) -> None:
    report = SimulationService(tmp_path, code_revision="test").run(request())
    api = client(tmp_path)
    url = f"/research/datasets/{report.manifest.snapshot_id}/bars"
    response = api.get(url + "?page=2&page_size=25")
    assert response.status_code == 200
    page = response.json()
    assert page["total"] == 120
    assert len(page["items"]) == 25
    assert Decimal(page["items"][0]["close"]) == Decimal("115.2")
    assert "storage_uri" not in page
    assert api.get(url + "?page_size=1001").status_code == 422
    assert api.get("/research/datasets/bad/bars").status_code == 404


def test_preview_cap_before_decode(tmp_path: Path) -> None:
    identity = snapshot(tmp_path, [100] * 3001)
    with patch("packages.market_data.snapshots.pl.read_parquet") as decode:
        response = client(tmp_path).get(f"/research/datasets/{identity}/bars")
    assert response.status_code == 422
    decode.assert_not_called()


def test_payoff_uses_average_not_sum_and_null_missing_class(tmp_path: Path) -> None:
    report = SimulationService(tmp_path, code_revision="test").run(request())
    fill = report.result.fills[0]
    fills = []
    for i, price in enumerate([100, 120, 100, 110, 100, 90]):
        fills.append(
            fill.model_copy(
                update={
                    "side": "buy" if i % 2 == 0 else "sell",
                    "execution_price": Decimal(price),
                    "quantity": 1,
                    "commission": Decimal(0),
                    "tax": Decimal(0),
                }
            )
        )
    changed = report.model_copy(
        update={"result": report.result.model_copy(update={"fills": tuple(fills)})}
    )
    assert analyze(changed).statistics["payoff_ratio"].value == Decimal("1.5")
    stat = analyze(report).statistics["payoff_ratio"]
    assert stat.value is None
    assert stat.reason


def test_portfolio_summary_hand_calculated_and_incomplete(tmp_path: Path) -> None:
    api = client(tmp_path)
    experiment = api.post(
        "/research/experiments/portfolio",
        json={
            "initial_cash": "1000",
            "components": [
                {"weight": "0.25", "request": request().model_dump(mode="json")},
                {"weight": "0.5", "request": request().model_dump(mode="json")},
            ],
        },
    ).json()
    model = PortfolioExperiment.model_validate(experiment)
    model = model.model_copy(
        update={
            "curve": [
                model.curve[0].model_copy(update={"equity": Decimal(1100)}),
                model.curve[-1].model_copy(update={"equity": Decimal(990)}),
            ]
        }
    )
    stats = portfolio_analysis(model).statistics
    assert stats["net_profit"].value == -10
    assert stats["total_return"].value == Decimal("-0.01")
    assert stats["max_drawdown"].value == Decimal("0.1")
    incomplete = portfolio_analysis(model.model_copy(update={"curve": []})).statistics
    assert all(s.value is None and s.reason for s in incomplete.values())
    response = api.get(f"/research/experiments/{experiment['experiment_id']}/analysis")
    assert response.status_code == 200
    assert response.json()["statistics"]["initial_cash"]["value"] == "1000"
    assert api.get(f"/research/experiments/{experiment['experiment_id']}").json() == experiment
    failed = model.model_copy(
        update={
            "components": [
                model.components[0].model_copy(update={"status": "failed"}),
                *model.components[1:],
            ]
        }
    )
    assert all(s.value is None for s in portfolio_analysis(failed).statistics.values())
    missing = model.model_copy(update={"excluded_timestamps": {model.components[0].run_id: 1}})
    assert all(s.value is None for s in portfolio_analysis(missing).statistics.values())


def test_bar_preview_integrity_and_tick_precision(tmp_path: Path) -> None:
    api = client(tmp_path)
    payload = request().model_dump(mode="json")
    payload["strategy"]["timeframe"] = "tick"
    report = api.post("/simulations", json=payload).json()
    identity = report["manifest"]["snapshot_id"]
    bars = api.get(f"/research/datasets/{identity}/bars?page_size=1").json()
    assert bars["interval"] == "tick"
    assert bars["items"][0]["close"] == "100.0"
    path = (
        tmp_path
        / "published"
        / "normalized"
        / (report["manifest"]["normalized_checksum"].removeprefix("sha256:") + ".parquet")
    )
    path.write_bytes(b"corrupt")
    assert api.get(f"/research/datasets/{identity}/bars").status_code == 409
