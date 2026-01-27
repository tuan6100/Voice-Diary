import logging
import json
import os
from pathlib import Path
from datetime import datetime, timezone

# Chỉ PostProcessor mới cần import thuật toán alignment
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
            key_manifest = f"analysis/{job_id}/segments_manifest.json"
            chunks_meta = await self.s3.read_json(key_manifest)

            if not chunks_meta:
                raise FileNotFoundError(f"Manifest not found at {key_manifest}")
            full_word_list = []
            logger.info(f"Merging {len(chunks_meta)} transcript chunks...")
            for chunk in chunks_meta:
                s3_path = chunk.get('transcript_s3_path')
                chunk_start_sec = chunk.get('start_ms', 0) / 1000.0
                words_data = await self.s3.read_json(s3_path)
                if not words_data: continue
                for word in words_data:
                    word['start'] += chunk_start_sec
                    word['end'] += chunk_start_sec
                    full_word_list.append(word)
            key_diarization = f"analysis/{job_id}/diarization.json"
            diarization_data = await self.s3.read_json(key_diarization)
            if not diarization_data:
                logger.warning(f"Diarization not found for {job_id}. Using Unknown speakers.")
                raw_diarization = []
            else:
                raw_diarization = diarization_data if isinstance(diarization_data, list) else diarization_data.get(
                    'segments', [])

            logger.info("Running alignment algorithm...")
            aligned_segments = align_transcript_with_diarization(full_word_list, raw_diarization)
            txt_lines = []
            header = f"TRANSCRIPT FOR JOB: {job_id}\nDATE: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n" + "=" * 50 + "\n"
            txt_lines.append(header)
            for seg in aligned_segments:
                start_str = self._format_timestamp(seg['start'])
                speaker = seg['speaker']
                text = seg['text']
                txt_lines.append(f"[{start_str}] {speaker}: {text}")
            full_text_content = "\n".join(txt_lines)

            key_final_json = f"results/{job_id}/metadata.json"
            key_final_txt = f"results/{job_id}/transcript.txt"

            final_output = {
                "job_id": job_id,
                "status": "COMPLETED",
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "assets": {
                    "original": f"raw/{job_id}/input.wav",
                    "hls": f"hls/{job_id}/playlist.m3u8",
                    "text_file": key_final_txt
                },
                "results": {
                    "transcript_aligned": aligned_segments,
                }
            }
            local_json_str = str(local_final_json)
            with open(local_json_str, 'w', encoding='utf-8') as f:
                json.dump(final_output, f, ensure_ascii=False, indent=2)
            await self.s3.upload_file(local_json_str, key_final_json)
            local_txt_str = str(local_final_txt)
            with open(local_txt_str, 'w', encoding='utf-8') as f:
                f.write(full_text_content)
            await self.s3.upload_file(local_txt_str, key_final_txt)
            logger.info(f"Uploaded final metadata to {key_final_json}")
            event = JobCompletedEvent(
                job_id=job_id,
                metadata_path=key_final_json,
                status="COMPLETED"
            )
            await self.producer.publish("worker_events", "job.finalized", event)

        except Exception as e:
            logger.error(f"Post-processing failed for {job_id}: {e}", exc_info=True)
            raise e

        finally:
            if local_final_json.exists(): os.remove(local_final_json)
            if local_final_txt.exists(): os.remove(local_final_txt)