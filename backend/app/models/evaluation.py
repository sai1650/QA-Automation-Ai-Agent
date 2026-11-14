from datetime import datetime
from typing import Any
from sqlalchemy import Boolean, DateTime, Float, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPrimaryKeyMixin, utc_now


class EvaluationExperiment(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "evaluation_experiments"
    __table_args__ = (
        Index("ix_evaluation_experiments_created_at", "created_at"),
        Index(
            "ix_evaluation_experiments_dataset_created",
            "dataset_id",
            "created_at",
        ),
        Index("ix_evaluation_experiments_agent_created", "agent_name", "created_at"),
    )

    experiment_name: Mapped[str] = mapped_column(String(160), nullable=False)
    dataset_id: Mapped[str] = mapped_column(String(64), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(32), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(40), nullable=False)
    provider_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_name: Mapped[str] = mapped_column(String(40), nullable=False)
    model_identifier: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(80), nullable=False)
    rag_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    configuration: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    sample_results: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    total_samples: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_samples: Mapped[int] = mapped_column(Integer, nullable=False)
    failed_samples: Mapped[int] = mapped_column(Integer, nullable=False)
    skipped_samples: Mapped[int] = mapped_column(Integer, nullable=False)
    run_count: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_ms: Mapped[float] = mapped_column(Float, nullable=False)
    limitations: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
