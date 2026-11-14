from sqlalchemy import Engine

from app.database.session import engine
from app.models import Base


def initialize_database(bind: Engine = engine) -> None:
    """Create missing tables for disposable development/test databases only.

    Use Alembic migrations to manage schema changes in shared or production
    databases. This function never drops or recreates existing tables.
    """
    Base.metadata.create_all(bind=bind)
