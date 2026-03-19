"""Unit tests for the Contract Generator stage (Stage 2 of contract pipeline)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.pipelines.base import ProgressEvent
from backend.pipelines.contract.models import GameContract, NodeContract, RichGameSpec
from backend.pipelines.contract.contract_generator import run_contract_generator

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_SPEC = RichGameSpec(
    title="Space Defender",
    genre="shooter",
    mechanics=["shoot", "dodge", "power-ups"],
    visual_hints=["neon", "glow", "dark background"],
    entities=[
        {"name": "Player", "type": "CharacterBody2D", "behavior": "Player-controlled ship"},
        {"name": "Enemy", "type": "CharacterBody2D", "behavior": "Flies in patterns, shoots"},
        {"name": "Bullet", "type": "Area2D", "behavior": "Projectile, damages on contact"},
        {"name": "PowerUp", "type": "Area2D", "behavior": "Collectible buff"},
    ],
    interactions=[
        "Bullet overlaps Enemy -> destroy enemy, add score",
        "Enemy collides Player -> lose health",
        "Player overlaps PowerUp -> activate buff",
    ],
    scene_structure="Single screen with player at bottom, enemies spawning from top",
    win_condition="Survive all enemy waves",
    fail_condition="Health reaches zero",
)

SAMPLE_CONTRACT_JSON = {
    "title": "Space Defender",
    "nodes": [
        {
            "script_path": "player.gd",
            "scene_path": "Player.tscn",
            "node_type": "CharacterBody2D",
            "description": "Player-controlled ship",
            "methods": ["shoot()", "take_damage(amount: int)"],
            "signals": ["died", "health_changed"],
            "groups": ["player"],
            "dependencies": [],
        },
        {
            "script_path": "enemy.gd",
            "scene_path": "Enemy.tscn",
            "node_type": "CharacterBody2D",
            "description": "Enemy ship that flies in patterns",
            "methods": ["patrol()", "attack()"],
            "signals": ["destroyed"],
            "groups": ["enemies"],
            "dependencies": ["player.gd"],
        },
        {
            "script_path": "bullet.gd",
            "scene_path": "Bullet.tscn",
            "node_type": "Area2D",
            "description": "Projectile that damages on contact",
            "methods": [],
            "signals": [],
            "groups": ["projectiles"],
            "dependencies": [],
        },
        {
            "script_path": "power_up.gd",
            "scene_path": "PowerUp.tscn",
            "node_type": "Area2D",
            "description": "Collectible power-up buff",
            "methods": ["activate(target)"],
            "signals": ["collected"],
            "groups": ["pickups"],
            "dependencies": ["player.gd"],
        },
    ],
    "game_manager_enums": {"GameState": ["MENU", "PLAYING", "GAME_OVER"]},
    "game_manager_properties": ["score", "high_score", "lives"],
    "autoloads": ["SignalBus"],
    "main_scene": "Main.tscn",
    "control_scheme": "point_and_shoot",
    "controls": [
        {"key": "Mouse", "action": "Aim"},
        {"key": "Left Click", "action": "Shoot"},
    ],
    "visual_style": {"palette": "neon", "shader": "glow", "mood": "intense"},
}


def _make_mock_client(response_json: dict) -> AsyncMock:
    """Create a mock AsyncAnthropic client that returns the given JSON."""
    client = AsyncMock()
    mock_response = MagicMock()
    mock_content_block = MagicMock()
    mock_content_block.text = json.dumps(response_json)
    mock_response.content = [mock_content_block]
    client.messages.create = AsyncMock(return_value=mock_response)
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_contract_generator_emits_stage_start():
    """run_contract_generator emits a ProgressEvent with type='stage_start' containing 'contract'."""
    client = _make_mock_client(SAMPLE_CONTRACT_JSON)
    emit = AsyncMock()

    await run_contract_generator(client, SAMPLE_SPEC, emit)

    emit.assert_called()
    first_call = emit.call_args_list[0]
    event: ProgressEvent = first_call[0][0]
    assert event.type == "stage_start"
    assert "contract" in event.message.lower()


@pytest.mark.anyio
async def test_contract_generator_returns_game_contract_with_nodes():
    """run_contract_generator returns a GameContract with nodes list populated."""
    client = _make_mock_client(SAMPLE_CONTRACT_JSON)
    emit = AsyncMock()

    result = await run_contract_generator(client, SAMPLE_SPEC, emit)

    assert isinstance(result, GameContract)
    assert len(result.nodes) == 4
    assert result.title == "Space Defender"


@pytest.mark.anyio
async def test_contract_generator_nodes_have_script_path_and_type():
    """Each NodeContract has script_path and node_type set."""
    client = _make_mock_client(SAMPLE_CONTRACT_JSON)
    emit = AsyncMock()

    result = await run_contract_generator(client, SAMPLE_SPEC, emit)

    for node in result.nodes:
        assert isinstance(node, NodeContract)
        assert node.script_path != ""
        assert node.node_type != ""


@pytest.mark.anyio
async def test_contract_generator_includes_control_scheme_and_visual_style():
    """GameContract includes control_scheme and visual_style fields."""
    client = _make_mock_client(SAMPLE_CONTRACT_JSON)
    emit = AsyncMock()

    result = await run_contract_generator(client, SAMPLE_SPEC, emit)

    assert result.control_scheme == "point_and_shoot"
    assert result.visual_style.get("palette") == "neon"
    assert result.visual_style.get("shader") == "glow"


@pytest.mark.anyio
async def test_contract_generator_prompt_includes_spec_and_schemas():
    """The LLM prompt includes the full RichGameSpec JSON and schema info."""
    client = _make_mock_client(SAMPLE_CONTRACT_JSON)
    emit = AsyncMock()

    await run_contract_generator(client, SAMPLE_SPEC, emit)

    client.messages.create.assert_called_once()
    call_kwargs = client.messages.create.call_args
    messages = call_kwargs.kwargs.get("messages") or call_kwargs[1].get("messages")
    user_content = str(messages[0].get("content", ""))
    # Should include spec data
    assert "Space Defender" in user_content
    assert "shooter" in user_content
    # Should include schema info (NodeContract / GameContract)
    system = call_kwargs.kwargs.get("system") or call_kwargs[1].get("system")
    full_prompt = str(system) + user_content
    assert "NodeContract" in full_prompt or "node_type" in full_prompt
    assert "GameContract" in full_prompt or "game_manager_enums" in full_prompt
