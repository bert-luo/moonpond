"""Tests for POST /api/generate endpoint (PIPE-01)."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.godot.runner import RunResult
from backend.main import app

_MOCK_RESULT = RunResult(success=True, stderr="", output_path=Path("/tmp/fake"))


def _mock_export():
    """Context manager that patches run_headless_export for all generate tests."""
    return patch(
        "backend.pipelines.stub.pipeline.run_headless_export",
        new_callable=AsyncMock,
        return_value=_MOCK_RESULT,
    )


@pytest.mark.anyio
async def test_generate_returns_job_id():
    """POST /api/generate returns 200 with job_id string of length 36."""
    with _mock_export():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/api/generate", json={"prompt": "a space shooter"})
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert len(data["job_id"]) == 36


@pytest.mark.anyio
async def test_job_id_is_uuid():
    """job_id parses as valid UUID4."""
    with _mock_export():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/api/generate", json={"prompt": "test"})
    data = resp.json()
    parsed = uuid.UUID(data["job_id"])
    assert parsed.version == 4


@pytest.mark.anyio
async def test_pipeline_query_param():
    """POST /api/generate?pipeline=stub uses stub pipeline and returns 200."""
    with _mock_export():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/generate?pipeline=stub", json={"prompt": "test"}
            )
    assert resp.status_code == 200


@pytest.mark.anyio
async def test_unknown_pipeline_returns_400():
    """POST /api/generate?pipeline=nonexistent returns 400."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/generate?pipeline=nonexistent", json={"prompt": "test"}
        )
    assert resp.status_code == 400
