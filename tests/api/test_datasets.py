from io import BytesIO
from pathlib import Path

import polars as pl
from fastapi.testclient import TestClient

from apps.api.app import create_app
from packages.application.datasets import DatasetSnapshotService
from packages.market_data.snapshots import FileSnapshotStore, SnapshotManifest
from packages.shared.settings import Settings

FIXTURES = Path(__file__).parents[1] / "fixtures" / "market_data"


def _client(
    tmp_path: Path,
    *,
    max_bytes: int = 10_000,
    max_rows: int = 1_000_000,
    max_columns: int = 32,
) -> TestClient:
    settings = Settings(
        data_storage_path=tmp_path,
        dataset_upload_max_bytes=max_bytes,
        dataset_upload_max_rows=max_rows,
        dataset_upload_max_columns=max_columns,
    )
    service = DatasetSnapshotService(FileSnapshotStore(tmp_path / "snapshots"))
    return TestClient(create_app(settings, dataset_service=service))


def _params() -> dict[str, str]:
    return {
        "instrument_id": "US:XNAS:AAPL",
        "symbol": "AAPL",
        "exchange": "XNAS",
        "currency": "USD",
        "timezone": "America/New_York",
        "start": "2024-01-02T00:00:00Z",
        "end": "2024-01-05T00:00:00Z",
        "price_adjustment": "raw",
        "volume_adjustment": "raw",
    }


def test_upload_creates_and_retrieves_immutable_snapshot(tmp_path: Path) -> None:
    # Given
    client = _client(tmp_path)

    # When
    created = client.post(
        "/datasets",
        params=_params(),
        content=(FIXTURES / "local_bars.csv").read_bytes(),
        headers={"Content-Type": "text/csv", "X-Filename": "bars.csv"},
    )
    snapshot_id = SnapshotManifest.model_validate(created.json()).snapshot_id
    retrieved = client.get(f"/dataset-snapshots/{snapshot_id}")

    # Then
    assert created.status_code == 201
    assert retrieved.status_code == 200
    assert retrieved.json() == created.json()
    assert retrieved.json()["validation_status"] == "valid_with_warnings"


def test_upload_rejects_path_traversal_and_unsupported_type(tmp_path: Path) -> None:
    # Given
    client = _client(tmp_path)

    # When
    traversal = client.post(
        "/datasets",
        params=_params(),
        content=b"content",
        headers={"Content-Type": "text/csv", "X-Filename": "../bars.csv"},
    )
    unsupported = client.post(
        "/datasets",
        params=_params(),
        content=b"content",
        headers={"Content-Type": "application/zip", "X-Filename": "bars.zip"},
    )
    oversized = client.post(
        "/datasets",
        params=_params(),
        content=b"x" * 10_001,
        headers={"Content-Type": "text/csv", "X-Filename": "bars.csv"},
    )
    mismatched = client.post(
        "/datasets",
        params=_params(),
        content=b"content",
        headers={"Content-Type": "text/csv", "X-Filename": "bars.parquet"},
    )

    # Then
    assert traversal.status_code == 400
    assert unsupported.status_code == 415
    assert oversized.status_code == 413
    assert mismatched.status_code == 415


def test_invalid_dataset_uses_dataset_invalid_error_contract(tmp_path: Path) -> None:
    # Given
    client = _client(tmp_path)
    payload = b"timestamp,open,high,low,close,volume\n2024-01-02T00:00:00-05:00,0,1,0,2,-1\n"

    # When
    response = client.post(
        "/datasets",
        params=_params(),
        content=payload,
        headers={"Content-Type": "text/csv", "X-Filename": "invalid.csv"},
    )

    # Then
    assert response.status_code == 422
    assert response.json()["code"] == "DATASET_INVALID"


def test_invalid_upload_schema_uses_dataset_invalid_error_contract(tmp_path: Path) -> None:
    # Given
    client = _client(tmp_path)
    payload = b"timestamp,open,high,low,close\n2024-01-02,1,2,1,2\n"

    # When
    response = client.post(
        "/datasets",
        params=_params(),
        content=payload,
        headers={"Content-Type": "text/csv", "X-Filename": "invalid.csv"},
    )

    # Then
    assert response.status_code == 422
    assert response.json()["code"] == "DATASET_INVALID"


def test_invalid_upload_does_not_persist_raw_artifacts(tmp_path: Path) -> None:
    client = _client(tmp_path)
    payload = b"timestamp,open,high,low,close\n2024-01-02,1,2,1,2\n"

    response = client.post(
        "/datasets",
        params=_params(),
        content=payload,
        headers={"Content-Type": "text/csv", "X-Filename": "invalid.csv"},
    )

    assert response.status_code == 422
    assert not any((tmp_path / "raw").rglob("*.payload"))


def test_parquet_upload_rejects_excess_rows_before_publication(tmp_path: Path) -> None:
    client = _client(tmp_path, max_rows=2)
    stream = BytesIO()
    pl.read_csv(FIXTURES / "local_bars.csv", infer_schema=False).write_parquet(stream)

    response = client.post(
        "/datasets",
        params=_params(),
        content=stream.getvalue(),
        headers={
            "Content-Type": "application/vnd.apache.parquet",
            "X-Filename": "bars.parquet",
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "DATASET_INVALID"
    assert not any((tmp_path / "raw").rglob("*.payload"))


def test_streamed_upload_stops_at_configured_body_limit(tmp_path: Path) -> None:
    client = _client(tmp_path, max_bytes=10)

    response = client.post(
        "/datasets",
        params=_params(),
        content=(chunk for chunk in (b"123456", b"78901")),
        headers={"Content-Type": "text/csv", "X-Filename": "bars.csv"},
    )

    assert response.status_code == 413
    assert not any((tmp_path / "uploads").rglob("*"))


def test_parquet_upload_rejects_invalid_file_signature(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.post(
        "/datasets",
        params=_params(),
        content=b"not parquet",
        headers={
            "Content-Type": "application/vnd.apache.parquet",
            "X-Filename": "bars.parquet",
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "DATASET_INVALID"


def test_parquet_upload_rejects_excess_columns_before_publication(tmp_path: Path) -> None:
    client = _client(tmp_path, max_columns=6)
    stream = BytesIO()
    frame = pl.read_csv(FIXTURES / "local_bars.csv", infer_schema=False).with_columns(
        pl.lit("ignored").alias("unexpected")
    )
    frame.write_parquet(stream)

    response = client.post(
        "/datasets",
        params=_params(),
        content=stream.getvalue(),
        headers={
            "Content-Type": "application/vnd.apache.parquet",
            "X-Filename": "bars.parquet",
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "DATASET_INVALID"
    assert not any((tmp_path / "raw").rglob("*.payload"))


def test_upload_rejects_rows_outside_requested_range(tmp_path: Path) -> None:
    client = _client(tmp_path)
    payload = (
        b"timestamp,open,high,low,close,volume\n"
        b"2024-01-01T00:00:00-05:00,100,101,99,100,10\n"
        b"2024-01-02T00:00:00-05:00,100,101,99,100,10\n"
    )

    response = client.post(
        "/datasets",
        params=_params(),
        content=payload,
        headers={"Content-Type": "text/csv", "X-Filename": "bars.csv"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "DATASET_INVALID"
    assert response.json()["details"]["issues"][0]["code"] == "outside_request_range"
