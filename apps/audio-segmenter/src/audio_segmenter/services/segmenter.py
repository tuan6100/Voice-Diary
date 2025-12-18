import logging
import shutil
from pathlib import Path

from audio_segmenter.utils.splitter import split_audio_smart
from shared_schemas.commands import SegmentCommand
from shared_messaging.producer import RabbitMQProducer
from shared_schemas.events import SegmentCompletedEvent
from shared_storage.s3 import S3Client

logger = logging.getLogger(__name__)


class AudioSegmenterService:
    def __init__(self, s3: S3Client, producer: RabbitMQProducer):
        self.s3 = s3
        self.Producer = producer
        self.temp_dir = Path("tmp/audio-segmenting").resolve()
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def handle_command(self, cmd_data: dict):
        command = SegmentCommand(**cmd_data)
        job_id = command.job_id
        job_dir = self.temp_dir / job_id
        input_file = job_dir / "input.wav"
        output_chunks_dir = job_dir / "chunks"

        try:
            if job_dir.exists(): shutil.rmtree(job_dir)
            job_dir.mkdir(parents=True, exist_ok=True)
            output_chunks_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"Starting Segmentation Job: {job_id}")

            # FIX: Thêm await và str(path)
            await self.s3.download_file(command.input_path, str(input_file))

            chunks_meta = split_audio_smart(str(input_file), str(output_chunks_dir))
            logger.info(f"Split into {len(chunks_meta)} chunks.")

            segments_payload = []
            for chunk in chunks_meta:
                s3_key = f"segments/{job_id}/{chunk['filename']}"
                await self.s3.upload_file(chunk['local_path'], s3_key)
                segments_payload.append({
                    "s3_path": s3_key,
                    "start_ms": chunk['start_ms'],
                    "end_ms": chunk['end_ms'],
                    "index": chunk['index']
                })

            event = SegmentCompletedEvent(
                job_id=job_id,
                audio_path=command.input_path,
                segments=segments_payload
            )

            await self.Producer.publish("worker_events", "segment.done", event)
            logger.info(f"Job {job_id} Segmentation Completed.")

        except Exception as e:
            logger.error(f"Job {job_id} Failed: {e}")

        finally:
            if job_dir.exists(): shutil.rmtree(job_dir)