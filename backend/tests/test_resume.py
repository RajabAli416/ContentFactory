"""Resume must not regenerate completed expensive stages."""

from __future__ import annotations

import pytest

from app.core import database as dbmod
from app.orchestration.pipeline import PipelineOrchestrator
from app.schemas.project import ProjectCreate
from app.services.manifest_service import ManifestService
from app.services.project_service import ProjectService


@pytest.mark.asyncio
async def test_skip_completed_visuals(tmp_data):
    db = dbmod.SessionLocal()
    try:
        project = ProjectService(db).create(
            ProjectCreate(topic="Resume test topic", target_duration_seconds=15)
        )
        orch = PipelineOrchestrator()
        from app.models.job import Job

        job1 = await orch.start_job(db, project.id, "full_pipeline")
        await orch._tasks[job1.id]
        db.expire_all()
        assert db.get(Job, job1.id).status == "COMPLETED"

        manifest = ManifestService().load(project.id)
        raw_paths = [s.raw_asset_path for s in manifest.scenes]
        assert all(raw_paths)

        # Second full run should skip content/narration/visuals via _should_skip_stage
        assert await orch._should_skip_stage(project.id, "CONTENT_GENERATION")
        assert await orch._should_skip_stage(project.id, "NARRATION_GENERATION")
        assert await orch._should_skip_stage(project.id, "VISUAL_GENERATION")
        assert await orch._should_skip_stage(project.id, "FINAL_RENDER")
    finally:
        db.close()
