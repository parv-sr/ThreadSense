from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from dotenv import load_dotenv


def _should_override_from_dotenv() -> bool:
    app_env = os.getenv("APP_ENV", "dev").strip().lower()
    is_local_env = app_env in {"dev", "local"}
    is_container_runtime = Path("/.dockerenv").exists() or any(
        os.getenv(key) for key in ("KUBERNETES_SERVICE_HOST", "CONTAINERIZED", "DOCKER_CONTAINER")
    )
    return is_local_env and not is_container_runtime


load_dotenv(override=_should_override_from_dotenv())


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
        default="postgresql+asyncpg://postgres:postgres@postgres:5432/threadsense",
        alias="DATABASE_URL",
    )

    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_token: str | None = Field(default=None, alias="REDIS_TOKEN")
    taskiq_result_ttl_seconds: int = Field(default=3600, alias="TASKIQ_RESULT_TTL_SECONDS")
    ingest_max_bytes: int = Field(default=50 * 1024 * 1024, alias="INGEST_MAX_BYTES")
    ingest_max_retries: int = Field(default=3, alias="INGEST_MAX_RETRIES")
    db_pool_size: int = Field(default=5, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=5, alias="DB_MAX_OVERFLOW")
    db_pool_timeout_seconds: int = Field(default=30, alias="DB_POOL_TIMEOUT_SECONDS")
    db_pool_recycle_seconds: int = Field(default=1800, alias="DB_POOL_RECYCLE_SECONDS")

    openai_embedding_model: str = Field(default="text-embedding-3-small", alias="OPENAI_EMBEDDING_MODEL")
    qdrant_url: str | None = Field(default=None, alias="QDRANT_URL")
    qdrant_cluster_endpoint: str | None = Field(default=None, alias="QDRANT_CLUSTER_ENDPOINT")
    qdrant_api_key: str | None = Field(default=None, alias="QDRANT_API_KEY")

    @property
    def qdrant_endpoint(self) -> str:
        return (self.qdrant_cluster_endpoint or self.qdrant_url or "http://localhost:6333").strip()

    @property
    def redis_broker_url(self) -> str:
        parsed = urlparse(self.redis_url)
        if not self.redis_token or parsed.password:
            return self.redis_url

        username = parsed.username or ""
        auth = f":{self.redis_token}" if not username else f"{username}:{self.redis_token}"
        netloc = f"{auth}@{parsed.hostname or ''}"
        if parsed.port:
            netloc += f":{parsed.port}"
        return urlunparse((parsed.scheme, netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
