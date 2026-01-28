from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, List

from botocore.exceptions import ClientError

from audio_api.models.audio import TranscriptSegment
from shared_storage.s3 import S3Client


@dataclass(frozen=True)
class TranscriptS3SyncResult:
    job_id: str
    segments_count: int
    processed_at: str
    written_keys: List[str]

class TranscriptS3SyncService:

    def __init__(self, s3: S3Client):
        self.s3 = s3

    @staticmethod
    def _keys(job_id: str) -> tuple[str, str, str]:
        key_final_json = f"results/{job_id}/metadata.json"
        key_final_txt = f"results/{job_id}/transcript.txt"
        key_analysis_final = f"analysis/{job_id}/transcript_final.json"
        return key_final_json, key_final_txt, key_analysis_final

    @staticmethod
    def _transcript_dicts(segments: Iterable[TranscriptSegment]) -> list[dict]:
        return [
            {
                "start": seg.start,
                "end": seg.end,
                "text": seg.text,
                "speaker": "UNKNOWN",
            }
            for seg in segments
        ]

    @staticmethod
    def _transcript_txt(job_id: str, segments: Iterable[TranscriptSegment]) -> str:
        txt_content = f"TRANSCRIPT FOR JOB: {job_id} (Edited via Google Docs)\n" + "=" * 50 + "\n"
        for seg in segments:
            m = int(seg.start // 60)
            s = int(seg.start % 60)
            txt_content += f"[{m:02d}:{s:02d}] {seg.text}\n"
        return txt_content

    async def sync_edited_transcript(
        self,
        *,
        job_id: str,
        transcript_segments: List[TranscriptSegment],
        processed_at: datetime | None = None,
    ) -> TranscriptS3SyncResult:
        if not job_id:
            raise ValueError("job_id is required")
        processed_at_dt = processed_at or datetime.now(timezone.utc)
        processed_at_str = processed_at_dt.isoformat()
        key_final_json, key_final_txt, key_analysis_final = self._keys(job_id)
        transcript_dicts = self._transcript_dicts(transcript_segments)
        try:
            existing_meta = await self.s3.read_json(key_final_json)
        except ClientError:
            existing_meta = None

        if not existing_meta:
            existing_meta = {"job_id": job_id, "assets": {}, "results": {}}

        existing_meta.setdefault("results", {})
        existing_meta["results"]["transcript_aligned"] = transcript_dicts
        existing_meta["processed_at"] = processed_at_str
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8") as tmp:
            json.dump(existing_meta, tmp, ensure_ascii=False, indent=2)
            tmp_meta_path = tmp.name
        try:
            await self.s3.upload_file(tmp_meta_path, key_final_json)
        finally:
            try:
                os.remove(tmp_meta_path)
            except OSError:
                pass

        txt_content = self._transcript_txt(job_id, transcript_segments)
        with tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8") as tmp:
            tmp.write(txt_content)
            tmp_txt_path = tmp.name
        try:
            await self.s3.upload_file(tmp_txt_path, key_final_txt)
        finally:
            try:
                os.remove(tmp_txt_path)
            except OSError:
                pass

        with tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8") as tmp:
            json.dump(transcript_dicts, tmp, ensure_ascii=False, indent=2)
            tmp_analysis_path = tmp.name
        try:
            await self.s3.upload_file(tmp_analysis_path, key_analysis_final)
        finally:
            try:
                os.remove(tmp_analysis_path)
            except OSError:
                pass

        return TranscriptS3SyncResult(
            job_id=job_id,
            segments_count=len(transcript_segments),
            processed_at=processed_at_str,
            written_keys=[key_final_json, key_final_txt, key_analysis_final],
        )
