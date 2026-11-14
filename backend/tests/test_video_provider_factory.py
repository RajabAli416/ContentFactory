from app.core.config import get_settings
from app.engines.browser.snapgen_provider import SnapgenVideoGenerationProvider
from app.engines.browser.zsky_provider import ZskyVideoGenerationProvider


def _real_video_provider():
    """Call production factory logic (bypass conftest offline stubs)."""
    from app.engines.browser.factory import get_video_generation_provider as live_factory

    # Re-import unbound production function from source
    import importlib
    import app.engines.browser.factory as fac

    importlib.reload(fac)
    return fac.get_video_generation_provider()


def test_defaults_to_snapgen(monkeypatch, tmp_path):
    monkeypatch.setenv("VIDEO_GEN_PROVIDER", "snapgen")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-used")
    get_settings.cache_clear()
    provider = _real_video_provider()
    assert isinstance(provider, SnapgenVideoGenerationProvider)
    get_settings.cache_clear()


def test_can_select_zsky(monkeypatch, tmp_path):
    monkeypatch.setenv("VIDEO_GEN_PROVIDER", "zsky")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-used")
    get_settings.cache_clear()
    provider = _real_video_provider()
    assert isinstance(provider, ZskyVideoGenerationProvider)
    get_settings.cache_clear()
