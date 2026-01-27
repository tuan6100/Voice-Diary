import uvicorn
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from audio_api.cores import injectable
from audio_api.cores.config import settings
from audio_api.cores.database import init_db
from audio_api.router.router import api_router

from shared_messaging.producer import RabbitMQProducer
from shared_messaging.consumer import RabbitMQConsumer
from shared_storage.s3 import S3Client
from audio_api.services.handle_upload_finished import HandleUploadFinishedService


logger = logging.getLogger(__name__)
consumer: RabbitMQConsumer = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Audio API...")

    await init_db()
    logger.info("Database Connected")

    s3_client = S3Client(
        bucket=settings.S3_BUCKET_NAME,
        endpoint=settings.S3_ENDPOINT,
        access_key=settings.S3_ACCESS_KEY,
        secret_key=settings.S3_SECRET_KEY
    )

    producer = RabbitMQProducer(settings.RABBITMQ_URL)
    await producer.connect()
    injectable._Producer = producer
    logger.info("Producer Connected")

    global consumer
    consumer = RabbitMQConsumer(settings.RABBITMQ_URL, service_name="audio_api_listener")
    await consumer.connect()
    consumer_service = HandleUploadFinishedService(s3_client)

    await consumer.subscribe(
        exchange_name="worker_events",
        routing_key="job.finalized",
        handler=consumer_service.handle_job_finalized
    )
    logger.info("Background Consumer Listening...")

    yield

    logger.info("Stopping Audio API...")
    if consumer:
        await consumer.close()
    if producer:
        await producer.close()
    injectable._Producer = None


app = FastAPI(
    title=settings.PROJECT_NAME,
    lifespan=lifespan,
    swagger_ui_parameters={"syntaxHighlight": {"theme": "nord"}}
)

# CORS
origins = ["http://localhost:5173", "*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OAuth2
app.add_middleware(SessionMiddleware, secret_key=settings.JWT_SECRET_KEY)

# Router
app.include_router(api_router, prefix="/api/v1")

@app.get("/health")
def health():
    return {"status": "ok", "service": "audio-api-monolith"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)