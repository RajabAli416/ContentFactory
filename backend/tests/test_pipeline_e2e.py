"""Offline end-to-end pipeline (stub providers) producing a valid MP4."""

from __future__ import annotations

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_full_pipeline_offline(tmp_data):
    from app.main import create_app
    from app.orchestration.pipeline import orchestrator
    from app.core import database as dbmod
    from app.services.project_service import ProjectService
    from app.schemas.project import ProjectCreate

    app = create_app()

    # Create project via service (same as API)
    db = dbmod.SessionLocal()
    try:
        project = ProjectService(db).create(
            ProjectCreate(
                topic="Why deserts bloom after rare rain",
                target_duration_seconds=20,
                title="Desert Bloom",
            )
        )
        project_id = project.id
        job = await orchestrator.start_job(db, project_id, "full_pipeline")
        job_id = job.id
    finally:
        db.close()

    # Await the background task
    task = orchestrator._tasks.get(job_id)
    if task:
        await task
    else:
        # Task may have finished extremely quickly
        await __import__("asyncio").sleep(0.2)

    db = dbmod.SessionLocal()
    try:
        from app.models.job import Job

        job = db.get(Job, job_id)
        assert job is not None
        assert job.status == "COMPLETED", job.error_message
    finally:
        db.close()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(f"/api/v1/projects/{project_id}/manifest")
        assert res.status_code == 200
        manifest = res.json()
        assert manifest["script"]["full_text"]
        assert len(manifest["scenes"]) >= 2
        assert manifest["narration"]["status"] == "completed"
        assert all(s["generation_status"] == "completed" for s in manifest["scenes"])
        assert manifest["captions"]["status"] == "completed"
        assert manifest["render"]["status"] == "completed"
        assert manifest["render"]["qa_status"] == "completed"

        out = Path(manifest["render"]["output_path"])
        assert out.exists()
        assert out.stat().st_size > 1000

        media = await client.get(f"/api/v1/projects/{project_id}/media/render")
        assert media.status_code == 200
