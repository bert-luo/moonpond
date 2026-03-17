"""Test scaffold for ContractPipeline skeleton."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.pipelines.base import GameResult, ProgressEvent
from backend.pipelines.contract.pipeline import ContractPipeline


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------


@patch("backend.pipelines.contract.pipeline.AsyncAnthropic")
def test_contract_pipeline_instantiates(mock_anthropic_cls):
    pipeline = ContractPipeline()
    assert pipeline is not None
    mock_anthropic_cls.assert_called_once()


# ---------------------------------------------------------------------------
# generate() returns GameResult
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@patch("backend.pipelines.contract.pipeline.AsyncAnthropic")
async def test_contract_pipeline_generate_returns_game_result(mock_anthropic_cls):
    pipeline = ContractPipeline()
    emit = AsyncMock()

    result = await pipeline.generate(
        prompt="Make a space shooter",
        job_id="test-job-42",
        emit=emit,
        save_intermediate=True,
    )

    assert isinstance(result, GameResult)
    assert result.job_id == "test-job-42"


# ---------------------------------------------------------------------------
# generate() emits ProgressEvents
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@patch("backend.pipelines.contract.pipeline.AsyncAnthropic")
async def test_contract_pipeline_emits_progress(mock_anthropic_cls):
    pipeline = ContractPipeline()
    emit = AsyncMock()

    await pipeline.generate(
        prompt="Make a platformer",
        job_id="test-job-99",
        emit=emit,
    )

    # Should have been called at least twice (stage_start + done) + None sentinel
    assert emit.call_count >= 3

    # Extract ProgressEvent calls (skip None sentinel)
    events = [
        c.args[0]
        for c in emit.call_args_list
        if c.args and c.args[0] is not None
    ]
    assert any(isinstance(e, ProgressEvent) and e.type == "stage_start" for e in events)
    assert any(isinstance(e, ProgressEvent) and e.type == "done" for e in events)

    # Verify None sentinel was emitted
    none_calls = [c for c in emit.call_args_list if c.args and c.args[0] is None]
    assert len(none_calls) == 1
