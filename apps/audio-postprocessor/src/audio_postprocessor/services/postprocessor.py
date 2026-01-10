import logging
import json
import os
from pathlib import Path
from datetime import datetime, timezone

from audio_postprocessor.utils.alignment import align_transcript_with_diarization
from shared_messaging.producer import RabbitMQProducer
from shared_storage.s3 import S3Client
from shared_schemas.events import JobCompletedEvent

logger = logging.getLogger(__name__)


class AudioPostProcessorService:
    def __init__(self, s3: S3Client, producer: RabbitMQProducer):
        self.s3 = s3
        self.producer = producer
        self.temp_dir = Path("tmp/audio-postprocessor").resolve()
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def _format_timestamp(self, seconds: float) -> str:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m:02d}:{s:02d}"

    async def handle_command(self, cmd_data: dict):
        job_id = cmd_data.get("job_id")
        logger.info(f"Starting Alignment & Post-processing for Job: {job_id}")
        local_final_json = self.temp_dir / f"{job_id}_final.json"
        local_final_txt = self.temp_dir / f"{job_id}_transcript.txt"
        try:
            key_transcript = f"analysis/{job_id}/transcript.json"
            key_diarization = f"analysis/{job_id}/diarization.json"
            key_final_json = f"results/{job_id}/metadata.json"
            key_final_txt = f"results/{job_id}/transcript.txt"
            transcript_data = await self.s3.read_json(key_transcript)
            diarization_data = await self.s3.read_json(key_diarization)
            if not transcript_data:
                raise FileNotFoundError(f"Transcript not found for {job_id}")
            if not diarization_data:
                logger.warning(f"Diarization not found for {job_id}. Using Unknown speakers.")
                diarization_data = []
            raw_segments = transcript_data if isinstance(transcript_data, list) else transcript_data.get('segments', [])
            raw_diarization = diarization_data
            if isinstance(diarization_data, dict):
                raw_diarization = diarization_data.get('segments', [])
            aligned_segments = align_transcript_with_diarization(raw_segments, raw_diarization)
            txt_lines = []
            header = f"TRANSCRIPT FOR JOB: {job_id}\nDATE: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n" + "=" * 50 + "\n"
            txt_lines.append(header)
            for seg in aligned_segments:
                start_str = self._format_timestamp(seg['start'])
                speaker = seg['speaker']
                text = seg['text']
                txt_lines.append(f"[{start_str}] {speaker}: {text}")
            full_text_content = "\n".join(txt_lines)
            final_output = {
                "job_id": job_id,
                "status": "COMPLETED",
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "assets": {
                    "original": f"raw/{job_id}/input.wav",
                    "hls": f"hls/{job_id}/playlist.m3u8",
                    "text_file": key_final_txt  # Link đến file text
                },
                "results": {
                    "transcript_aligned": aligned_segments,
                }
            }

            # 6. Lưu và Upload JSON
            local_json_str = str(local_final_json)
            with open(local_json_str, 'w', encoding='utf-8') as f:
                json.dump(final_output, f, ensure_ascii=False, indent=2)
            await self.s3.upload_file(local_json_str, key_final_json)

            # 7. Lưu và Upload TXT
            local_txt_str = str(local_final_txt)
            with open(local_txt_str, 'w', encoding='utf-8') as f:
                f.write(full_text_content)
            await self.s3.upload_file(local_txt_str, key_final_txt)

            logger.info(f"Uploaded final metadata and text to {key_final_json}")

            event = JobCompletedEvent(
                job_id=job_id,
                metadata_path=key_final_json,
                status="COMPLETED"
            )
            await self.producer.publish("worker_events", "job.finalized", event)

        except Exception as e:
            logger.error(f"Post-processing failed for {job_id}: {e}", exc_info=True)

        finally:
            if local_final_json.exists(): os.remove(local_final_json)
            if local_final_txt.exists(): os.remove(local_final_txt)