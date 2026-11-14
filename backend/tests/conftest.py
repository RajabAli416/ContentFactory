"""Pytest fixtures — temp data dirs + offline mock providers for CI."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("LOG_LEVEL", "WARNING")
# Tests never call real Gemini; key placeholder satisfies require_api_key when
# factories are not patched (patched tests use Mock* providers instead).
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-used")


@pytest.fixture()
def tmp_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data = tmp_path / "data"
    (data / "projects").mkdir(parents=True)
    (data / "database").mkdir(parents=True)
    (data / "logs").mkdir(parents=True)

    db_url = f"sqlite:///{(data / 'database' / 'test.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-used")

    from app.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    object.__setattr__(settings, "data_dir", data)
    object.__setattr__(settings, "database_url", db_url)
    settings.ensure_directories()

    # Rebuild engine against temp DB
    from app.core import database as dbmod
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(db_url, connect_args={"check_same_thread": False})
    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from app import models  # noqa: F401
    from app.core.database import Base

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # Offline providers for pipeline / media tests (production is live-only)
    from app.engines.browser.mock_provider import MockVideoGenerationProvider
    from app.engines.content.mock_provider import MockContentProvider
    from app.engines.narration.mock_provider import MockTTSProvider

    monkeypatch.setattr(
        "app.engines.content.factory.get_content_provider",
        lambda: MockContentProvider(),
    )
    monkeypatch.setattr(
        "app.engines.narration.factory.get_tts_provider",
        lambda: MockTTSProvider(),
    )
    monkeypatch.setattr(
        "app.engines.browser.factory.get_video_generation_provider",
        lambda: MockVideoGenerationProvider(),
    )
    monkeypatch.setattr(
        "app.orchestration.pipeline.get_content_provider",
        lambda: MockContentProvider(),
    )
    monkeypatch.setattr(
        "app.orchestration.pipeline.get_tts_provider",
        lambda: MockTTSProvider(),
    )
    monkeypatch.setattr(
        "app.orchestration.pipeline.get_video_generation_provider",
        lambda: MockVideoGenerationProvider(),
    )

    yield settings

    get_settings.cache_clear()


@pytest.fixture()
def client(tmp_data):
    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c
