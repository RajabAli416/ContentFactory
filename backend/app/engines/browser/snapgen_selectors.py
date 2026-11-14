"""Centralized Snapgen Muse UI selectors.

Target: https://snapgen.ai/app/video-gen/muse?mode=create-new
"""

from __future__ import annotations

CREATE_URL_FRAGMENT = "/app/video-gen/muse"

PROMPT_PLACEHOLDER = "Describe the video you want to generate..."

MUSE_MODEL_SELECTORS = [
    'button:has-text("Muse AI")',
    'button:has-text("Muse")',
]

PROMPT_INPUT_SELECTORS = [
    f'textarea[placeholder="{PROMPT_PLACEHOLDER}"]',
    f'textarea[placeholder*="Describe the video" i]',
    'textarea[placeholder*="Describe" i]',
    "textarea",
]

ASPECT_RATIO_9_16_SELECTORS = [
    'label:has-text("Portrait (9:16)")',
    '[role="radio"]:has-text("Portrait (9:16)")',
    'text=Portrait (9:16)',
    'button:has-text("9:16")',
]

GENERATE_BUTTON_SELECTORS = [
    'button:has-text("Generate with Muse AI")',
    'button:has-text("Generate video")',
    'button:has-text("Generate")',
]

GENERATING_SELECTORS = [
    'text=/Generating/i',
    'text=/Processing/i',
    'text=/Queued/i',
    '[role="progressbar"]',
    ".loading",
    ".spinner",
]

DOWNLOAD_BUTTON_SELECTORS = [
    'button:has-text("Download")',
    'a:has-text("Download")',
    '[download]',
    'button[aria-label*="Download" i]',
]

VIDEO_PREVIEW_SELECTORS = [
    "video",
    "video source",
    'a[href*=".mp4"]',
]

# Only treat as hard login wall when a password field is present.
# Nav "Sign in" links alone are not enough (false positives on marketing chrome).
LOGIN_SELECTORS = [
    'form input[type="password"]',
    'input[type="password"]',
]

CAPTCHA_SELECTORS = [
    'iframe[src*="captcha"]',
    'iframe[src*="recaptcha"]',
    'text=/captcha/i',
    "#challenge-form",
]
