from __future__ import annotations

import asyncio

import structlog
from alembic import command
from alembic.config import Config
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PayloadSchemaType

from backend.src.core.config import get_settings
from backend.src.embeddings.constants import QDRANT_COLLECTION, QDRANT_VECTOR_NAME

logger = structlog.get_logger(__name__)
settings = get_settings()

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
        if client.collection_exists(QDRANT_COLLECTION):
            info = client.get_collection(QDRANT_COLLECTION)
            vectors_cfg = getattr(info.config.params, "vectors", None)
            configured_names: set[str] = set()
            if isinstance(vectors_cfg, dict):
                configured_names = set(vectors_cfg.keys())
            elif vectors_cfg is not None:
                # Single unnamed vector config should be rejected for this app.
                configured_names = {""}

            if QDRANT_VECTOR_NAME not in configured_names:
                raise RuntimeError(
                    "Qdrant collection exists with incompatible vector schema. "
                    f"Expected named vector '{QDRANT_VECTOR_NAME}', found {sorted(configured_names)}."
                )
            logger.info(
                "startup_qdrant_collection_exists",
                collection=QDRANT_COLLECTION,
                vector_name=QDRANT_VECTOR_NAME,
            )
            return

        client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config={
                QDRANT_VECTOR_NAME: VectorParams(
                    size=VECTOR_SIZE,
                    distance=Distance.COSINE,
                )
            },
        )
        client.create_payload_index(QDRANT_COLLECTION, "bhk", field_schema=PayloadSchemaType.FLOAT)
        client.create_payload_index(QDRANT_COLLECTION, "location", field_schema=PayloadSchemaType.TEXT)
        client.create_payload_index(QDRANT_COLLECTION, "sender", field_schema=PayloadSchemaType.KEYWORD)
        client.create_payload_index(QDRANT_COLLECTION, "price", field_schema=PayloadSchemaType.INTEGER)
        logger.info(
            "startup_qdrant_collection_created",
            collection=QDRANT_COLLECTION,
            vector_name=QDRANT_VECTOR_NAME,
        )
    finally:
        client.close()


async def initialize_infrastructure() -> None:
    await run_migrations()
    await asyncio.to_thread(ensure_qdrant_collection)


if __name__ == "__main__":
    asyncio.run(initialize_infrastructure())
