from __future__ import annotations

from typing import Any

from backend.src.preprocessing.tasks import preprocess_rawfile_task
from backend.src.tasks import broker


@broker.task
async def extract_and_embed_task(rawfile_id: str) -> dict[str, Any]:
    """Backward-compatible task name for the unified PostgreSQL preprocessing path."""

    return await preprocess_rawfile_task(rawfile_id)
