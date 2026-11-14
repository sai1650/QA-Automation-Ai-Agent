from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKeyConstraint

from app.models import Base, Execution, ExecutionStatus, Project


def test_project_execution_models_are_registered() -> None:
    assert {"projects", "executions"} <= set(Base.metadata.tables)


def test_model_keys_and_relationships() -> None:
    project = Project(
        id=UUID("00000000-0000-4000-8000-000000000001"),
        name="Example",
        base_url="https://example.com",
    )
    execution = Execution(
        id=UUID("00000000-0000-4000-8000-000000000002"),
        project=project,
        status=ExecutionStatus.QUEUED,
        requirements="Check the home page.",
    )

    assert isinstance(project.id, UUID)
    assert isinstance(execution.id, UUID)
    assert execution.project is project
    assert project.executions == [execution]


def test_execution_foreign_key_and_status_constraint_exist() -> None:
    table = Base.metadata.tables["executions"]

    assert any(
        isinstance(constraint, ForeignKeyConstraint)
        for constraint in table.constraints
    )
    assert any(
        isinstance(constraint, CheckConstraint)
        for constraint in table.constraints
    )
