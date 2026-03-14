"""Tests for GET /api/stream/{job_id} SSE endpoint (PIPE-02)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from backend.godot.runner import RunResult
from backend.main import app
from backend.pipelines.base import ProgressEvent
from backend.state import active_jobs

_MOCK_RESULT = RunResult(success=True, stderr="", output_path=Path("/tmp/fake"))


def _mock_export():
    return patch(
        "backend.pipelines.stub.pipeline.run_headless_export",
        new_callable=AsyncMock,
        return_value=_MOCK_RESULT,
    )


@pytest.mark.anyio
async def test_stream_content_type():
    """GET /api/stream/{job_id} returns text/event-stream content type."""
    with _mock_export():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Create a job first
            resp = await client.post("/api/generate", json={"prompt": "test"})
            job_id = resp.json()["job_id"]

            # Stream the job
            async with client.stream("GET", f"/api/stream/{job_id}") as stream_resp:
                assert "text/event-stream" in stream_resp.headers.get(
                    "content-type", ""
                )


@pytest.mark.anyio
async def test_stream_yields_events():
    """SSE stream includes stage_start events from stub pipeline."""
    with _mock_export():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Create a job
            resp = await client.post("/api/generate", json={"prompt": "test"})
            job_id = resp.json()["job_id"]

            # Read the full SSE stream
            async with client.stream("GET", f"/api/stream/{job_id}") as stream_resp:
                body = b""
                async for chunk in stream_resp.aiter_bytes():
                    body += chunk
                text = body.decode()

    # SSE stream should contain stage_start events
    assert "stage_start" in text
    # Should also contain a done event
    assert "done" in text


@pytest.mark.anyio
async def test_stream_heartbeat():
    """SSE stream sends a heartbeat comment when the queue is idle."""
    job_id = "heartbeat-test-job"
    queue: asyncio.Queue = asyncio.Queue()
    active_jobs[job_id] = queue

    async def _delayed_producer():
        """Wait longer than one heartbeat interval, then send event + sentinel."""
        await asyncio.sleep(1.5)  # longer than patched 0.5s interval
        await queue.put(ProgressEvent(type="stage_start", stage="gen", message="go"))
        await queue.put(None)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            producer = asyncio.create_task(_delayed_producer())
            with patch("backend.main.HEARTBEAT_INTERVAL_S", 0.5):
                async with client.stream(
                    "GET", f"/api/stream/{job_id}"
                ) as stream_resp:
                    body = b""
                    async for chunk in stream_resp.aiter_bytes():
                        body += chunk
                    text = body.decode()
            await producer
    finally:
        active_jobs.pop(job_id, None)

    # Heartbeat is an SSE comment line starting with ": "
    assert ": ping" in text, f"Expected heartbeat comment in stream output: {text!r}"
    # Pipeline events should still arrive after the heartbeat
    assert "stage_start" in text
