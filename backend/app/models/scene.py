"""Scene ORM model."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("projects.id"), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    narration_text: Mapped[str] = mapped_column(Text, default="")
    visual_description: Mapped[str] = mapped_column(Text, default="")
    video_prompt: Mapped[str] = mapped_column(Text, default="")
    negative_prompt: Mapped[str] = mapped_column(Text, default="")
    estimated_duration_seconds: Mapped[float] = mapped_column(Float, default=5.0)
    actual_duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    visual_style: Mapped[str] = mapped_column(String(128), default="cinematic documentary")
    camera_movement: Mapped[str] = mapped_column(String(128), default="slow dolly forward")
    composition: Mapped[str] = mapped_column(String(64), default="vertical 9:16")
    generation_status: Mapped[str] = mapped_column(String(32), default="pending")
    raw_asset_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    processed_asset_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    project: Mapped["Project"] = relationship("Project", back_populates="scenes")  # noqa: F821
