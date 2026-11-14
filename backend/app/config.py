from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    app_name: str = "Autonomous QA Intelligence Platform"
    app_version: str = "0.1.0"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"

    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:3b"
    llm_provider: str = "ollama"
    llm_timeout_seconds: int = Field(default=120, ge=1, le=300)
    llm_max_prompt_chars: int = Field(default=16000, ge=1000, le=50000)
    rag_enabled: bool = True
    rag_embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    rag_embedding_device: str = "cpu"
    rag_chunk_size: int = Field(default=800, ge=100, le=4000)
    rag_chunk_overlap: int = Field(default=120, ge=0, le=1000)
    rag_max_chunks_per_document: int = Field(default=100, ge=1, le=500)
    rag_top_k: int = Field(default=5, ge=1, le=20)
    rag_min_relevance_score: float = Field(default=0.35, ge=0, le=1)
    rag_max_document_chars: int = Field(default=100000, ge=100, le=500000)
    rag_max_context_chars: int = Field(default=6000, ge=500, le=20000)
    chroma_persist_directory: str = "./storage/chroma"
    chroma_collection_name: str = "qa_historical_knowledge"
    database_url: str = "sqlite:///./qa_agent.db"
    db_user: str | None = None
    db_password: SecretStr | None = None
    db_host: str | None = None
    db_port: int | None = None
    db_name: str | None = None

    log_level: str = "INFO"
    artifact_dir: str = "../artifacts"
    browser_headless: bool = True
    browser_navigation_timeout_ms: int = 30000
    browser_action_timeout_ms: int = 10000
    browser_execution_timeout_ms: int = 60000
    browser_max_elements: int = 250
    browser_max_events: int = 200
    browser_max_screenshot_bytes: int = 8_000_000
    browser_max_page_pixels: int = 20_000_000
    browser_max_concurrent_executions: int = 2
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173"
    )

    @model_validator(mode="after")
    def rag_chunking_settings_are_consistent(self) -> "Settings":
        if self.rag_chunk_overlap >= self.rag_chunk_size:
            raise ValueError("RAG_CHUNK_OVERLAP must be smaller than RAG_CHUNK_SIZE.")
        return self

    @staticmethod
    def _is_placeholder_value(value: str | None) -> bool:
        if value is None:
            return True
        normalized = value.strip().lower()
        return (
            normalized in {"", "root", "your_mysql_user", "your_mysql_password", "change_me", "changeme"}
            or normalized.startswith("your_mysql_")
            or normalized.startswith("change_")
        )

    @property
    def sqlalchemy_database_url(self) -> URL:
        mysql_settings = (
            self.db_user,
            self.db_password,
            self.db_host,
            self.db_port,
            self.db_name,
        )
        if any(value is not None for value in mysql_settings):
            if (
                self.db_user is None
                or self.db_password is None
                or self.db_host is None
                or self.db_port is None
                or self.db_name is None
            ):
                raise ValueError(
                    "DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, and DB_NAME "
                    "must all be configured together."
                )

            password = self.db_password.get_secret_value()
            if (
                self._is_placeholder_value(self.db_user)
                or self._is_placeholder_value(password)
                or self._is_placeholder_value(self.db_host)
                or self._is_placeholder_value(self.db_name)
            ):
                raise ValueError(
                    "DB_USER, DB_PASSWORD, DB_HOST, and DB_NAME must be set to a valid MySQL application account. "
                    "Do not use root or placeholder values."
                )

            return URL.create(
                drivername="mysql+pymysql",
                username=self.db_user,
                password=password,
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                query={"charset": "utf8mb4"},
            )

        legacy_url = make_url(self.database_url)
        if legacy_url.get_backend_name() == "mysql":
            return URL.create(
                drivername=legacy_url.drivername,
                username=legacy_url.username,
                password=legacy_url.password,
                host=legacy_url.host,
                port=legacy_url.port,
                database=legacy_url.database,
                query=legacy_url.query,
            )
        return legacy_url

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_origins.split(",")
            if origin.strip()
        ]

    @property
    def artifact_root(self) -> Path:
        configured_path = Path(self.artifact_dir)
        if configured_path.is_absolute():
            return configured_path.resolve()
        return (BACKEND_DIR / configured_path).resolve()

    @property
    def chroma_persist_path(self) -> Path:
        configured_path = Path(self.chroma_persist_directory)
        if configured_path.is_absolute():
            return configured_path.resolve()
        return (BACKEND_DIR / configured_path).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
