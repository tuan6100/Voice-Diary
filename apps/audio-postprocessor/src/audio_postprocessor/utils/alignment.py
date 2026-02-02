import logging

logger = logging.getLogger(__name__)


def calculate_overlap(seg1_start, seg1_end, seg2_start, seg2_end):
    overlap_start = max(seg1_start, seg2_start)
    overlap_end = min(seg1_end, seg2_end)
    return max(0, overlap_end - overlap_start)


def get_best_speaker_for_word(word, diarization_segments):
    w_start = word.get('start')
    w_end = word.get('end')
    best_speaker = "UNKNOWN"
    max_overlap = 0
    candidate_segments = []
    for spk in diarization_segments:
        if spk['end'] < w_start:
            continue
        elif spk['start'] > w_end:
            continue
        overlap = calculate_overlap(w_start, w_end, spk['start'], spk['end'])
        if overlap > 0:
            if overlap > max_overlap:
                max_overlap = overlap
                best_speaker = spk['speaker']
        if abs(spk['start'] - w_end) < 2.0 or abs(spk['end'] - w_start) < 2.0:
            candidate_segments.append(spk)
    if best_speaker != "UNKNOWN":
        return best_speaker
    min_distance = float('inf')
    nearest_speaker = "UNKNOWN"
    for spk in candidate_segments:
        if w_end <= spk['start']:
            dist = spk['start'] - w_end
        elif w_start >= spk['end']:
            dist = w_start - spk['end']
        else:
            dist = 0
        if dist < min_distance:
            min_distance = dist
            nearest_speaker = spk['speaker']
    return nearest_speaker


def merge_consecutive_segments(segments: list, max_gap: float = 2.0) -> list:
    if not segments:
        return []

    merged = []
    current = segments[0].copy()

    for i in range(1, len(segments)):
        next_seg = segments[i]
        time_gap = next_seg['start'] - current['end']
        if next_seg['speaker'] == current['speaker'] and time_gap <= max_gap:
            current['text'] = current['text'] + ' ' + next_seg['text']
            current['end'] = next_seg['end']
        else:
            merged.append(current)
            current = next_seg.copy()

    # Thêm segment cuối cùng
    merged.append(current)

    return merged


def align_transcript_with_diarization(
        word_segments: list,
        diarization_segments: list,
        merge_same_speaker: bool = True,
        max_gap: float = 2.0
) -> list:
    words_with_speaker = []
    sorted_diarization = sorted(diarization_segments, key=lambda x: x['start'])
    for word in word_segments:
        w_start = word.get('start')
        w_end = word.get('end')
        if w_start is None or w_end is None:
            continue
        speaker = get_best_speaker_for_word(word, sorted_diarization)
        if speaker == "UNKNOWN" and words_with_speaker:
            speaker = words_with_speaker[-1]['speaker']
        words_with_speaker.append({
            "word": word.get("word", ""),
            "start": w_start,
            "end": w_end,
            "speaker": speaker
        })

    if not words_with_speaker:
        return []

    final_segments = []
    for diar_seg in sorted_diarization:
        segment_words = []
        for w in words_with_speaker:
            if (w['start'] >= diar_seg['start'] and w['end'] <= diar_seg['end']) or \
                    (calculate_overlap(w['start'], w['end'], diar_seg['start'], diar_seg['end']) > 0):
                if w['speaker'] == diar_seg['speaker']:
                    segment_words.append(w)
        if segment_words:
            final_segments.append({
                "speaker": diar_seg['speaker'],
                "start": segment_words[0]['start'],
                "end": segment_words[-1]['end'],
                "text": " ".join([w['word'] for w in segment_words]).strip()
            })

    if merge_same_speaker and final_segments:
        final_segments = merge_consecutive_segments(final_segments, max_gap)

    return final_segments