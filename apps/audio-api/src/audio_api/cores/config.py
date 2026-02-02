from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "Audio API"
    JWT_SECRET_KEY: str = "JWT_SECRET_KEY"

    # S3 Config
    S3_ENDPOINT: Optional[str] = "https://s3.us-east-1.amazonaws.com"
    S3_REGION: str = "ap-southeast-1"
    S3_ACCESS_KEY: str = "S3_ACCESS_KEY"
    S3_SECRET_KEY: str = "S3_SECRET_KEY"
    S3_BUCKET_NAME: str = "audio-management"

    # Message Queue & Cache
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Database
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "voice_diary_db"

    GOOGLE_CLIENT_ID: str = "GOOGLE_CLIENT_ID"
    GOOGLE_CLIENT_SECRET: str = "GOOGLE_CLIENT_SECRET"
    GOOGLE_SCOPES: str = "email profile https://www.googleapis.com/auth/drive.file https://www.googleapis.com/auth/documents"

    class Config:
        env_file = ".env"


settings = Settings()