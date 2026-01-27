import asyncio
import os
import json
import logging
from pathlib import Path

from audio_recognizer.utils.engine import WhisperEngine
from shared_messaging.producer import RabbitMQProducer
from shared_schemas.commands import RecognizeCommand
from shared_schemas.events import RecognitionCompletedEvent
from shared_storage.s3 import S3Client

logger = logging.getLogger(__name__)


class AudioRecognizerService:
    def __init__(self, s3: S3Client, producer: RabbitMQProducer):
        self.s3 = s3
        self.Producer = producer
        self.temp_dir = Path("tmp/audio-recognizer").resolve()
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def handle_command(self, cmd_data: dict):
        command = RecognizeCommand(**cmd_data)
        job_id = command.job_id
        index = command.index
        start_ms = command.start_ms
        end_ms = command.end_ms
        local_input = self.temp_dir / f"{job_id}_{index}.wav"
        local_output_json = self.temp_dir / f"{job_id}_{index}.json"
        local_input_str = str(local_input)
        local_output_str = str(local_output_json)
        language = command.language

        try:
            logger.info(f"Processing Recognizer Job {job_id} - Chunk {index}")
            if not local_input.exists():
                await self.s3.download_file(command.input_path, local_input_str)
            def run_whisper_blocking():
                engine = WhisperEngine.get_instance()
                return engine.transcribe_file(local_input_str, language)
            words_data = await asyncio.to_thread(run_whisper_blocking)
            with open(local_output_str, "w", encoding="utf-8") as f:
                json.dump(words_data, f, ensure_ascii=False)
            s3_json_key = f"transcripts/{job_id}/{index}.json"
            await self.s3.upload_file(local_output_str, s3_json_key)
            full_text = " ".join([w.get('word', '') for w in words_data])
            event = RecognitionCompletedEvent(
                job_id=job_id,
                index=index,
                text=full_text,
                confidence=0.95,
                start_ms=start_ms,
                end_ms=end_ms,
                transcript_s3_path=s3_json_key
            )
            await self.Producer.publish("worker_events", "recognition.done", event)
            logger.info(f"Job {job_id} Chunk {index} Done.")

        except Exception as e:
            logger.error(f"Recognition failed for {job_id}_{index}: {e}")
            raise e

        finally:
            if local_input.exists(): os.remove(local_input)
            if local_output_json.exists(): os.remove(local_output_json)