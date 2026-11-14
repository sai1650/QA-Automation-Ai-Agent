from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.execution import Execution
from tests.test_projects import create_project


def test_project_execution_persistence_and_archive_history(
    client: TestClient,
    db_session: Session,
) -> None:
    project = create_project(client, name="Integration Project")
    execution_response = client.post(
        f"/api/v1/projects/{project['id']}/executions",
        json={
            "requirements": "Verify persistence across requests.",
            "options": {"browser": "chromium"},
            "authorized_target_confirmation": True,
        },
    )
    assert execution_response.status_code == 201
    execution_id = execution_response.json()["id"]

    retrieved = client.get(f"/api/v1/executions/{execution_id}")
    assert retrieved.status_code == 200
    assert retrieved.json()["requirements"] == "Verify persistence across requests."

    persisted_execution = db_session.scalar(
        select(Execution).where(Execution.id == UUID(execution_id))
    )
    assert persisted_execution is not None
    assert str(persisted_execution.project_id) == project["id"]

    archived = client.delete(f"/api/v1/projects/{project['id']}")
    assert archived.status_code == 200
    assert archived.json()["is_active"] is False
    assert client.get(f"/api/v1/projects/{project['id']}").status_code == 404

    historical_execution = client.get(
        f"/api/v1/executions/{execution_id}"
    )
    assert historical_execution.status_code == 200
    assert historical_execution.json()["id"] == execution_id

    rejected_new_execution = client.post(
        f"/api/v1/projects/{project['id']}/executions",
        json={
            "requirements": "This must not be queued.",
            "authorized_target_confirmation": True,
        },
    )
    assert rejected_new_execution.status_code == 409
