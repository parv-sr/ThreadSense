from __future__ import annotations

from fastapi import APIRouter

from backend.src.api.endpoints.chat import router as chat_router
from backend.src.api.endpoints.ingestion import router as ingestion_router
from backend.management.truncate_points import router as truncate_vector_router
from backend.management.truncate_db import router as truncate_sql_router

from backend.src.api.dependencies import get_current_user
from fastapi import Depends

api_router = APIRouter()
api_router.include_router(ingestion_router, dependencies=[Depends(get_current_user)])
api_router.include_router(chat_router, dependencies=[Depends(get_current_user)])
api_router.include_router(truncate_vector_router)
api_router.include_router(truncate_sql_router)