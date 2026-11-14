"""Project ORM model."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(64), default="draft", nullable=False)
    platform: Mapped[str] = mapped_column(String(64), default="youtube_shorts")
    language: Mapped[str] = mapped_column(String(64), default="English")
    content_mode: Mapped[str] = mapped_column(String(32), default="standard")
    tone: Mapped[str] = mapped_column(String(128), default="informative")
    visual_aesthetic: Mapped[str] = mapped_column(String(128), default="cinematic documentary")
    narration_voice: Mapped[str] = mapped_column(String(128), default="Aoede")
    target_duration_seconds: Mapped[int] = mapped_column(default=45)
    aspect_ratio: Mapped[str] = mapped_column(String(16), default="9:16")
    extra_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    manifest_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    jobs: Mapped[list["Job"]] = relationship("Job", back_populates="project", cascade="all, delete-orphan")  # noqa: F821
    scenes: Mapped[list["Scene"]] = relationship("Scene", back_populates="project", cascade="all, delete-orphan")  # noqa: F821
    assets: Mapped[list["Asset"]] = relationship("Asset", back_populates="project", cascade="all, delete-orphan")  # noqa: F821
