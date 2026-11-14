from typing import Any

from fastapi.testclient import TestClient

from app.dependencies import get_browser_inspection_service
from app.main import app
from app.services.browser_inspection import BrowserInspectionFailure
from tests.test_projects import create_project


class FakeInspectionService:
    settings = type("SettingsStub", (), {"browser_execution_timeout_ms": 5000})()
    last_artifacts = [
        {
            "name": "screenshots/viewport.png",
            "media_type": "image/png",
            "size_bytes": 64,
        }
    ]

    def __init__(self, *, failure: bool = False) -> None:
        self.failure = failure

    async def inspect(self, _: Any, target_url: str) -> dict[str, Any]:
        assert target_url == "https://example.com/"
        if self.failure:
            raise BrowserInspectionFailure(
                "Browser navigation or inspection failed.",
                result={"error": "Browser navigation or inspection failed."},
                artifacts=self.last_artifacts,
            )
        return {
            "final_url": "https://example.com/final",
            "title": "Example page",
            "navigation_status": 200,
        }


def create_queued_execution(client: TestClient) -> dict[str, Any]:
    project = create_project(client)
    response = client.post(
        f"/api/v1/projects/{project['id']}/executions",
        json={
            "requirements": "Inspect the authorized page.",
            "authorized_target_confirmation": True,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_run_inspection_persists_results_and_prevents_duplicates(
    client: TestClient,
) -> None:
    execution = create_queued_execution(client)
    app.dependency_overrides[get_browser_inspection_service] = (
        lambda: FakeInspectionService()
    )
    try:
        response = client.post(
            f"/api/v1/executions/{execution['id']}/run"
        )
    finally:
        app.dependency_overrides.pop(get_browser_inspection_service, None)

    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "COMPLETED"
    assert result["duration_ms"] >= 0
    assert result["final_url"] == "https://example.com/final"
    assert result["result"]["navigation_status"] == 200

    duplicate = client.post(f"/api/v1/executions/{execution['id']}/run")
    assert duplicate.status_code == 409


def test_inspection_and_artifact_metadata_endpoints(
    client: TestClient,
) -> None:
    execution = create_queued_execution(client)
    app.dependency_overrides[get_browser_inspection_service] = (
        lambda: FakeInspectionService()
    )
    try:
        assert (
            client.post(f"/api/v1/executions/{execution['id']}/run").status_code
            == 200
        )
    finally:
        app.dependency_overrides.pop(get_browser_inspection_service, None)

    inspection = client.get(
        f"/api/v1/executions/{execution['id']}/inspection"
    )
    artifacts = client.get(
        f"/api/v1/executions/{execution['id']}/artifacts"
    )

    assert inspection.status_code == 200
    assert inspection.json()["result"]["title"] == "Example page"
    assert artifacts.status_code == 200
    assert artifacts.json()["items"][0]["name"] == "screenshots/viewport.png"
    assert "C:\\" not in artifacts.text


def test_failed_inspection_marks_execution_failed(client: TestClient) -> None:
    execution = create_queued_execution(client)
    app.dependency_overrides[get_browser_inspection_service] = (
        lambda: FakeInspectionService(failure=True)
    )
    try:
        response = client.post(
            f"/api/v1/executions/{execution['id']}/run"
        )
    finally:
        app.dependency_overrides.pop(get_browser_inspection_service, None)

    assert response.status_code == 502
    inspection = client.get(
        f"/api/v1/executions/{execution['id']}/inspection"
    )
    assert inspection.json()["status"] == "FAILED"
