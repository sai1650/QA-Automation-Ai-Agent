import os
import sys

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import get_settings
from app.database.session import engine


def main() -> int:
    settings = get_settings()
    url = settings.sqlalchemy_database_url
    override_names = [
        name
        for name in (
            "DATABASE_URL",
            "DB_USER",
            "DB_PASSWORD",
            "DB_HOST",
            "DB_PORT",
            "DB_NAME",
        )
        if name in os.environ
    ]
    password = (
        settings.db_password.get_secret_value()
        if settings.db_password is not None
        else None
    )

    print(f"Host: {url.host or '(local)'}")
    print(f"Port: {url.port or '(default)'}")
    print(f"Username: {url.username or '(not configured)'}")
    print(f"Database: {url.database or '(not configured)'}")
    print(f"Password configured: {'yes' if password else 'no'}")
    print(
        "Password is still a placeholder: "
        f"{'yes' if password in {'YOUR_MYSQL_PASSWORD', 'your_mysql_password'} else 'no'}"
    )
    print(
        "Process environment overrides: "
        f"{', '.join(override_names) if override_names else 'none'}"
    )

    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar_one()
    except SQLAlchemyError as error:
        original_error = getattr(error, "orig", None)
        error_code = (
            original_error.args[0]
            if getattr(original_error, "args", None)
            else "unavailable"
        )
        print(f"Connection: failed (database driver error {error_code})")
        print("Password value was not displayed.")
        return 1

    if result != 1:
        print("Connection: failed (SELECT 1 returned an unexpected result)")
        return 1

    print("Connection: successful")
    print("SELECT 1: 1")
    return 0


if __name__ == "__main__":
    sys.exit(main())
