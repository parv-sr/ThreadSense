from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

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
log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await broker.startup()
    log.info("taskiq_started", redis_url=settings.redis_url)
    try:
        yield
    finally:
        await broker.shutdown()
        log.info("taskiq_shutdown")


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled_exception", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )
