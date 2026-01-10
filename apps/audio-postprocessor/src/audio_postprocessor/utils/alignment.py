import logging

logger = logging.getLogger(__name__)


def calculate_overlap(seg1_start, seg1_end, seg2_start, seg2_end):
    overlap_start = max(seg1_start, seg2_start)
    overlap_end = min(seg1_end, seg2_end)
    return max(0, overlap_end - overlap_start)

def align_transcript_with_diarization(transcript_segments: list, diarization_segments: list) -> list:
    aligned_results = []
    sorted_transcript = sorted(transcript_segments, key=lambda x: x['start'])
    sorted_diarization = sorted(diarization_segments, key=lambda x: x['start'])
    for text_seg in sorted_transcript:
        t_start = text_seg.get('start', 0)
        t_end = text_seg.get('end', 0)
        best_speaker = "UNKNOWN"
        max_overlap_duration = 0
        for spk_seg in sorted_diarization:
            s_start = spk_seg.get('start', 0)
            s_end = spk_seg.get('end', 0)
            if s_end < t_start:
                continue
            if s_start > t_end:
                break
            overlap = calculate_overlap(t_start, t_end, s_start, s_end)
            if overlap > max_overlap_duration:
                max_overlap_duration = overlap
                best_speaker = spk_seg.get('speaker', 'UNKNOWN')
        aligned_results.append({
            "text": text_seg.get('text'),
            "start": t_start,
            "end": t_end,
            "speaker": best_speaker,
            "confidence": text_seg.get('confidence', 1.0)  # Nếu có
        })

    return aligned_results