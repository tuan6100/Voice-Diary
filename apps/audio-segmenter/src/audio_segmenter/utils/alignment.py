

def merge_transcript_with_speakers(transcript_segments, speaker_turns):
    """
    transcript_segments: List[{text, start, end}] (Output của Whisper)
    speaker_turns: List[{speaker, start, end}] (Output của Diarizer)
    """
    final_result = []

    for text_seg in transcript_segments:
        text_start = text_seg['start']
        text_end = text_seg['end']


        best_speaker = "UNKNOWN"
        max_overlap = 0

        for spk_turn in speaker_turns:

            overlap_start = max(text_start, spk_turn['start'])
            overlap_end = min(text_end, spk_turn['end'])
            overlap_duration = max(0, overlap_end - overlap_start)

            if overlap_duration > max_overlap:
                max_overlap = overlap_duration
                best_speaker = spk_turn['speaker']

        final_result.append({
            "text": text_seg['text'],
            "start": text_start,
            "end": text_end,
            "speaker": best_speaker
        })

    return final_result