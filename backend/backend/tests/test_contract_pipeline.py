"""Integration tests for the ContractPipeline end-to-end flow."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.pipelines.base import GameResult, ProgressEvent
from backend.pipelines.contract.pipeline import ContractPipeline


# ---------------------------------------------------------------------------
# Helpers — mock LLM responses for each stage
# ---------------------------------------------------------------------------

_RICH_GAME_SPEC_JSON = json.dumps(
    {
        "title": "Space Blaster",
        "genre": "shooter",
        "mechanics": ["shoot", "dodge"],
        "visual_hints": ["neon", "glow"],
        "entities": [
            {"name": "Player", "type": "CharacterBody2D", "behavior": "moves and shoots"},
            {"name": "Enemy", "type": "Area2D", "behavior": "moves toward player"},
        ],
        "interactions": ["Player bullet hits Enemy"],
        "scene_structure": "Main scene with Player and Enemy spawner",
        "win_condition": "Survive for 60 seconds",
        "fail_condition": "Player health reaches 0",
    }
)

_GAME_CONTRACT_JSON = json.dumps(
    {
        "title": "Space Blaster",
        "nodes": [
            {
                "script_path": "player.gd",
                "scene_path": None,
                "node_type": "CharacterBody2D",
                "description": "Player ship",
                "methods": ["shoot()", "take_damage(amount: int)"],
                "signals": ["died"],
                "groups": ["player"],
                "dependencies": [],
            },
            {
                "script_path": "enemy.gd",
                "scene_path": None,
                "node_type": "Area2D",
                "description": "Enemy ship",
                "methods": ["die()"],
                "signals": ["destroyed"],
                "groups": ["enemies"],
                "dependencies": [],
            },
        ],
        "game_manager_enums": {"GameState": ["PLAYING", "GAME_OVER"]},
        "game_manager_properties": ["score", "health"],
        "autoloads": [],
        "main_scene": "Main.tscn",
        "control_scheme": "wasd",
        "controls": [
            {"key": "WASD", "action": "Move ship"},
            {"key": "Space", "action": "Shoot"},
        ],
        "visual_style": {"palette": "neon", "shader": "glow", "mood": "intense"},
    }
)

_NODE_FILES_JSON = json.dumps(
    {
        "player.gd": 'extends CharacterBody2D\nfunc _ready():\n\tpass\nfunc shoot():\n\tpass\nfunc take_damage(amount: int):\n\tpass',
    }
)

_ENEMY_FILES_JSON = json.dumps(
    {
        "enemy.gd": "extends Area2D\nfunc _ready():\n\tpass\nfunc die():\n\tpass",
    }
)

_MAIN_TSCN = (
    '[gd_scene load_steps=3 format=3]\n'
    '[ext_resource type="Script" path="res://player.gd" id="1"]\n'
    '[ext_resource type="Script" path="res://enemy.gd" id="2"]\n'
    '[node name="Main" type="Node2D"]\n'
    '[node name="Player" type="CharacterBody2D" parent="."]\n'
    'script = ExtResource("1")\n'
    '[node name="Enemy" type="Area2D" parent="."]\n'
    'script = ExtResource("2")\n'
)


def _mock_response(text: str):
    """Create a mock Anthropic response with given text content."""
    mock = MagicMock()
    mock.content = [MagicMock(text=text)]
    return mock


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------


@patch("backend.pipelines.contract.pipeline.AsyncAnthropic")
def test_contract_pipeline_instantiates(mock_anthropic_cls):
    pipeline = ContractPipeline()
    assert pipeline is not None
    mock_anthropic_cls.assert_called_once()


# ---------------------------------------------------------------------------
# Full flow test with mocked LLM
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@patch("backend.pipelines.exporter.shutil.copytree")
@patch("backend.pipelines.exporter.run_headless_export")
@patch("backend.pipelines.contract.pipeline.AsyncAnthropic")
async def test_contract_pipeline_full_flow(
    mock_anthropic_cls, mock_export, mock_copytree, tmp_path
):
    from backend.godot.runner import RunResult

    # Set up mock client
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    # LLM calls in order:
    # 1. spec_expander
    # 2. contract_generator
    # 3. node_generator — player.gd (wave 1, all nodes at depth 0)
    # 4. node_generator — enemy.gd (wave 1, parallel with player)
    # 5. wiring_generator — Main.tscn
    mock_client.messages.create = AsyncMock(
        side_effect=[
            _mock_response(_RICH_GAME_SPEC_JSON),
            _mock_response(_GAME_CONTRACT_JSON),
            _mock_response(_NODE_FILES_JSON),
            _mock_response(_ENEMY_FILES_JSON),
            _mock_response(_MAIN_TSCN),
        ]
    )

    # Mock the Godot exporter
    mock_export.return_value = RunResult(
        success=True, stderr="", output_path=Path("/tmp/test/export/index.html")
    )

    emit = AsyncMock()

    # Make copytree mock create the destination dir so file writes succeed
    def fake_copytree(src, dst, **kwargs):
        Path(dst).mkdir(parents=True, exist_ok=True)

    mock_copytree.side_effect = fake_copytree

    with (
        patch("backend.pipelines.exporter.GAMES_DIR", tmp_path),
        patch("backend.pipelines.contract.pipeline.GAMES_DIR", tmp_path),
    ):
        pipeline = ContractPipeline()
        result = await pipeline.generate(
            "Make a space shooter", "test-job-contract", emit
        )

    # Verify result is a valid GameResult
    assert isinstance(result, GameResult)
    assert result.wasm_path  # non-empty
    assert isinstance(result.controls, list)
    assert len(result.controls) == 2

    # Verify progress events were emitted
    emit_calls = [
        c.args[0]
        for c in emit.call_args_list
        if c.args and c.args[0] is not None
    ]
    stage_starts = [
        e for e in emit_calls
        if isinstance(e, ProgressEvent) and e.type == "stage_start"
    ]
    done_events = [
        e for e in emit_calls
        if isinstance(e, ProgressEvent) and e.type == "done"
    ]

    # At least: contract pipeline start, spec_expander, contract_generator,
    # node_generator waves, wiring_generator, exporter = multiple stage_starts
    assert len(stage_starts) >= 5
    assert len(done_events) == 1
    assert done_events[0].message == "Your game is ready."

    # Verify None sentinel was emitted (exactly once)
    none_calls = [c for c in emit.call_args_list if c.args and c.args[0] is None]
    assert len(none_calls) == 1


# ---------------------------------------------------------------------------
# Intermediate artifacts test
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@patch("backend.pipelines.exporter.shutil.copytree")
@patch("backend.pipelines.exporter.run_headless_export")
@patch("backend.pipelines.contract.pipeline.AsyncAnthropic")
async def test_contract_pipeline_saves_intermediates(
    mock_anthropic_cls, mock_export, mock_copytree, tmp_path
):
    from backend.godot.runner import RunResult

    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    mock_client.messages.create = AsyncMock(
        side_effect=[
            _mock_response(_RICH_GAME_SPEC_JSON),
            _mock_response(_GAME_CONTRACT_JSON),
            _mock_response(_NODE_FILES_JSON),
            _mock_response(_ENEMY_FILES_JSON),
            _mock_response(_MAIN_TSCN),
        ]
    )

    mock_export.return_value = RunResult(
        success=True, stderr="", output_path=Path("/tmp/test/export/index.html")
    )

    # Make copytree mock create the destination dir so file writes succeed
    def fake_copytree(src, dst, **kwargs):
        Path(dst).mkdir(parents=True, exist_ok=True)

    mock_copytree.side_effect = fake_copytree

    emit = AsyncMock()

    with (
        patch("backend.pipelines.exporter.GAMES_DIR", tmp_path),
        patch("backend.pipelines.contract.pipeline.GAMES_DIR", tmp_path),
    ):
        pipeline = ContractPipeline()
        await pipeline.generate(
            "Make a space shooter", "test-job-inter", emit, save_intermediate=True
        )

    # Find intermediate dir (slug + timestamp)
    intermediate_dirs = list(tmp_path.glob("*/intermediate"))
    assert len(intermediate_dirs) >= 1
    dump_dir = intermediate_dirs[0]

    # Check all intermediate files exist
    assert (dump_dir / "1_rich_game_spec.json").exists()
    assert (dump_dir / "2_game_contract.json").exists()
    assert (dump_dir / "3_node_files").is_dir()
    assert (dump_dir / "4_wiring_files").is_dir()
    assert (dump_dir / "5_result.json").exists()


# ---------------------------------------------------------------------------
# Error handling test
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@patch("backend.pipelines.contract.pipeline.AsyncAnthropic")
async def test_contract_pipeline_error_emits_and_reraises(mock_anthropic_cls):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    # Spec expander will fail
    mock_client.messages.create = AsyncMock(
        side_effect=RuntimeError("LLM unavailable")
    )

    emit = AsyncMock()
    pipeline = ContractPipeline()

    with pytest.raises(RuntimeError, match="LLM unavailable"):
        await pipeline.generate("fail", "test-err", emit)

    # Should have emitted error event + None sentinel
    emit_calls = [
        c.args[0]
        for c in emit.call_args_list
        if c.args and c.args[0] is not None
    ]
    error_events = [
        e for e in emit_calls
        if isinstance(e, ProgressEvent) and e.type == "error"
    ]
    assert len(error_events) >= 1

    none_calls = [c for c in emit.call_args_list if c.args and c.args[0] is None]
    assert len(none_calls) >= 1
