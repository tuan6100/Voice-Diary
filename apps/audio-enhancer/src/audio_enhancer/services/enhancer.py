import asyncio
import logging
from pathlib import Path

from audio_enhancer.utils.quality_check import check_audio_quality
from audio_enhancer.utils.enhancement import denoise_audio
from shared_storage.s3 import S3Client
from shared_schemas.events import EnhancementCompletedEvent
from shared_messaging.producer import RabbitMQProducer

logger = logging.getLogger(__name__)


class AudioEnhancerService:
    def __init__(self, s3: S3Client, producer: RabbitMQProducer):
        self.s3 = s3
        self.producer = producer
        self.temp_dir = Path("tmp/audio-enhancer").resolve()
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    async def handle_command(self, cmd_data: dict):
        job_id = cmd_data.get("job_id")
        segment_index = cmd_data.get("index")
        s3_input_path = cmd_data.get("s3_path")
        local_input = self.temp_dir / f"{job_id}_{segment_index}_in.wav"
        local_output = self.temp_dir / f"{job_id}_{segment_index}_out.wav"
        local_input_str = str(local_input.resolve())
        local_output_str = str(local_output.resolve())
        start_ms = cmd_data.get("start_ms")
        end_ms = cmd_data.get("end_ms")

        try:
            logger.info(f"Enhancing Job {job_id} - Seg {segment_index}")
            if not local_input.exists():
                await self.s3.download_file(s3_input_path, local_input_str)
            if not local_input.exists() or local_input.stat().st_size == 0:
                raise FileNotFoundError(f"Downloaded file invalid: {local_input_str}")

            quality_info = await asyncio.to_thread(check_audio_quality, local_input_str)
            logger.info(
                f"Seg {segment_index} Quality: "
                f"{quality_info['level']} (SNR: {quality_info['snr']:.2f})"
            )

            final_s3_path = s3_input_path
            if quality_info["need_denoise"]:
                logger.info(f"Denoising segment {segment_index}...")
                await denoise_audio(local_input_str, local_output_str)
                clean_s3_key = s3_input_path.replace("segments/", "enhanced/")
                await self.s3.upload_file(local_output_str, clean_s3_key)
                final_s3_path = clean_s3_key
                logger.info(f"Segment {segment_index} denoised")
            else:
                logger.info("Audio is clean enough. Skipping denoise.")

            event = EnhancementCompletedEvent(
                job_id=job_id,
                index=segment_index,
                s3_path=final_s3_path,
                snr=quality_info["snr"],
                is_denoised=quality_info["need_denoise"],
                start_ms=start_ms,
                end_ms=end_ms
            )

            await self.producer.publish(
                "worker_events",
                "enhancement.done",
                event
            )

        except Exception as e:
            logger.exception(f"Error enhancing segment {segment_index}")
            raise e

        finally:
            self._safe_cleanup(local_input)
            self._safe_cleanup(local_output)

    @staticmethod
    def _safe_cleanup(path: Path):
        try:
            if path.exists():
                path.unlink()
        except PermissionError:
            logger.warning(f"File still in use, skip cleanup: {path}")
