"""Integration tests for the ingestion API endpoints using shared fixtures."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from backend.tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_ingest_endpoint_accepts_upload(client: AsyncClient, auth_token: str) -> None:
    files = {"file": ("chat.txt", b"[01/01/24, 10:00 AM] Alice: rent 2bhk bandra 50k", "text/plain")}
    response = await client.post("/api/ingest/", files=files, headers=auth_headers(auth_token))
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "QUEUED"
    assert "rawfile_id" in data


@pytest.mark.asyncio
async def test_ingest_endpoint_rejects_invalid_format(client: AsyncClient, auth_token: str) -> None:
    files = {"file": ("data.pdf", b"%PDF-1.4 content", "application/pdf")}
    response = await client.post("/api/ingest/", files=files, headers=auth_headers(auth_token))
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_ingest_endpoint_rejects_empty(client: AsyncClient, auth_token: str) -> None:
    files = {"file": ("empty.txt", b"", "text/plain")}
    response = await client.post("/api/ingest/", files=files, headers=auth_headers(auth_token))
    assert response.status_code == 400
