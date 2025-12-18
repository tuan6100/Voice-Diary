import os
import shutil
import logging
from pathlib import Path

from audio_transcoder.utils.hls_generator import generate_hls_and_waveform
# FIX: Sửa import đúng chuẩn shared_
from shared_messaging.producer import RabbitMQProducer
from shared_schemas.commands import TranscodeCommand
from shared_schemas.events import TranscodeCompletedEvent
from shared_storage.s3 import S3Client

logger = logging.getLogger(__name__)


class AudioTranscoderService:
    def __init__(self, s3: S3Client, producer: RabbitMQProducer):
        self.s3 = s3
        self.Producer = producer
        # FIX: Resolve path
        self.temp_dir = Path("tmp/audio-transcoder").resolve()
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def handle_command(self, cmd_data: dict):
        command = TranscodeCommand(**cmd_data)
        job_id = command.job_id

        job_dir = self.temp_dir / job_id
        input_file = job_dir / "input.wav"
        output_hls_dir = job_dir / "hls"

        try:
            if job_dir.exists(): shutil.rmtree(job_dir)
            job_dir.mkdir(parents=True, exist_ok=True)
            output_hls_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"Transcoding Job {job_id}...")

            # FIX: Thêm await
            await self.s3.download_file(command.input_path, str(input_file))

            generate_hls_and_waveform(str(input_file), str(output_hls_dir))

            s3_base_path = f"hls/{job_id}"

            for filename in os.listdir(output_hls_dir):
                local_path = os.path.join(output_hls_dir, filename)
                s3_key = f"{s3_base_path}/{filename}"

                if os.path.isfile(local_path):
                    # FIX: Thêm await
                    await self.s3.upload_file(local_path, s3_key)

            playlist_path = f"{s3_base_path}/playlist.m3u8"

            event = TranscodeCompletedEvent(
                job_id=job_id,
                hls_path=playlist_path
            )

            await self.Producer.publish("worker_events", "transcode.done", event)
            logger.info(f"Job {job_id} Transcoded & Uploaded.")

        except Exception as e:
            logger.error(f"Transcode failed for {job_id}: {e}")

        finally:
            if job_dir.exists(): shutil.rmtree(job_dir)