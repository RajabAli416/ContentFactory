"""Project API request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class ProjectCreate(BaseModel):
    topic: str = Field(..., min_length=1, max_length=2000)
    title: str | None = Field(None, max_length=512)
    target_duration_seconds: int = Field(45, ge=10, le=180)
    platform: str = "youtube_shorts"
    language: str = "English"
    content_mode: str = "standard"
    tone: str = "informative"
    visual_aesthetic: str = "cinematic documentary"
    narration_voice: str = "Aoede"
    aspect_ratio: str = "9:16"
    extra_instructions: str | None = None


class ProjectUpdate(BaseModel):
    title: str | None = None
    topic: str | None = None
    target_duration_seconds: int | None = Field(None, ge=10, le=180)
    platform: str | None = None
    language: str | None = None
    content_mode: str | None = None
    tone: str | None = None
    visual_aesthetic: str | None = None
    narration_voice: str | None = None
    aspect_ratio: str | None = None
    extra_instructions: str | None = None
    status: str | None = None


class ProjectResponse(BaseModel):
    id: str
    title: str
    topic: str
    status: str
    platform: str
    language: str
    content_mode: str = "standard"
    tone: str
    visual_aesthetic: str
    narration_voice: str
    target_duration_seconds: int
    aspect_ratio: str
    extra_instructions: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("content_mode", mode="before")
    @classmethod
    def default_content_mode(cls, v: str | None) -> str:
        return v or "standard"


class ProjectListResponse(BaseModel):
    items: list[ProjectResponse]
    total: int
