"""Central application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root: backend/app/core/config.py -> parents[3] = project-root
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str = ""
    gemini_text_model: str = "gemini-2.0-flash"
    gemini_tts_model: str = "gemini-2.5-flash-preview-tts"

    backend_host: str = "127.0.0.1"
    backend_port: int = 8000
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    chrome_path: str = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    chrome_debug_port: int = 9222
    chrome_user_data_dir: str = "./data/chrome-profile"

    # Live visual provider: snapgen (default) | zsky
    video_gen_provider: Literal["snapgen", "zsky"] = "snapgen"

    snapgen_base_url: str = "https://snapgen.ai/app/video-gen/muse?mode=create-new"
    snapgen_generation_timeout_seconds: int = 300
    snapgen_download_timeout_seconds: int = 120
    # Muse (and similar) emit fixed-length clips; scene count = ceil(target / this)
    visual_clip_duration_seconds: float = 10.0
    # Snapgen Muse has no end-credit bumper — keep full clip
    snapgen_end_trim_seconds: float = 0.0

    # Kept as alternate provider
    zsky_base_url: str = "https://zsky.ai/create"
    zsky_generation_timeout_seconds: int = 300
    zsky_download_timeout_seconds: int = 120
    # Zsky often appends a branded credit frame; trim it off before assembly
    zsky_end_trim_seconds: float = 0.8

    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"

    database_url: str = ""

    log_level: str = "INFO"
    speaking_rate_wpm: int = 150

    default_width: int = 1080
    default_height: int = 1920
    default_fps: int = 30
    default_transition: str = "hard_cut"
    default_transition_duration: float = 0.3
    gap_fill_strategy: Literal["freeze_frame", "slow_motion", "reuse_clip"] = "freeze_frame"

    # Brainrot-style captions
    caption_preset: Literal["classic", "hormozi", "outline"] = "classic"
    # More words per on-screen chunk reads better for Roman Urdu / desi
    caption_max_words: int = 8
    caption_desi_max_words: int = 10
    caption_font_latin: str = "Arial Black"
    caption_font_urdu: str = "Segoe UI"
    caption_font_devanagari: str = "Nirmala UI"

    # Keep Snapgen/Zsky clip audio under narration (0 = mute bed, 1 = full)
    scene_audio_enabled: bool = True
    scene_audio_volume: float = 0.22

    # Whisper word-level caption timing (near-perfect karaoke)
    caption_whisper_align: bool = True
    caption_whisper_model: str = "small"
    # auto | en | ur | … — auto picks from project language (English→en, Desi/Urdu→ur)
    caption_whisper_language: str = "auto"


    data_dir: Path = Field(default_factory=lambda: PROJECT_ROOT / "data")

    @field_validator("chrome_user_data_dir", mode="before")
    @classmethod
    def resolve_chrome_dir(cls, v: str) -> str:
        path = Path(v)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return str(path.resolve())

    def model_post_init(self, __context: object) -> None:  # noqa: N805
        if not self.database_url:
            db_path = (PROJECT_ROOT / "data" / "database" / "app.db").resolve()
            object.__setattr__(self, "database_url", f"sqlite:///{db_path.as_posix()}")
        elif self.database_url.startswith("sqlite:///./"):
            rel = self.database_url.replace("sqlite:///./", "", 1)
            db_path = (PROJECT_ROOT / rel).resolve()
            object.__setattr__(self, "database_url", f"sqlite:///{db_path.as_posix()}")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def projects_dir(self) -> Path:
        return self.data_dir / "projects"

    @property
    def database_dir(self) -> Path:
        return self.data_dir / "database"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def chrome_cdp_url(self) -> str:
        return f"http://127.0.0.1:{self.chrome_debug_port}"

    def ensure_directories(self) -> None:
        for path in (
            self.data_dir,
            self.projects_dir,
            self.database_dir,
            self.logs_dir,
            self.data_dir / "assets",
            self.data_dir / "exports",
            Path(self.chrome_user_data_dir),
        ):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
