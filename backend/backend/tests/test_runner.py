"""Tests for Godot headless runner (PIPE-05)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.godot.runner import run_headless_export


def _make_mock_process(returncode: int = 0, stderr: bytes = b"") -> MagicMock:
    """Create a mock subprocess process."""
    proc = MagicMock()
    proc.communicate = AsyncMock(return_value=(b"", stderr))
    proc.returncode = returncode
    return proc


@pytest.mark.anyio
async def test_runner_validates_file_not_exit_code(tmp_path: Path):
    """RunResult.success is False when output file missing despite exit code 0."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    export_dir = tmp_path / "export"

    mock_proc = _make_mock_process(returncode=0, stderr=b"")

    with patch(
        "backend.godot.runner.asyncio.create_subprocess_exec",
        new_callable=AsyncMock,
        return_value=mock_proc,
    ):
        result = await run_headless_export(project_dir, export_dir)

    # Exit code was 0 but no output file exists -> success should be False
    assert result.success is False


@pytest.mark.anyio
async def test_runner_captures_stderr(tmp_path: Path):
    """RunResult.stderr contains subprocess stderr output."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    export_dir = tmp_path / "export"

    mock_proc = _make_mock_process(returncode=1, stderr=b"ERROR: something failed")

    with patch(
        "backend.godot.runner.asyncio.create_subprocess_exec",
        new_callable=AsyncMock,
        return_value=mock_proc,
    ):
        result = await run_headless_export(project_dir, export_dir)

    assert result.stderr == "ERROR: something failed"
