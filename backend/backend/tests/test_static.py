"""Tests for static file serving at /games/ (PIPE-03)."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from backend.main import GAMES_DIR, app


@pytest.mark.anyio
async def test_static_file_served():
    """A file written to games/{id}/export/ is served at /games/{id}/export/."""
    test_id = str(uuid.uuid4())
    export_dir = GAMES_DIR / test_id / "export"
    export_dir.mkdir(parents=True, exist_ok=True)

    index_file = export_dir / "index.html"
    index_file.write_text("<html><body>test game</body></html>")

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get(f"/games/{test_id}/export/index.html")
        assert resp.status_code == 200
        assert "test game" in resp.text
    finally:
        # Clean up
        import shutil

        shutil.rmtree(GAMES_DIR / test_id, ignore_errors=True)
