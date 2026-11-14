"""Centralized Zsky UI selectors.

These have NOT been independently verified against the live Zsky interface.
Update this module when diagnostics reveal stable attributes.
Prefer role/label/placeholder over positional CSS.
"""

from __future__ import annotations

# Navigation
CREATE_URL_FRAGMENT = "/create"

# Prompt input candidates (tried in order)
PROMPT_INPUT_SELECTORS = [
    'textarea[placeholder*="prompt" i]',
    'textarea[placeholder*="describe" i]',
    'textarea[aria-label*="prompt" i]',
    '[contenteditable="true"]',
    "textarea",
]

# Submit / generate button candidates
GENERATE_BUTTON_SELECTORS = [
    'button:has-text("Generate")',
    'button:has-text("Create")',
    'button:has-text("Submit")',
    'button[type="submit"]',
    '[data-testid="generate"]',
]

# Generation in-progress indicators
GENERATING_SELECTORS = [
    'text=/generat(ing|e)/i',
    '[role="progressbar"]',
    ".loading",
    ".spinner",
]

# Ready / download indicators
DOWNLOAD_BUTTON_SELECTORS = [
    'button:has-text("Download")',
    'a:has-text("Download")',
    '[download]',
    '[data-testid="download"]',
]

# Auth / challenge detection
LOGIN_SELECTORS = [
    'button:has-text("Log in")',
    'button:has-text("Sign in")',
    'input[type="password"]',
    'text=/sign in/i',
]

CAPTCHA_SELECTORS = [
    'iframe[src*="captcha"]',
    'iframe[src*="recaptcha"]',
    'text=/captcha/i',
    "#challenge-form",
]

# Video preview
VIDEO_PREVIEW_SELECTORS = [
    "video",
    "video source",
]
