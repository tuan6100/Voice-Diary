import os
import ffmpeg
import logging

logger = logging.getLogger(__name__)


def generate_hls_and_waveform(input_path: str, output_dir: str, segment_time: int = 10):
    os.makedirs(output_dir, exist_ok=True)
    hls_playlist = os.path.join(output_dir, "playlist.m3u8")
    hls_segment = os.path.join(output_dir, "segment_%03d.ts")

    try:
        logger.info(f"Start transcoding: {input_path}")
        (
            ffmpeg
            .input(input_path)
            .output(
                hls_playlist,
                format='hls',
                acodec='aac',
                audio_bitrate='128k',
                hls_time=segment_time,
                hls_list_size=0,
                hls_segment_filename=hls_segment
            )
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        logger.info("HLS generated successfully.")

        return {
            "playlist": "playlist.m3u8"
        }
    except ffmpeg.Error as e:
        error_msg = e.stderr.decode('utf8') if e.stderr else str(e)
        logger.error(f"FFmpeg Transcode Error: {error_msg}")
        raise RuntimeError(f"Transcoding failed: {error_msg}")