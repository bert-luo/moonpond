"""Unit tests for game_manager.gd generation from GameContract."""

from __future__ import annotations

from backend.stages.contract_models import GameContract, NodeContract
from backend.stages.game_manager_generator import generate_game_manager_script


def _make_contract(**kwargs) -> GameContract:
    """Helper to build a GameContract with sensible defaults."""
    defaults = {
        "title": "Test Game",
        "nodes": [
            NodeContract(
                script_path="player.gd",
                node_type="CharacterBody2D",
                description="Player character",
            ),
        ],
        "control_scheme": "wasd",
    }
    defaults.update(kwargs)
    return GameContract(**defaults)


# ---------------------------------------------------------------------------
# Base template preservation
# ---------------------------------------------------------------------------


def test_empty_contract_produces_base_template():
    """An empty contract (no extras) should produce the base template content."""
    contract = _make_contract()
    script = generate_game_manager_script(contract)

    # Must contain the base template pieces
    assert "extends Node" in script
    assert "var active_palette: Gradient = null" in script
    assert "enum GameState { PLAYING, WON, LOST }" in script
    assert "var state: GameState = GameState.PLAYING" in script
    assert "func _ready() -> void:" in script
    assert 'active_palette = load("res://assets/palettes/neon.tres")' in script
    assert "func set_palette(palette_name: String) -> void:" in script
    assert "func get_palette_color(t: float) -> Color:" in script
    assert "func set_state(new_state: GameState) -> void:" in script


# ---------------------------------------------------------------------------
# Enum generation
# ---------------------------------------------------------------------------


def test_contract_enums_adds_enum_blocks():
    """game_manager_enums should produce enum declarations in the script."""
    contract = _make_contract(
        game_manager_enums={
            "EnemyType": ["GRUNT", "BOSS", "MINIBOSS"],
            "PowerUp": ["SPEED", "SHIELD"],
        }
    )
    script = generate_game_manager_script(contract)

    assert "enum EnemyType { GRUNT, BOSS, MINIBOSS }" in script
    assert "enum PowerUp { SPEED, SHIELD }" in script


def test_gamestate_enum_not_duplicated():
    """If the contract includes GameState in enums, it should NOT be duplicated."""
    contract = _make_contract(
        game_manager_enums={
            "GameState": ["PLAYING", "WON", "LOST", "PAUSED"],
        }
    )
    script = generate_game_manager_script(contract)

    # GameState should appear exactly once as an enum declaration
    count = script.count("enum GameState")
    assert count == 1, f"GameState enum appeared {count} times, expected 1"


# ---------------------------------------------------------------------------
# Property generation
# ---------------------------------------------------------------------------


def test_contract_properties_adds_var_declarations():
    """game_manager_properties should produce var declarations."""
    contract = _make_contract(
        game_manager_properties=["score", "lives", "level_name"]
    )
    script = generate_game_manager_script(contract)

    assert "var score" in script
    assert "var lives" in script
    assert "var level_name" in script


# ---------------------------------------------------------------------------
# Method generation
# ---------------------------------------------------------------------------


def test_contract_methods_adds_func_stubs():
    """game_manager_methods should produce func stub definitions."""
    contract = _make_contract(
        game_manager_methods=[
            "add_currency(amount: int)",
            "can_afford(cost: int) -> bool",
            "reset_game()",
        ]
    )
    script = generate_game_manager_script(contract)

    assert "func add_currency(amount: int):" in script
    assert "func can_afford(cost: int) -> bool:" in script
    assert "func reset_game():" in script
    # Each stub should have a pass body
    assert script.count("pass") >= 3


# ---------------------------------------------------------------------------
# Signal generation
# ---------------------------------------------------------------------------


def test_contract_signals_adds_signal_declarations():
    """game_manager_signals should produce signal declarations."""
    contract = _make_contract(
        game_manager_signals=["currency_changed", "income_changed", "game_reset"]
    )
    script = generate_game_manager_script(contract)

    assert "signal currency_changed" in script
    assert "signal income_changed" in script
    assert "signal game_reset" in script


# ---------------------------------------------------------------------------
# Combined
# ---------------------------------------------------------------------------


def test_full_contract_includes_all_sections():
    """A contract with all extras should include enums, props, methods, and signals."""
    contract = _make_contract(
        game_manager_enums={"Difficulty": ["EASY", "HARD"]},
        game_manager_properties=["score", "health"],
        game_manager_methods=["reset()", "add_score(points: int)"],
        game_manager_signals=["score_changed", "health_depleted"],
    )
    script = generate_game_manager_script(contract)

    # Base preserved
    assert "extends Node" in script
    assert "enum GameState { PLAYING, WON, LOST }" in script

    # Extras added
    assert "enum Difficulty { EASY, HARD }" in script
    assert "var score" in script
    assert "var health" in script
    assert "func reset():" in script
    assert "func add_score(points: int):" in script
    assert "signal score_changed" in script
    assert "signal health_depleted" in script
