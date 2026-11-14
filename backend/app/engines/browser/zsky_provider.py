"""Zsky.ai video generation via Playwright CDP automation (alternate provider).

Uses sync Playwright in a worker thread for Windows uvicorn compatibility.
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

from app.core.config import get_settings
from app.core.logging import get_logger
from app.engines.base import VideoGenerationProvider
from app.engines.browser import zsky_selectors as sel
from app.engines.browser.chrome import ensure_chrome_cdp, is_chrome_debugging_alive
from app.engines.video.ffmpeg_runner import validate_video_file_sync

logger = get_logger(__name__)

ProgressCb = Callable[[str], Awaitable[None]] | None


class ZskyAutomationError(RuntimeError):
    def __init__(self, message: str, *, needs_manual: bool = False):
        super().__init__(message)
        self.needs_manual = needs_manual


class ZskyVideoGenerationProvider(VideoGenerationProvider):
    async def check_ready(self) -> dict[str, Any]:
        settings = get_settings()
        alive = is_chrome_debugging_alive()
        return {
            "ready": alive,
            "provider": "zsky",
            "cdp_url": settings.chrome_cdp_url,
            "chrome_running": alive,
            "base_url": settings.zsky_base_url,
            "selectors_verified": False,
            "message": (
                "Chrome CDP reachable"
                if alive
                else "Chrome CDP not running — launch via scripts/launch_chrome_cdp.bat"
            ),
        }

    async def generate_clip(
        self,
        prompt: str,
        output_path: Path,
        *,
        options: dict[str, Any] | None = None,
        on_progress: ProgressCb = None,
    ) -> Path:
        opts = options or {}
        diagnostics_dir = Path(opts.get("diagnostics_dir") or output_path.parent / "diagnostics")
        diagnostics_dir.mkdir(parents=True, exist_ok=True)

        async def progress(msg: str) -> None:
            logger.info(msg)
            if on_progress:
                await on_progress(msg)

        chrome = await ensure_chrome_cdp()
        if not chrome.get("running"):
            raise ZskyAutomationError(
                chrome.get("error") or "Dedicated Chrome CDP instance is not running",
                needs_manual=True,
            )

        await progress("Connecting to Chrome via CDP (sync Playwright worker)")
        progress_log: list[str] = []
        path = await asyncio.to_thread(
            self._generate_clip_sync,
            prompt,
            output_path,
            diagnostics_dir,
            progress_log,
        )
        for msg in progress_log:
            await progress(msg)
        return path

    def _generate_clip_sync(
        self,
        prompt: str,
        output_path: Path,
        diagnostics_dir: Path,
        progress_log: list[str],
    ) -> Path:
        settings = get_settings()
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise ZskyAutomationError("playwright is not installed") from exc

        output_path.parent.mkdir(parents=True, exist_ok=True)
        cdp_endpoint = f"http://127.0.0.1:{settings.chrome_debug_port}"

        def log(msg: str) -> None:
            progress_log.append(msg)
            logger.info(msg)

        with sync_playwright() as p:
            try:
                browser = p.chromium.connect_over_cdp(cdp_endpoint)
            except Exception as exc:
                raise ZskyAutomationError(f"Failed to connect over CDP: {exc}") from exc

            context = browser.contexts[0] if browser.contexts else browser.new_context(
                accept_downloads=True
            )
            page = context.pages[0] if context.pages else context.new_page()

            log(f"Navigating to {settings.zsky_base_url}")
            try:
                page.goto(settings.zsky_base_url, wait_until="domcontentloaded", timeout=60000)
            except Exception as exc:
                self._diagnostics_sync(page, diagnostics_dir, "navigate_failed")
                raise ZskyAutomationError(f"Navigation failed: {exc}") from exc

            if self._matches_any_sync(page, sel.CAPTCHA_SELECTORS):
                self._diagnostics_sync(page, diagnostics_dir, "captcha_detected")
                raise ZskyAutomationError(
                    "CAPTCHA detected — pause for manual intervention",
                    needs_manual=True,
                )
            if self._matches_any_sync(page, sel.LOGIN_SELECTORS):
                self._diagnostics_sync(page, diagnostics_dir, "login_required")
                raise ZskyAutomationError(
                    "Zsky authentication required — log in manually in the dedicated Chrome window, then retry",
                    needs_manual=True,
                )

            prompt_el = self._first_locator_sync(page, sel.PROMPT_INPUT_SELECTORS)
            if not prompt_el:
                self._diagnostics_sync(page, diagnostics_dir, "prompt_input_missing")
                raise ZskyAutomationError(
                    "Could not locate Zsky prompt input — UI selectors may need updating "
                    "(see zsky_selectors.py and diagnostics screenshots)"
                )

            log("Submitting prompt")
            try:
                prompt_el.click()
                prompt_el.fill("")
                prompt_el.fill(prompt)
            except Exception:
                prompt_el.click()
                page.keyboard.press("Control+A")
                page.keyboard.type(prompt, delay=5)

            gen_btn = self._first_locator_sync(page, sel.GENERATE_BUTTON_SELECTORS)
            if not gen_btn:
                self._diagnostics_sync(page, diagnostics_dir, "generate_button_missing")
                raise ZskyAutomationError("Could not locate Generate button")

            gen_btn.click()
            log("Generation started — monitoring UI state")

            started = self._wait_for_any_sync(page, sel.GENERATING_SELECTORS, 15000)
            if not started:
                log("No explicit generating indicator — continuing with download wait")

            dl_btn = self._wait_first_sync(
                page,
                sel.DOWNLOAD_BUTTON_SELECTORS,
                settings.zsky_generation_timeout_seconds * 1000,
            )

            download = None
            if dl_btn:
                log("Download control ready")
                try:
                    with page.expect_download(
                        timeout=settings.zsky_download_timeout_seconds * 1000
                    ) as download_info:
                        dl_btn.click()
                    download = download_info.value
                except Exception as exc:
                    log(f"Download click/expect failed ({exc}); trying video URL fallback")

            if download is None:
                video_url = self._extract_video_url_sync(page)
                if not video_url:
                    self._diagnostics_sync(page, diagnostics_dir, "download_failed")
                    raise ZskyAutomationError(
                        "Generation finished but no download control or video URL was found"
                    )
                log("Fetching video from preview URL")
                self._download_url_sync(page, video_url, output_path)
                validate_video_file_sync(output_path)
                return output_path

            log("Saving download")
            download.save_as(str(output_path))
            if not output_path.exists() or output_path.stat().st_size == 0:
                self._diagnostics_sync(page, diagnostics_dir, "empty_download")
                raise ZskyAutomationError("Downloaded file missing or empty")

            validate_video_file_sync(output_path)
            log(f"Validated clip: {output_path.name}")
            return output_path

    def _matches_any_sync(self, page, selectors: list[str]) -> bool:
        for s in selectors:
            try:
                loc = page.locator(s).first
                if loc.count() > 0 and loc.is_visible():
                    return True
            except Exception:
                continue
        return False

    def _first_locator_sync(self, page, selectors: list[str]):
        for s in selectors:
            try:
                loc = page.locator(s).first
                if loc.count() > 0 and loc.is_visible():
                    return loc
            except Exception:
                continue
        return None

    def _wait_for_any_sync(self, page, selectors: list[str], timeout_ms: int) -> bool:
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            if self._matches_any_sync(page, selectors):
                return True
            time.sleep(0.5)
        return False

    def _wait_first_sync(self, page, selectors: list[str], timeout_ms: int):
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            loc = self._first_locator_sync(page, selectors)
            if loc:
                return loc
            time.sleep(0.75)
        return None

    def _extract_video_url_sync(self, page) -> str | None:
        for s in sel.VIDEO_PREVIEW_SELECTORS:
            try:
                loc = page.locator(s).first
                if loc.count() == 0:
                    continue
                src = loc.get_attribute("src")
                if src:
                    return src
            except Exception:
                continue
        return None

    def _download_url_sync(self, page, url: str, output_path: Path) -> None:
        response = page.request.get(url)
        if not response.ok:
            raise ZskyAutomationError(f"Failed to download video URL: HTTP {response.status}")
        output_path.write_bytes(response.body())

    def _diagnostics_sync(self, page, diagnostics_dir: Path, label: str) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        shot = diagnostics_dir / f"{ts}_{label}.png"
        info = diagnostics_dir / f"{ts}_{label}.txt"
        try:
            page.screenshot(path=str(shot), full_page=True)
        except Exception as exc:
            logger.warning("Screenshot failed: %s", exc)
        try:
            info.write_text(f"url={page.url}\ntitle={page.title()}", encoding="utf-8")
        except Exception as exc:
            logger.warning("Diagnostic info failed: %s", exc)
