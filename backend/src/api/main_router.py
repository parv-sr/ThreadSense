from __future__ import annotations

from fastapi import APIRouter

from backend.src.api.endpoints.auth import router as auth_router
from backend.src.api.endpoints.chat import router as chat_router
from backend.src.api.endpoints.ingestion import router as ingestion_router
from backend.src.api.endpoints.listings import router as listings_router
from backend.management.truncate_points import router as truncate_vector_router
from backend.management.truncate_db import router as truncate_sql_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(ingestion_router)
api_router.include_router(listings_router)
api_router.include_router(chat_router)
api_router.include_router(truncate_vector_router)
api_router.include_router(truncate_sql_router)
