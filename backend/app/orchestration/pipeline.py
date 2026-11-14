"""Async production pipeline with resume, retry, and single-job concurrency."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core import database as dbmod
from app.core.logging import get_logger, log_extra
from app.core.paths import ensure_project_layout, project_dir
from app.engines.assets.registry import AssetRegistry
from app.engines.browser.factory import get_video_generation_provider
from app.engines.captions.provider import DurationCaptionProvider
from app.engines.content.factory import get_content_provider
from app.engines.export.qa import run_qa_checks
from app.engines.narration.factory import get_tts_provider
from app.engines.video.processor import FFmpegVideoProcessor
from app.models.job import Job, JobStageRecord
from app.models.project import Project
from app.orchestration.progress import progress_hub
from app.orchestration.stage_meta import stage_detail, stage_label
from app.schemas.content import ContentGenerationRequest
from app.schemas.manifest import (
    PIPELINE_STAGES,
    ManifestPackaging,
    ManifestScene,
    ProductionManifest,
    utc_now_iso,
)
from app.services.manifest_service import ManifestService
from app.services.project_service import ProjectService

logger = get_logger(__name__)


ACTIVE_STATUSES = {"PENDING", "RUNNING", "PAUSED"}
RUNNABLE_STAGES = [s for s in PIPELINE_STAGES if s != "PROJECT_CREATED"]


class PipelineOrchestrator:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._active_job_id: str | None = None
        self._cancel_flags: set[str] = set()
        self._pause_flags: set[str] = set()
        self._tasks: dict[str, asyncio.Task] = {}

    def has_active_job(self, db: Session) -> Job | None:
        return (
            db.query(Job)
            .filter(Job.status.in_(["PENDING", "RUNNING", "PAUSED"]))
            .order_by(Job.created_at.desc())
            .first()
        )

    async def start_job(
        self,
        db: Session,
        project_id: str,
        job_type: str = "full_pipeline",
        *,
        start_stage: str | None = None,
    ) -> Job:
        existing = self.has_active_job(db)
        if existing and existing.status in {"PENDING", "RUNNING"}:
            raise RuntimeError(
                f"Another job is active ({existing.id}). Cancel or wait before starting a new one."
            )

        job_id = f"job_{uuid.uuid4().hex[:12]}"
        stages = [s for s in PIPELINE_STAGES if s != "PROJECT_CREATED"]
        # For partial jobs, map job_type to stage subsets
        stage_map = {
            "full_pipeline": stages,
            "generate_content": ["CONTENT_GENERATION", "SCENE_PLANNING", "PROMPT_GENERATION"],
            "generate_narration": ["NARRATION_GENERATION"],
            "generate_visuals": ["VISUAL_GENERATION", "ASSET_VALIDATION"],
            "render": [
                "CLIP_PROCESSING",
                "TIMELINE_ASSEMBLY",
                "CAPTION_GENERATION",
                "FINAL_RENDER",
                "QUALITY_ASSURANCE",
                "COMPLETED",
            ],
            "single_scene": ["VISUAL_GENERATION", "ASSET_VALIDATION"],
        }
        selected = stage_map.get(job_type, stages)

        job = Job(
            id=job_id,
            project_id=project_id,
            job_type=job_type,
            status="PENDING",
            current_stage=selected[0] if selected else None,
        )
        db.add(job)
        for i, stage in enumerate(selected):
            db.add(
                JobStageRecord(
                    job_id=job_id,
                    stage=stage,
                    sequence=i,
                    status="PENDING",
                )
            )
        db.commit()
        db.refresh(job)

        task = asyncio.create_task(self._run_job(job_id, start_stage=start_stage))
        self._tasks[job_id] = task
        return job

    async def pause(self, job_id: str) -> None:
        self._pause_flags.add(job_id)
        await progress_hub.publish(
            job_id, {"status": "PAUSED", "message": "Pause requested", "level": "warning"}
        )

    async def resume(self, db: Session, job_id: str) -> Job:
        job = db.get(Job, job_id)
        if not job:
            raise FileNotFoundError(job_id)
        self._pause_flags.discard(job_id)
        if job.status == "PAUSED":
            job.status = "PENDING"
            db.commit()
            task = asyncio.create_task(self._run_job(job_id, resume=True))
            self._tasks[job_id] = task
        return job

    async def cancel(self, db: Session, job_id: str) -> Job:
        self._cancel_flags.add(job_id)
        job = db.get(Job, job_id)
        if job and job.status in ACTIVE_STATUSES:
            job.status = "CANCELLED"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        await progress_hub.publish(
            job_id, {"status": "CANCELLED", "message": "Job cancelled", "level": "warning"}
        )
        return job  # type: ignore[return-value]

    def _stage_progress_fields(self, stage: str | None, progress_pct: float | None = None) -> dict[str, Any]:
        stage_key = stage or ""
        try:
            idx = RUNNABLE_STAGES.index(stage_key) if stage_key in RUNNABLE_STAGES else -1
        except ValueError:
            idx = -1
        total = len(RUNNABLE_STAGES)
        if progress_pct is None and idx >= 0:
            # Stage start ≈ index/total; completed handled by callers
            progress_pct = (idx / max(total, 1)) * 100.0
        return {
            "stage": stage_key or None,
            "stage_label": stage_label(stage_key),
            "stage_detail": stage_detail(stage_key),
            "stage_index": idx + 1 if idx >= 0 else None,
            "stage_total": total,
            "progress_pct": round(float(progress_pct), 1) if progress_pct is not None else None,
        }

    async def _emit(self, job: Job, **kwargs: Any) -> None:
        stage = kwargs.pop("stage", job.current_stage)
        progress_pct = kwargs.pop("progress_pct", None)
        status = kwargs.pop("status", job.status)
        meta = self._stage_progress_fields(stage, progress_pct)
        # Prefer human labels in default messages when callers pass raw stage names
        if "message" not in kwargs and stage:
            meta.setdefault("message", stage_label(stage))
        await progress_hub.publish(
            job.id,
            {
                "project_id": job.project_id,
                "status": status,
                **meta,
                **kwargs,
            },
        )

    def _stage_complete_pct(self, stage: str) -> float:
        try:
            idx = RUNNABLE_STAGES.index(stage)
        except ValueError:
            return 0.0
        return round(((idx + 1) / max(len(RUNNABLE_STAGES), 1)) * 100.0, 1)

    def _intra_stage_pct(self, stage: str, done: float, total: int) -> float:
        """Map intra-stage work onto the overall pipeline percentage span."""
        try:
            idx = RUNNABLE_STAGES.index(stage)
        except ValueError:
            return 0.0
        n = max(len(RUNNABLE_STAGES), 1)
        start = (idx / n) * 100.0
        end = ((idx + 1) / n) * 100.0
        frac = float(done) / max(total, 1)
        return round(start + (end - start) * frac, 1)

    async def _run_job(
        self, job_id: str, *, resume: bool = False, start_stage: str | None = None
    ) -> None:
        async with self._lock:
            if self._active_job_id and self._active_job_id != job_id:
                db = dbmod.SessionLocal()
                try:
                    job = db.get(Job, job_id)
                    if job:
                        job.status = "FAILED"
                        job.error_message = "Another job is already running"
                        db.commit()
                finally:
                    db.close()
                return
            self._active_job_id = job_id

        db = dbmod.SessionLocal()
        try:
            job = db.get(Job, job_id)
            if not job:
                return
            job.status = "RUNNING"
            job.started_at = job.started_at or datetime.now(timezone.utc)
            db.commit()

            await self._emit(
                job,
                stage=job.current_stage or "CONTENT_GENERATION",
                message="Pipeline started",
                progress_pct=0,
            )

            stages = (
                db.query(JobStageRecord)
                .filter(JobStageRecord.job_id == job_id)
                .order_by(JobStageRecord.sequence)
                .all()
            )
            total_stages = len([s for s in stages if s.stage in RUNNABLE_STAGES]) or len(RUNNABLE_STAGES)

            skip_until = start_stage
            for stage_rec in stages:
                if job_id in self._cancel_flags:
                    job.status = "CANCELLED"
                    db.commit()
                    await self._emit(
                        job,
                        stage=stage_rec.stage,
                        status="CANCELLED",
                        message="Pipeline cancelled",
                    )
                    return

                while job_id in self._pause_flags:
                    job.status = "PAUSED"
                    db.commit()
                    await self._emit(
                        job,
                        stage=stage_rec.stage,
                        status="PAUSED",
                        message=f"Paused — {stage_label(stage_rec.stage)}",
                    )
                    await asyncio.sleep(0.5)
                    if job_id in self._cancel_flags:
                        job.status = "CANCELLED"
                        db.commit()
                        await self._emit(
                            job,
                            stage=stage_rec.stage,
                            status="CANCELLED",
                            message="Pipeline cancelled",
                        )
                        return
                    job.status = "RUNNING"
                    db.commit()

                # Resume: skip completed stages
                if stage_rec.status == "COMPLETED":
                    continue
                if skip_until and stage_rec.stage != skip_until:
                    # Also skip if we're resuming and stage completed in manifest
                    continue
                if skip_until and stage_rec.stage == skip_until:
                    skip_until = None

                # Skip expensive completed visual work based on manifest
                if await self._should_skip_stage(job.project_id, stage_rec.stage):
                    stage_rec.status = "SKIPPED"
                    stage_rec.completed_at = datetime.now(timezone.utc)
                    db.commit()
                    await self._emit(
                        job,
                        stage=stage_rec.stage,
                        status="SKIPPED",
                        message=f"Skipped — already done: {stage_label(stage_rec.stage)}",
                        progress_pct=self._stage_complete_pct(stage_rec.stage),
                    )
                    continue

                job.current_stage = stage_rec.stage
                stage_rec.status = "RUNNING"
                stage_rec.started_at = datetime.now(timezone.utc)
                db.commit()
                try:
                    stage_idx = RUNNABLE_STAGES.index(stage_rec.stage)
                    start_pct = (stage_idx / max(total_stages, 1)) * 100.0
                except ValueError:
                    start_pct = None
                await self._emit(
                    job,
                    stage=stage_rec.stage,
                    status="RUNNING",
                    message=f"Starting — {stage_label(stage_rec.stage)}",
                    progress_pct=start_pct,
                    step="start",
                )
                self._update_manifest_stage(job.project_id, stage_rec.stage, "running")

                try:
                    await self._execute_stage(db, job, stage_rec.stage)
                    stage_rec.status = "COMPLETED"
                    stage_rec.completed_at = datetime.now(timezone.utc)
                    db.commit()
                    self._update_manifest_stage(job.project_id, stage_rec.stage, "completed")
                    await self._emit(
                        job,
                        stage=stage_rec.stage,
                        status="COMPLETED",
                        message=f"Done — {stage_label(stage_rec.stage)}",
                        progress_pct=self._stage_complete_pct(stage_rec.stage),
                        step="complete",
                    )
                except Exception as exc:
                    logger.exception(
                        "Stage failed",
                        extra=log_extra(job.project_id, job.id, stage_rec.stage),
                    )
                    stage_rec.status = "FAILED"
                    stage_rec.error_message = str(exc)
                    stage_rec.retry_count += 1
                    job.status = "FAILED"
                    job.error_message = str(exc)
                    db.commit()
                    self._update_manifest_stage(
                        job.project_id, stage_rec.stage, "failed", error=str(exc)
                    )
                    await self._emit(
                        job,
                        stage=stage_rec.stage,
                        status="FAILED",
                        message=f"Failed — {stage_label(stage_rec.stage)}: {exc}",
                        level="error",
                        step="error",
                    )
                    return

            job.status = "COMPLETED"
            job.completed_at = datetime.now(timezone.utc)
            job.current_stage = "COMPLETED"
            project = db.get(Project, job.project_id)
            if project:
                project.status = "completed"
            db.commit()
            self._update_manifest_stage(job.project_id, "COMPLETED", "completed")
            await self._emit(
                job,
                stage="COMPLETED",
                status="COMPLETED",
                message="Pipeline complete — video ready to export",
                progress_pct=100,
                step="complete",
            )
        finally:
            db.close()
            self._active_job_id = None
            self._cancel_flags.discard(job_id)
            self._pause_flags.discard(job_id)
            self._tasks.pop(job_id, None)

    async def _should_skip_stage(self, project_id: str, stage: str) -> bool:
        try:
            manifest = ManifestService().load(project_id)
        except FileNotFoundError:
            return False
        if stage == "CONTENT_GENERATION" and manifest.script.full_text and manifest.scenes:
            return True
        if stage in {"SCENE_PLANNING", "PROMPT_GENERATION"} and manifest.scenes and all(
            s.video_prompt for s in manifest.scenes
        ):
            return True
        if stage == "NARRATION_GENERATION" and manifest.narration.status == "completed":
            return True
        if stage == "VISUAL_GENERATION" and manifest.scenes and all(
            s.generation_status == "completed" and s.raw_asset_path for s in manifest.scenes
        ):
            return True
        if stage == "FINAL_RENDER" and manifest.render.status == "completed" and manifest.render.output_path:
            return True
        return False

    def _update_manifest_stage(
        self, project_id: str, stage: str, status: str, error: str | None = None
    ) -> None:
        ms = ManifestService()
        try:
            manifest = ms.load(project_id)
        except FileNotFoundError:
            return
        for st in manifest.pipeline_stages:
            if st.stage == stage:
                st.status = status  # type: ignore[assignment]
                if status == "running":
                    st.started_at = utc_now_iso()
                if status in {"completed", "failed", "skipped"}:
                    st.completed_at = utc_now_iso()
                if error:
                    st.error = error
                    st.retry_count += 1
        if status == "completed" and stage == "COMPLETED":
            manifest.status = "completed"
        elif status == "running":
            manifest.status = "in_progress"
        elif status == "failed":
            manifest.status = "failed"
        ms.save(manifest)

    async def _execute_stage(self, db: Session, job: Job, stage: str) -> None:
        handlers = {
            "CONTENT_GENERATION": self._stage_content,
            "SCENE_PLANNING": self._stage_scene_planning,
            "PROMPT_GENERATION": self._stage_prompt_generation,
            "NARRATION_GENERATION": self._stage_narration,
            "VISUAL_GENERATION": self._stage_visuals,
            "ASSET_VALIDATION": self._stage_asset_validation,
            "CLIP_PROCESSING": self._stage_clip_processing,
            "TIMELINE_ASSEMBLY": self._stage_timeline,
            "CAPTION_GENERATION": self._stage_captions,
            "FINAL_RENDER": self._stage_final_render,
            "QUALITY_ASSURANCE": self._stage_qa,
            "COMPLETED": self._stage_noop,
        }
        handler = handlers.get(stage, self._stage_noop)
        await handler(db, job)

    async def _stage_noop(self, db: Session, job: Job) -> None:
        return

    async def _stage_content(self, db: Session, job: Job) -> None:
        project = db.get(Project, job.project_id)
        assert project
        provider = get_content_provider()
        ms_peek = ManifestService()
        try:
            content_mode = getattr(project, "content_mode", None) or ms_peek.load(
                job.project_id
            ).settings.content_mode
        except Exception:
            content_mode = "standard"
        mode_label = "Desi (Urdu)" if content_mode == "desi" else "Standard"
        await self._emit(
            job,
            stage="CONTENT_GENERATION",
            message=f"Drafting script — {mode_label} · {project.topic[:80]}",
            step="generate",
        )
        req = ContentGenerationRequest(
            topic=project.topic,
            target_duration_seconds=project.target_duration_seconds,
            platform=project.platform,
            tone=project.tone,
            visual_aesthetic=project.visual_aesthetic,
            language=project.language,
            content_mode="desi" if content_mode == "desi" else "standard",
            extra_instructions=project.extra_instructions,
            narration_voice=project.narration_voice,
        )
        result = await provider.generate_content(req)
        await self._emit(
            job,
            stage="CONTENT_GENERATION",
            message=f"Script ready — {len(result.scenes)} scenes · ~{result.estimated_duration_seconds:.0f}s",
            step="save",
            scene_count=len(result.scenes),
        )
        ms = ManifestService()
        manifest = ms.load(job.project_id)
        manifest.settings.content_mode = req.content_mode
        manifest.script.title = result.title
        manifest.script.hook = result.hook
        manifest.script.full_text = result.full_script
        manifest.script.caption_text = result.caption_text or result.full_script
        manifest.script.closing_line = result.closing_line
        manifest.script.estimated_duration_seconds = result.estimated_duration_seconds
        if result.packaging:
            manifest.packaging = ManifestPackaging.model_validate(result.packaging.model_dump())
        if result.title:
            project.title = result.title
            manifest.title = result.title
        manifest.scenes = [
            ManifestScene(
                scene_id=s.scene_id,
                sequence=s.sequence,
                narration_text=s.narration_text,
                caption_text=s.caption_text or s.narration_text,
                visual_description=s.visual_description,
                video_prompt=s.video_prompt,
                negative_prompt=s.negative_prompt,
                estimated_duration_seconds=s.estimated_duration_seconds,
                visual_style=s.visual_style,
                camera_movement=s.camera_movement,
                composition=s.composition,
            )
            for s in result.scenes
        ]
        root = ensure_project_layout(job.project_id)
        (root / "scripts" / "script.json").write_text(
            result.model_dump_json(indent=2), encoding="utf-8"
        )
        (root / "scripts" / "packaging.json").write_text(
            json.dumps(manifest.packaging.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        ms.save(manifest)
        ProjectService(db).sync_scenes_from_manifest(job.project_id, manifest.scenes)
        db.commit()

    async def _stage_scene_planning(self, db: Session, job: Job) -> None:
        # Content stage already includes scenes; ensure prompts folder snapshot
        ms = ManifestService()
        manifest = ms.load(job.project_id)
        if not manifest.scenes:
            raise RuntimeError("No scenes available after content generation")
        await self._emit(
            job,
            stage="SCENE_PLANNING",
            message=f"Planning {len(manifest.scenes)} scenes for timeline budget",
            step="plan",
            scene_count=len(manifest.scenes),
        )
        root = project_dir(job.project_id)
        (root / "scripts" / "scenes.json").write_text(
            json.dumps([s.model_dump() for s in manifest.scenes], indent=2),
            encoding="utf-8",
        )

    async def _stage_prompt_generation(self, db: Session, job: Job) -> None:
        ms = ManifestService()
        manifest = ms.load(job.project_id)
        root = project_dir(job.project_id)
        prompts_dir = root / "prompts"
        total = len(manifest.scenes)
        for idx, scene in enumerate(manifest.scenes):
            if not scene.video_prompt:
                raise RuntimeError(f"Missing video prompt for {scene.scene_id}")
            (prompts_dir / f"{scene.scene_id}.txt").write_text(
                scene.video_prompt, encoding="utf-8"
            )
            (prompts_dir / f"{scene.scene_id}.json").write_text(
                scene.model_dump_json(indent=2), encoding="utf-8"
            )
            await self._emit(
                job,
                stage="PROMPT_GENERATION",
                scene_id=scene.scene_id,
                message=f"Prompt {idx + 1}/{total} — {scene.scene_id}",
                progress_pct=self._intra_stage_pct("PROMPT_GENERATION", idx + 1, total),
                step="write",
                scene_index=idx + 1,
                scene_total=total,
            )
        ms.save(manifest)

    async def _stage_narration(self, db: Session, job: Job) -> None:
        ms = ManifestService()
        manifest = ms.load(job.project_id)
        text = manifest.script.full_text
        if not text:
            text = " ".join(s.narration_text for s in manifest.scenes)
        if not text.strip():
            raise RuntimeError("No narration text available")
        provider = get_tts_provider()
        out_dir = project_dir(job.project_id) / "narration"
        from app.engines.content.desi import desi_tts_style, is_desi_mode

        style = None
        if is_desi_mode(manifest.settings.content_mode, manifest.settings.language):
            style = desi_tts_style()
        voice = manifest.settings.narration_voice or "Aoede"
        await self._emit(
            job,
            stage="NARRATION_GENERATION",
            message=f"Synthesizing voiceover — {voice}"
            + (" · Desi Urdu style" if style else ""),
            step="tts",
        )
        result = await provider.generate_speech(
            text,
            out_dir,
            voice=voice,
            style=style,
        )
        await self._emit(
            job,
            stage="NARRATION_GENERATION",
            message=f"Narration ready — {result['duration_seconds']:.1f}s · {result['provider']}",
            step="normalize",
            duration_seconds=result["duration_seconds"],
        )
        manifest.narration.provider = result["provider"]
        manifest.narration.voice = result["voice"]
        manifest.narration.wav_path = result["wav_path"]
        manifest.narration.mp3_path = result["mp3_path"]
        manifest.narration.audio_path = result["wav_path"]
        manifest.narration.duration_seconds = result["duration_seconds"]
        manifest.narration.metadata_path = result.get("metadata_path")
        manifest.narration.style = style
        manifest.narration.status = "completed"
        ms.save(manifest)
        registry = AssetRegistry(db)
        await registry.register_file(
            project_id=job.project_id,
            file_path=Path(result["wav_path"]),
            asset_type="narration_audio",
            source="raw",
            provider=result["provider"],
            validate=False,
        )

    async def _stage_visuals(self, db: Session, job: Job) -> None:
        ms = ManifestService()
        manifest = ms.load(job.project_id)
        provider = get_video_generation_provider()
        settings = get_settings()
        root = project_dir(job.project_id)
        download_dir = root / "assets" / "downloaded"
        diag_dir = root / "logs" / "browser"
        diag_dir.mkdir(parents=True, exist_ok=True)

        total = len(manifest.scenes)
        provider_name = settings.video_gen_provider
        await self._emit(
            job,
            stage="VISUAL_GENERATION",
            message=f"Generating {total} clips via {provider_name}",
            step="begin",
            scene_total=total,
        )
        for idx, scene in enumerate(manifest.scenes):
            if job.id in self._cancel_flags:
                raise RuntimeError("Cancelled")
            if scene.generation_status == "completed" and scene.raw_asset_path and Path(scene.raw_asset_path).exists():
                await self._emit(
                    job,
                    stage="VISUAL_GENERATION",
                    scene_id=scene.scene_id,
                    message=f"Reuse existing clip {idx + 1}/{total} — {scene.scene_id}",
                    progress_pct=self._intra_stage_pct("VISUAL_GENERATION", idx + 1, total),
                    step="skip",
                    scene_index=idx + 1,
                    scene_total=total,
                )
                continue

            scene.generation_status = "generating"
            ms.save(manifest)
            out = download_dir / f"{scene.scene_id}.mp4"
            await self._emit(
                job,
                stage="VISUAL_GENERATION",
                scene_id=scene.scene_id,
                message=f"Generating clip {idx + 1}/{total} — {scene.scene_id}",
                progress_pct=self._intra_stage_pct("VISUAL_GENERATION", idx + 0.15, total),
                step="generate",
                scene_index=idx + 1,
                scene_total=total,
            )

            async def on_progress(msg: str, sid: str = scene.scene_id, i: int = idx) -> None:
                await self._emit(
                    job,
                    stage="VISUAL_GENERATION",
                    scene_id=sid,
                    message=f"Clip {i + 1}/{total}: {msg}",
                    progress_pct=self._intra_stage_pct("VISUAL_GENERATION", i + 0.5, total),
                    step="provider",
                    scene_index=i + 1,
                    scene_total=total,
                )

            try:
                path = await provider.generate_clip(
                    scene.video_prompt,
                    out,
                    options={
                        "duration_seconds": scene.estimated_duration_seconds,
                        "width": settings.default_width,
                        "height": settings.default_height,
                        "fps": settings.default_fps,
                        "diagnostics_dir": str(diag_dir),
                        "negative_prompt": scene.negative_prompt,
                    },
                    on_progress=on_progress,
                )
                scene.raw_asset_path = str(path)
                scene.generation_status = "completed"
                from app.engines.video.ffmpeg_runner import probe_media

                info = await probe_media(path)
                scene.actual_duration_seconds = float(info.get("duration") or 0)
                ms.save(manifest)
                await AssetRegistry(db).register_file(
                    project_id=job.project_id,
                    file_path=path,
                    asset_type="video_clip",
                    source="downloaded",
                    scene_id=scene.scene_id,
                    provider=settings.video_gen_provider,
                )
            except Exception as exc:
                scene.generation_status = "failed"
                ms.save(manifest)
                raise RuntimeError(f"Scene {scene.scene_id} failed: {exc}") from exc

            await self._emit(
                job,
                stage="VISUAL_GENERATION",
                scene_id=scene.scene_id,
                message=f"Clip ready {idx + 1}/{total} — {scene.scene_id} ({scene.actual_duration_seconds:.1f}s)",
                progress_pct=self._intra_stage_pct("VISUAL_GENERATION", idx + 1, total),
                step="complete",
                scene_index=idx + 1,
                scene_total=total,
            )

    async def _stage_asset_validation(self, db: Session, job: Job) -> None:
        ms = ManifestService()
        manifest = ms.load(job.project_id)
        from app.engines.video.ffmpeg_runner import validate_video_file

        total = len(manifest.scenes)
        for idx, scene in enumerate(manifest.scenes):
            if not scene.raw_asset_path:
                raise RuntimeError(f"Missing asset for {scene.scene_id}")
            await self._emit(
                job,
                stage="ASSET_VALIDATION",
                scene_id=scene.scene_id,
                message=f"Validating {idx + 1}/{total} — {scene.scene_id}",
                progress_pct=self._intra_stage_pct("ASSET_VALIDATION", idx + 1, total),
                step="validate",
                scene_index=idx + 1,
                scene_total=total,
            )
            await validate_video_file(Path(scene.raw_asset_path))

    async def _stage_clip_processing(self, db: Session, job: Job) -> None:
        ms = ManifestService()
        manifest = ms.load(job.project_id)
        settings = get_settings()
        processor = FFmpegVideoProcessor()
        processed_dir = project_dir(job.project_id) / "assets" / "processed"
        narration_dur = float(manifest.narration.duration_seconds or 0)
        # Allocate target durations proportional to estimates
        estimates = [max(s.estimated_duration_seconds, 1.0) for s in manifest.scenes]
        total_est = sum(estimates) or 1.0
        targets = []
        if narration_dur > 0:
            targets = [narration_dur * (e / total_est) for e in estimates]
        else:
            targets = estimates

        total = len(manifest.scenes)
        await self._emit(
            job,
            stage="CLIP_PROCESSING",
            message=f"Fitting {total} clips to {narration_dur:.1f}s narration"
            if narration_dur
            else f"Normalizing {total} clips",
            step="begin",
            scene_total=total,
        )
        for idx, (scene, target) in enumerate(zip(manifest.scenes, targets)):
            raw = Path(scene.raw_asset_path or "")
            out = processed_dir / f"{scene.scene_id}_norm.mp4"
            end_trim = float(manifest.settings.end_trim_seconds or 0)
            # Provider defaults: Snapgen has no credit bumper; Zsky often does.
            if end_trim <= 0:
                if settings.video_gen_provider == "zsky":
                    end_trim = float(settings.zsky_end_trim_seconds or 0)
                else:
                    end_trim = float(settings.snapgen_end_trim_seconds or 0)
            await self._emit(
                job,
                stage="CLIP_PROCESSING",
                scene_id=scene.scene_id,
                message=f"Normalize {idx + 1}/{total} — {scene.scene_id} → {target:.1f}s",
                progress_pct=self._intra_stage_pct("CLIP_PROCESSING", idx + 0.4, total),
                step="normalize",
                scene_index=idx + 1,
                scene_total=total,
            )
            await processor.normalize_clip(
                raw,
                out,
                {
                    "width": settings.default_width,
                    "height": settings.default_height,
                    "fps": settings.default_fps,
                    "end_trim_seconds": end_trim,
                    "keep_audio": bool(settings.scene_audio_enabled),
                },
            )
            # Fit to target via freeze extend (never cut narration later)
            fitted = processed_dir / f"{scene.scene_id}_fit.mp4"
            await processor.freeze_extend(out, fitted, target)
            scene.processed_asset_path = str(fitted)
            scene.actual_duration_seconds = target
            await AssetRegistry(db).register_file(
                project_id=job.project_id,
                file_path=fitted,
                asset_type="processed_clip",
                source="processed",
                scene_id=scene.scene_id,
                provider="ffmpeg",
            )
            await self._emit(
                job,
                stage="CLIP_PROCESSING",
                scene_id=scene.scene_id,
                message=f"Processed {idx + 1}/{total} — {scene.scene_id}",
                progress_pct=self._intra_stage_pct("CLIP_PROCESSING", idx + 1, total),
                step="fit",
                scene_index=idx + 1,
                scene_total=total,
            )
        ms.save(manifest)

    async def _stage_timeline(self, db: Session, job: Job) -> None:
        ms = ManifestService()
        manifest = ms.load(job.project_id)
        processor = FFmpegVideoProcessor()
        clips = [Path(s.processed_asset_path) for s in manifest.scenes if s.processed_asset_path]
        if not clips:
            raise RuntimeError("No processed clips for timeline assembly")
        await self._emit(
            job,
            stage="TIMELINE_ASSEMBLY",
            message=f"Concatenating {len(clips)} clips ({manifest.settings.transition})",
            step="concat",
            scene_total=len(clips),
        )
        out = project_dir(job.project_id) / "renders" / "timeline_video.mp4"
        await processor.concatenate(
            clips,
            out,
            transition=manifest.settings.transition,
            transition_duration=manifest.settings.transition_duration,
        )
        # Store path in render temporarily
        manifest.render.output_path = str(out)
        ms.save(manifest)

    async def _stage_captions(self, db: Session, job: Job) -> None:
        ms = ManifestService()
        manifest = ms.load(job.project_id)
        audio = Path(manifest.narration.audio_path or "")
        if not audio.exists():
            raise RuntimeError("Narration audio missing for captions")
        from app.engines.content.desi import is_desi_mode

        spoken = manifest.script.full_text or " ".join(s.narration_text for s in manifest.scenes)
        # Desi mode: burn Roman Urdu captions while audio is Urdu TTS
        if is_desi_mode(manifest.settings.content_mode, manifest.settings.language):
            script = (
                manifest.script.caption_text
                or " ".join((s.caption_text or s.narration_text) for s in manifest.scenes)
                or spoken
            )
        else:
            script = (
                manifest.script.caption_text
                or spoken
            )
        caps_dir = project_dir(job.project_id) / "captions"
        provider = DurationCaptionProvider()
        settings = get_settings()
        style = dict(manifest.captions.style or {})
        desi = is_desi_mode(manifest.settings.content_mode, manifest.settings.language)
        style["content_mode"] = manifest.settings.content_mode
        style["project_language"] = manifest.settings.language
        if desi:
            style["desi"] = True
            style["max_words"] = int(
                settings.caption_desi_max_words
                or settings.caption_max_words
                or 10
            )
        elif not style.get("max_words"):
            style["max_words"] = int(settings.caption_max_words or 5)
        from app.engines.captions.language import resolve_whisper_language

        whisper_lang = resolve_whisper_language(
            content_mode=manifest.settings.content_mode,
            project_language=manifest.settings.language,
            spoken_text=spoken,
            configured=settings.caption_whisper_language,
            override=style.get("whisper_language"),
        )
        style["whisper_language"] = whisper_lang or "auto"
        manifest.captions.style = style
        align = "Whisper word align" if settings.caption_whisper_align else "duration pacing"
        lang_note = f" · {whisper_lang or 'auto'}"
        if desi:
            lang_note += " · Roman Urdu captions"
        await self._emit(
            job,
            stage="CAPTION_GENERATION",
            message=f"Building karaoke captions — {align}{lang_note}",
            step="generate",
        )
        result = await provider.generate_captions(
            audio,
            script,
            caps_dir,
            style=style,
            duration_seconds=manifest.narration.duration_seconds,
            spoken_text=spoken if script.strip() != spoken.strip() else None,
        )
        # Also copy to renders naming
        renders = project_dir(job.project_id) / "renders"
        renders.mkdir(parents=True, exist_ok=True)
        srt_final = renders / "final_video.srt"
        ass_final = renders / "final_video.ass"
        srt_final.write_text(Path(result["srt_path"]).read_text(encoding="utf-8"), encoding="utf-8")
        ass_final.write_text(Path(result["ass_path"]).read_text(encoding="utf-8"), encoding="utf-8")
        manifest.captions.srt_path = str(srt_final)
        manifest.captions.ass_path = str(ass_final)
        manifest.captions.status = "completed"
        ms.save(manifest)
        await self._emit(
            job,
            stage="CAPTION_GENERATION",
            message="Captions written (SRT + ASS)",
            step="save",
        )

    async def _stage_final_render(self, db: Session, job: Job) -> None:
        ms = ManifestService()
        manifest = ms.load(job.project_id)
        processor = FFmpegVideoProcessor()
        timeline = Path(manifest.render.output_path or "")
        if not timeline.exists():
            raise RuntimeError("Timeline video missing")
        audio = Path(manifest.narration.audio_path or "")
        ass = Path(manifest.captions.ass_path) if manifest.captions.ass_path else None
        out = project_dir(job.project_id) / "renders" / "final_video.mp4"
        await self._emit(
            job,
            stage="FINAL_RENDER",
            message="Muxing video + narration"
            + (" + burned captions" if ass and ass.exists() else ""),
            step="mux",
        )
        await processor.mux_audio_video(timeline, audio, out, caption_ass=ass)
        from app.engines.video.ffmpeg_runner import probe_media

        info = await probe_media(out)
        manifest.render.output_path = str(out)
        manifest.render.duration_seconds = float(info.get("duration") or 0)
        manifest.render.status = "completed"
        meta = {
            "output_path": str(out),
            "duration_seconds": manifest.render.duration_seconds,
            "probe": {k: info.get(k) for k in ("width", "height", "fps", "video_codec", "audio_codec")},
        }
        meta_path = project_dir(job.project_id) / "renders" / "render_metadata.json"
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        manifest.render.metadata_path = str(meta_path)
        ms.save(manifest)
        await AssetRegistry(db).register_file(
            project_id=job.project_id,
            file_path=out,
            asset_type="render",
            source="render",
            provider="ffmpeg",
        )
        await self._emit(
            job,
            stage="FINAL_RENDER",
            message=f"Final video ready — {manifest.render.duration_seconds:.1f}s",
            step="complete",
            duration_seconds=manifest.render.duration_seconds,
        )

    async def _stage_qa(self, db: Session, job: Job) -> None:
        ms = ManifestService()
        manifest = ms.load(job.project_id)
        render_path = Path(manifest.render.output_path or "")
        await self._emit(
            job,
            stage="QUALITY_ASSURANCE",
            message="Running duration and stream checks",
            step="probe",
        )
        report = await run_qa_checks(manifest, render_path)
        manifest.render.qa_report = report
        manifest.render.qa_status = "completed" if report.get("passed") else "failed"
        if not report.get("passed"):
            ms.save(manifest)
            raise RuntimeError(f"QA failed: {report}")
        ms.save(manifest)
        await self._emit(
            job,
            stage="QUALITY_ASSURANCE",
            message="QA passed — export ready",
            step="pass",
        )


orchestrator = PipelineOrchestrator()
