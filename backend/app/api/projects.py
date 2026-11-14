"""Project and production endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.paths import open_folder, project_dir
from app.orchestration.pipeline import orchestrator
from app.schemas.content import SceneUpdate
from app.schemas.job import JobResponse, JobStageResponse
from app.schemas.manifest import ManifestScene, ProductionManifest
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.manifest_service import ManifestService
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


def _job_response(job) -> JobResponse:
    return JobResponse(
        id=job.id,
        project_id=job.project_id,
        job_type=job.job_type,
        status=job.status,
        current_stage=job.current_stage,
        error_message=job.error_message,
        retry_count=job.retry_count,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        stages=[
            JobStageResponse(
                stage=s.stage,
                sequence=s.sequence,
                status=s.status,
                retry_count=s.retry_count,
                error_message=s.error_message,
                output_ref=s.output_ref,
                started_at=s.started_at,
                completed_at=s.completed_at,
            )
            for s in (job.stages or [])
        ],
    )


@router.post("", response_model=ProjectResponse)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)):
    return ProjectService(db).create(payload)


@router.get("", response_model=ProjectListResponse)
def list_projects(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    items, total = ProjectService(db).list(skip=skip, limit=limit)
    return ProjectListResponse(items=items, total=total)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, db: Session = Depends(get_db)):
    project = ProjectService(db).get(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: str, payload: ProjectUpdate, db: Session = Depends(get_db)):
    project = ProjectService(db).update(project_id, payload)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.delete("/{project_id}")
def delete_project(project_id: str, db: Session = Depends(get_db)):
    ok = ProjectService(db).delete(project_id)
    if not ok:
        raise HTTPException(404, "Project not found")
    return {"ok": True}


@router.post("/{project_id}/duplicate", response_model=ProjectResponse)
def duplicate_project(project_id: str, db: Session = Depends(get_db)):
    project = ProjectService(db).duplicate(project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    return project


@router.get("/{project_id}/manifest", response_model=ProductionManifest)
def get_manifest(project_id: str, db: Session = Depends(get_db)):
    if not ProjectService(db).get(project_id):
        raise HTTPException(404, "Project not found")
    try:
        return ManifestService().load(project_id)
    except FileNotFoundError:
        raise HTTPException(404, "Manifest not found")


@router.patch("/{project_id}/manifest", response_model=ProductionManifest)
def patch_manifest(project_id: str, payload: dict, db: Session = Depends(get_db)):
    if not ProjectService(db).get(project_id):
        raise HTTPException(404, "Project not found")
    return ManifestService().update(project_id, payload)


@router.get("/{project_id}/scenes")
def list_scenes(project_id: str, db: Session = Depends(get_db)):
    if not ProjectService(db).get(project_id):
        raise HTTPException(404, "Project not found")
    manifest = ManifestService().load(project_id)
    return {"items": manifest.scenes, "total": len(manifest.scenes)}


@router.patch("/{project_id}/scenes/{scene_id}", response_model=ManifestScene)
def update_scene(
    project_id: str, scene_id: str, payload: SceneUpdate, db: Session = Depends(get_db)
):
    if not ProjectService(db).get(project_id):
        raise HTTPException(404, "Project not found")
    ms = ManifestService()
    manifest = ms.load(project_id)
    scene = next((s for s in manifest.scenes if s.scene_id == scene_id), None)
    if not scene:
        raise HTTPException(404, "Scene not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(scene, key, value)
    ms.save(manifest)
    ProjectService(db).sync_scenes_from_manifest(project_id, manifest.scenes)
    return scene


@router.post("/{project_id}/generate-content", response_model=JobResponse)
async def generate_content(project_id: str, db: Session = Depends(get_db)):
    if not ProjectService(db).get(project_id):
        raise HTTPException(404, "Project not found")
    try:
        job = await orchestrator.start_job(db, project_id, "generate_content")
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _job_response(job)


@router.post("/{project_id}/generate-narration", response_model=JobResponse)
async def generate_narration(project_id: str, db: Session = Depends(get_db)):
    if not ProjectService(db).get(project_id):
        raise HTTPException(404, "Project not found")
    try:
        job = await orchestrator.start_job(db, project_id, "generate_narration")
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _job_response(job)


@router.post("/{project_id}/generate-visuals", response_model=JobResponse)
async def generate_visuals(project_id: str, db: Session = Depends(get_db)):
    if not ProjectService(db).get(project_id):
        raise HTTPException(404, "Project not found")
    try:
        job = await orchestrator.start_job(db, project_id, "generate_visuals")
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _job_response(job)


@router.post("/{project_id}/render", response_model=JobResponse)
async def render_project(project_id: str, db: Session = Depends(get_db)):
    if not ProjectService(db).get(project_id):
        raise HTTPException(404, "Project not found")
    try:
        job = await orchestrator.start_job(db, project_id, "render")
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _job_response(job)


@router.post("/{project_id}/run", response_model=JobResponse)
async def run_full_pipeline(project_id: str, db: Session = Depends(get_db)):
    if not ProjectService(db).get(project_id):
        raise HTTPException(404, "Project not found")
    try:
        job = await orchestrator.start_job(db, project_id, "full_pipeline")
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _job_response(job)


@router.post("/{project_id}/scenes/{scene_id}/generate", response_model=JobResponse)
async def generate_scene(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    if not ProjectService(db).get(project_id):
        raise HTTPException(404, "Project not found")
    ms = ManifestService()
    manifest = ms.load(project_id)
    scene = next((s for s in manifest.scenes if s.scene_id == scene_id), None)
    if not scene:
        raise HTTPException(404, "Scene not found")
    # Reset only this scene, keep others completed so orchestrator regenerates only missing... 
    # For single scene we force this scene pending and others stay; visual stage skips completed.
    scene.generation_status = "pending"
    scene.raw_asset_path = None
    scene.processed_asset_path = None
    ms.save(manifest)
    try:
        job = await orchestrator.start_job(db, project_id, "generate_visuals")
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    return _job_response(job)


@router.post("/{project_id}/scenes/{scene_id}/retry", response_model=JobResponse)
async def retry_scene(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    return await generate_scene(project_id, scene_id, db)


@router.get("/{project_id}/media/{media_type}")
def get_media(project_id: str, media_type: str, db: Session = Depends(get_db)):
    if not ProjectService(db).get(project_id):
        raise HTTPException(404, "Project not found")
    manifest = ManifestService().load(project_id)
    mapping = {
        "narration": manifest.narration.mp3_path or manifest.narration.wav_path,
        "render": manifest.render.output_path,
        "srt": manifest.captions.srt_path,
        "ass": manifest.captions.ass_path,
    }
    path = mapping.get(media_type)
    if not path or not Path(path).exists():
        raise HTTPException(404, "Media not found")
    return FileResponse(path)


@router.get("/{project_id}/scenes/{scene_id}/preview")
def scene_preview(project_id: str, scene_id: str, db: Session = Depends(get_db)):
    if not ProjectService(db).get(project_id):
        raise HTTPException(404, "Project not found")
    manifest = ManifestService().load(project_id)
    scene = next((s for s in manifest.scenes if s.scene_id == scene_id), None)
    if not scene:
        raise HTTPException(404, "Scene not found")
    path = scene.processed_asset_path or scene.raw_asset_path
    if not path or not Path(path).exists():
        raise HTTPException(404, "Clip not found")
    return FileResponse(path)


@router.post("/{project_id}/open-folder")
def open_project_folder(project_id: str, db: Session = Depends(get_db)):
    if not ProjectService(db).get(project_id):
        raise HTTPException(404, "Project not found")
    open_folder(project_dir(project_id))
    return {"ok": True, "path": str(project_dir(project_id))}
