"""Project CRUD and filesystem bootstrap."""

from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.paths import ensure_project_layout, project_dir
from app.models.project import Project
from app.models.scene import Scene
from app.schemas.manifest import ManifestScene
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.manifest_service import ManifestService


def _new_id(prefix: str = "proj") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class ProjectService:
    def __init__(self, db: Session):
        self.db = db
        self.manifests = ManifestService()

    def create(self, payload: ProjectCreate) -> Project:
        project_id = _new_id("proj")
        title = payload.title or payload.topic[:80]
        ensure_project_layout(project_id)
        content_mode = (payload.content_mode or "standard").strip().lower()
        if content_mode not in {"standard", "desi"}:
            content_mode = "standard"
        platform = payload.platform
        language = payload.language
        tone = payload.tone
        if content_mode == "desi":
            platform = platform if platform and platform != "youtube_shorts" else "tiktok"
            language = language if language and language.lower() not in {"english", "en"} else "Urdu"
            tone = tone if tone and tone != "informative" else "conversational desi storytelling"
        manifest = self.manifests.create(
            project_id=project_id,
            title=title,
            topic=payload.topic,
            target_duration_seconds=payload.target_duration_seconds,
            platform=platform,
            language=language,
            content_mode=content_mode,
            tone=tone,
            visual_aesthetic=payload.visual_aesthetic,
            narration_voice=payload.narration_voice,
            extra_instructions=payload.extra_instructions,
            aspect_ratio=payload.aspect_ratio,
        )
        project = Project(
            id=project_id,
            title=title,
            topic=payload.topic,
            status="draft",
            platform=platform,
            language=language,
            content_mode=content_mode,
            tone=tone,
            visual_aesthetic=payload.visual_aesthetic,
            narration_voice=payload.narration_voice,
            target_duration_seconds=payload.target_duration_seconds,
            aspect_ratio=payload.aspect_ratio,
            extra_instructions=payload.extra_instructions,
            manifest_path=str(self.manifests.path_for(project_id)),
        )
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def list(self, skip: int = 0, limit: int = 50) -> tuple[list[Project], int]:
        q = self.db.query(Project).order_by(Project.updated_at.desc())
        total = q.count()
        items = q.offset(skip).limit(limit).all()
        return items, total

    def get(self, project_id: str) -> Project | None:
        return self.db.get(Project, project_id)

    def update(self, project_id: str, payload: ProjectUpdate) -> Project | None:
        project = self.get(project_id)
        if not project:
            return None
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(project, key, value)
        project.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(project)

        # Mirror relevant fields into manifest settings
        patch: dict = {}
        if "title" in data:
            patch["title"] = data["title"]
        if "topic" in data:
            patch["topic"] = data["topic"]
        if "status" in data:
            patch["status"] = data["status"]
        settings_keys = {
            "target_duration_seconds",
            "platform",
            "language",
            "content_mode",
            "tone",
            "visual_aesthetic",
            "narration_voice",
            "aspect_ratio",
            "extra_instructions",
        }
        settings_patch = {k: data[k] for k in settings_keys if k in data}
        if settings_patch:
            patch["settings"] = settings_patch
        if patch:
            self.manifests.update(project_id, patch)
        return project

    def delete(self, project_id: str) -> bool:
        project = self.get(project_id)
        if not project:
            return False
        self.db.delete(project)
        self.db.commit()
        root = project_dir(project_id)
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
        return True

    def duplicate(self, project_id: str) -> Project | None:
        source = self.get(project_id)
        if not source:
            return None
        new_id = _new_id("proj")
        ensure_project_layout(new_id)
        src_manifest = self.manifests.load(project_id)
        data = src_manifest.model_dump(mode="json")
        data["project_id"] = new_id
        data["title"] = f"{source.title} (Copy)"
        data["status"] = "draft"
        # Reset generation/render state
        data["narration"]["status"] = "pending"
        data["narration"]["audio_path"] = None
        data["narration"]["wav_path"] = None
        data["narration"]["mp3_path"] = None
        data["narration"]["duration_seconds"] = None
        for scene in data.get("scenes", []):
            scene["generation_status"] = "pending"
            scene["raw_asset_path"] = None
            scene["processed_asset_path"] = None
            scene["actual_duration_seconds"] = None
            scene["scene_id"] = scene["scene_id"].replace(project_id, new_id)
            if not scene["scene_id"].startswith("scene_"):
                scene["scene_id"] = f"scene_{scene['sequence']:03d}"
        data["captions"]["status"] = "pending"
        data["captions"]["srt_path"] = None
        data["captions"]["ass_path"] = None
        data["render"]["status"] = "pending"
        data["render"]["output_path"] = None
        data["render"]["qa_status"] = "pending"
        data["render"]["qa_report"] = None
        from app.schemas.manifest import ProductionManifest, default_pipeline_stages, utc_now_iso

        stages = default_pipeline_stages()
        stages[0].status = "completed"
        stages[0].completed_at = utc_now_iso()
        data["pipeline_stages"] = [s.model_dump() for s in stages]
        new_manifest = ProductionManifest.model_validate(data)
        self.manifests.save(new_manifest)

        project = Project(
            id=new_id,
            title=data["title"],
            topic=source.topic,
            status="draft",
            platform=source.platform,
            language=source.language,
            content_mode=getattr(source, "content_mode", None) or "standard",
            tone=source.tone,
            visual_aesthetic=source.visual_aesthetic,
            narration_voice=source.narration_voice,
            target_duration_seconds=source.target_duration_seconds,
            aspect_ratio=source.aspect_ratio,
            extra_instructions=source.extra_instructions,
            manifest_path=str(self.manifests.path_for(new_id)),
        )
        self.db.add(project)
        # Copy scene rows
        for sc in new_manifest.scenes:
            self.db.add(
                Scene(
                    id=f"{new_id}_{sc.scene_id}",
                    project_id=new_id,
                    sequence=sc.sequence,
                    narration_text=sc.narration_text,
                    visual_description=sc.visual_description,
                    video_prompt=sc.video_prompt,
                    negative_prompt=sc.negative_prompt,
                    estimated_duration_seconds=sc.estimated_duration_seconds,
                    visual_style=sc.visual_style,
                    camera_movement=sc.camera_movement,
                    composition=sc.composition,
                    generation_status="pending",
                )
            )
        self.db.commit()
        self.db.refresh(project)
        return project

    def sync_scenes_from_manifest(self, project_id: str, scenes: list[ManifestScene]) -> None:
        self.db.query(Scene).filter(Scene.project_id == project_id).delete()
        for sc in scenes:
            self.db.add(
                Scene(
                    id=f"{project_id}_{sc.scene_id}",
                    project_id=project_id,
                    sequence=sc.sequence,
                    narration_text=sc.narration_text,
                    visual_description=sc.visual_description,
                    video_prompt=sc.video_prompt,
                    negative_prompt=sc.negative_prompt,
                    estimated_duration_seconds=sc.estimated_duration_seconds,
                    visual_style=sc.visual_style,
                    camera_movement=sc.camera_movement,
                    composition=sc.composition,
                    generation_status=sc.generation_status,
                    raw_asset_path=sc.raw_asset_path,
                    processed_asset_path=sc.processed_asset_path,
                    actual_duration_seconds=sc.actual_duration_seconds,
                )
            )
        self.db.commit()
