"""Centralized application settings using environment variables."""

from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Expose backend configuration values."""

    openai_api_key: str | None = None
    neo4j_uri: str | None = None
    neo4j_username: str | None = None
    neo4j_password: str | None = None
    database_url: str = "sqlite:///./osint.db"
    person_service_url: str | None = None
    news_api_key: str | None = None
    twitter_bearer_token: str | None = None
    cors_origins: List[str] = []

    class Config:
        env_file = ".env"
        env_prefix = ""


settings = Settings()
