"""Mock content provider — deterministic structured scripts without network."""

from __future__ import annotations

import re

from app.engines.base import ContentProvider
from app.engines.content.desi import build_packaging, is_desi_mode
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


def _estimate_duration(text: str, wpm: int = 150) -> float:
    words = len(re.findall(r"\w+", text))
    return round((words / max(wpm, 1)) * 60, 2)


class MockContentProvider(ContentProvider):
    async def generate_content(self, request: ContentGenerationRequest) -> ContentGenerationResult:
        topic = request.topic.strip()
        target = request.target_duration_seconds
        aesthetic = request.visual_aesthetic
        scene_count = planned_scene_count(target)
        clip = visual_clip_duration_seconds()
        desi = is_desi_mode(request.content_mode, request.language)

        if desi:
            return self._desi_content(topic, target, aesthetic, scene_count, clip)

        hook = f"What if everything you thought about {topic} was only half the story?"
        pool = [
            f"Most people encounter {topic} every day without noticing the hidden patterns underneath.",
            f"Look closer and the structure of {topic} starts to reveal why it shapes decisions, habits, and outcomes.",
            f"In practice, the critical detail about {topic} is not the headline — it is the quiet mechanism behind it.",
            f"That mechanism creates cascading effects: small causes, outsized consequences.",
            f"Once you see it, you cannot unsee how {topic} influences the world around you.",
            f"So the next time {topic} comes up, ask what sits beneath the surface — that is where the real story lives.",
        ]

        if scene_count == 1:
            all_texts = [f"{hook} {pool[-1]}"]
        elif scene_count == 2:
            all_texts = [hook, pool[-1]]
        else:
            body_needed = scene_count - 2
            body = pool[:body_needed]
            while len(body) < body_needed:
                body.append(
                    f"Another layer of {topic} shows how context, timing, and perception rewrite the narrative."
                )
            all_texts = [hook, *body[:body_needed], pool[-1]]

        closing = all_texts[-1]
        scenes = self._scenes(all_texts, all_texts, topic, aesthetic, clip)
        scenes = normalize_scenes_to_budget(scenes, target_duration_seconds=target)
        full_script = " ".join(s.narration_text for s in scenes)
        return ContentGenerationResult(
            title=f"{topic[:60].rstrip()} — The Hidden Layer",
            hook=hook,
            full_script=full_script,
            caption_text=full_script,
            closing_line=closing,
            estimated_duration_seconds=_estimate_duration(full_script),
            scenes=scenes,
            packaging=ContentPackaging(
                post_title=f"{topic[:60].rstrip()} — The Hidden Layer",
                post_caption=hook,
                hashtags=["#fyp", "#viral", "#foryou"],
                hashtag_string="#fyp #viral #foryou",
                markets=[],
                caption_script="latin",
                spoken_script="latin",
            ),
            research_notes="Mock provider: no external research performed.",
            factual_disclaimer=(
                "Mock content for pipeline testing. Do not treat as verified facts."
            ),
        )

    def _desi_content(
        self,
        topic: str,
        target: int,
        aesthetic: str,
        scene_count: int,
        clip: float,
    ) -> ContentGenerationResult:
        urdu_pool = [
            f"کیا آپ نے کبھی سوچا کہ {topic} کے پیچھے اصل راز کیا ہے؟",
            f"اکثر لوگ {topic} کو سطحی طور پر دیکھتے ہیں، مگر اصل کہانی نیچے چھپی ہوتی ہے۔",
            f"جب آپ قریب سے دیکھیں تو {topic} کے پیچھے ایک خاموش میکانزم نظر آتا ہے۔",
            f"یہی میکانزم چھوٹی وجہ سے بڑا نتیجہ پیدا کرتا ہے — اور سب حیران رہ جاتے ہیں۔",
            f"ایک بار سمجھ آ جائے تو آپ {topic} کو پرانی نظر سے نہیں دیکھ سکتے۔",
            f"اگلی بار جب {topic} کی بات ہو، سطح کے نیچے جھانکیں — اصل کہانی وہیں ہے۔",
        ]
        roman_pool = [
            f"Kya aap ne kabhi socha ke {topic} ke peeche asl raaz kya hai?",
            f" Aksar log {topic} ko sathi tor par dekhte hain, magar asl kahani neeche chupi hoti hai.",
            f"Jab aap qareeb se dekhein to {topic} ke peeche ek khamosh mechanism nazar aata hai.",
            f"Yehi mechanism chhoti wajah se bara natija paida karta hai — aur sab hairan reh jate hain.",
            f"Ek baar samajh aa jaye to aap {topic} ko purani nazar se nahi dekh sakte.",
            f"Agli baar jab {topic} ki baat ho, satah ke neeche jhaankein — asl kahani wahin hai.",
        ]
        # Fix accidental leading space on roman_pool[1]
        roman_pool[1] = roman_pool[1].lstrip()

        if scene_count == 1:
            urdu_texts = [f"{urdu_pool[0]} {urdu_pool[-1]}"]
            roman_texts = [f"{roman_pool[0]} {roman_pool[-1]}"]
        elif scene_count == 2:
            urdu_texts = [urdu_pool[0], urdu_pool[-1]]
            roman_texts = [roman_pool[0], roman_pool[-1]]
        else:
            body_needed = scene_count - 2
            urdu_body = urdu_pool[1 : 1 + body_needed]
            roman_body = roman_pool[1 : 1 + body_needed]
            while len(urdu_body) < body_needed:
                urdu_body.append(urdu_pool[2])
                roman_body.append(roman_pool[2])
            urdu_texts = [urdu_pool[0], *urdu_body[:body_needed], urdu_pool[-1]]
            roman_texts = [roman_pool[0], *roman_body[:body_needed], roman_pool[-1]]

        scenes = self._scenes(urdu_texts, roman_texts, topic, aesthetic, clip)
        scenes = normalize_scenes_to_budget(scenes, target_duration_seconds=target)
        full_script = " ".join(s.narration_text for s in scenes)
        caption_text = " ".join(s.caption_text for s in scenes)
        title = f"{topic[:40].rstrip()} — Desi Hidden Layer"
        packaging = ContentPackaging(
            **build_packaging(
                title=title,
                hook=roman_texts[0],
                topic=topic,
                post_caption=f"{roman_texts[0]}\n\nPoori baat comments mein batao 🔥",
                post_title=title,
            )
        )
        return ContentGenerationResult(
            title=title,
            hook=urdu_texts[0],
            full_script=full_script,
            caption_text=caption_text,
            closing_line=urdu_texts[-1],
            estimated_duration_seconds=_estimate_duration(roman_texts and " ".join(roman_texts) or full_script),
            scenes=scenes,
            packaging=packaging,
            research_notes="Mock desi provider: Urdu TTS + Roman Urdu captions sample.",
            factual_disclaimer=(
                "Mock content for pipeline testing. Do not treat as verified facts."
            ),
        )

    def _scenes(
        self,
        narration_texts: list[str],
        caption_texts: list[str],
        topic: str,
        aesthetic: str,
        clip: float,
    ) -> list[GeneratedScene]:
        camera_moves = [
            "slow dolly forward",
            "gentle aerial push-in",
            "static locked-off with subtle drift",
            "tracking shot left to right",
            "crane rising reveal",
            "macro push into detail",
        ]
        scenes: list[GeneratedScene] = []
        for i, text in enumerate(narration_texts, start=1):
            caption = caption_texts[i - 1] if i - 1 < len(caption_texts) else text
            visual = (
                f"Cinematic vertical composition illustrating the idea of {topic}: "
                f"atmospheric environment, documentary realism, no people speaking to camera. "
                f"Beat: {caption[:80]}"
            )
            prompt = (
                f"{aesthetic}, vertical 9:16, cinematic lighting, shallow depth of field, "
                f"no text, no subtitles, no watermarks, no talking presenter. "
                f"Subject related to {topic}. {visual} "
                f"Camera: {camera_moves[(i - 1) % len(camera_moves)]}."
            )
            scenes.append(
                GeneratedScene(
                    scene_id=f"scene_{i:03d}",
                    sequence=i,
                    narration_text=text,
                    caption_text=caption,
                    visual_description=visual,
                    video_prompt=prompt,
                    estimated_duration_seconds=clip,
                    visual_style=aesthetic,
                    camera_movement=camera_moves[(i - 1) % len(camera_moves)],
                    composition="vertical 9:16",
                )
            )
        return scenes
