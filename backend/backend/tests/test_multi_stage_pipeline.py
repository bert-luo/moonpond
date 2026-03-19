"""Integration tests for the MultiStagePipeline end-to-end flow."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.pipelines.base import GameResult, ProgressEvent
from backend.pipelines.multi_stage.pipeline import MultiStagePipeline
from backend.pipelines.registry import get_pipeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GAME_SPEC_JSON = json.dumps(
    {
        "title": "Robot Runner",
        "genre": "platformer",
        "mechanics": ["jump", "dodge"],
        "visual_hints": ["neon", "pixel art"],
    }
)

_GAME_DESIGN_JSON = json.dumps(
    {
        "title": "Robot Runner",
        "genre": "platformer",
        "scenes": [
            {
                "name": "main",
                "description": "Main gameplay scene",
                "nodes": ["CharacterBody2D", "Sprite2D"],
            }
        ],
        "visual_style": {"palette": "neon", "shader": "pixel_art", "mood": "cyberpunk"},
        "mechanics": ["jump", "dodge"],
        "control_scheme": "wasd",
        "controls": [
            {"key": "WASD", "action": "Move robot"},
            {"key": "Space", "action": "Jump"},
        ],
        "win_condition": "Reach the end",
        "fail_condition": "Fall off",
    }
)

_CLEAN_CODE_JSON = json.dumps(
    {
        "main.gd": "extends Node2D\nfunc _ready():\n\tpass",
        "player.gd": 'extends CharacterBody2D\nfunc _physics_process(delta):\n\tif Input.is_action_pressed("move_right"):\n\t\tvelocity.x = 200',
    }
)

_POLISHED_CODE_JSON = json.dumps(
    {
        "main.gd": 'extends Node2D\nfunc _ready():\n\tvar shader = preload("res://assets/shaders/pixel_art.gdshader")\n\tpass',
        "player.gd": 'extends CharacterBody2D\nfunc _physics_process(delta):\n\tif Input.is_action_pressed("move_right"):\n\t\tvelocity.x = 200',
    }
)

_CONTAMINATED_CODE_JSON = json.dumps(
    {
        "main.gd": "extends Node2D\nvar active = True\nfunc _ready():\n\tpass",
        "player.gd": "extends CharacterBody2D\nfunc _physics_process(delta):\n\tpass",
    }
)


def _mock_response(text: str):
    """Create a mock Anthropic response with given text content."""
    mock = MagicMock()
    mock.content = [MagicMock(text=text)]
    return mock


# ---------------------------------------------------------------------------
# Full flow test
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@patch("backend.pipelines.exporter.shutil.copytree")
@patch("backend.pipelines.exporter.run_headless_export")
@patch("backend.pipelines.multi_stage.pipeline.AsyncAnthropic")
async def test_multi_stage_pipeline_full_flow(
    mock_anthropic_cls, mock_export, mock_copytree, tmp_path
):
    from backend.godot.runner import RunResult

    # Set up mock client
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    # LLM calls in order: prompt_enhancer, game_designer, code_generator, visual_polisher
    mock_client.messages.create = AsyncMock(
        side_effect=[
            _mock_response(_GAME_SPEC_JSON),
            _mock_response(_GAME_DESIGN_JSON),
            _mock_response(_CLEAN_CODE_JSON),
            _mock_response(_POLISHED_CODE_JSON),
        ]
    )

    # Mock the exporter
    mock_export.return_value = RunResult(
        success=True, stderr="", output_path=Path("/tmp/test/export/index.html")
    )

    emit = AsyncMock()

    # Pre-create project dir since copytree is mocked
    (tmp_path / "test-job-1" / "project").mkdir(parents=True)

    with patch("backend.pipelines.exporter.GAMES_DIR", tmp_path):
        pipeline = MultiStagePipeline()
        result = await pipeline.generate("Make a robot runner", "test-job-1", emit)

    # Verify result
    assert isinstance(result, GameResult)
    assert result.job_id == "test-job-1"
    assert "test-job-1" in result.wasm_path

    # Verify 5 stage_start events + 1 done event
    emit_calls = [c.args[0] for c in emit.call_args_list if c.args and c.args[0] is not None]
    stage_starts = [e for e in emit_calls if isinstance(e, ProgressEvent) and e.type == "stage_start"]
    done_events = [e for e in emit_calls if isinstance(e, ProgressEvent) and e.type == "done"]

    assert len(stage_starts) == 5
    assert len(done_events) == 1
    assert done_events[0].message == "Your game is ready."

    # Verify None sentinel was emitted
    none_calls = [c for c in emit.call_args_list if c.args and c.args[0] is None]
    assert len(none_calls) == 1


# ---------------------------------------------------------------------------
# Self-correction retry test
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@patch("backend.pipelines.exporter.shutil.copytree")
@patch("backend.pipelines.exporter.run_headless_export")
@patch("backend.pipelines.multi_stage.pipeline.AsyncAnthropic")
async def test_multi_stage_pipeline_self_correction_retry(
    mock_anthropic_cls, mock_export, mock_copytree, tmp_path
):
    from backend.godot.runner import RunResult

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    # LLM calls: prompt_enhancer, game_designer, code_gen (contaminated), code_gen (clean), visual_polisher
    mock_client.messages.create = AsyncMock(
        side_effect=[
            _mock_response(_GAME_SPEC_JSON),
            _mock_response(_GAME_DESIGN_JSON),
            _mock_response(_CONTAMINATED_CODE_JSON),  # First attempt — has Python True
            _mock_response(_CLEAN_CODE_JSON),  # Self-correction retry — clean
            _mock_response(_POLISHED_CODE_JSON),
        ]
    )

    mock_export.return_value = RunResult(
        success=True, stderr="", output_path=Path("/tmp/test/export/index.html")
    )

    emit = AsyncMock()

    # Pre-create project dir since copytree is mocked
    (tmp_path / "test-job-2" / "project").mkdir(parents=True)

    with patch("backend.pipelines.exporter.GAMES_DIR", tmp_path):
        pipeline = MultiStagePipeline()
        result = await pipeline.generate("Make a robot runner", "test-job-2", emit)

    assert isinstance(result, GameResult)
    assert result.job_id == "test-job-2"

    # Code generator was called twice (original + retry), but stage_start emitted only once
    emit_calls = [c.args[0] for c in emit.call_args_list if c.args and c.args[0] is not None]
    code_stage_starts = [
        e for e in emit_calls
        if isinstance(e, ProgressEvent) and e.type == "stage_start" and "code" in e.message.lower()
    ]
    assert len(code_stage_starts) == 1


# ---------------------------------------------------------------------------
# Registry test
# ---------------------------------------------------------------------------


def test_multi_stage_pipeline_registered():
    assert get_pipeline("multi_stage") is MultiStagePipeline
