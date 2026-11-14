from collections.abc import Generator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.database.session as database_session
from app.database.session import create_database_engine
from app.models import Execution, ExecutionStatus, Project

BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_engine_initializes_for_sqlite() -> None:
    test_engine = create_database_engine("sqlite://")
    try:
        assert test_engine.dialect.name == "sqlite"
        with test_engine.connect():
            pass
    finally:
        test_engine.dispose()


def test_migration_creates_expected_tables(migrated_engine: Engine) -> None:
    database_inspector = inspect(migrated_engine)
    table_names = set(database_inspector.get_table_names())

    assert {"alembic_version", "projects", "executions"} <= table_names
    status_constraints = database_inspector.get_check_constraints("executions")
    assert any(
        constraint["name"] == "ck_executions_execution_status"
        for constraint in status_constraints
    )


def test_migration_can_downgrade_and_upgrade_again(
    migrated_engine: Engine,
) -> None:
    project = Project(name="Preserved project", base_url="https://example.com")
    execution = Execution(
        project=project,
        status=ExecutionStatus.QUEUED,
        requirements="Preserve this legacy row.",
    )
    with Session(migrated_engine) as session:
        session.add(execution)
        session.commit()
        execution_id = execution.id

    database_url = migrated_engine.url.render_as_string(hide_password=False)
    alembic_config = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_config.set_main_option(
        "sqlalchemy.url", database_url.replace("%", "%%")
    )

    migrated_engine.dispose()
    command.downgrade(alembic_config, "20261109_0001")
    downgraded_engine = create_database_engine(database_url)
    try:
        downgraded_inspector = inspect(downgraded_engine)
        assert {"alembic_version", "projects", "executions"} <= set(
            downgraded_inspector.get_table_names()
        )
        columns = {
            column["name"]
            for column in downgraded_inspector.get_columns("executions")
        }
        assert "inspection_result" not in columns
        assert "qa_workflow_state" not in columns
        with downgraded_engine.connect() as connection:
            preserved_requirements = connection.execute(
                text("SELECT requirements FROM executions WHERE id = :id"),
                {"id": execution_id.hex},
            ).scalar_one()
            assert preserved_requirements == "Preserve this legacy row."
    finally:
        downgraded_engine.dispose()

    command.upgrade(alembic_config, "head")
    upgraded_engine = create_database_engine(database_url)
    try:
        table_names = set(inspect(upgraded_engine).get_table_names())
        assert {"projects", "executions"} <= table_names
        columns = {
            column["name"]
            for column in inspect(upgraded_engine).get_columns("executions")
        }
        assert {
            "duration_ms",
            "final_url",
            "inspection_result",
            "artifact_metadata",
            "qa_workflow_state",
            "qa_report",
        } <= columns
        with Session(upgraded_engine) as session:
            preserved = session.get(Execution, execution_id)
            assert preserved is not None
            assert preserved.requirements == "Preserve this legacy row."
    finally:
        upgraded_engine.dispose()


def test_project_and_execution_persist_with_relationship(
    migrated_engine: Engine,
) -> None:
    project = Project(name="Example", base_url="https://example.com")
    execution = Execution(
        project=project,
        status=ExecutionStatus.QUEUED,
        requirements="Check the home page.",
        options={"include_links": True},
    )

    with Session(migrated_engine) as session:
        session.add(execution)
        session.commit()
        project_id = project.id
        execution_id = execution.id
        session.expunge_all()

        persisted_execution = session.get(Execution, execution_id)
        assert persisted_execution is not None
        assert persisted_execution.project_id == project_id
        assert persisted_execution.project.name == "Example"
        assert persisted_execution.options == {"include_links": True}

        persisted_project = session.scalar(
            select(Project).where(Project.id == project_id)
        )
        assert persisted_project is not None
        assert persisted_project.executions[0].id == execution_id


def test_execution_requires_existing_project(migrated_engine: Engine) -> None:
    execution = Execution(
        project_id=uuid4(),
        status=ExecutionStatus.QUEUED,
        requirements="Check the home page.",
    )
    with Session(migrated_engine) as session:
        session.add(execution)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


def test_session_dependency_closes_after_consumption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed: list[bool] = []

    class TrackedSession:
        def close(self) -> None:
            closed.append(True)

    monkeypatch.setattr(database_session, "SessionLocal", TrackedSession)
    dependency: Generator[Session, None, None] = database_session.get_db()

    next(dependency)
    dependency.close()

    assert closed == [True]
