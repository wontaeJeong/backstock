import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from apps.api.app import create_app
from packages.application.simulation_models import SimulationRequest
from packages.application.simulations import SimulationService
from packages.domain.market_data import BarRequest
from packages.shared.settings import Settings
from tests.application.test_simulations import definition
from tests.research.test_tick_provider_features import tick_request


def test_catalog_search_is_current_limited_and_new_symbols_run(tmp_path: Path) -> None:
    api = TestClient(create_app(Settings(data_storage_path=tmp_path)))
    catalog = api.get("/research/catalog?q=Tesla").json()
    assert catalog["listing_scope"] == "curated_current_not_point_in_time"
    assert catalog["symbols"] == ["TSLA"]
    assert catalog["remote_intervals"] == ["1d", "1m", "5m"]
    assert "tick" in catalog["intervals"]
    strategy = definition().model_dump(mode="json")
    strategy["universe"] = ["NASDAQ:TSLA"]
    report = api.post(
        "/simulations",
        json={"source": "demo", "symbol": "TSLA", "strategy": strategy, "initial_cash": "1000"},
    )
    assert report.status_code == 201, report.text


def test_new_defaults_read_legacy_raw_hash_and_current_json_fidelity(tmp_path: Path) -> None:
    service = SimulationService(tmp_path, code_revision="test")
    report = service.run(
        SimulationRequest(
            source="demo", symbol="AAPL", strategy=definition(), initial_cash=Decimal(1000)
        )
    )
    payload = report.model_dump(mode="json")
    for fields in (payload["request"], payload["config"]):
        for field in ("spread_bps", "latency_ms", "volume_participation"):
            fields.pop(field)
    payload["request"]["strategy"].pop("session")
    payload["request"]["strategy"]["order"].pop("stop_offset_bps")
    payload["result"]["summary"].pop("spread")
    for fill in payload["result"]["fills"]:
        fill.pop("spread")
    for order in payload["result"]["orders"]:
        order.pop("triggered_at")
        order["intent"].pop("stop_price")
    for event in payload["result"]["events"]:
        event.pop("spread")
    payload.pop("run_id")
    identity = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    payload["run_id"] = identity
    (tmp_path / "runs" / f"{identity}.json").write_text(json.dumps(payload))
    loaded = service.get(identity)
    assert loaded is not None
    assert loaded.request.volume_participation is None
    assert loaded.config.spread_bps == 0
    assert loaded.result.summary.spread == 0
    assert service.get(report.run_id) == report


def test_execution_fields_survive_all_experiment_request_copies(tmp_path: Path) -> None:
    api = TestClient(create_app(Settings(data_storage_path=tmp_path)))
    base = {
        "source": "demo",
        "symbol": "AAPL",
        "strategy": definition("1m").model_dump(mode="json"),
        "initial_cash": "1000",
        "spread_bps": "10",
        "latency_ms": 1,
        "volume_participation": "0.1",
    }
    grid = api.post(
        "/research/experiments/grid",
        json={"base": base, "axes": [{"path": "spread_bps", "values": [0, 10]}]},
    )
    assert grid.status_code == 201, grid.text
    walk = api.post(
        "/research/experiments/walk-forward",
        json={
            "base": base,
            "axes": [{"path": "latency_ms", "values": [0, 1]}],
            "train_bars": 20,
            "test_bars": 10,
            "folds": 1,
        },
    )
    assert walk.status_code == 201, walk.text
    portfolio = api.post(
        "/research/experiments/portfolio",
        json={
            "initial_cash": "2000",
            "components": [{"request": base, "weight": "0.5"}, {"request": base, "weight": "0.5"}],
        },
    )
    assert portfolio.status_code == 201, portfolio.text
    ids = [row["run_id"] for row in grid.json()["rows"]]
    ids += [walk.json()["folds"][0]["test_run_id"]]
    ids += [c["run_id"] for c in portfolio.json()["components"]]
    for identity in ids:
        report = api.get(f"/simulations/{identity}").json()
        assert report["config"]["volume_participation"] == "0.1"
        assert report["config"]["spread_bps"] == report["request"]["spread_bps"]
        assert report["config"]["latency_ms"] == report["request"]["latency_ms"]


def test_tick_upload_to_quote_fill_and_analysis_csv(tmp_path: Path) -> None:
    api = TestClient(create_app(Settings(data_storage_path=tmp_path)))
    response = api.post(
        "/datasets",
        params={
            "instrument_id": "NASDAQ:AAPL",
            "symbol": "AAPL",
            "exchange": "NASDAQ",
            "currency": "USD",
            "timezone": "America/New_York",
            "start": "2024-01-02T09:30:00-05:00",
            "end": "2024-01-02T09:31:00-05:00",
            "price_adjustment": "raw",
            "volume_adjustment": "raw",
            "interval": "tick",
        },
        headers={"Content-Type": "text/csv", "X-Filename": "ticks.csv"},
        content=(
            "timestamp,price,size,bid,ask\n2024-01-02T09:30:00-05:00,100,5,99,101\n"
            "2024-01-02T09:30:01-05:00,100,5,99,101\n"
        ),
    )
    assert response.status_code == 201, response.text
    response = api.post(
        "/simulations",
        json={
            "source": "snapshot",
            "symbol": "AAPL",
            "snapshot_id": response.json()["snapshot_id"],
            "strategy": definition("tick").model_dump(mode="json"),
            "initial_cash": "1000",
            "spread_bps": "100",
            "slippage_bps": "10",
            "commission_bps": "0",
        },
    )
    assert response.status_code == 201, response.text
    report = response.json()
    fill = report["result"]["fills"][0]
    assert Decimal(fill["execution_price"]) == Decimal("101.101")
    assert Decimal(fill["spread"]) == 2
    assert Decimal(fill["slippage"]) == Decimal("0.202")
    analysis = api.get(f"/research/runs/{report['run_id']}/analysis").json()
    assert Decimal(analysis["statistics"]["spread"]["value"]) == 2
    csv = api.get(f"/research/runs/{report['run_id']}/export.csv?kind=fills").text
    assert csv.splitlines()[0].endswith(",slippage,spread")


def test_tick_request_cannot_claim_adjusted_prices() -> None:
    with pytest.raises(ValidationError, match="raw"):
        BarRequest.model_validate(
            {**tick_request().model_dump(), "adjustment": "total_return_adjusted"}
        )
