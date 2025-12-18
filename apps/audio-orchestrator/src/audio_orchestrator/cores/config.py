from typing import Optional, List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Audio Orchestrator"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    REDIS_URL: str = "redis://localhost:6379/0"
    S3_ENDPOINT: Optional[str] = None
    S3_REGION: str = "ap-southeast-1"
    S3_ACCESS_KEY: str = "S3_ACCESS_KEY"
    S3_SECRET_KEY: str = "S3_SECRET_KEY"
    S3_BUCKET_NAME: str = "audio-management"
    CLEANUP_TARGETS: List[str] = ["clean", "segments", "enhanced", "transcripts"]

    class Config:
        env_file = ".env"


settings = Settings()