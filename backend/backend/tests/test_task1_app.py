"""RED phase tests for Task 1: FastAPI app, stub pipeline, registry wiring."""

import pytest


def test_app_imports():
    """backend.main should be importable and expose an app."""
    from backend.main import app
    assert app is not None


def test_registry_has_stub():
    """Registry should contain 'stub' mapping to StubPipeline."""
    from backend.pipelines.registry import PIPELINES
    from backend.pipelines.stub.pipeline import StubPipeline
    assert "stub" in PIPELINES
    assert PIPELINES["stub"] is StubPipeline


def test_stub_pipeline_importable():
    """StubPipeline class should be importable."""
    from backend.pipelines.stub.pipeline import StubPipeline
    assert StubPipeline is not None


@pytest.mark.anyio
async def test_generate_endpoint_returns_job_id():
    """POST /api/generate should return 200 with a job_id."""
    from httpx import ASGITransport, AsyncClient
    from backend.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/generate", json={"prompt": "test"})
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert len(data["job_id"]) == 36


@pytest.mark.anyio
async def test_unknown_pipeline_returns_400():
    """POST /api/generate?pipeline=nonexistent should return 400."""
    from httpx import ASGITransport, AsyncClient
    from backend.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            "/api/generate?pipeline=nonexistent", json={"prompt": "test"}
        )
    assert resp.status_code == 400
