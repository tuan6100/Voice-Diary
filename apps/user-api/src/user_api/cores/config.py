from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "User Utility API"
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "voice_diary_db"
    class Config:
        env_file = ".env"


settings = Settings()