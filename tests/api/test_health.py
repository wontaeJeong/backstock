from fastapi.testclient import TestClient

from apps.api.app import create_app


def test_live_endpoint_reports_process_health() -> None:
    # Given
    client = TestClient(create_app())

    # When
    response = client.get("/health/live")

    # Then
    assert response.status_code == 200
    assert response.json() == {"status": "live"}


def test_ready_endpoint_reports_configuration_health() -> None:
    # Given
    client = TestClient(create_app())

    # When
    response = client.get("/health/ready")

    # Then
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_request_id_is_returned_and_propagated() -> None:
    # Given
    client = TestClient(create_app())

    # When
    response = client.get("/health/live", headers={"X-Request-ID": "test-request-42"})

    # Then
    assert response.headers["X-Request-ID"] == "test-request-42"


def test_unknown_route_uses_common_error_contract() -> None:
    # Given
    client = TestClient(create_app())

    # When
    response = client.get("/missing", headers={"X-Request-ID": "missing-request"})

    # Then
    assert response.status_code == 404
    assert response.json() == {
        "code": "NOT_FOUND",
        "message": "Resource not found",
        "details": {},
        "request_id": "missing-request",
    }
