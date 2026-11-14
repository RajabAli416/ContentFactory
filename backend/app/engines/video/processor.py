"""FFmpeg-based clip normalization, trimming, assembly, and export."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.engines.base import VideoProcessor
from app.engines.video.ffmpeg_runner import probe_media, run_ffmpeg, validate_video_file


class FFmpegVideoProcessor(VideoProcessor):
    async def process_clip(self, input_path: Path, options: dict[str, Any]) -> Path:
        return await self.normalize_clip(input_path, Path(options["output_path"]), options)

    async def normalize_clip(
        self,
        input_path: Path,
        output_path: Path,
        options: dict[str, Any] | None = None,
    ) -> Path:
        settings = get_settings()
        opts = options or {}
        width = int(opts.get("width", settings.default_width))
        height = int(opts.get("height", settings.default_height))
        fps = int(opts.get("fps", settings.default_fps))
        end_trim = float(opts.get("end_trim_seconds", 0) or 0)
        target_duration = opts.get("target_duration_seconds")
        keep_audio = bool(opts.get("keep_audio", settings.scene_audio_enabled))

        await validate_video_file(input_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Scale to cover then crop center — never stretch
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},fps={fps},format=yuv420p"
        )

        args = ["-y", "-i", str(input_path)]
        if end_trim > 0:
            info = await probe_media(input_path)
            dur = max((info.get("duration") or 0) - end_trim, 0.5)
            args += ["-t", f"{dur:.3f}"]
        if target_duration:
            # Will trim or pad later in timeline; for now set max duration
            args += ["-t", f"{float(target_duration):.3f}"]

        args += [
            "-vf",
            vf,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
        ]
        if keep_audio:
            args += [
                "-c:a",
                "aac",
                "-ar",
                "48000",
                "-ac",
                "2",
                "-b:a",
                "160k",
            ]
        else:
            args += ["-an"]
        args += ["-movflags", "+faststart", str(output_path)]
        await run_ffmpeg(args)
        await validate_video_file(output_path)
        return output_path

    async def freeze_extend(self, input_path: Path, output_path: Path, duration: float) -> Path:
        """Extend clip to duration by freezing the last frame (pad audio with silence)."""
        info = await probe_media(input_path)
        current = float(info.get("duration") or 0)
        settings = get_settings()
        keep_audio = bool(settings.scene_audio_enabled and info.get("has_audio"))

        if current >= duration - 0.05:
            args = [
                "-y",
                "-i",
                str(input_path),
                "-t",
                f"{duration:.3f}",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
            ]
            if keep_audio:
                args += ["-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "160k"]
            else:
                args += ["-an"]
            args.append(str(output_path))
            await run_ffmpeg(args)
            return output_path

        pad = duration - current
        # tpad freezes last frame; apad extends audio with silence
        if keep_audio:
            fc = (
                f"[0:v]tpad=stop_mode=clone:stop_duration={pad:.3f},"
                f"fps={settings.default_fps},format=yuv420p[v];"
                f"[0:a]apad=pad_dur={pad:.3f},aformat=sample_rates=48000:channel_layouts=stereo[a]"
            )
            await run_ffmpeg(
                [
                    "-y",
                    "-i",
                    str(input_path),
                    "-filter_complex",
                    fc,
                    "-map",
                    "[v]",
                    "-map",
                    "[a]",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "18",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "160k",
                    "-t",
                    f"{duration:.3f}",
                    str(output_path),
                ]
            )
        else:
            await run_ffmpeg(
                [
                    "-y",
                    "-i",
                    str(input_path),
                    "-vf",
                    f"tpad=stop_mode=clone:stop_duration={pad:.3f},fps={settings.default_fps},format=yuv420p",
                    "-an",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "18",
                    "-pix_fmt",
                    "yuv420p",
                    "-t",
                    f"{duration:.3f}",
                    str(output_path),
                ]
            )
        return output_path

    async def concatenate(
        self,
        clip_paths: list[Path],
        output_path: Path,
        *,
        transition: str = "hard_cut",
        transition_duration: float = 0.3,
    ) -> Path:
        if not clip_paths:
            raise ValueError("No clips to concatenate")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if transition == "hard_cut" or len(clip_paths) == 1:
            return await self._concat_demuxer(clip_paths, output_path)

        # Crossfade chain via filter_complex
        return await self._concat_xfade(clip_paths, output_path, transition_duration)

    async def _concat_demuxer(self, clip_paths: list[Path], output_path: Path) -> Path:
        settings = get_settings()
        keep_audio = bool(settings.scene_audio_enabled)
        # Ensure every clip has an audio stream so concat doesn't drop the bed
        prepared: list[Path] = []
        tmp_dir: Path | None = None
        if keep_audio:
            tmp_dir = Path(tempfile.mkdtemp(prefix="cf_concat_"))
            for i, p in enumerate(clip_paths):
                info = await probe_media(p)
                if info.get("has_audio"):
                    prepared.append(p)
                    continue
                filled = tmp_dir / f"silent_{i:03d}.mp4"
                dur = float(info.get("duration") or 1)
                await run_ffmpeg(
                    [
                        "-y",
                        "-i",
                        str(p),
                        "-f",
                        "lavfi",
                        "-i",
                        f"anullsrc=r=48000:cl=stereo",
                        "-c:v",
                        "copy",
                        "-c:a",
                        "aac",
                        "-shortest",
                        "-t",
                        f"{dur:.3f}",
                        str(filled),
                    ]
                )
                prepared.append(filled)
        else:
            prepared = list(clip_paths)

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
            for p in prepared:
                # Escape single quotes for concat demuxer
                escaped = str(p.resolve()).replace("'", "'\\''")
                f.write(f"file '{escaped}'\n")
            list_path = Path(f.name)
        try:
            args = [
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(list_path),
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
            ]
            if keep_audio:
                args += ["-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "160k"]
            else:
                args += ["-an"]
            args += ["-movflags", "+faststart", str(output_path)]
            await run_ffmpeg(args)
        finally:
            list_path.unlink(missing_ok=True)
            if tmp_dir and tmp_dir.exists():
                for child in tmp_dir.glob("*"):
                    child.unlink(missing_ok=True)
                tmp_dir.rmdir()
        return output_path

    async def _concat_xfade(
        self, clip_paths: list[Path], output_path: Path, duration: float
    ) -> Path:
        # Build xfade filter chain
        inputs: list[str] = []
        for p in clip_paths:
            inputs += ["-i", str(p)]
        durations = []
        for p in clip_paths:
            info = await probe_media(p)
            durations.append(float(info.get("duration") or 1))

        filter_parts = []
        current_label = "[0:v]"
        offset = 0.0
        for i in range(1, len(clip_paths)):
            offset += max(durations[i - 1] - duration, 0)
            out_label = f"[v{i}]" if i < len(clip_paths) - 1 else "[vout]"
            filter_parts.append(
                f"{current_label}[{i}:v]xfade=transition=fade:duration={duration:.3f}:offset={offset:.3f}{out_label}"
            )
            current_label = out_label if i < len(clip_paths) - 1 else "[vout]"
            # After xfade, effective duration shrinks by transition duration
            # Adjust next offset base: use cumulative

        # Recalculate offsets properly
        filter_parts = []
        current_label = "[0:v]"
        cumulative = durations[0]
        for i in range(1, len(clip_paths)):
            offset = max(cumulative - duration, 0)
            out_label = f"[v{i}]" if i < len(clip_paths) - 1 else "[vout]"
            filter_parts.append(
                f"{current_label}[{i}:v]xfade=transition=fade:duration={duration:.3f}:offset={offset:.3f}{out_label}"
            )
            cumulative = offset + durations[i]
            current_label = out_label

        fc = ";".join(filter_parts)
        await run_ffmpeg(
            [
                "-y",
                *inputs,
                "-filter_complex",
                fc,
                "-map",
                "[vout]",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(output_path),
            ]
        )
        return output_path

    async def mux_audio_video(
        self,
        video_path: Path,
        audio_path: Path,
        output_path: Path,
        *,
        caption_ass: Path | None = None,
        scene_audio_volume: float | None = None,
    ) -> Path:
        """Burn captions + mix narration over quieter original scene audio when present."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        settings = get_settings()
        bed_vol = (
            settings.scene_audio_volume
            if scene_audio_volume is None
            else float(scene_audio_volume)
        )
        mix_bed = bool(settings.scene_audio_enabled and bed_vol > 0)

        audio_info = await probe_media(audio_path)
        video_info = await probe_media(video_path)
        audio_dur = float(audio_info.get("duration") or 0)
        video_dur = float(video_info.get("duration") or 0)

        if video_dur + 0.05 < audio_dur:
            extended = output_path.with_name(output_path.stem + "_ext.mp4")
            await self.freeze_extend(video_path, extended, audio_dur)
            video_path = extended
            video_info = await probe_media(video_path)

        has_bed = bool(mix_bed and video_info.get("has_audio"))
        burn_caps = bool(caption_ass and caption_ass.exists())

        args = ["-y", "-i", str(video_path), "-i", str(audio_path)]
        fc_parts: list[str] = []
        if burn_caps:
            ass_escaped = str(caption_ass.resolve()).replace("\\", "/").replace(":", "\\:")
            fc_parts.append(f"[0:v]ass='{ass_escaped}'[vout]")
        if has_bed:
            fc_parts.append(
                f"[0:a]volume={bed_vol:.3f},aformat=sample_rates=48000:channel_layouts=stereo[bed]"
            )
            fc_parts.append(
                "[1:a]aformat=sample_rates=48000:channel_layouts=stereo[nar]"
            )
            # Narration is length authority; bed is ducked under it
            fc_parts.append(
                "[nar][bed]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[aout]"
            )

        if fc_parts:
            args += ["-filter_complex", ";".join(fc_parts)]

        if burn_caps:
            args += ["-map", "[vout]"]
        else:
            args += ["-map", "0:v:0"]

        if has_bed:
            args += ["-map", "[aout]"]
        else:
            args += ["-map", "1:a:0"]

        args += [
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-ar",
            "48000",
            "-b:a",
            "192k",
            "-t",
            f"{audio_dur:.3f}",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
        await run_ffmpeg(args)
        return output_path
