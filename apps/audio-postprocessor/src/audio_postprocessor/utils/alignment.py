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
            pass
        elif spk['start'] > w_end:
            pass

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


def align_transcript_with_diarization(word_segments: list, diarization_segments: list) -> list:
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
    current_segment = {
        "speaker": words_with_speaker[0]['speaker'],
        "start": words_with_speaker[0]['start'],
        "end": words_with_speaker[0]['end'],
        "words": [words_with_speaker[0]['word']]
    }

    for i in range(1, len(words_with_speaker)):
        w = words_with_speaker[i]

        if w['speaker'] == current_segment['speaker']:
            current_segment['words'].append(w['word'])
            current_segment['end'] = w['end']
        else:
            current_segment['text'] = " ".join(current_segment['words']).strip()
            del current_segment['words']
            final_segments.append(current_segment)

            current_segment = {
                "speaker": w['speaker'],
                "start": w['start'],
                "end": w['end'],
                "words": [w['word']]
            }

    current_segment['text'] = " ".join(current_segment['words']).strip()
    del current_segment['words']
    final_segments.append(current_segment)

    return final_segments