import os
from typing import List, Dict
from pydub import AudioSegment
from pydub.silence import detect_nonsilent


def split_audio_smart(
        input_path: str,
        output_dir: str,
        min_silence_len: int = 700,
        silence_thresh: int = -40
) -> List[Dict]:
    os.makedirs(output_dir, exist_ok=True)
    audio = AudioSegment.from_file(input_path)
    nonsilent_ranges = detect_nonsilent(
        audio,
        min_silence_len=min_silence_len,
        silence_thresh=silence_thresh
    )
    chunks_metadata = []
    if not nonsilent_ranges:
        return []
    for i, (start_ms, end_ms) in enumerate(nonsilent_ranges):
        pad_ms = 200
        start_ms = max(0, start_ms - pad_ms)
        end_ms = min(len(audio), end_ms + pad_ms)
        chunk = audio[start_ms:end_ms]
        filename = f"chunk_{i:04d}.wav"
        out_path = os.path.join(output_dir, filename)
        chunk.export(out_path, format="wav")
        chunks_metadata.append({
            "index": i,
            "local_path": out_path,
            "filename": filename,
            "start_ms": start_ms,
            "end_ms": end_ms,
            "duration_ms": end_ms - start_ms
        })
    return chunks_metadata