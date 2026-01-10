import ffmpeg
import logging
import os

logger = logging.getLogger(__name__)


def process_audio(input_path: str, output_path: str):
    try:
        logger.info(f"Processing audio: {input_path} -> {output_path}")
        stream = ffmpeg.input(input_path)
        stream = stream.filter('highpass', f=80)
        stream = stream.filter('lowpass', f=8000)
        stream = stream.filter('loudnorm', I=-16, TP=-1.5, LRA=11)
        stream = stream.output(
            output_path,
            ac=1,
            ar=16000,
            f='wav'
        )
        ffmpeg.run(stream, overwrite_output=True, capture_stdout=True, capture_stderr=True)
        logger.info("FFmpeg process completed successfully.")
    except ffmpeg.Error as e:
        error_message = e.stderr.decode('utf8') if e.stderr else str(e)
        logger.error(f"FFmpeg Error: {error_message}")
        raise RuntimeError(f"FFmpeg failed: {error_message}")