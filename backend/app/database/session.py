from collections.abc import Generator
from sqlite3 import Connection as SQLiteConnection

from sqlalchemy import Engine, URL, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def create_database_engine(database_url: str | URL) -> Engine:
    url = make_url(database_url) if isinstance(database_url, str) else database_url
    connect_args = (
        {"check_same_thread": False}
        if url.get_backend_name() == "sqlite"
        else {}
    )
    database_engine = create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
    )

    if url.get_backend_name() == "sqlite":

        @event.listens_for(database_engine, "connect")
        def enable_sqlite_foreign_keys(
            dbapi_connection: SQLiteConnection,
            _: object,
        ) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return database_engine


engine = create_database_engine(get_settings().sqlalchemy_database_url)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
