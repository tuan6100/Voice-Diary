# Voice Diary

A modular, event-driven audio processing system built as a set of microservices. It ingests audio uploads, processes them through a workflow (preprocess → segment → enhance → language detection → recognition + diarization + transcoding → post-processing), and exposes APIs for upload, streaming, and feed/albums.

## Overview
Voice Diary orchestrates a pipeline of audio processing tasks using async Python services and shared libraries. New uploads are accepted by `audio-api`, then a RabbitMQ-based workflow is orchestrated by `audio-orchestrator`. Work is distributed to specialized worker services.

### API Table
Base URL: `http://localhost:8000/api/v1`****

#### Upload (`/api/v1/upload`)
| Method | Path                               | Purpose                                           | Request                                                     | Response / Notes                                                    |
|--------|------------------------------------|---------------------------------------------------|-------------------------------------------------------------|---------------------------------------------------------------------|
| POST   | `/upload/init`                     | Create an upload session & get a presigned S3 URL | JSON body: `UploadInitRequest` (`filename`, `content_type`) | `UploadInitResponse`: `{ job_id, presigned_url, storage_path }`     |
| POST   | `/upload/{job_id}/confirm`         | Confirm S3 upload and trigger processing          | Path: `job_id` (user_id from `get_current_user_id`)         | `{ "status": "queued" }` and publishes `media_events:file.uploaded` |
| GET    | `/upload/progress/{job_id}`        | Get job status & progress                         | Path: `job_id`                                              | `{job_id, status, progress, message}`                               |
| GET    | `/upload/progress/{job_id}/stream` | Stream job progress (SSE)                         | Path: `job_id`                                              | SSE `update` events, closes on COMPLETED/FAILED                     |
| POST   | `/upload/{job_id}/cancel`          | Cancel a processing job                           | Path: `job_id`                                              | Publishes `audio_ops:cmd.cancel`, sets Redis status `CANCELLING`    |

Implemented handler (needs wiring):
- Controller route: `GET /{job_id}` in `progress.py`
- Intended mount: `api_router.include_router(progress.router, prefix="/upload/status")`

When wired, response is:
```json
{ "job_id": "...", "status": "PROCESSING", "progress": 42, "message": "..." }
```

#### Streaming & transcript (`/api/v1/media`)
| Method | Path                                         | Purpose                          | Request                           | Response / Notes                               |
|--------|----------------------------------------------|----------------------------------|-----------------------------------|------------------------------------------------|
| GET    | `/media/{audio_id}/stream`                   | Get HLS stream info              | Path: `audio_id` (Mongo ObjectId) | `{ stream_url, duration }` or 404 if not ready |
| GET    | `/media/{audio_id}/captions.vtt`             | Get transcript as WebVTT         | Path: `audio_id`                  | `text/vtt` (PlainTextResponse)                 |
| GET    | `/media/{audio_id}/download?format=txt\|vtt` | Download transcript              | Query: `format` default `txt`     | `text/plain` attachment (`.txt` or `.vtt`)     |
| POST   | `/media/{audio_id}/export/google-docs`       | Export transcript to Google Docs | Path: `audio_id`                  | Returns `doc_link`                             |
| PUT    | `/media/{audio_id}/sync-google-docs`         | Sync edited transcript from Docs | Path: `audio_id`                  | Updates DB transcript + syncs artifacts to S3  |

#### Auth (`/api/v1/auth`)
| Method | Path                 | Purpose                    | Request                             | Response / Notes                     |
|--------|----------------------|----------------------------|-------------------------------------|--------------------------------------|
| POST   | `/auth/mobile-login` | Login/Register with Google | JSON: `MobileLoginRequest` (`code`) | `{ access_token, user, token_type }` |

#### Feed & Posts (`/api/v1/feed`)
| Method | Path                   | Purpose                 | Request                                         | Response / Notes                                                   |
|--------|------------------------|-------------------------|-------------------------------------------------|--------------------------------------------------------------------|
| GET    | `/feed/`               | Get feed list           | Query: `limit`, `skip`, optional `q`, `hashtag` | `List[dict]` with `{ post, audio_status, duration, preview_text }` |
| POST   | `/feed/{post_id}/like` | Increment likes counter | Path: `post_id`                                 | `{ likes: <int> }`                                                 |
| POST   | `/feed/{post_id}/view` | Increment views counter | Path: `post_id`                                 | `{ status: "ok" }`                                                 |

#### Albums (`/api/v1/albums`)
| Method | Path                                   | Purpose                  | Request / Params                                                     | Response / Notes                                                                      |
|--------|----------------------------------------|--------------------------|----------------------------------------------------------------------|---------------------------------------------------------------------------------------|
| POST   | `/albums/?title=...`                   | Create an album          | Query: `title` (string). Auth required.                              | Returns `Album` document.                                                             |
| GET    | `/albums/my`                           | Get my albums            | Auth required.                                                       | Returns `List[Album]` for current user.                                               |
| GET    | `/albums/search?keyword=...&limit=10`  | Search albums            | Query: `keyword` (optional, min 1 char), `limit` (int, default 10).  | If no `keyword`, returns recent albums (sorted by `-id`).                             |
| GET    | `/albums/{album_id}`                   | Album detail             | Path: `album_id` (Mongo ObjectId).                                   | Album fields plus `total_tracks`. 404 if not found.                                   |
| PATCH  | `/albums/{album_id}?title=...`         | Rename album             | Path: `album_id`. Query: `title`. Auth required.                     | Returns updated `Album`. 403 if not owner; 404 if not found.                          |
| DELETE | `/albums/{album_id}`                   | Delete album             | Path: `album_id`. Auth required.                                     | `{ "message": "Album deleted successfully" }`. 403 if not owner; 404 if not found.    |
| POST   | `/albums/{album_id}/posts?post_id=...` | Add a post to album      | Path: `album_id`. Query: `post_id` (string ObjectId). Auth required. | Returns updated `Album`. 404 if album/post missing; 403 if not owner.                 |
| DELETE | `/albums/{album_id}/posts/{post_id}`   | Remove a post from album | Path: `album_id`, `post_id`. Auth required.                          | Returns updated `Album`. 404 if album missing or post not in album; 403 if not owner. |
| GET    | `/albums/{album_id}/playlist`          | Playlist for album       | Path: `album_id`.                                                    | `{ id, album, tracks[], total_duration }` (tracks include `file` = HLS URL).          |
| GET    | `/albums/{album_id}/shuffle`           | Shuffle playlist         | Path: `album_id`.                                                    | `{ id, album, mode: "shuffle", tracks[] }`.                                           |



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
