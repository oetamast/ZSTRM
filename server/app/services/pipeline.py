from __future__ import annotations

from ..models import AudioReplaceMode, Job, PresetType


def build_pipeline_summary(job: Job) -> str:
    preset = None
    asset = None
    destination = None
    try:
        from sqlmodel import select
        from ..database import get_session
        from ..models import Asset, Destination, Preset

        with get_session() as session:
            preset = session.get(Preset, job.preset_id)
            asset = session.get(Asset, job.asset_id)
            destination = session.get(Destination, job.destination_id)
    except Exception:
        preset = None
    preset_part = preset.name if preset else "copy"
    if preset and preset.preset_type == PresetType.encode:
        preset_part = f"encode-v{preset.video_bitrate or 'auto'}-a{preset.audio_bitrate or 'auto'}"
    audio_part = "audio" if asset and not asset.audio_only else "video-only"
    dest_part = destination.endpoint if destination else "unknown-dest"
    ffmpeg_flags = ["-re"]
    if preset and preset.preset_type == PresetType.copy and not preset.force_encode:
        ffmpeg_flags.append("-c copy")
    if preset and preset.audio_replace == AudioReplaceMode.external_loop:
        ffmpeg_flags.append("-stream_loop -1 -i external_audio.mp3")
    if preset and preset.audio_replace == AudioReplaceMode.video_only:
        ffmpeg_flags.append("-an")
    return f"ffmpeg {' '.join(ffmpeg_flags)} // preset={preset_part} // {audio_part} -> {dest_part}"
