from pydantic import SecretStr
from sqlalchemy.engine import make_url

from app.config import Settings


def test_mysql_settings_encode_reserved_credentials() -> None:
    settings = Settings(
        _env_file=None,
        db_user="qa@user",
        db_password=SecretStr("pass@word:/#"),
        db_host="localhost",
        db_port=3306,
        db_name="AI_AGENT",
    )

    url = settings.sqlalchemy_database_url
    parsed_url = make_url(url.render_as_string(hide_password=False))

    assert parsed_url.drivername == "mysql+pymysql"
    assert parsed_url.username == "qa@user"
    assert parsed_url.password == "pass@word:/#"
    assert parsed_url.host == "localhost"
    assert parsed_url.port == 3306
    assert parsed_url.database == "AI_AGENT"


def test_legacy_mysql_database_url_is_rebuilt() -> None:
    settings = Settings(
        _env_file=None,
        database_url=(
            "mysql+pymysql://legacy%40user:secret%40pass"
            "@localhost:3306/AI_AGENT?charset=utf8mb4"
        ),
    )

    url = settings.sqlalchemy_database_url

    assert url.username == "legacy@user"
    assert url.password == "secret@pass"
    assert url.query["charset"] == "utf8mb4"
