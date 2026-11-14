"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager

# Windows: ProactorEventLoop is required for subprocess support (Playwright/FFmpeg).
# Uvicorn --reload can otherwise leave a SelectorEventLoop that raises NotImplementedError.
if sys.platform == "win32" and hasattr(asyncio, "WindowsProactorEventLoopPolicy"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import jobs, projects, system
from app.core.config import get_settings
from app.core.database import init_db
from app.core.logging import setup_logging
from app.orchestration.progress import progress_hub


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(settings.log_level)
    settings.ensure_directories()
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="ContentFactory",
        description="AI-powered faceless short-form video production system",
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(system.router, prefix="/api/v1")
    app.include_router(projects.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")

    @app.websocket("/ws/jobs/{job_id}")
    async def ws_jobs(websocket: WebSocket, job_id: str):
        await progress_hub.connect(job_id, websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            await progress_hub.disconnect(job_id, websocket)

    @app.get("/")
    async def root():
        return {"name": "ContentFactory", "version": __version__, "docs": "/docs"}

    return app


app = create_app()
