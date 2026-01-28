import asyncio
import logging
import json
import os
import tempfile

from audio_orchestrator.cores.config import settings
# Import commands
from shared_schemas.commands import (
    PreprocessCommand, SegmentCommand, RecognizeCommand,
    TranscodeCommand, EnhanceCommand, DiarizeCommand, PostProcessCommand, LanguageDetectCommand
)
# Import events
from shared_schemas.events import (
    FileUploadedEvent, PreprocessCompletedEvent, SegmentCompletedEvent,
    RecognitionCompletedEvent, TranscodeCompletedEvent,
    DiarizationCompletedEvent, EnhancementCompletedEvent, JobCompletedEvent, LanguageDetectionCompletedEvent
)

from audio_orchestrator.services.state_manager import StateManager, JobStatus
from shared_messaging.producer import RabbitMQProducer
from shared_storage.s3 import S3Client  # Cần để upload file transcript tạm

logger = logging.getLogger(__name__)


class WorkflowOrchestrator:
    def __init__(self, producer: RabbitMQProducer, state_manager: StateManager, s3: S3Client):
        self.producer = producer
        self.state = state_manager
        self.s3 = s3

    async def _is_step_completed(self, job_id: str, step_key: str) -> bool:
        return await self.state.redis.hget(f"job:{job_id}:steps", step_key) == "1"

    async def _mark_step_completed(self, job_id: str, step_key: str):
        await self.state.redis.hset(f"job:{job_id}:steps", step_key, "1")

    async def _is_cancelled(self, job_id: str) -> bool:
        status = await self.state.get_job_status(job_id)
        if status == "CANCELLED":
            logger.warning(f"Job {job_id} was CANCELLED. Stopping workflow.")
            return True
        return False

    async def handle_file_uploaded(self, event: dict):
        data = FileUploadedEvent(**event)
        job_id = data.job_id
        if await self.state.get_job_status(job_id):
            logger.info(f"Job {job_id} already exists. Resuming...")
        else:
            logger.info(f"Started flow for Job {job_id}")
            await self.state.init_job(job_id, data.user_id)

        if not await self._is_step_completed(job_id, "preprocess"):
            await self.state.update_progress(job_id, JobStatus.PREPROCESSING, 5, "Cleaning audio...")
            cmd = PreprocessCommand(job_id=job_id, input_path=data.storage_path)
            await self.producer.publish("audio_ops", "cmd.preprocess", cmd)

    async def handle_preprocess_done(self, event: dict):
        data = PreprocessCompletedEvent(**event)
        if await self._is_cancelled(data.job_id): return
        await self._mark_step_completed(data.job_id, "preprocess")

        if not await self._is_step_completed(data.job_id, "segmenting_trigger"):
            await self.state.update_progress(data.job_id, JobStatus.SEGMENTING, 15, "Analyzing structure...")
            cmd_seg = SegmentCommand(job_id=data.job_id, input_path=data.clean_audio_path)
            await self.producer.publish("audio_ops", "cmd.segment", cmd_seg)
            cmd_diar = DiarizeCommand(job_id=data.job_id, input_path=data.clean_audio_path)
            await self.producer.publish("audio_ops", "cmd.diarize", cmd_diar)
            await self._mark_step_completed(data.job_id, "segmenting_trigger")

    async def handle_segment_done(self, event: dict):
        data = SegmentCompletedEvent(**event)
        if await self._is_cancelled(data.job_id): return
        job_id = data.job_id
        total_segments = len(data.segments)
        await self.state.redis.hset(f"job:{job_id}:cnt", "total", str(total_segments))
        await self.state.redis.hset(f"job:{job_id}:cnt", "done", "0")
        if not await self._is_step_completed(job_id, "transcode_trigger"):
            cmd_trans = TranscodeCommand(job_id=job_id, input_path=data.audio_path)
            await self.producer.publish("audio_ops", "cmd.transcode", cmd_trans)
            await self._mark_step_completed(job_id, "transcode_trigger")
        for seg in data.segments:
            cmd = EnhanceCommand(
                job_id=job_id,
                index=seg['index'],
                s3_path=seg['s3_path'],
                start_ms=seg['start_ms'],
                end_ms=seg['end_ms']
            )
            await self.producer.publish("audio_ops", "cmd.enhance", cmd)
        await self.state.update_progress(job_id, JobStatus.PROCESSING, 30, f"Processing {total_segments} chunks...")

    async def handle_diarization_done(self, event: dict):
        try:
            data = DiarizationCompletedEvent(**event)
            if await self._is_cancelled(data.job_id): return
            job_id = data.job_id
            s3_key = f"analysis/{job_id}/diarization.json"
            diar_content = json.dumps([s.model_dump() for s in data.speaker_segments], ensure_ascii=False)
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8') as tmp:
                tmp.write(diar_content)
                tmp_path = tmp.name
            await self.s3.upload_file(tmp_path, s3_key)
            os.remove(tmp_path)
            await self._mark_step_completed(job_id, "diarization")
            await self._check_finish_and_trigger_post(job_id)
        except Exception as e:
            logger.error(f"Error in handle_diarization_done: {e}")

    async def handle_transcode_done(self, event: dict):
        try:
            data = TranscodeCompletedEvent(**event)
            if await self._is_cancelled(data.job_id): return
            await self._mark_step_completed(data.job_id, "transcode")
            await self._check_finish_and_trigger_post(data.job_id)
        except Exception as e:
            logger.error(f"Error in handle_transcode_done: {e}")

    async def handle_enhancement_done(self, event: dict):
        try:
            data = EnhancementCompletedEvent(**event)
            if await self._is_cancelled(data.job_id): return
            logger.info(f"Enhance done {data.job_id}:{data.index}. Sending to LangDetect.")
            cmd_detect = LanguageDetectCommand(
                job_id=data.job_id,
                input_path=data.s3_path,
                index=data.index,
                start_ms=data.start_ms,
                end_ms=data.end_ms
            )
            await self.producer.publish("audio_ops", "cmd.lang_detect", cmd_detect)
        except Exception as e:
            logger.error(f"Error handle_enhancement_done: {e}")

    async def handle_lang_detect_done(self, event: dict):
        try:
            data = LanguageDetectionCompletedEvent(**event)
            if await self._is_cancelled(data.job_id): return
            logger.info(f"LangDetect done {data.job_id}:{data.index} ({data.language}). Sending to Recognize.")
            cmd_recog = RecognizeCommand(
                job_id=data.job_id,
                input_path=data.input_path,
                index=data.index,
                start_ms=data.start_ms,
                end_ms=data.end_ms,
                language=data.language
            )
            await self.producer.publish("audio_ops", "cmd.recognize", cmd_recog)
        except Exception as e:
            logger.error(f"Error handle_lang_detect_done: {e}")

    async def handle_recognition_done(self, event: dict):
        try:
            logger.debug(f"Received Recognition Event: {event}")
            data = RecognitionCompletedEvent(**event)
            if await self._is_cancelled(data.job_id): return
            job_id = data.job_id
            segment_meta = {
                "index": data.index,
                "start_ms": data.start_ms,
                "end_ms": data.end_ms,
                "transcript_s3_path": data.transcript_s3_path
            }
            await self.state.redis.rpush(f"job:{job_id}:transcripts", json.dumps(segment_meta))
            completed_count = await self.state.redis.hincrby(f"job:{job_id}:cnt", "done", 1)
            total_count_str = await self.state.redis.hget(f"job:{job_id}:cnt", "total")
            total_count = int(total_count_str) if total_count_str else 9999
            logger.info(f"Job {job_id}: Recognized {completed_count}/{total_count}")
            if total_count > 0:
                progress_percent = 30 + int((completed_count / total_count) * 40)
                await self.state.update_progress(job_id, JobStatus.PROCESSING, progress_percent)
            if completed_count >= total_count:
                await self._mark_step_completed(job_id, "recognition_all")
                await self._check_finish_and_trigger_post(job_id)
        except Exception as e:
            logger.error(f"Error in handle_recognition_done: {e}")

    async def _check_finish_and_trigger_post(self, job_id: str):
        if await self._is_cancelled(job_id): return
        is_recog_done = await self._is_step_completed(job_id, "recognition_all")
        is_diar_done = await self._is_step_completed(job_id, "diarization")
        is_trans_done = await self._is_step_completed(job_id, "transcode")
        is_already_triggered = await self._is_step_completed(job_id, "postprocess_triggered")
        if is_recog_done and is_diar_done and is_trans_done and not is_already_triggered:
            logger.info(f"Job {job_id}: All inputs ready. Preparing Manifest for PostProcess...")
            await self._mark_step_completed(job_id, "postprocess_triggered")
            raw_meta = await self.state.redis.lrange(f"job:{job_id}:transcripts", 0, -1)
            chunks_meta = [json.loads(x) for x in raw_meta]
            chunks_meta.sort(key=lambda x: x['start_ms'])
            manifest_s3_key = f"analysis/{job_id}/segments_manifest.json"
            with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8') as tmp:
                json.dump(chunks_meta, tmp, ensure_ascii=False)
                tmp_path = tmp.name
            await self.s3.upload_file(tmp_path, manifest_s3_key)
            os.remove(tmp_path)
            logger.info(f"Job {job_id}: Manifest uploaded to {manifest_s3_key}")
            cmd = PostProcessCommand(job_id=job_id)
            await self.producer.publish("audio_ops", "cmd.postprocess", cmd)
            await self.state.update_progress(job_id, JobStatus.POST_PROCESSING, 80, "Finalizing...")

    async def handle_job_finalized(self, event: dict):
        try:
            data = JobCompletedEvent(**event)
            job_id = data.job_id
            logger.info(f"Job {job_id} FULLY COMPLETED. Starting Cleanup...")
            await self.state.update_progress(job_id, JobStatus.COMPLETED, 100, "Audio has been recognized successfully")
            cleanup_tasks = []
            for target in settings.CLEANUP_TARGETS:
                prefix = f"{target}/{job_id}/"
                cleanup_tasks.append(self.s3.delete_folder(prefix))
            if cleanup_tasks:
                await asyncio.gather(*cleanup_tasks)
                logger.info(f"Cleaned up folders: {settings.CLEANUP_TARGETS}")
        except Exception as e:
            logger.error(f"Error in handle_job_finalized: {e}")