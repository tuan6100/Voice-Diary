import os
import logging
from pathlib import Path
import asyncio

from shared_schemas.commands import LanguageDetectCommand
from shared_schemas.events import LanguageDetectionCompletedEvent
from shared_messaging.producer import RabbitMQProducer
from shared_storage.s3 import S3Client
from audio_langdetector.utils.engine import VoxLinguaEngine

logger = logging.getLogger(__name__)


class LanguageDetectorService:
    def __init__(self, s3: S3Client, producer: RabbitMQProducer):
        self.s3 = s3
        self.producer = producer
        self.temp_dir = Path("tmp/audio-langdetector").resolve()
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def handle_command(self, cmd_data: dict):
        command = LanguageDetectCommand(**cmd_data)

        local_input = self.temp_dir / f"{command.job_id}_{command.index}.wav"
        local_input_str = str(local_input.resolve()).replace("\\", "/")

        try:
            logger.info(f"Detecting language for Job {command.job_id} Seg {command.index}...")
            if not local_input.exists():
                await self.s3.download_file(command.input_path, local_input_str)

            def _run_detect():
                engine = VoxLinguaEngine.get_instance()
                return engine.detect(local_input_str)
            lang_code, prob = await asyncio.to_thread(_run_detect)
            logger.info(f"Seg {command.index}: {lang_code} ({prob:.2%})")

            event = LanguageDetectionCompletedEvent(
                job_id=command.job_id,
                language=lang_code,
                probability=prob,
                index=command.index,
                input_path=command.input_path,
                start_ms=command.start_ms,
                end_ms=command.end_ms
            )
            await self.producer.publish("worker_events", "lang_detect.done", event)

        except Exception as e:
            logger.error(f"LangDetect failed: {e}")
            raise e
        finally:
            if local_input.exists(): os.remove(local_input)