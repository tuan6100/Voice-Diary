from typing import List

from audio_api.models.audio import TranscriptSegment


def format_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    sec = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{sec:06.3f}"

def generate_webvtt(segments: List[TranscriptSegment]) -> str:
    lines = ["WEBVTT", ""]
    for i, seg in enumerate(segments):
        start = format_timestamp(seg.start)
        end = format_timestamp(seg.end)
        lines.append(f"{i + 1}")
        lines.append(f"{start} --> {end}")
        lines.append(seg.text)
        lines.append("")
    return "\n".join(lines)

def generate_plain_text(segments: List[TranscriptSegment], is_detail: bool = False) -> str:
    lines = []
    for seg in segments:
        if is_detail:
            lines.append(seg.text)
        else:
            time_label = f"[{int(seg.start // 60):02d}:{int(seg.start % 60):02d}]"
            lines.append(f"{time_label} {seg.text}")
    return "\n".join(lines)