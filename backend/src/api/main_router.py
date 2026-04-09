from __future__ import annotations

from fastapi import APIRouter

from backend.src.api.endpoints.ingestion import router as ingestion_router

api_router = APIRouter()
api_router.include_router(ingestion_router)
