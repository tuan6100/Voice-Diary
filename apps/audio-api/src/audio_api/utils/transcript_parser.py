import re
from typing import List
from audio_api.models.audio import TranscriptSegment


def parse_transcript_from_text(raw_text: str) -> List[TranscriptSegment]:
    """
    Chuyển đổi văn bản thô dạng:
    [00:12] Speaker A: Nội dung...
    [00:15] Speaker B: Nội dung khác...

    Thành List[TranscriptSegment] để lưu vào Audio.transcript
    """
    if not raw_text:
        return []

    segments = []

    # Regex giải thích:
    # 1. \[\s*(\d{1,2}):(\d{2})\s*\] : Tìm timestamp [MM:SS]
    # 2. \s* : Khoảng trắng tùy ý
    # 3. (?:(.*?):\s*)? : (Tùy chọn) Tìm tên Speaker kết thúc bằng dấu hai chấm
    # 4. (.*?) : Nội dung text
    # 5. (?=\[\s*\d{1,2}:\d{2}\s*\]|$) : Dừng khi gặp timestamp tiếp theo hoặc hết chuỗi

    pattern = re.compile(
        r'\[\s*(\d{1,2}):(\d{2})\s*\]\s*(?:(.*?):\s*)?(.*?)(?=\[\s*\d{1,2}:\d{2}\s*\]|$)',
        re.DOTALL
    )

    matches = pattern.findall(raw_text)

    for i, match in enumerate(matches):
        minutes, seconds, speaker_candidate, content = match

        # Tính giây bắt đầu
        try:
            start_seconds = int(minutes) * 60 + int(seconds)
        except ValueError:
            continue

        text = content.strip()
        speaker = speaker_candidate.strip() if speaker_candidate else "Unknown"

        segments.append(TranscriptSegment(
            start=float(start_seconds),
            end=0.0,  # Sẽ tính toán lại bên dưới
            speaker=speaker,
            text=text
        ))

    # Tính toán thời gian kết thúc (end time)
    for i in range(len(segments) - 1):
        segments[i].end = segments[i + 1].start

    # Segment cuối cùng cộng thêm 2 giây
    if segments:
        segments[-1].end = segments[-1].start + 2.0

    return segments