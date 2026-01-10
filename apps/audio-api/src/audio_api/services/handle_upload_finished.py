import logging
from shared_schemas.events import JobCompletedEvent
from shared_storage.s3 import S3Client
from audio_api.models.audio import Audio, ProcessingStatus, AudioMetadata
from audio_api.models.post import Post
from audio_api.models.album import Album

logger = logging.getLogger(__name__)


class HandleUploadFinishedService:
    def __init__(self, s3: S3Client):
        self.s3 = s3

    async def handle_job_finalized(self, event_data: dict):
        try:
            event = JobCompletedEvent(**event_data)
            logger.info(f"⚡ Processing finalized job: {event.job_id}")
            metadata = await self.s3.read_json(event.metadata_path)
            if not metadata:
                logger.error("Missing metadata")
                return
            audio = await Audio.find_one(Audio.job_id == event.job_id)
            if not audio:
                logger.warning(f"Audio record not found for job {event.job_id}")
                return
            results = metadata.get("results", {})
            assets = metadata.get("assets", {})
            audio.status = ProcessingStatus.COMPLETED
            audio.audio_meta = AudioMetadata(
                original_url=assets.get("original"),
                hls_url=assets.get("hls"),
                duration=results.get("duration", 0.0)
            )
            audio.transcript = [
                {"start": s["start"], "end": s["end"], "text": s["text"]}
                for s in results.get("transcript_aligned", [])
            ]
            await audio.save()
            linked_post = await Post.find_one(Post.audio_id == str(audio.id))
            if linked_post:
                pass
            await self._add_to_default_album(audio.user_id, str(linked_post.id if linked_post else audio.id))


        except Exception as e:
            logger.error(f"Failed to sync job {event.job_id}: {e}", exc_info=True)

    async def _add_to_default_album(self, user_id: str, item_id: str):
        album = await Album.find_one(Album.user_id == user_id, Album.title == "My Recordings")
        if not album:
            album = Album(user_id=user_id, title="My Recordings", post_ids=[])
            await album.insert()

        if item_id not in album.post_ids:
            album.post_ids.append(item_id)
            await album.save()