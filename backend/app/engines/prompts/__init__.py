"""Prompt template helpers."""

from __future__ import annotations


def format_visual_prompt(
    *,
    subject: str,
    aesthetic: str,
    camera_movement: str,
    extra: str = "",
) -> str:
    return (
        f"{aesthetic}, vertical 9:16 composition, cinematic lighting, "
        f"no text, no subtitles, no watermarks, no talking presenter, no avatar. "
        f"Subject: {subject}. Camera: {camera_movement}. {extra}"
    ).strip()
