from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.application.datasets import DatasetSnapshotService
from packages.market_data.snapshots import FileSnapshotStore
from packages.shared.settings import Settings
from packages.strategy.templates import moving_average_crossover


def _client(tmp_path: Path) -> TestClient:
    settings = Settings(data_storage_path=tmp_path)
    service = DatasetSnapshotService(FileSnapshotStore(tmp_path / "snapshots"))
    return TestClient(create_app(settings, dataset_service=service))


def test_validate_accepts_a_well_formed_strategy(tmp_path: Path) -> None:
    client = _client(tmp_path)
    payload = moving_average_crossover(("KRX:005930",)).model_dump(mode="json")

    response = client.post("/strategies/validate", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["version_id"].startswith("sha256:")
    assert body["definition"]["name"] == "moving-average-crossover"


def test_validate_rejects_a_malformed_strategy(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/strategies/validate",
        json={"name": "missing-required-fields", "universe": ["AAA"]},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "STRATEGY_INVALID"
    assert body["details"]["issues"]


def test_metadata_lists_operators_indicators_schema_and_templates(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/strategies/metadata")

    assert response.status_code == 200
    body = response.json()
    operator_names = {item["name"] for item in body["operators"]}
    indicator_names = {item["name"] for item in body["indicators"]}
    assert "crosses_above" in operator_names
    assert "rsi" in indicator_names
    assert "properties" in body["json_schema"]
    assert set(body["templates"]) == {
        "moving_average_crossover",
        "mean_reversion",
        "volatility_breakout",
        "calendar_rebalancing",
    }
