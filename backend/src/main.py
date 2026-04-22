from __future__ import annotations

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.src.api.endpoints.chat import build_retriever
from backend.src.api.main_router import api_router
from backend.src.core.config import get_settings
from backend.src.db.diagnostics import PROBE_SQL, mask_database_url
from backend.src.db.session import engine
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
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await initialize_infrastructure()

    await broker.startup()
    logger.info("taskiq_started", redis_url=settings.redis_broker_url)
    logger.info("database_runtime_config", database_url=mask_database_url(settings.database_url))

    async with engine.connect() as conn:
        probe_row = (await conn.execute(PROBE_SQL)).one()
        logger.info(
            "database_runtime_probe",
            current_database=probe_row[0],
            current_schema=probe_row[1],
            inet_server_addr=str(probe_row[2]) if probe_row[2] is not None else None,
            inet_server_port=probe_row[3],
        )

    try:
        app.state.rag_retriever = build_retriever()
        logger.info("rag_retriever_ready")
    except Exception as exc:  # noqa: BLE001
        app.state.rag_retriever = None
        app.state.rag_retriever_error = str(exc)
        logger.warning("rag_retriever_init_failed", error=str(exc))

    try:
        yield
    finally:
        await broker.shutdown()
        logger.info("taskiq_shutdown")


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
app.include_router(api_router)


@app.get("/health")
async def health(request: Request) -> dict[str, str]:
    status = "degraded" if getattr(request.app.state, "rag_retriever", None) is None else "ok"
    return {"status": status, "service": settings.app_name}


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_exception", error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "An internal server error occurred."},
    )
