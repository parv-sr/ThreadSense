from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from dotenv import load_dotenv
load_dotenv(override=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ThreadSense v2"
    app_env: str = Field(default="dev", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")

    database_url: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/threadsense",
        alias="DATABASE_URL",
    )

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    taskiq_result_ttl_seconds: int = Field(default=3600, alias="TASKIQ_RESULT_TTL_SECONDS")
    ingest_max_bytes: int = Field(default=50 * 1024 * 1024, alias="INGEST_MAX_BYTES")
    ingest_max_retries: int = Field(default=3, alias="INGEST_MAX_RETRIES")

    openai_embedding_model: str = Field(default="text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL")
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    qdrant_api_key: str | None = Field(default=None, alias="QDRANT_API_KEY")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
