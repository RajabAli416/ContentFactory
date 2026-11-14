"""Desi mode helpers: Urdu speech + Roman Urdu captions + PK/IN TikTok packaging."""

from __future__ import annotations

from typing import Any

# Evergreen discovery tags that routinely surface on TikTok in PK/IN feeds.
# Mix of market tags + broad discovery — topic-specific tags are added by Gemini.
DESI_CORE_HASHTAGS: list[str] = [
    "#fyp",
    "#foryou",
    "#foryoupage",
    "#viral",
    "#trending",
    "#desi",
    "#desivibes",
    "#southasia",
]

PAKISTAN_HASHTAGS: list[str] = [
    "#pakistan",
    "#pakistani",
    "#pakistantiktok",
    "#lahore",
    "#karachi",
    "#islamabad",
    "#urdupoetry",
    "#urdustatus",
    "#urdutiktok",
    "#pakistanifyp",
]

INDIA_HASHTAGS: list[str] = [
    "#india",
    "#indian",
    "#indiantiktok",
    "#delhi",
    "#mumbai",
    "#bollywood",
    "#hindi",
    "#desicontent",
    "#indianfyp",
]

DESI_CONTENT_HASHTAGS: list[str] = [
    "#facts",
    "#didyouknow",
    "#storytime",
    "#mindblown",
    "#romanurdu",
    "#urdu",
    "#desifacts",
]

DESI_TTS_STYLE = (
    "Speak clear Pakistani Urdu with a natural conversational short-form cadence. "
    "Urdu, Pakistani accent. No English narration unless a brand name must stay English."
)

DESI_LANGUAGE_RULES = """
DESI MODE LANGUAGE RULES (critical):
- Narration / full_script / each scene narration_text: write in Urdu using Urdu
  (Arabic/Nastaliq) script. This text is sent to TTS — write exactly what should be spoken.
  No emojis, no stage directions, no markdown.
- Caption fields (caption_text, each scene caption_text): write the SAME meaning in
  Roman Urdu using Latin letters the way people text in Pakistan/India
  (e.g. "sab se bada raaz yeh hai"). Same beat order as narration.
- Title/hook/closing_line: Urdu script for hook/closing; title may be Roman Urdu or Urdu.
- Keep spoken Urdu natural for TikTok — short punchy lines, strong hook in first 2 seconds.
- Visual prompts stay in English (for the image/video model).
"""

DESI_PACKAGING_RULES = """
PACKAGING (TikTok PK + IN engagement):
Return a "packaging" object with:
- post_title: short scroll-stopping title (Roman Urdu or mix), max ~70 chars
- post_caption: ready-to-paste TikTok caption in Roman Urdu / Hinglish, 1-3 lines,
  hook + curiosity, invite comment. No hashtag soup inside this string.
- hashtags: 12-18 tags as strings starting with #. Prioritize high-reach Pakistan and
  India TikTok discovery tags relevant to this topic, plus evergreen #fyp/#viral style tags.
  Prefer tags people actually search/browse in PK/IN (desi, pakistan, india, urdu, storytime,
  facts, city tags when relevant). Avoid banned/spammy nonsense.
- markets: ["pakistan", "india"]
"""


def is_desi_mode(mode: str | None, language: str | None = None) -> bool:
    m = (mode or "").strip().lower()
    if m in {"desi", "roman_urdu", "urdu_desi"}:
        return True
    lang = (language or "").strip().lower().replace(" ", "_")
    return lang in {"desi", "roman_urdu"}


def merge_hashtags(*groups: list[str], limit: int = 18) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for group in groups:
        for tag in group:
            t = tag.strip()
            if not t:
                continue
            if not t.startswith("#"):
                t = f"#{t.lstrip('#')}"
            key = t.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(t)
            if len(out) >= limit:
                return out
    return out


def default_desi_hashtags(topic: str = "") -> list[str]:
    topic_bits: list[str] = []
    clean = "".join(ch if ch.isalnum() else " " for ch in (topic or "").lower())
    for word in clean.split():
        if len(word) >= 4:
            topic_bits.append(f"#{word}")
        if len(topic_bits) >= 3:
            break
    return merge_hashtags(
        DESI_CORE_HASHTAGS,
        PAKISTAN_HASHTAGS[:6],
        INDIA_HASHTAGS[:5],
        DESI_CONTENT_HASHTAGS,
        topic_bits,
    )


def build_packaging(
    *,
    title: str,
    hook: str,
    topic: str,
    hashtags: list[str] | None = None,
    post_caption: str | None = None,
    post_title: str | None = None,
) -> dict[str, Any]:
    tags = merge_hashtags(hashtags or [], default_desi_hashtags(topic))
    caption = (post_caption or "").strip() or (
        f"{hook}\n\nFollow for more desi facts 🔥"
        if hook
        else f"{topic} — poori kahani caption mein nahi samati 👀"
    )
    return {
        "post_title": (post_title or title or topic)[:80],
        "post_caption": caption,
        "hashtags": tags,
        "hashtag_string": " ".join(tags),
        "markets": ["pakistan", "india"],
        "caption_script": "roman_urdu",
        "spoken_script": "urdu",
    }


def desi_tts_style(extra: str | None = None) -> str:
    base = DESI_TTS_STYLE
    if extra and extra.strip():
        return f"{base} {extra.strip()}"
    return base
