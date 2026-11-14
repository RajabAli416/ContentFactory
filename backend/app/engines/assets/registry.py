"""Centralized asset registration and validation."""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.engines.video.ffmpeg_runner import probe_media, validate_video_file
from app.models.asset import Asset


class AssetRegistry:
    def __init__(self, db: Session):
        self.db = db

    async def register_file(
        self,
        *,
        project_id: str,
        file_path: Path,
        asset_type: str = "video_clip",
        source: str = "downloaded",
        scene_id: str | None = None,
        provider: str | None = None,
        notes: str | None = None,
        validate: bool = True,
    ) -> Asset:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(str(path))
        if path.stat().st_size == 0:
            raise ValueError(f"Empty asset: {path}")

        meta: dict = {}
        if validate and asset_type in {"video_clip", "render", "processed_clip"}:
            meta = await validate_video_file(path)
        elif path.suffix.lower() in {".wav", ".mp3", ".m4a", ".aac"}:
            meta = await probe_media(path)

        checksum = self._checksum(path)
        # Duplicate detection by checksum within project
        existing = (
            self.db.query(Asset)
            .filter(Asset.project_id == project_id, Asset.checksum == checksum)
            .first()
        )
        if existing and Path(existing.file_path).exists():
            return existing

        asset = Asset(
            id=f"asset_{uuid.uuid4().hex[:12]}",
            project_id=project_id,
            scene_id=scene_id,
            asset_type=asset_type,
            source=source,
            file_path=str(path.resolve()),
            file_size_bytes=path.stat().st_size,
            duration_seconds=meta.get("duration"),
            width=meta.get("width"),
            height=meta.get("height"),
            fps=meta.get("fps"),
            codec=meta.get("video_codec") or meta.get("audio_codec"),
            checksum=checksum,
            provider=provider,
            notes=notes,
        )
        self.db.add(asset)
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def _checksum(self, path: Path, chunk: int = 1024 * 1024) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            while True:
                data = f.read(chunk)
                if not data:
                    break
                h.update(data)
        return h.hexdigest()
