"""Filesystem path helpers with traversal protection."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from app.core.config import get_settings

SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")

PROJECT_SUBDIRS = (
    "research",
    "scripts",
    "prompts",
    "narration",
    "assets/raw",
    "assets/downloaded",
    "assets/processed",
    "captions",
    "renders",
    "logs",
)


def validate_id(value: str, label: str = "id") -> str:
    if not value or not SAFE_ID_RE.match(value):
        raise ValueError(f"Invalid {label}: must be alphanumeric, underscore, or hyphen")
    return value


def project_dir(project_id: str) -> Path:
    validate_id(project_id, "project_id")
    settings = get_settings()
    path = (settings.projects_dir / project_id).resolve()
    if not str(path).startswith(str(settings.projects_dir.resolve())):
        raise ValueError("Path traversal detected")
    return path


def ensure_project_layout(project_id: str) -> Path:
    root = project_dir(project_id)
    root.mkdir(parents=True, exist_ok=True)
    for sub in PROJECT_SUBDIRS:
        (root / sub).mkdir(parents=True, exist_ok=True)
    return root


def safe_join(base: Path, *parts: str) -> Path:
    """Join path parts under base, rejecting traversal."""
    candidate = base.joinpath(*parts).resolve()
    base_resolved = base.resolve()
    if not str(candidate).startswith(str(base_resolved)):
        raise ValueError("Path traversal detected")
    return candidate


def copy_without_overwrite(src: Path, dest: Path) -> Path:
    """Copy src to dest; if dest exists, append a numeric suffix."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        shutil.copy2(src, dest)
        return dest
    stem, suffix = dest.stem, dest.suffix
    counter = 1
    while True:
        alt = dest.with_name(f"{stem}_{counter}{suffix}")
        if not alt.exists():
            shutil.copy2(src, alt)
            return alt
        counter += 1


def open_folder(path: Path) -> None:
    """Open a folder in the OS file explorer (Windows)."""
    import os
    import subprocess

    resolved = path.resolve()
    if os.name == "nt":
        subprocess.Popen(["explorer", str(resolved)])  # noqa: S603
    else:
        subprocess.Popen(["xdg-open", str(resolved)])  # noqa: S603
