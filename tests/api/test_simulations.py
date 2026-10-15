from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.shared.settings import Settings
from tests.application.test_simulations import definition


def test_demo_api_persists_and_retrieves_real_result(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_storage_path=tmp_path)))
    response = client.post(
        "/simulations",
        json={
            "source": "demo",
            "symbol": "AAPL",
            "strategy": definition().model_dump(mode="json"),
            "initial_cash": "1000",
        },
    )
    assert response.status_code == 201, response.text
    report = response.json()
    assert report["result"]["status"] == "succeeded"
    assert client.get(f"/simulations/{report['run_id']}").json() == report
    assert client.get("/simulations/not-found").status_code == 404
    assert len(client.get("/research/catalog").json()["symbols"]) >= 3


def test_invalid_simulation_has_safe_error_and_body_limit(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_storage_path=tmp_path)))
    response = client.post(
        "/simulations",
        json={
            "source": "demo",
            "symbol": "MSFT",
            "strategy": definition().model_dump(mode="json"),
            "initial_cash": "1000",
        },
    )
    assert response.status_code == 422
    assert client.post("/simulations", content=b" " * 100000).status_code == 413


def test_intraday_five_minute_demo(tmp_path: Path) -> None:
    client = TestClient(create_app(Settings(data_storage_path=tmp_path)))
    response = client.post(
        "/simulations",
        json={
            "source": "demo",
            "symbol": "AAPL",
            "strategy": definition("5m").model_dump(mode="json"),
            "initial_cash": "1000",
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["manifest"]["interval"] == "5m"
