"""Resolve Whisper ASR language from project / narration settings."""

from __future__ import annotations

import re

_ARABIC = re.compile(r"[\u0600-\u06FF\u0750-\u077F]")

# Map common project language labels → Whisper language codes
_LANG_ALIASES: dict[str, str] = {
    "en": "en",
    "eng": "en",
    "english": "en",
    "ur": "ur",
    "urd": "ur",
    "urdu": "ur",
    "hi": "hi",
    "hin": "hi",
    "hindi": "hi",
    "ar": "ar",
    "ara": "ar",
    "arabic": "ar",
    "es": "es",
    "spa": "es",
    "spanish": "es",
    "fr": "fr",
    "fra": "fr",
    "french": "fr",
    "de": "de",
    "deu": "de",
    "german": "de",
    "pt": "pt",
    "por": "pt",
    "portuguese": "pt",
    "id": "id",
    "ind": "id",
    "indonesian": "id",
    "tr": "tr",
    "tur": "tr",
    "turkish": "tr",
}


def normalize_whisper_language(value: str | None) -> str | None:
    """Return a Whisper language code, or None for auto-detect."""
    if value is None:
        return None
    raw = str(value).strip().lower()
    if raw in {"", "auto", "none", "detect"}:
        return None
    if raw in _LANG_ALIASES:
        return _LANG_ALIASES[raw]
    # Already a short code like "en", "ur"
    if re.fullmatch(r"[a-z]{2}", raw):
        return raw
    return _LANG_ALIASES.get(raw.split("-")[0], raw[:2] if len(raw) >= 2 else None)


def resolve_whisper_language(
    *,
    content_mode: str | None = None,
    project_language: str | None = None,
    spoken_text: str | None = None,
    configured: str | None = None,
    override: str | None = None,
) -> str | None:
    """Pick Whisper language for caption alignment.

    Priority:
    1. Explicit override (per-run style)
    2. Configured env value if not auto
    3. Desi / Urdu project → ur
    4. Project language label → mapped code
    5. Arabic-script spoken text → ur
    6. Otherwise → en (English default for standard projects)
    """
    if override is not None and str(override).strip():
        forced = normalize_whisper_language(override)
        # "auto" / empty normalize to None → keep resolving from project
        if forced is not None:
            return forced

    # Only honor a concrete configured language; "auto"/empty falls through
    if configured and str(configured).strip().lower() not in {"", "auto", "none", "detect"}:
        configured_norm = normalize_whisper_language(configured)
        if configured_norm:
            return configured_norm

    mode = (content_mode or "").strip().lower()
    lang_label = (project_language or "").strip().lower()

    if mode == "desi" or lang_label in {"urdu", "ur", "urd"}:
        return "ur"

    # Audio script beats a mismatched label (e.g. English project with Urdu TTS text)
    if spoken_text and _ARABIC.search(spoken_text):
        return "ur"

    mapped = normalize_whisper_language(project_language)
    if mapped:
        return mapped

    return "en"
