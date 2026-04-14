from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

from backend.src.api.endpoints.chat import build_rag_agent
from backend.src.api.main_router import api_router
from backend.src.core.config import get_settings
from backend.src.tasks import broker

settings = get_settings()


def configure_logging() -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
    )


configure_logging()
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await broker.startup()
    logger.info("taskiq_started", redis_url=settings.redis_url)

    # === QDRANT COLLECTION AUTO-CREATION (pure dense vector - simple & stable) ===
    logger.info("Initializing Qdrant collection...")

    client = QdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key,
        timeout=10,
    )

    COLLECTION_NAME = "threadsense_listings"
    VECTOR_SIZE = 1536                    # text-embedding-3-small
    DISTANCE = Distance.COSINE

    # Force recreate to fix any previous hybrid/sparse configuration issues
    if client.collection_exists(COLLECTION_NAME):
        logger.info(f"Deleting existing collection '{COLLECTION_NAME}' to ensure clean state")
        client.delete_collection(COLLECTION_NAME)

    logger.info(f"Creating Qdrant collection '{COLLECTION_NAME}' with dense vector only")
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "dense": VectorParams(
                size=VECTOR_SIZE,
                distance=DISTANCE,
            )
        },
    )
    logger.info(f"✅ Qdrant collection '{COLLECTION_NAME}' created successfully (dense vector only)")

    try:
        app.state.rag_agent = build_rag_agent()
        logger.info("rag_agent_ready")
    except Exception as exc:  # noqa: BLE001
        app.state.rag_agent = None
        logger.exception("rag_agent_init_failed", error=str(exc))

    try:
        yield
    finally:
        await broker.shutdown()
        logger.info("taskiq_shutdown")


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_exception", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )