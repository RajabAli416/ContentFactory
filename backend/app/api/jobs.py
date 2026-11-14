"""Job management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db
from app.models.job import Job
from app.orchestration.pipeline import orchestrator
from app.orchestration.progress import progress_hub
from app.schemas.job import JobListResponse, JobResponse, JobStageResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _job_response(job: Job) -> JobResponse:
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


@router.get("", response_model=JobListResponse)
def list_jobs(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    q = db.query(Job).options(joinedload(Job.stages)).order_by(Job.created_at.desc())
    total = q.count()
    items = q.offset(skip).limit(limit).all()
    return JobListResponse(items=[_job_response(j) for j in items], total=total)


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.query(Job).options(joinedload(Job.stages)).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    return _job_response(job)


@router.post("/{job_id}/pause", response_model=JobResponse)
async def pause_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    await orchestrator.pause(job_id)
    db.refresh(job)
    return _job_response(job)


@router.post("/{job_id}/resume", response_model=JobResponse)
async def resume_job(job_id: str, db: Session = Depends(get_db)):
    try:
        job = await orchestrator.resume(db, job_id)
    except FileNotFoundError:
        raise HTTPException(404, "Job not found")
    return _job_response(job)


@router.post("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(job_id: str, db: Session = Depends(get_db)):
    job = await orchestrator.cancel(db, job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return _job_response(job)


@router.websocket("/ws/{job_id}")
async def job_ws(websocket: WebSocket, job_id: str):
    # Note: mounted under /api/v1 via include; also expose at /ws/jobs/{id} from main
    await progress_hub.connect(job_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await progress_hub.disconnect(job_id, websocket)
