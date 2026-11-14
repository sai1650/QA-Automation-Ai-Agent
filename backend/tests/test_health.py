from fastapi.testclient import TestClient

from app.config import get_settings


def test_root_returns_success(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["application"] == get_settings().app_name


def test_health_returns_success(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_health_contains_application_name(client: TestClient) -> None:
    response = client.get("/health")

    assert response.json()["application"] == "Autonomous QA Intelligence Platform"


def test_api_documentation_is_accessible(client: TestClient) -> None:
    response = client.get("/docs")

    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower()


def test_invalid_route_returns_not_found(client: TestClient) -> None:
    response = client.get("/route-that-does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
