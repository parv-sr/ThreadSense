from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.src.api.main_router import api_router
from backend.src.core.config import get_settings
from backend.src.db.diagnostics import mask_database_url
from backend.src.startup import initialize_infrastructure
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
log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # ── Stage 1: Database migrations ──────────────────────────────────────
        await initialize_infrastructure()

        # ── Stage 2: Celery broker connection ─────────────────────────────────
        await broker.startup()
        log.info("broker_connected", redis_url=settings.redis_broker_url)

        # ── Stage 3: Orphan recovery ──────────────────────────────────────────
        try:
            from backend.src.tasks.recovery import recover_orphaned_tasks
            await recover_orphaned_tasks()
        except Exception as exc:  # noqa: BLE001
            log.error("orphan_recovery_failed", error=str(exc))

        # ── Stage 4: Ready ────────────────────────────────────────────────────
        log.info(
            "startup_ready",
            database=mask_database_url(settings.database_url),
            llm_model=settings.openrouter_chat_model,
            embedding_model=settings.openrouter_embedding_model,
        )
    except Exception:
        import traceback
        traceback.print_exc()
        raise

    try:
        yield
    finally:
        await broker.shutdown()
        log.info("shutdown_complete")


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
app.include_router(api_router, prefix="/api")


@app.get("/health")
async def health(request: Request) -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_exception", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "An internal server error occurred."},
    )
