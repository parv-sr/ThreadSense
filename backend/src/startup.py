from __future__ import annotations

import asyncio

import structlog
from alembic import command
from alembic.config import Config
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

from backend.src.core.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

COLLECTION_NAME = "threadsense_listings"
VECTOR_NAME = "dense"
VECTOR_SIZE = 1536


def _run_alembic_upgrade() -> None:
    alembic_cfg = Config("backend/alembic.ini")
    command.upgrade(alembic_cfg, "head")


async def run_migrations() -> None:
    logger.info("startup_migrations_begin")
    await asyncio.to_thread(_run_alembic_upgrade)
    logger.info("startup_migrations_done")


def ensure_qdrant_collection() -> None:
    logger.info("startup_qdrant_ensure_begin", qdrant_url=settings.qdrant_endpoint)
    client = QdrantClient(
        url=settings.qdrant_endpoint,
        api_key=settings.qdrant_api_key,
        timeout=10,
    )
    try:
        if client.collection_exists(COLLECTION_NAME):
            logger.info("startup_qdrant_collection_exists", collection=COLLECTION_NAME)
            return

        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config={
                VECTOR_NAME: VectorParams(
                    size=VECTOR_SIZE,
                    distance=Distance.COSINE,
                )
            },
        )
        logger.info("startup_qdrant_collection_created", collection=COLLECTION_NAME)
    finally:
        client.close()


async def initialize_infrastructure() -> None:
    await run_migrations()
    await asyncio.to_thread(ensure_qdrant_collection)


if __name__ == "__main__":
    asyncio.run(initialize_infrastructure())
