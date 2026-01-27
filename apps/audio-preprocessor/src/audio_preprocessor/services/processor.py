import logging
import os
from pathlib import Path

from audio_preprocessor.utils.ffmpeg_ops import process_audio
from shared_messaging.producer import RabbitMQProducer
from shared_schemas.commands import PreprocessCommand
from shared_schemas.events import PreprocessCompletedEvent
from shared_storage.s3 import S3Client

logger = logging.getLogger(__name__)


class AudioProcessorService:
    def __init__(self, s3: S3Client, producer: RabbitMQProducer):
        self.s3 = s3
        self.producer = producer
        self.temp_dir = Path("tmp/audio-processing")
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def handle_command(self, cmd_data: dict):
        command = PreprocessCommand(**cmd_data)
        job_id = command.job_id
        local_input = self.temp_dir / f"{job_id}_input"
        local_output = self.temp_dir / f"{job_id}_clean.wav"
        try:
            logger.info(f"Starting Preprocess Job: {job_id}")
            files = self.s3.list_files(command.input_path)
            if not files:
                raise FileNotFoundError(f"No files found in S3 prefix: {command.input_path}")
            actual_s3_key = files[0]
            logger.info(f"Found file to process: {actual_s3_key}")
            await self.s3.download_file(actual_s3_key, str(local_input))
            process_audio(str(local_input), str(local_output))
            s3_output_key = f"clean/{job_id}/audio.wav"
            await self.s3.upload_file(str(local_output), s3_output_key)
            event = PreprocessCompletedEvent(
                job_id=job_id,
                clean_audio_path=s3_output_key
            )
            await self.producer.publish("worker_events", "preprocess.done", event)
            logger.info(f"Job {job_id} Completed. Uploaded to {s3_output_key}")

        except Exception as e:
            logger.error(f"Job {job_id} Failed: {e}")
            raise e

        finally:
            if local_input.exists(): os.remove(local_input)
            if local_output.exists(): os.remove(local_output)
