from __future__ import annotations

import os

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.db.session import AsyncSessionLocal
from backend.src.embeddings.service import EmbeddingService

router = APIRouter(prefix="/admin")


def verify_admin(x_api_key: str = Header(...)) -> None:
    admin_key = os.getenv("THREADSENSE_ADMIN_KEY", "change-me")
    if not admin_key or x_api_key != admin_key:
        raise HTTPException(status_code=403, detail="Forbidden")


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


@router.post("/truncate-embeddings")
async def truncate_embeddings(
    _: None = Depends(verify_admin),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    try:
        await EmbeddingService().truncate_all_points(db)
        return {"status": "success"}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail="Truncate failed") from exc
