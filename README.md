# Voice Diary

A modular, event-driven audio processing system built as a set of microservices. It ingests audio uploads, processes them through a workflow (preprocess → segment → enhance → language detection → recognition + diarization + transcoding → post-processing), and exposes APIs for upload, streaming, and feed/albums.

> This README is generated from the actual code structure in `apps/` and shared libraries in `libs/`.

## Table of Contents
- Overview
- Architecture
  - Runtime Dependencies (Docker Compose)
  - Data Flow (High level)
  - Storage Layout (S3 keys)
  - State/Progress Tracking (Redis)
  - Messaging (RabbitMQ)
- Services and Responsibilities
- API Reference (audio-api)
- Installation
- Running
  - Start Infrastructure (Docker Compose)
  - Run Services (uv)
- Configuration
- Workflow Walkthrough
- Error Handling and DLQ
- Troubleshooting
- Testing
- Next Steps

## Overview
Voice Diary orchestrates a pipeline of audio processing tasks using async Python services and shared libraries. New uploads are accepted by `audio-api`, then a RabbitMQ-based workflow is orchestrated by `audio-orchestrator`. Work is distributed to specialized worker services.

## Architecture

### Runtime Dependencies (Docker Compose)
`docker-compose.yml` currently starts **infrastructure only**:
- MongoDB (Beanie models in `audio-api`)
- RabbitMQ (event bus)
- Redis (job progress/state)

> The Python apps themselves are run with `uv run ...` (see Running).

### Data Flow (High level)
1. Client calls `audio-api` to create an upload session.
2. Client uploads the file directly to S3 using a presigned URL.
3. Client confirms upload; `audio-api` publishes a `FileUploadedEvent`.
4. `audio-orchestrator` subscribes to `media_events:file.uploaded`, initializes job state in Redis, then publishes commands to `audio_ops`.
5. Workers consume commands from `audio_ops` and publish `worker_events:*.*.done` events.
6. When all steps are ready, `audio-postprocessor` emits `worker_events:job.finalized`.
7. Both `audio-orchestrator` and `audio-api` subscribe to `worker_events:job.finalized`:
   - Orchestrator marks job COMPLETED and performs cleanup.
   - API updates MongoDB `Audio`/`Post` metadata.

### Storage Layout (S3 keys)
The pipeline uses S3 prefixes consistently (see `UploadFlowService` + worker services):
- Raw upload: `raw/<YYYY-MM-DD>/<job_id>/<filename>`
- Cleaned audio: `clean/<job_id>/audio.wav`
- Segments: `segments/<job_id>/<chunk_filename>.wav`
- Enhanced segments (optional): `enhanced/<job_id>/...`
- Transcripts: `transcripts/<job_id>/<index>.json`
- Analysis:
  - `analysis/<job_id>/transcript.json`
  - `analysis/<job_id>/diarization.json`
- Final results:
  - `results/<job_id>/metadata.json`
  - `results/<job_id>/transcript.txt`
- HLS output: `hls/<job_id>/playlist.m3u8` (+ TS/media files)

### State/Progress Tracking (Redis)
Redis keys are written by the orchestrator (`apps/audio-orchestrator/.../state_manager.py`) and read by `audio-api/controllers/audio/progress.py`.

Key schema:
- `job:{job_id}` (HASH)
  - `user_id`, `status`, `progress`, `message`
- `job:{job_id}:steps` (HASH)
  - `preprocess=1`, `segmenting_trigger=1`, `transcode_trigger=1`, `recognition_all=1`, `diarization=1`, `postprocess_triggered=1`, `transcode=1`
- `job:{job_id}:cnt` (HASH)
  - `total`, `done` (recognition segments counters)
- `job:{job_id}:transcripts` (LIST)
  - JSON strings with recognized segment fragments

Note: jobs have a TTL (currently 1 hour by default in `StateManager.ttl`). If the key expires, status endpoints will return 404.

### Messaging (RabbitMQ)
RabbitMQ exchanges used by the code:
- `media_events` (events from API → orchestrator)
  - `file.uploaded`
- `audio_ops` (commands from orchestrator → workers)
  - `cmd.preprocess`
  - `cmd.segment`
  - `cmd.enhance`
  - `cmd.lang_detect`
  - `cmd.recognize`
  - `cmd.diarize`
  - `cmd.transcode`
  - `cmd.postprocess`
- `worker_events` (events from workers → orchestrator + api)
  - `preprocess.done`
  - `segment.done`
  - `enhancement.done`
  - `lang_detect.done`
  - `recognition.done`
  - `diarization.done`
  - `transcode.done`
  - `job.finalized`

DLQ behavior is implemented in `libs/messaging/src/shared_messaging/consumer.py`:
- For each subscription, a DLQ exchange is created: `<exchange_name>.dlq`
- Retries are tracked via message header `x-retry`
- If retry count exceeds `max_retries` (default **3**), message is published to the DLQ exchange.

## Services and Responsibilities

### `audio-api` (HTTP + background consumer)
- HTTP FastAPI app mounted under `/api/v1` (see `apps/audio-api/src/main.py`).
- Also runs a background RabbitMQ consumer that listens to `worker_events:job.finalized` to sync final results into MongoDB.

Key internal services:
- `UploadFlowService` (`audio_api/services/upload_flow.py`)
  - Generates S3 presigned URL.
  - Publishes `FileUploadedEvent` to `media_events:file.uploaded` after confirm.
- `HandleUploadFinishedService` (`audio_api/services/handle_upload_finished.py`)
  - Consumes `JobCompletedEvent` from `worker_events:job.finalized`.
  - Reads `results/<job_id>/metadata.json` from S3 and updates `Audio` record (HLS URL, duration, transcript aligned, etc.).

### `audio-orchestrator`
The orchestrator is the workflow brain (see `apps/audio-orchestrator/src/audio_orchestrator/services/workflow.py`).
It:
- Initializes job state in Redis
- Publishes commands to workers
- Ensures idempotency via `job:{job_id}:steps`
- Aggregates recognition results in Redis
- Triggers post-processing when recognition + diarization + transcoding are all complete
- Cleans up S3 after finalization

### Workers (consume `audio_ops:*`, publish `worker_events:*`)
- `audio-preprocessor`
  - consumes: `audio_ops:cmd.preprocess` (`PreprocessCommand`)
  - produces: `worker_events:preprocess.done` (`PreprocessCompletedEvent`)
- `audio-segmenter`
  - consumes: `audio_ops:cmd.segment` (`SegmentCommand`)
  - produces: `worker_events:segment.done` (`SegmentCompletedEvent`)
- `audio-enhancer`
  - consumes: `audio_ops:cmd.enhance`
  - produces: `worker_events:enhancement.done` (`EnhancementCompletedEvent`)
- `audio-langdetector`
  - consumes: `audio_ops:cmd.lang_detect` (`LanguageDetectCommand`)
  - produces: `worker_events:lang_detect.done` (`LanguageDetectionCompletedEvent`)
- `audio-recognizer`
  - consumes: `audio_ops:cmd.recognize` (`RecognizeCommand`)
  - produces: `worker_events:recognition.done` (`RecognitionCompletedEvent`)
- `audio-diarizer`
  - consumes: `audio_ops:cmd.diarize`
  - produces: `worker_events:diarization.done` (`DiarizationCompletedEvent`)
- `audio-transcoder`
  - consumes: `audio_ops:cmd.transcode` (`TranscodeCommand`)
  - produces: `worker_events:transcode.done` (`TranscodeCompletedEvent`)
- `audio-postprocessor`
  - consumes: `audio_ops:cmd.postprocess`
  - produces: `worker_events:job.finalized` (`JobCompletedEvent`)

## API Reference (audio-api)
Base URL:
- API: `http://localhost:8000/api/v1`
- Health: `http://localhost:8000/health`

### API Table

#### Upload (`/api/v1/upload`)
| Method | Path                        | Purpose                                           | Request                                                     | Response / Notes                                                    |
|--------|-----------------------------|---------------------------------------------------|-------------------------------------------------------------|---------------------------------------------------------------------|
| POST   | `/upload/init`              | Create an upload session & get a presigned S3 URL | JSON body: `UploadInitRequest` (`filename`, `content_type`) | `UploadInitResponse`: `{ job_id, presigned_url, storage_path }`     |
| POST   | `/upload/{job_id}/confirm`  | Confirm S3 upload and trigger processing          | Path: `job_id` (user_id from `get_current_user_id`)         | `{ "status": "queued" }` and publishes `media_events:file.uploaded` |
| GET    | `/upload/progress/{job_id}` | Get job status & progress                         | Path: `job_id`                                              | `{job_id, status, progress, message}`                               |


Implemented handler (needs wiring):
- Controller route: `GET /{job_id}` in `progress.py`
- Intended mount: `api_router.include_router(progress.router, prefix="/upload/status")`

When wired, response is:
```json
{ "job_id": "...", "status": "PROCESSING", "progress": 42, "message": "..." }
```

#### Streaming & transcript (`/api/v1/media`)
| Method | Path                                         | Purpose                  | Request                           | Response / Notes                               |
|--------|----------------------------------------------|--------------------------|-----------------------------------|------------------------------------------------|
| GET    | `/media/{audio_id}/stream`                   | Get HLS stream info      | Path: `audio_id` (Mongo ObjectId) | `{ stream_url, duration }` or 404 if not ready |
| GET    | `/media/{audio_id}/captions.vtt`             | Get transcript as WebVTT | Path: `audio_id`                  | `text/vtt` (PlainTextResponse)                 |
| GET    | `/media/{audio_id}/download?format=txt\|vtt` | Download transcript      | Query: `format` default `txt`     | `text/plain` attachment (`.txt` or `.vtt`)     |

#### Feed & Posts (`/api/v1/feed`)
| Method | Path                   | Purpose                 | Request                                         | Response / Notes                                                   |
|--------|------------------------|-------------------------|-------------------------------------------------|--------------------------------------------------------------------|
| GET    | `/feed/`               | Get feed list           | Query: `limit`, `skip`, optional `q`, `hashtag` | `List[dict]` with `{ post, audio_status, duration, preview_text }` |
| POST   | `/feed/{post_id}/like` | Increment likes counter | Path: `post_id`                                 | `{ likes: <int> }`                                                 |
| POST   | `/feed/{post_id}/view` | Increment views counter | Path: `post_id`                                 | `{ status: "ok" }`                                                 |

#### Albums (`/api/v1/albums`)
| Method | Path                          | Purpose             | Request                                                          | Response / Notes                                        |
|--------|-------------------------------|---------------------|------------------------------------------------------------------|---------------------------------------------------------|
| POST   | `/albums/`                    | Create an album     | Query: `title` (and `user_id` defaults to `test_user` currently) | Album document                                          |
| POST   | `/albums/{album_id}/add`      | Add a post to album | Path: `album_id`, Query: `post_id`                               | Album document                                          |
| GET    | `/albums/{album_id}/playlist` | Playlist for album  | Path: `album_id`                                                 | `{ album, tracks[] }` (tracks include `file` = HLS URL) |

### Notes
- `auth` and `profile` controllers exist but are not implemented / not wired (see `audio_api/router/router.py`).

## Installation
This repo is an `uv` workspace (`pyproject.toml` at repo root includes `apps/*` and `libs/*`).

Prerequisites:
- Python 3.11+
- `uv`
- Docker (for RabbitMQ/Redis/Mongo)

Install dependencies:
```bash
uv sync --all-packages
```

## Running

### Start Infrastructure (Docker Compose)
Start MongoDB, RabbitMQ, and Redis:
```bash
docker compose up -d
```

### Run Services (uv)
Run each component in its own terminal.

API:
```bash
uv run python apps/audio-api/src/main.py
```

Orchestrator:
```bash
uv run python apps/audio-orchestrator/src/main.py
```

Workers:
```bash
uv run python apps/audio-preprocessor/src/main.py
uv run python apps/audio-segmenter/src/main.py
uv run python apps/audio-enhancer/src/main.py
uv run python apps/audio-langdetector/src/main.py
uv run python apps/audio-recognizer/src/main.py
uv run python apps/audio-diarizer/src/main.py
uv run python apps/audio-transcoder/src/main.py
uv run python apps/audio-postprocessor/src/main.py
```

## Configuration
Each app reads settings from its own `cores/config.py`. Common env vars used across apps:
- `RABBITMQ_URL`
- `REDIS_URL` (orchestrator + progress)
- `MONGODB_URL` (audio-api)
- `S3_BUCKET_NAME`, `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`

## Workflow Walkthrough
1. `POST /api/v1/upload/init` → returns `job_id` and `presigned_url`.
2. Client `PUT` audio bytes to the `presigned_url` (direct to S3).
3. `POST /api/v1/upload/{job_id}/confirm` → publishes `FileUploadedEvent`.
4. Orchestrator receives event and runs:
   - preprocess → segment + diarize (parallel) + transcode (triggered on segment)
   - per-segment enhance → lang_detect → recognize
   - when recognition_all + diarization + transcode are done → postprocess
   - postprocess emits `job.finalized`

## Error Handling and DLQ
- Consumers retry failed messages by republishing with header `x-retry`.
- **If retry more than 3 times**, message is published to the DLQ exchange (`<exchange>.dlq`) with the same routing key.

Operational tip: create a small DLQ consumer/monitor to alert on DLQ growth.

