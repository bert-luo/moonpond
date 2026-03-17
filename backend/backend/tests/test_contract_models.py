"""Unit tests for contract data models (RichGameSpec, NodeContract, GameContract)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.stages.contract_models import GameContract, NodeContract, RichGameSpec


# ---------------------------------------------------------------------------
# RichGameSpec
# ---------------------------------------------------------------------------


def test_rich_game_spec_validates():
    spec = RichGameSpec(
        title="Robot Runner",
        genre="platformer",
        mechanics=["jump", "dodge"],
        visual_hints=["neon", "pixel art"],
        entities=[
            {"name": "Player", "type": "CharacterBody2D", "behavior": "Player-controlled robot"},
            {"name": "Spike", "type": "StaticBody2D", "behavior": "Damages player on contact"},
        ],
        interactions=["Player collides with Spike -> lose health"],
        scene_structure="Single scrolling level with platforms and obstacles",
        win_condition="Reach the end of the level",
        fail_condition="Health reaches zero",
    )
    assert spec.title == "Robot Runner"
    assert spec.genre == "platformer"
    assert len(spec.mechanics) == 2
    assert len(spec.entities) == 2
    assert len(spec.interactions) == 1
    assert spec.scene_structure != ""
    assert spec.win_condition == "Reach the end of the level"
    assert spec.fail_condition == "Health reaches zero"


# ---------------------------------------------------------------------------
# NodeContract
# ---------------------------------------------------------------------------


def test_node_contract_validates():
    node = NodeContract(
        script_path="player.gd",
        node_type="CharacterBody2D",
        description="Player-controlled character",
    )
    assert node.script_path == "player.gd"
    assert node.node_type == "CharacterBody2D"
    assert node.description == "Player-controlled character"
    assert node.scene_path is None
    assert node.methods == []
    assert node.signals == []
    assert node.groups == []
    assert node.dependencies == []


def test_node_contract_empty_dependencies_is_leaf():
    node = NodeContract(
        script_path="spike.gd",
        node_type="StaticBody2D",
        description="Static hazard",
        dependencies=[],
    )
    assert node.dependencies == []


# ---------------------------------------------------------------------------
# GameContract
# ---------------------------------------------------------------------------


def test_game_contract_validates():
    contract = GameContract(
        title="Robot Runner",
        nodes=[
            NodeContract(
                script_path="player.gd",
                node_type="CharacterBody2D",
                description="Player character",
            ),
        ],
        game_manager_enums={"GameState": ["PLAYING", "PAUSED", "GAME_OVER"]},
        autoloads=["SignalBus"],
        main_scene="Main.tscn",
        control_scheme="wasd",
        controls=[{"key": "WASD", "action": "Move"}, {"key": "Space", "action": "Jump"}],
        visual_style={"palette": "neon", "shader": "pixel_art", "mood": "cyberpunk"},
    )
    assert contract.title == "Robot Runner"
    assert len(contract.nodes) == 1
    assert contract.game_manager_enums["GameState"] == ["PLAYING", "PAUSED", "GAME_OVER"]
    assert contract.main_scene == "Main.tscn"
    assert contract.control_scheme == "wasd"
    assert len(contract.controls) == 2
    assert contract.visual_style["palette"] == "neon"


def test_game_contract_model_validate_realistic_json():
    data = {
        "title": "Space Defender",
        "nodes": [
            {
                "script_path": "player.gd",
                "scene_path": "Player.tscn",
                "node_type": "CharacterBody2D",
                "description": "Player ship",
                "methods": ["shoot()", "take_damage(amount: int)"],
                "signals": ["died", "health_changed"],
                "groups": ["player"],
                "dependencies": [],
            },
            {
                "script_path": "enemy.gd",
                "scene_path": "Enemy.tscn",
                "node_type": "CharacterBody2D",
                "description": "Enemy ship",
                "methods": ["patrol()", "attack()"],
                "signals": ["destroyed"],
                "groups": ["enemies"],
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
    contract = GameContract.model_validate(data)
    assert contract.title == "Space Defender"
    assert len(contract.nodes) == 2
    assert contract.nodes[1].dependencies == ["player.gd"]


def test_game_contract_missing_title_raises_validation_error():
    with pytest.raises(ValidationError):
        GameContract(
            nodes=[],
            control_scheme="wasd",
        )
