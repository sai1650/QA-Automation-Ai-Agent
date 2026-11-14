from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.database.session import create_database_engine
from app.main import app
from app.database.session import get_db

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture
def migrated_engine(tmp_path: Path) -> Iterator[Engine]:
    database_path = tmp_path / "phase1_test.db"
    database_url = URL.create(
        "sqlite",
        database=str(database_path),
    ).render_as_string(hide_password=False)
    alembic_config = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_config.set_main_option(
        "sqlalchemy.url", database_url.replace("%", "%%")
    )
    command.upgrade(alembic_config, "head")
    command.check(alembic_config)

    test_engine = create_database_engine(database_url)
    try:
        yield test_engine
    finally:
        test_engine.dispose()


@pytest.fixture
def db_session(migrated_engine: Engine) -> Iterator[Session]:
    session_factory = sessionmaker(
        bind=migrated_engine,
        autoflush=False,
        expire_on_commit=False,
    )
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)
