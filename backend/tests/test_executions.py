import pytest
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationException
from app.models.execution import Execution, ExecutionStatus
from app.services.execution_service import validate_transition

from tests.test_projects import create_project


def create_execution(
    client: TestClient,
    project_id: str,
    *,
    authorization_confirmed: bool = True,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/projects/{project_id}/executions",
        json={
            "requirements": "Test login and product search.",
            "options": {"browser": "chromium", "capture_screenshots": True},
            "authorized_target_confirmation": authorization_confirmed,
        },
    )
    return response.json()


def test_create_execution_successfully(client: TestClient) -> None:
    project = create_project(client)

    response = client.post(
        f"/api/v1/projects/{project['id']}/executions",
        json={
            "requirements": "Test login and product search.",
            "options": {"browser": "chromium"},
            "authorized_target_confirmation": True,
        },
    )

    assert response.status_code == 201
    execution = response.json()
    assert execution["project_id"] == project["id"]
    assert execution["status"] == "QUEUED"
    assert execution["options"] == {"browser": "chromium"}
    assert execution["started_at"] is None
    assert execution["completed_at"] is None


def test_create_execution_for_nonexistent_project(client: TestClient) -> None:
    response = client.post(
        f"/api/v1/projects/{uuid4()}/executions",
        json={
            "requirements": "Test the home page.",
            "authorized_target_confirmation": True,
        },
    )

    assert response.status_code == 404


def test_reject_execution_for_archived_project(client: TestClient) -> None:
    project = create_project(client)
    client.delete(f"/api/v1/projects/{project['id']}")

    response = client.post(
        f"/api/v1/projects/{project['id']}/executions",
        json={
            "requirements": "Test the home page.",
            "authorized_target_confirmation": True,
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "project_archived"


def test_reject_execution_without_authorization(client: TestClient) -> None:
    project = create_project(client)

    response = client.post(
        f"/api/v1/projects/{project['id']}/executions",
        json={
            "requirements": "Test the home page.",
            "authorized_target_confirmation": False,
        },
    )

    assert response.status_code == 422


def test_get_execution_by_id(client: TestClient) -> None:
    project = create_project(client)
    created = create_execution(client, str(project["id"]))

    response = client.get(f"/api/v1/executions/{created['id']}")

    assert response.status_code == 200
    assert response.json()["id"] == created["id"]
    assert response.json()["status"] == "QUEUED"


def test_get_missing_execution_returns_404(client: TestClient) -> None:
    response = client.get(f"/api/v1/executions/{uuid4()}")

    assert response.status_code == 404


def test_list_executions_with_project_status_and_pagination(
    client: TestClient,
) -> None:
    project = create_project(client)
    create_execution(client, str(project["id"]))
    create_execution(client, str(project["id"]))

    response = client.get(
        "/api/v1/executions",
        params={
            "project_id": project["id"],
            "status": "QUEUED",
            "page": 2,
            "page_size": 1,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 2
    assert result["page"] == 2
    assert len(result["items"]) == 1


def test_list_executions_for_project_with_skip_limit(
    client: TestClient,
) -> None:
    project = create_project(client)
    other_project = create_project(client, name="Other Project")
    first = create_execution(client, str(project["id"]))
    second = create_execution(client, str(project["id"]))
    create_execution(client, str(other_project["id"]))

    response = client.get(
        f"/api/v1/projects/{project['id']}/executions?skip=1&limit=1"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 2
    assert result["skip"] == 1
    assert result["limit"] == 1
    assert len(result["items"]) == 1
    assert result["items"][0]["id"] in {first["id"], second["id"]}
    assert result["items"][0]["project_id"] == project["id"]


def test_list_executions_for_missing_project_returns_404(
    client: TestClient,
) -> None:
    response = client.get(f"/api/v1/projects/{uuid4()}/executions")

    assert response.status_code == 404


def test_invalid_execution_pagination_returns_422(
    client: TestClient,
) -> None:
    project = create_project(client)
    assert (
        client.get(f"/api/v1/projects/{project['id']}/executions?skip=-1")
        .status_code
        == 422
    )
    assert (
        client.get(f"/api/v1/projects/{project['id']}/executions?limit=101")
        .status_code
        == 422
    )


def test_cancel_queued_execution(client: TestClient) -> None:
    project = create_project(client)
    execution = create_execution(client, str(project["id"]))

    response = client.post(
        f"/api/v1/executions/{execution['id']}/cancel"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "CANCELLED"
    assert response.json()["completed_at"] is not None


def test_cancel_waiting_approval_execution(client: TestClient, db_session: Session) -> None:
    project = create_project(client)
    execution_data = create_execution(client, str(project["id"]))
    execution = db_session.get(Execution, UUID(str(execution_data["id"])))
    assert execution is not None
    execution.status = ExecutionStatus.WAITING_APPROVAL
    execution.qa_workflow_state = {
        "approval_status": "PENDING",
        "workflow_status": "WAITING_APPROVAL",
    }
    db_session.commit()

    response = client.post(
        f"/api/v1/executions/{execution_data['id']}/cancel"
    )

    assert response.status_code == 200
    db_session.refresh(execution)
    assert execution.status is ExecutionStatus.CANCELLED
    assert execution.qa_workflow_state["approval_status"] is None
    assert execution.qa_workflow_state["workflow_status"] == "CANCELLED"


@pytest.mark.parametrize(
    "non_cancellable_status",
    [
        ExecutionStatus.RUNNING,
        ExecutionStatus.COMPLETED,
        ExecutionStatus.FAILED,
        ExecutionStatus.CANCELLED,
    ],
)
def test_cancel_nonqueued_execution_returns_conflict(
    client: TestClient,
    db_session: Session,
    non_cancellable_status: ExecutionStatus,
) -> None:
    project = create_project(client)
    execution = create_execution(client, str(project["id"]))
    persisted_execution = db_session.get(
        Execution, UUID(str(execution["id"]))
    )
    assert persisted_execution is not None
    persisted_execution.status = non_cancellable_status
    db_session.commit()

    response = client.post(
        f"/api/v1/executions/{execution['id']}/cancel"
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_execution_transition"


def test_invalid_execution_transition_is_rejected() -> None:
    with pytest.raises(ApplicationException) as exc_info:
        validate_transition(ExecutionStatus.COMPLETED, ExecutionStatus.RUNNING)
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "invalid_execution_transition"
