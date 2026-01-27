import os
import math
from typing import List, Dict
from pydub import AudioSegment
from pydub.silence import detect_nonsilent

MAX_DURATION_MS = 60 * 1000
MIN_SILENCE_LEN_FLOOR = 200

def _recursive_find_ranges(
        audio_segment: AudioSegment,
        min_silence_len: int,
        silence_thresh: int
) -> List[tuple]:

    ranges = detect_nonsilent(
        audio_segment,
        min_silence_len=min_silence_len,
        silence_thresh=silence_thresh
    )
    if not ranges:
        return [(0, len(audio_segment))]

    final_ranges = []

    for start, end in ranges:
        duration = end - start
        if duration > MAX_DURATION_MS and min_silence_len > MIN_SILENCE_LEN_FLOOR:
            new_min_silence = max(MIN_SILENCE_LEN_FLOOR, min_silence_len - 150)
            sub_audio = audio_segment[start:end]
            sub_ranges = _recursive_find_ranges(sub_audio, new_min_silence, silence_thresh)
            for sub_start, sub_end in sub_ranges:
                final_ranges.append((start + sub_start, start + sub_end))
        elif duration > MAX_DURATION_MS:
            num_parts = math.ceil(duration / MAX_DURATION_MS)
            for i in range(num_parts):
                part_start = start + (i * MAX_DURATION_MS)
                part_end = min(end, start + ((i + 1) * MAX_DURATION_MS))
                final_ranges.append((part_start, part_end))

        else:
            final_ranges.append((start, end))

    return final_ranges


def split_audio_smart(
        input_path: str,
        output_dir: str,
        min_silence_len: int = 700,
        silence_thresh: int = -40
) -> List[Dict]:
    os.makedirs(output_dir, exist_ok=True)
    try:
        audio = AudioSegment.from_file(input_path)
    except Exception as e:
        print(f"Error loading audio file {input_path}: {e}")
        return []
    valid_ranges = _recursive_find_ranges(audio, min_silence_len, silence_thresh)
    chunks_metadata = []
    for i, (start_ms, end_ms) in enumerate(valid_ranges):
        pad_ms = 200
        safe_start = max(0, start_ms - pad_ms)
        safe_end = min(len(audio), end_ms + pad_ms)
        chunk = audio[safe_start:safe_end]
        filename = f"chunk_{i}.wav"
        out_path = os.path.join(output_dir, filename)
        chunk.export(out_path, format="wav")
        chunks_metadata.append({
            "index": i,
            "local_path": out_path,
            "filename": filename,
            "start_ms": safe_start,
            "end_ms": safe_end,
            "duration_ms": safe_end - safe_start
        })

    return chunks_metadata