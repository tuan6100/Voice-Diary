from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Audio Enhancer Worker"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    S3_ENDPOINT: Optional[str] = None
    S3_REGION: str = "ap-southeast-1"
    S3_ACCESS_KEY: str = "S3_ACCESS_KEY"
    S3_SECRET_KEY: str = "S3_SECRET_KEY"
    S3_BUCKET_NAME: str = "audio-management"

    SPEECHBRAIN_CACHE_DIR: str = "/tmp/pretrained_models"

    class Config:
        env_file = ".env"


settings = Settings()