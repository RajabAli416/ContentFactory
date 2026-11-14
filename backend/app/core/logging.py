"""Structured logging configuration."""

from __future__ import annotations

import logging
import sys
from typing import Any


class ContextFilter(logging.Filter):
    """Inject optional contextual fields into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        for key in ("project_id", "job_id", "stage", "scene_id"):
            if not hasattr(record, key):
                setattr(record, key, "-")
        return True


class StructuredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = []
        for key in ("project_id", "job_id", "stage", "scene_id"):
            val = getattr(record, key, "-")
            if val and val != "-":
                extras.append(f"{key}={val}")
        if extras:
            return f"{base} | {' '.join(extras)}"
        return base


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(level.upper())
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        StructuredFormatter(
            fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    handler.addFilter(ContextFilter())
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_extra(
    project_id: str | None = None,
    job_id: str | None = None,
    stage: str | None = None,
    scene_id: str | None = None,
) -> dict[str, Any]:
    return {
        "project_id": project_id or "-",
        "job_id": job_id or "-",
        "stage": stage or "-",
        "scene_id": scene_id or "-",
    }
