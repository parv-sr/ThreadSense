"""Tests for upload CRUD operations (create, list, detail, delete)."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from backend.tests.conftest import auth_headers


@pytest.mark.asyncio
async def test_upload_file_creates_rawfile(client: AsyncClient, auth_token: str) -> None:
    files = {"file": ("test_chat.txt", b"[01/01/24, 10:00 AM] Alice: 2bhk rent bandra 50k", "text/plain")}
    resp = await client.post("/api/ingest/", files=files, headers=auth_headers(auth_token))
    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "QUEUED"
    assert "rawfile_id" in data
    assert "task_id" in data


@pytest.mark.asyncio
async def test_upload_rejects_unsupported_format(client: AsyncClient, auth_token: str) -> None:
    files = {"file": ("data.csv", b"col1,col2\n1,2", "text/csv")}
    resp = await client.post("/api/ingest/", files=files, headers=auth_headers(auth_token))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_rejects_empty_file(client: AsyncClient, auth_token: str) -> None:
    files = {"file": ("empty.txt", b"", "text/plain")}
    resp = await client.post("/api/ingest/", files=files, headers=auth_headers(auth_token))
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_uploads(client: AsyncClient, auth_token: str) -> None:
    resp = await client.get("/api/ingest/uploads", headers=auth_headers(auth_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "uploads" in data
    assert isinstance(data["uploads"], list)


@pytest.mark.asyncio
async def test_upload_detail(client: AsyncClient, auth_token: str) -> None:
    # First create an upload
    files = {"file": ("detail_test.txt", b"[01/01/24, 10:00 AM] Bob: 3bhk sale andheri 1.5cr", "text/plain")}
    create_resp = await client.post("/api/ingest/", files=files, headers=auth_headers(auth_token))
    rawfile_id = create_resp.json()["rawfile_id"]

    # Then fetch detail
    resp = await client.get(f"/api/ingest/uploads/{rawfile_id}", headers=auth_headers(auth_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "upload" in data
    assert data["upload"]["rawfileId"] == rawfile_id
    assert "insights" in data


@pytest.mark.asyncio
async def test_upload_detail_returns_dedupe_stats(client: AsyncClient, auth_token: str) -> None:
    files = {"file": ("stats_test.txt", b"[01/01/24, 10:00 AM] Carol: studio rent khar 25k", "text/plain")}
    create_resp = await client.post("/api/ingest/", files=files, headers=auth_headers(auth_token))
    rawfile_id = create_resp.json()["rawfile_id"]

    resp = await client.get(f"/api/ingest/uploads/{rawfile_id}", headers=auth_headers(auth_token))
    data = resp.json()
    assert "dedupeStats" in data["upload"]


@pytest.mark.asyncio
async def test_delete_upload(client: AsyncClient, auth_token: str) -> None:
    # Create
    files = {"file": ("delete_test.txt", b"[01/01/24, 10:00 AM] Dan: 1bhk rent worli", "text/plain")}
    create_resp = await client.post("/api/ingest/", files=files, headers=auth_headers(auth_token))
    rawfile_id = create_resp.json()["rawfile_id"]

    # Delete
    resp = await client.delete(f"/api/ingest/uploads/{rawfile_id}", headers=auth_headers(auth_token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted"] is True

    # Verify it's gone
    detail_resp = await client.get(f"/api/ingest/uploads/{rawfile_id}", headers=auth_headers(auth_token))
    assert detail_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_nonexistent_upload(client: AsyncClient, auth_token: str) -> None:
    resp = await client.delete(
        "/api/ingest/uploads/00000000-0000-0000-0000-000000000000",
        headers=auth_headers(auth_token),
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_upload_progress_endpoint(client: AsyncClient, auth_token: str) -> None:
    files = {"file": ("progress_test.txt", b"[01/01/24, 10:00 AM] Eve: 2bhk rent powai 35k", "text/plain")}
    create_resp = await client.post("/api/ingest/", files=files, headers=auth_headers(auth_token))
    rawfile_id = create_resp.json()["rawfile_id"]

    resp = await client.get(f"/api/ingest/uploads/{rawfile_id}/progress", headers=auth_headers(auth_token))
    assert resp.status_code == 200
    data = resp.json()
    assert "progress" in data
    assert "percentage" in data["progress"]


@pytest.mark.asyncio
async def test_cannot_access_other_users_upload(client: AsyncClient, test_engine) -> None:
    from backend.tests.conftest import auth_token as create_token
    token1 = await create_token(client, test_engine)
    files = {"file": ("user1.txt", b"[01/01/24] Alice: 2bhk rent", "text/plain")}
    resp1 = await client.post("/api/ingest/", files=files, headers=auth_headers(token1))
    upload_id = resp1.json()["rawfile_id"]

    token2 = await create_token(client, test_engine)
    fetch_resp = await client.get(f"/api/ingest/uploads/{upload_id}", headers=auth_headers(token2))
    assert fetch_resp.status_code in (404, 403)


@pytest.mark.asyncio
async def test_cannot_delete_other_users_upload(client: AsyncClient, test_engine) -> None:
    from backend.tests.conftest import auth_token as create_token
    token1 = await create_token(client, test_engine)
    token2 = await create_token(client, test_engine)
    
    files = {"file": ("user1.txt", b"[01/01/24] Alice: 2bhk rent", "text/plain")}
    resp1 = await client.post("/api/ingest/", files=files, headers=auth_headers(token1))
    upload_id = resp1.json()["rawfile_id"]

    del_resp = await client.delete(f"/api/ingest/uploads/{upload_id}", headers=auth_headers(token2))
    assert del_resp.status_code in (404, 403)
