import logging

logger = logging.getLogger(__name__)


def calculate_overlap(seg1_start, seg1_end, seg2_start, seg2_end):
    """
    Tính độ dài khoảng thời gian giao nhau giữa 2 segment.
    Công thức: Max(Start) -> Min(End)
    """
    overlap_start = max(seg1_start, seg2_start)
    overlap_end = min(seg1_end, seg2_end)

    # Nếu start < end thì mới có overlap, ngược lại trả về 0
    return max(0, overlap_end - overlap_start)


def align_transcript_with_diarization(transcript_segments: list, diarization_segments: list) -> list:
    """
    Gióng hàng Transcript với Diarization.

    Input:
    - transcript_segments: [{'text': '...', 'start': 1.0, 'end': 2.0}, ...]
    - diarization_segments: [{'speaker': 'SPEAKER_01', 'start': 0.5, 'end': 2.5}, ...]

    Output:
    - List transcript đã được gán speaker.
    """
    aligned_results = []

    # Sắp xếp theo thời gian để tối ưu (tùy chọn, nhưng nên làm)
    sorted_transcript = sorted(transcript_segments, key=lambda x: x['start'])
    sorted_diarization = sorted(diarization_segments, key=lambda x: x['start'])

    for text_seg in sorted_transcript:
        t_start = text_seg.get('start', 0)
        t_end = text_seg.get('end', 0)

        best_speaker = "UNKNOWN"
        max_overlap_duration = 0

        # Duyệt qua các segment người nói để tìm ai trùng khớp nhất
        # (Có thể tối ưu thuật toán này bằng Interval Tree nếu dữ liệu rất lớn,
        # nhưng với audio thông thường < 1 tiếng thì loop lồng nhau vẫn rất nhanh)
        for spk_seg in sorted_diarization:
            s_start = spk_seg.get('start', 0)
            s_end = spk_seg.get('end', 0)

            # Kiểm tra nếu speaker segment kết thúc trước khi text bắt đầu -> Bỏ qua
            if s_end < t_start:
                continue

            # Kiểm tra nếu speaker segment bắt đầu sau khi text kết thúc -> Dừng vòng lặp (vì đã sort)
            if s_start > t_end:
                break

            # Tính overlap
            overlap = calculate_overlap(t_start, t_end, s_start, s_end)

            if overlap > max_overlap_duration:
                max_overlap_duration = overlap
                best_speaker = spk_seg.get('speaker', 'UNKNOWN')

        # Tạo kết quả mới cho segment này
        aligned_results.append({
            "text": text_seg.get('text'),
            "start": t_start,
            "end": t_end,
            "speaker": best_speaker,
            "confidence": text_seg.get('confidence', 1.0)  # Nếu có
        })

    return aligned_results