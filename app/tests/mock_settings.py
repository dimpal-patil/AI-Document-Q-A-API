# tests/mock_settings.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///:memory:"
    REDIS_URL: str = "redis://localhost:6379"
    SECRET_KEY: str = "testsecret"
    OPENAI_API_KEY: str = "testkey"

settings = Settings()