"""Unit tests for all five pipeline stages."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.pipelines.base import GameResult, ProgressEvent
from backend.pipelines.exporter import run_exporter
from backend.pipelines.multi_stage.code_generator import (
    _check_gdscript_syntax_patterns,
    run_code_generator,
)
from backend.pipelines.multi_stage.game_designer import run_game_designer
from backend.pipelines.multi_stage.models import (
    ControlMapping,
    ControlScheme,
    GameDesign,
    GameSpec,
    SceneSpec,
    VisualStyle,
)
from backend.pipelines.multi_stage.prompt_enhancer import run_prompt_enhancer
from backend.pipelines.multi_stage.visual_polisher import run_visual_polisher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_response(text: str):
    """Create a mock Anthropic response with given text content."""
    mock = MagicMock()
    mock.content = [MagicMock(text=text)]
    return mock


# Realistic mock data
_GAME_SPEC_JSON = '{"title": "Robot Runner", "genre": "platformer", "mechanics": ["jump", "dodge"], "visual_hints": ["neon", "pixel art"]}'

_GAME_DESIGN_JSON = """{
  "title": "Robot Runner",
  "genre": "platformer",
  "scenes": [
    {"name": "main", "description": "Main gameplay scene", "nodes": ["CharacterBody2D", "Sprite2D", "CollisionShape2D"]}
  ],
  "visual_style": {"palette": "neon", "shader": "pixel_art", "mood": "cyberpunk action"},
  "mechanics": ["jump", "dodge"],
  "control_scheme": "wasd",
  "controls": [
    {"key": "WASD", "action": "Move robot"},
    {"key": "Space", "action": "Jump"}
  ],
  "win_condition": "Reach the end of the level",
  "fail_condition": "Fall off the platform or hit an enemy"
}"""

_CODE_FILES_JSON = '{"main.gd": "extends Node2D\\nfunc _ready():\\n\\tpass", "player.gd": "extends CharacterBody2D\\nfunc _physics_process(delta):\\n\\tif Input.is_action_pressed(\\"move_right\\"):\\n\\t\\tvelocity.x = 200"}'

_POLISHED_FILES_JSON = '{"main.gd": "extends Node2D\\nfunc _ready():\\n\\tvar shader = preload(\\"res://assets/shaders/pixel_art.gdshader\\")\\n\\tpass", "player.gd": "extends CharacterBody2D\\nfunc _physics_process(delta):\\n\\tif Input.is_action_pressed(\\"move_right\\"):\\n\\t\\tvelocity.x = 200"}'

_GAME_DESIGN = GameDesign(
    title="Robot Runner",
    genre="platformer",
    scenes=[
        SceneSpec(
            name="main",
            description="Main gameplay scene",
            nodes=["CharacterBody2D", "Sprite2D", "CollisionShape2D"],
        )
    ],
    visual_style=VisualStyle(palette="neon", shader="pixel_art", mood="cyberpunk action"),
    mechanics=["jump", "dodge"],
    control_scheme=ControlScheme.WASD,
    controls=[
        ControlMapping(key="WASD", action="Move robot"),
        ControlMapping(key="Space", action="Jump"),
    ],
    win_condition="Reach the end of the level",
    fail_condition="Fall off the platform or hit an enemy",
)


# ---------------------------------------------------------------------------
# Prompt Enhancer tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_prompt_enhancer_returns_game_spec():
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_mock_response(_GAME_SPEC_JSON))
    emit = AsyncMock()

    result = await run_prompt_enhancer(client, "Make a robot running game", emit)

    assert isinstance(result, GameSpec)
    assert result.title == "Robot Runner"
    assert result.genre == "platformer"
    assert result.mechanics == ["jump", "dodge"]
    assert result.visual_hints == ["neon", "pixel art"]


@pytest.mark.anyio
async def test_prompt_enhancer_emits_stage_start():
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_mock_response(_GAME_SPEC_JSON))
    emit = AsyncMock()

    await run_prompt_enhancer(client, "Make a robot running game", emit)

    emit.assert_any_call(
        ProgressEvent(type="stage_start", message="Understanding your idea...")
    )


# ---------------------------------------------------------------------------
# Game Designer tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_game_designer_returns_game_design():
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_mock_response(_GAME_DESIGN_JSON))
    emit = AsyncMock()

    game_spec = GameSpec(
        title="Robot Runner",
        genre="platformer",
        mechanics=["jump", "dodge"],
        visual_hints=["neon", "pixel art"],
    )
    result = await run_game_designer(client, game_spec, emit)

    assert isinstance(result, GameDesign)
    assert result.title == "Robot Runner"
    assert result.control_scheme == ControlScheme.WASD
    assert result.visual_style.palette == "neon"
    assert len(result.scenes) == 1
    assert len(result.controls) == 2


@pytest.mark.anyio
async def test_game_designer_emits_stage_start():
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_mock_response(_GAME_DESIGN_JSON))
    emit = AsyncMock()

    game_spec = GameSpec(
        title="Robot Runner",
        genre="platformer",
        mechanics=["jump", "dodge"],
        visual_hints=["neon", "pixel art"],
    )
    await run_game_designer(client, game_spec, emit)

    emit.assert_any_call(
        ProgressEvent(type="stage_start", message="Designing game structure...")
    )


# ---------------------------------------------------------------------------
# Code Generator tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_code_generator_returns_dict():
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_mock_response(_CODE_FILES_JSON))
    emit = AsyncMock()

    result = await run_code_generator(client, _GAME_DESIGN, emit)

    assert isinstance(result, dict)
    assert "main.gd" in result
    assert "player.gd" in result


@pytest.mark.anyio
async def test_code_generator_emits_stage_start_only_first_call():
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_mock_response(_CODE_FILES_JSON))
    emit = AsyncMock()

    # First call (no previous_error) — should emit stage_start
    await run_code_generator(client, _GAME_DESIGN, emit, previous_error=None)
    emit.assert_any_call(
        ProgressEvent(type="stage_start", message="Writing game code...")
    )

    emit.reset_mock()

    # Retry call (with previous_error) — should NOT emit stage_start
    await run_code_generator(client, _GAME_DESIGN, emit, previous_error="some error")
    stage_starts = [
        c
        for c in emit.call_args_list
        if c.args and isinstance(c.args[0], ProgressEvent) and c.args[0].type == "stage_start"
    ]
    assert len(stage_starts) == 0


def test_code_generator_syntax_checker_catches_python_patterns():
    files = {
        "test.gd": 'extends Node2D\nvar active = True\nvar other = False\nvar val = None',
    }
    result = _check_gdscript_syntax_patterns(files)
    assert result is not None
    assert "True" in result
    assert "False" in result
    assert "None" in result


def test_code_generator_syntax_checker_catches_is_key_pressed():
    files = {
        "test.gd": "extends Node2D\nfunc _input(event):\n\tif Input.is_key_pressed(KEY_A):\n\t\tpass",
    }
    result = _check_gdscript_syntax_patterns(files)
    assert result is not None
    assert "is_key_pressed" in result


def test_code_generator_syntax_checker_passes_clean_code():
    files = {
        "main.gd": 'extends Node2D\nfunc _ready():\n\tvar active = true\n\tvar val = null',
        "player.gd": 'extends CharacterBody2D\nfunc _physics_process(delta):\n\tif Input.is_action_pressed("move_right"):\n\t\tvelocity.x = 200',
    }
    result = _check_gdscript_syntax_patterns(files)
    assert result is None


# ---------------------------------------------------------------------------
# Visual Polisher tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_visual_polisher_returns_patched_dict():
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_mock_response(_POLISHED_FILES_JSON))
    emit = AsyncMock()

    files = {"main.gd": "extends Node2D\nfunc _ready():\n\tpass"}
    visual_style = VisualStyle(palette="neon", shader="pixel_art", mood="cyberpunk action")

    result = await run_visual_polisher(client, files, visual_style, emit)

    assert isinstance(result, dict)
    assert "main.gd" in result
    assert "shader" in result["main.gd"]


@pytest.mark.anyio
async def test_visual_polisher_emits_stage_start():
    client = MagicMock()
    client.messages.create = AsyncMock(return_value=_mock_response(_POLISHED_FILES_JSON))
    emit = AsyncMock()

    files = {"main.gd": "extends Node2D"}
    visual_style = VisualStyle(palette="neon", shader="pixel_art", mood="cyberpunk action")

    await run_visual_polisher(client, files, visual_style, emit)

    emit.assert_any_call(
        ProgressEvent(type="stage_start", message="Adding visual polish...")
    )


# ---------------------------------------------------------------------------
# Exporter tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@patch("backend.pipelines.exporter.shutil.copytree")
@patch("backend.pipelines.exporter.run_headless_export")
async def test_exporter_calls_headless_export(mock_export, mock_copytree, tmp_path):
    from backend.godot.runner import RunResult

    # copytree is mocked, so we must pre-create the project dir that copytree would have made
    project_dir = tmp_path / "test-job" / "project"
    project_dir.mkdir(parents=True)

    mock_export.return_value = RunResult(
        success=True,
        stderr="",
        output_path=Path("/tmp/test/export/index.html"),
    )
    emit = AsyncMock()

    with patch("backend.pipelines.exporter.GAMES_DIR", tmp_path):
        result = await run_exporter(
            "test-job",
            {"main.gd": "extends Node2D"},
            [{"key": "WASD", "action": "Move"}],
            emit,
        )

    assert isinstance(result, GameResult)
    assert result.job_id == "test-job"
    assert "test-job" in result.wasm_path
    mock_export.assert_called_once()


@pytest.mark.anyio
@patch("backend.pipelines.exporter.shutil.copytree")
@patch("backend.pipelines.exporter.run_headless_export")
async def test_exporter_emits_stage_start(mock_export, mock_copytree, tmp_path):
    from backend.godot.runner import RunResult

    project_dir = tmp_path / "test-job" / "project"
    project_dir.mkdir(parents=True)

    mock_export.return_value = RunResult(
        success=True,
        stderr="",
        output_path=Path("/tmp/test/export/index.html"),
    )
    emit = AsyncMock()

    with patch("backend.pipelines.exporter.GAMES_DIR", tmp_path):
        await run_exporter(
            "test-job",
            {"main.gd": "extends Node2D"},
            [{"key": "WASD", "action": "Move"}],
            emit,
        )

    emit.assert_any_call(
        ProgressEvent(type="stage_start", message="Building for web...")
    )
