"""Unit tests for game_manager.gd generation from GameContract."""

from __future__ import annotations

from backend.pipelines.contract.models import GameContract, NodeContract
from backend.pipelines.contract.game_manager_generator import (
    _assemble_script,
    _extract_method_name,
    generate_game_manager_script,
)


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
    assert "var state: int = 0" in script
    assert "func _ready() -> void:" in script
    assert 'active_palette = load("res://assets/palettes/neon.tres")' in script
    assert "func set_palette(palette_name: String) -> void:" in script
    assert "func get_palette_color(t: float) -> Color:" in script
    assert "func set_state(new_state: int) -> void:" in script
    # No hardcoded GameState enum in template -- comes from contract
    assert "enum GameState" not in script


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


def test_gamestate_enum_from_contract():
    """GameState enum should come from the contract, not the template."""
    contract = _make_contract(
        game_manager_enums={
            "GameState": ["PLAYING", "WON", "LOST", "PAUSED"],
        }
    )
    script = generate_game_manager_script(contract)

    # GameState should appear exactly once, with contract-specified variants
    count = script.count("enum GameState")
    assert count == 1, f"GameState enum appeared {count} times, expected 1"
    assert "enum GameState { PLAYING, WON, LOST, PAUSED }" in script


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

    # Extras added
    assert "enum Difficulty { EASY, HARD }" in script
    assert "var score" in script
    assert "var health" in script
    assert "func reset():" in script
    assert "func add_score(points: int):" in script
    assert "signal score_changed" in script
    assert "signal health_depleted" in script


# ---------------------------------------------------------------------------
# Assembly with real method bodies
# ---------------------------------------------------------------------------


def test_assemble_with_method_bodies_replaces_stubs():
    """When method_bodies are provided, they replace pass stubs."""
    contract = _make_contract(
        game_manager_properties=["score"],
        game_manager_methods=[
            "add_score(amount: int)",
            "get_score() -> int",
        ],
        game_manager_signals=["score_changed"],
    )
    bodies = {
        "add_score(amount: int)": "\tscore += amount\n\tscore_changed.emit()",
        "get_score() -> int": "\treturn score",
    }
    script = _assemble_script(contract, method_bodies=bodies)

    assert "func add_score(amount: int):" in script
    assert "score += amount" in script
    assert "score_changed.emit()" in script
    assert "func get_score() -> int:" in script
    assert "return score" in script
    # No pass stubs for methods that got bodies
    # (pass may appear in template base methods, so check specifically)
    lines = script.split("\n")
    for i, line in enumerate(lines):
        if "func add_score" in line or "func get_score" in line:
            assert lines[i + 1].strip() != "pass"


def test_assemble_falls_back_to_stub_for_missing_body():
    """Methods missing from method_bodies dict should get pass stubs."""
    contract = _make_contract(
        game_manager_methods=[
            "add_score(amount: int)",
            "reset()",
        ],
    )
    bodies = {
        "add_score(amount: int)": "\tscore += amount",
        # reset() intentionally missing
    }
    script = _assemble_script(contract, method_bodies=bodies)

    assert "score += amount" in script
    # reset() should have pass stub
    lines = script.split("\n")
    for i, line in enumerate(lines):
        if "func reset():" in line:
            assert lines[i + 1].strip() == "pass"
            break
    else:
        raise AssertionError("func reset() not found in script")


def test_assemble_normalizes_body_indentation():
    """Method bodies without leading tabs should get tab-indented."""
    contract = _make_contract(
        game_manager_methods=["do_thing()"],
    )
    # Body with no leading tabs (simulating raw LLM output)
    bodies = {
        "do_thing()": "var x = 1\nprint(x)",
    }
    script = _assemble_script(contract, method_bodies=bodies)

    lines = script.split("\n")
    for i, line in enumerate(lines):
        if "func do_thing():" in line:
            assert lines[i + 1] == "\tvar x = 1"
            assert lines[i + 2] == "\tprint(x)"
            break
    else:
        raise AssertionError("func do_thing() not found in script")


# ---------------------------------------------------------------------------
# Bug A: Duplicate base method filtering
# ---------------------------------------------------------------------------


def test_extract_method_name_parses_signature():
    """_extract_method_name parses bare name from full GDScript signatures."""
    assert _extract_method_name("set_state(new_state: int) -> void") == "set_state"
    assert _extract_method_name("add_score(points: int)") == "add_score"


def test_duplicate_base_method_filtered():
    """Contract methods that duplicate template base methods are filtered out."""
    contract = _make_contract(
        game_manager_methods=[
            "set_state(new_state: int) -> void",
            "add_score(points: int)",
        ]
    )
    script = generate_game_manager_script(contract)

    # set_state should appear exactly once (from template), not duplicated
    count = script.count("func set_state")
    assert count == 1, f"func set_state appeared {count} times, expected 1"

    # add_score should appear once (from contract)
    count = script.count("func add_score")
    assert count == 1, f"func add_score appeared {count} times, expected 1"


def test_similar_name_not_filtered():
    """Methods with names that are superstrings of base methods are NOT filtered."""
    contract = _make_contract(
        game_manager_methods=["set_state_from_network(data: Dictionary)"]
    )
    script = generate_game_manager_script(contract)

    assert "func set_state_from_network" in script
