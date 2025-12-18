import os
import logging
from pathlib import Path

from audio_diarizer.utils.diarization import diarize_audio
from shared_messaging.producer import RabbitMQProducer
from shared_schemas.events import DiarizationCompletedEvent
from shared_storage.s3 import S3Client

logger = logging.getLogger(__name__)


class DiarizerService:
    def __init__(self, s3: S3Client, producer: RabbitMQProducer):
        self.s3 = s3
        self.Producer = producer
        # FIX: Resolve path
        self.temp_dir = Path("tmp/diarization").resolve()
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def handle_command(self, cmd_data: dict):
        job_id = cmd_data.get("job_id")
        s3_path = cmd_data.get("input_path")

        local_file = self.temp_dir / f"{job_id}.wav"
        local_file_str = str(local_file)

        try:
            logger.info(f"Diarizing Job {job_id}...")
            # FIX: Thêm await
            await self.s3.download_file(s3_path, local_file_str)

            # Đảm bảo hàm này trả về list các dict khớp với SpeakerSegment model
            segments = diarize_audio(local_file_str)
            logger.info(f"Found {len(segments)} turns in audio.")

            event = DiarizationCompletedEvent(
                job_id=job_id,
                speaker_segments=segments
            )
            await self.Producer.publish("worker_events", "diarization.done", event)

        except Exception as e:
            logger.error(f"Diarization failed for {job_id}: {e}")
        finally:
            if local_file.exists(): os.remove(local_file)