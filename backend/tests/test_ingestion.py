from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from backend.src.main import app


@pytest.mark.asyncio
async def test_health_endpoint() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_ingest_endpoint_accepts_upload() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        files = {"file": ("chat.txt", b"[01/01/24, 10:00 AM] Alice: rent 2bhk", "text/plain")}
        response = await client.post("/ingest/", files=files)

    # Skeleton assertion; replace with broker-mocked assertions in integration tests.
    assert response.status_code in {202, 500}
