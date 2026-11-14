"""Gemini structured content generation."""

from __future__ import annotations

import json
import re

from app.core.ai_config import get_ai_config
from app.core.logging import get_logger
from app.engines.base import ContentProvider
from app.engines.content.mock_provider import _estimate_duration
from app.engines.content.desi import (
    DESI_LANGUAGE_RULES,
    DESI_PACKAGING_RULES,
    build_packaging,
    is_desi_mode,
    merge_hashtags,
    default_desi_hashtags,
)
from app.engines.content.scene_budget import (
    normalize_scenes_to_budget,
    planned_scene_count,
    visual_clip_duration_seconds,
)
from app.schemas.content import (
    ContentGenerationRequest,
    ContentGenerationResult,
    ContentPackaging,
    GeneratedScene,
)

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are a short-form faceless video scriptwriter and visual director.
Produce narration-led vertical video plans. The narrator is OFF-SCREEN voiceover only.
NEVER invent on-screen characters, avatars, presenters, talking heads, or cast.
Visuals must be cinematic, documentary, atmospheric, illustrative — no baked-in text/subtitles/watermarks.
Return ONLY valid JSON matching the required schema. Do not invent unverified statistics or sources.
Distinguish established facts from speculation when the topic is factual.
"""


class GeminiContentProvider(ContentProvider):
    async def generate_content(self, request: ContentGenerationRequest) -> ContentGenerationResult:
        cfg = get_ai_config()
        api_key = cfg.require_api_key()

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError("google-genai is not installed") from exc

        client = genai.Client(api_key=api_key)
        scene_count = planned_scene_count(request.target_duration_seconds)
        clip = visual_clip_duration_seconds()
        user_prompt = self._build_prompt(request, cfg.speaking_rate_wpm, scene_count, clip)

        response = client.models.generate_content(
            model=cfg.text_model,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.7,
                response_mime_type="application/json",
            ),
        )
        text = response.text or ""
        data = self._parse_json(text)
        result = self._to_result(data, request)

        # Duration revise loop — keep the same scene count
        if result.estimated_duration_seconds > request.target_duration_seconds * 1.2:
            revise_prompt = (
                f"Revise this JSON script to fit approximately "
                f"{request.target_duration_seconds} seconds at {cfg.speaking_rate_wpm} WPM. "
                f"Keep EXACTLY {scene_count} scenes. Keep the same JSON schema. "
                f"Shorten narration without losing the hook.\n\n"
                f"{result.model_dump_json()}"
            )
            response2 = client.models.generate_content(
                model=cfg.text_model,
                contents=revise_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.5,
                    response_mime_type="application/json",
                ),
            )
            data2 = self._parse_json(response2.text or "")
            result = self._to_result(data2, request)

        return result

    def _build_prompt(
        self,
        request: ContentGenerationRequest,
        wpm: int,
        scene_count: int,
        clip_seconds: float,
    ) -> str:
        desi = is_desi_mode(request.content_mode, request.language)
        mode_block = ""
        packaging_keys = ""
        if desi:
            mode_block = f"\n{DESI_LANGUAGE_RULES}\n{DESI_PACKAGING_RULES}\n"
            packaging_keys = (
                "caption_text (Roman Urdu for whole video), "
                "packaging: {post_title, post_caption, hashtags, markets}, "
            )
            scene_fields = (
                "scene_id, sequence, narration_text (Urdu script), caption_text (Roman Urdu), "
                "visual_description, video_prompt, negative_prompt, estimated_duration_seconds, "
                "visual_style, camera_movement, composition, transition_suggestion"
            )
            language_line = "Language mode: DESI (spoken Urdu script + Roman Urdu captions)"
        else:
            scene_fields = (
                "scene_id, sequence, narration_text, caption_text (same as narration unless needed), "
                "visual_description, video_prompt, negative_prompt, estimated_duration_seconds, "
                "visual_style, camera_movement, composition, transition_suggestion"
            )
            language_line = f"Language: {request.language}"
            packaging_keys = (
                "caption_text, packaging: {post_title, post_caption, hashtags, markets}, "
            )

        return f"""Create a faceless short-form video production plan.

Topic: {request.topic}
Target duration: {request.target_duration_seconds} seconds
Platform: {request.platform}
Tone: {request.tone}
Visual aesthetic: {request.visual_aesthetic}
{language_line}
Content mode: {request.content_mode}
Speaking rate assumption: {wpm} WPM
Extra instructions: {request.extra_instructions or "none"}
{mode_block}
CRITICAL SCENE BUDGET:
- Each visual clip is fixed at approximately {clip_seconds:.0f} seconds (Muse / Snapgen).
- You MUST return EXACTLY {scene_count} scenes (ceil(target/{clip_seconds:.0f})).
- Pack the narration into those {scene_count} beats — do NOT create one scene per sentence.
- Set every scene estimated_duration_seconds to {clip_seconds:.0f}.

Return JSON with keys:
title, hook, full_script, {packaging_keys}closing_line, estimated_duration_seconds, research_notes, factual_disclaimer,
scenes: array of EXACTLY {scene_count} objects {{
  {scene_fields}
}}

Rules:
- Strong hook first; no fluff intro.
- Natural spoken language.
- video_prompt describes visuals (not narration verbatim), vertical 9:16. Keep video_prompt in English.
- negative_prompt must exclude text, subtitles, watermarks, talking presenters.
- scene_id like scene_001 through scene_{scene_count:03d}.
"""

    def _parse_json(self, text: str) -> dict:
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", text)
            if not match:
                raise ValueError("Gemini returned non-JSON content")
            return json.loads(match.group(0))

    def _to_result(self, data: dict, request: ContentGenerationRequest) -> ContentGenerationResult:
        desi = is_desi_mode(request.content_mode, request.language)
        scenes_raw = data.get("scenes") or []
        scenes: list[GeneratedScene] = []
        clip = visual_clip_duration_seconds()
        for i, sc in enumerate(scenes_raw, start=1):
            narration = sc.get("narration_text") or ""
            caption = sc.get("caption_text") or narration
            scenes.append(
                GeneratedScene(
                    scene_id=sc.get("scene_id") or f"scene_{i:03d}",
                    sequence=int(sc.get("sequence") or i),
                    narration_text=narration,
                    caption_text=caption,
                    visual_description=sc.get("visual_description") or "",
                    video_prompt=sc.get("video_prompt") or "",
                    negative_prompt=sc.get("negative_prompt")
                    or "text overlays, subtitles, watermarks, talking head, presenter, avatar",
                    estimated_duration_seconds=float(
                        sc.get("estimated_duration_seconds") or clip
                    ),
                    visual_style=sc.get("visual_style") or request.visual_aesthetic,
                    camera_movement=sc.get("camera_movement") or "slow dolly forward",
                    composition=sc.get("composition") or "vertical 9:16",
                    transition_suggestion=sc.get("transition_suggestion") or "hard_cut",
                )
            )
        scenes = normalize_scenes_to_budget(
            scenes, target_duration_seconds=request.target_duration_seconds
        )
        full_script = data.get("full_script") or " ".join(s.narration_text for s in scenes)
        caption_text = data.get("caption_text") or " ".join(
            (s.caption_text or s.narration_text) for s in scenes
        )
        est = data.get("estimated_duration_seconds")
        if est is None:
            est = _estimate_duration(full_script)
        packaging = self._packaging_from_data(data, request, full_script, desi=desi)
        return ContentGenerationResult(
            title=data.get("title") or request.topic[:80],
            hook=data.get("hook") or (scenes[0].narration_text if scenes else ""),
            full_script=full_script,
            caption_text=caption_text,
            closing_line=data.get("closing_line") or (scenes[-1].narration_text if scenes else ""),
            estimated_duration_seconds=float(est),
            scenes=scenes,
            packaging=packaging,
            research_notes=data.get("research_notes"),
            factual_disclaimer=data.get("factual_disclaimer"),
        )

    def _packaging_from_data(
        self,
        data: dict,
        request: ContentGenerationRequest,
        full_script: str,
        *,
        desi: bool,
    ) -> ContentPackaging:
        raw = data.get("packaging") if isinstance(data.get("packaging"), dict) else {}
        title = data.get("title") or request.topic[:80]
        hook = data.get("hook") or ""
        if desi:
            built = build_packaging(
                title=title,
                hook=str(raw.get("post_caption") or hook or ""),
                topic=request.topic,
                hashtags=list(raw.get("hashtags") or []),
                post_caption=raw.get("post_caption"),
                post_title=raw.get("post_title") or title,
            )
            return ContentPackaging(**built)
        tags = merge_hashtags(list(raw.get("hashtags") or []), default_desi_hashtags(request.topic)[:6])
        if request.platform == "tiktok" and not tags:
            tags = ["#fyp", "#viral", "#foryou"]
        caption = str(raw.get("post_caption") or hook or full_script[:160])
        return ContentPackaging(
            post_title=str(raw.get("post_title") or title)[:80],
            post_caption=caption,
            hashtags=tags,
            hashtag_string=" ".join(tags),
            markets=list(raw.get("markets") or (["pakistan", "india"] if desi else [])),
            caption_script="latin",
            spoken_script="latin",
        )
