"""Snapgen Muse video generation via Playwright CDP automation.

Uses sync Playwright inside a worker thread so Windows event loops that lack
asyncio subprocess support (common with uvicorn --reload) still work.
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
from app.engines.browser import snapgen_selectors as sel
from app.engines.browser.chrome import ensure_chrome_cdp, is_chrome_debugging_alive
from app.engines.video.ffmpeg_runner import validate_video_file_sync

logger = get_logger(__name__)

ProgressCb = Callable[[str], Awaitable[None]] | None


class SnapgenAutomationError(RuntimeError):
    def __init__(self, message: str, *, needs_manual: bool = False):
        super().__init__(message)
        self.needs_manual = needs_manual


class SnapgenVideoGenerationProvider(VideoGenerationProvider):
    async def check_ready(self) -> dict[str, Any]:
        settings = get_settings()
        alive = is_chrome_debugging_alive()
        return {
            "ready": alive,
            "provider": "snapgen",
            "cdp_url": settings.chrome_cdp_url,
            "chrome_running": alive,
            "base_url": settings.snapgen_base_url,
            "selectors_verified": True,
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
            raise SnapgenAutomationError(
                chrome.get("error") or "Dedicated Chrome CDP instance is not running",
                needs_manual=True,
            )

        await progress("Connecting to Chrome via CDP (sync Playwright worker)")
        progress_log: list[str] = []
        # Run sync Playwright off the event loop — avoids Windows NotImplementedError
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
            raise SnapgenAutomationError("playwright is not installed") from exc

        output_path.parent.mkdir(parents=True, exist_ok=True)
        cdp_endpoint = f"http://127.0.0.1:{settings.chrome_debug_port}"

        def log(msg: str) -> None:
            progress_log.append(msg)
            logger.info(msg)

        with sync_playwright() as p:
            try:
                browser = p.chromium.connect_over_cdp(cdp_endpoint)
            except Exception as exc:
                raise SnapgenAutomationError(f"Failed to connect over CDP: {exc}") from exc

            context = browser.contexts[0] if browser.contexts else browser.new_context(
                accept_downloads=True
            )
            page = context.pages[0] if context.pages else context.new_page()

            log(f"Navigating to {settings.snapgen_base_url}")
            try:
                page.goto(
                    settings.snapgen_base_url,
                    wait_until="domcontentloaded",
                    timeout=60000,
                )
            except Exception as exc:
                self._diagnostics_sync(page, diagnostics_dir, "navigate_failed")
                raise SnapgenAutomationError(f"Navigation failed: {exc}") from exc

            if self._matches_any_sync(page, sel.CAPTCHA_SELECTORS):
                self._diagnostics_sync(page, diagnostics_dir, "captcha_detected")
                raise SnapgenAutomationError(
                    "CAPTCHA detected — pause for manual intervention",
                    needs_manual=True,
                )
            if self._matches_any_sync(page, sel.LOGIN_SELECTORS):
                self._diagnostics_sync(page, diagnostics_dir, "login_required")
                raise SnapgenAutomationError(
                    "Snapgen authentication required — log in manually in the dedicated "
                    "Chrome window, then retry",
                    needs_manual=True,
                )

            # Give the React app time to hydrate the Muse create form
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                log("networkidle wait timed out — continuing")

            muse_btn = self._first_locator_sync(page, sel.MUSE_MODEL_SELECTORS, require_visible=False)
            if muse_btn:
                try:
                    muse_btn.scroll_into_view_if_needed(timeout=3000)
                    muse_btn.click(timeout=3000)
                    log("Selected Muse AI model")
                    time.sleep(0.8)
                except Exception:
                    log("Muse model control present but not clickable — continuing")

            aspect = self._first_locator_sync(page, sel.ASPECT_RATIO_9_16_SELECTORS)
            if aspect:
                try:
                    aspect.scroll_into_view_if_needed(timeout=3000)
                    aria = aspect.get_attribute("aria-checked")
                    if aria != "true":
                        aspect.click(timeout=3000)
                    log("Ensured Portrait (9:16) orientation")
                except Exception:
                    log("Could not set 9:16 — continuing with defaults")

            prompt_el = self._wait_for_prompt_sync(page, timeout_ms=30000)
            if not prompt_el:
                self._diagnostics_sync(page, diagnostics_dir, "prompt_input_missing")
                raise SnapgenAutomationError(
                    "Could not locate Snapgen prompt input — UI selectors may need updating "
                    "(see snapgen_selectors.py and diagnostics screenshots)"
                )

            log("Submitting Snapgen prompt")
            try:
                prompt_el.scroll_into_view_if_needed(timeout=5000)
                prompt_el.click(timeout=5000)
                prompt_el.fill("")
                prompt_el.fill(prompt)
            except Exception:
                prompt_el.click(timeout=5000)
                page.keyboard.press("Control+A")
                page.keyboard.type(prompt, delay=5)

            gen_btn = self._wait_enabled_button_sync(
                page, sel.GENERATE_BUTTON_SELECTORS, timeout_ms=10000
            )
            if not gen_btn:
                self._diagnostics_sync(page, diagnostics_dir, "generate_button_missing")
                raise SnapgenAutomationError("Could not locate/enable Snapgen Generate button")

            gen_btn.click()
            log("Snapgen generation started — monitoring UI state")

            started = self._wait_for_any_sync(
                page, sel.GENERATING_SELECTORS, timeout_ms=15000
            )
            if not started:
                log("No explicit generating indicator — continuing with download wait")

            # Wait for completion UI, then download via button or video URL.
            # expect_download is on Page (not BrowserContext) in Playwright sync API.
            dl_btn = self._wait_first_sync(
                page,
                sel.DOWNLOAD_BUTTON_SELECTORS,
                timeout_ms=settings.snapgen_generation_timeout_seconds * 1000,
            )

            download = None
            if dl_btn:
                log("Download control ready")
                try:
                    with page.expect_download(
                        timeout=settings.snapgen_download_timeout_seconds * 1000
                    ) as download_info:
                        dl_btn.click()
                    download = download_info.value
                except Exception as exc:
                    log(f"Download click/expect failed ({exc}); trying video URL fallback")

            if download is None:
                video_url = self._extract_video_url_sync(page)
                if not video_url:
                    self._diagnostics_sync(page, diagnostics_dir, "download_failed")
                    raise SnapgenAutomationError(
                        "Generation finished but no download control or video URL was found"
                    )
                log("Fetching video from preview URL")
                self._download_url_sync(page, video_url, output_path)
                self._validate_sync(output_path)
                return output_path

            log("Saving Snapgen download")
            download.save_as(str(output_path))
            if not output_path.exists() or output_path.stat().st_size == 0:
                self._diagnostics_sync(page, diagnostics_dir, "empty_download")
                raise SnapgenAutomationError("Downloaded file missing or empty")

            self._validate_sync(output_path)
            log(f"Validated Snapgen clip: {output_path.name}")
            return output_path

    def _validate_sync(self, path: Path) -> None:
        validate_video_file_sync(path)

    def _matches_any_sync(self, page, selectors: list[str]) -> bool:
        for s in selectors:
            try:
                loc = page.locator(s).first
                if loc.count() > 0 and loc.is_visible():
                    return True
            except Exception:
                continue
        return False

    def _first_locator_sync(self, page, selectors: list[str], *, require_visible: bool = True):
        for s in selectors:
            try:
                loc = page.locator(s).first
                if loc.count() == 0:
                    continue
                if require_visible and not loc.is_visible():
                    # Off-screen / collapsed — still usable after scroll
                    try:
                        loc.scroll_into_view_if_needed(timeout=2000)
                    except Exception:
                        continue
                return loc
            except Exception:
                continue
        return None

    def _wait_for_prompt_sync(self, page, timeout_ms: int = 30000):
        """Prefer Playwright placeholder/role APIs, then CSS fallbacks."""
        deadline = time.time() + timeout_ms / 1000

        # Strongest match from the live Muse create UI
        try:
            loc = page.get_by_placeholder(sel.PROMPT_PLACEHOLDER)
            loc.first.wait_for(state="attached", timeout=min(timeout_ms, 20000))
            el = loc.first
            el.scroll_into_view_if_needed(timeout=5000)
            return el
        except Exception:
            pass

        try:
            loc = page.get_by_role("textbox", name=sel.PROMPT_PLACEHOLDER)
            if loc.count() > 0:
                el = loc.first
                el.scroll_into_view_if_needed(timeout=5000)
                return el
        except Exception:
            pass

        while time.time() < deadline:
            el = self._first_locator_sync(
                page, sel.PROMPT_INPUT_SELECTORS, require_visible=False
            )
            if el:
                try:
                    el.scroll_into_view_if_needed(timeout=3000)
                except Exception:
                    pass
                return el
            # Nudge page in case the create form is below the hero/examples
            try:
                page.mouse.wheel(0, 800)
            except Exception:
                pass
            time.sleep(0.4)
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

    def _wait_enabled_button_sync(self, page, selectors: list[str], timeout_ms: int):
        deadline = time.time() + timeout_ms / 1000
        while time.time() < deadline:
            for s in selectors:
                try:
                    loc = page.locator(s).first
                    if loc.count() == 0:
                        continue
                    if loc.is_visible() and loc.is_enabled():
                        return loc
                except Exception:
                    continue
            time.sleep(0.25)
        return self._first_locator_sync(page, selectors)

    def _extract_video_url_sync(self, page) -> str | None:
        for s in sel.VIDEO_PREVIEW_SELECTORS:
            try:
                loc = page.locator(s).first
                if loc.count() == 0:
                    continue
                href = loc.get_attribute("href")
                if href and ".mp4" in href:
                    return href
                src = loc.get_attribute("src")
                if src:
                    return src
            except Exception:
                continue
        return None

    def _download_url_sync(self, page, url: str, output_path: Path) -> None:
        response = page.request.get(url)
        if not response.ok:
            raise SnapgenAutomationError(f"Failed to download video URL: HTTP {response.status}")
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
            content = [f"url={page.url}", f"title={page.title()}"]
            info.write_text("\n".join(content), encoding="utf-8")
        except Exception as exc:
            logger.warning("Diagnostic info failed: %s", exc)
