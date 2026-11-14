"""Job API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class JobStageResponse(BaseModel):
    stage: str
    sequence: int
    status: str
    retry_count: int
    error_message: str | None
    output_ref: str | None
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class JobResponse(BaseModel):
    id: str
    project_id: str
    job_type: str
    status: str
    current_stage: str | None
    error_message: str | None
    retry_count: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    stages: list[JobStageResponse] = []

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    items: list[JobResponse]
    total: int


class JobProgressEvent(BaseModel):
    job_id: str
    project_id: str
    status: str
    stage: str | None = None
    scene_id: str | None = None
    message: str = ""
    progress_pct: float | None = None
    level: str = "info"
    timestamp: str | None = None
