"""Tests for the wiring generator stage."""

from __future__ import annotations

import json
import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.pipelines.base import ProgressEvent
from backend.stages.contract_models import GameContract, NodeContract
from backend.stages.wiring_generator import (
    _build_wiring_system_prompt,
    _patch_project_godot_autoloads,
    run_wiring_generator,
)


def _make_contract(nodes: list[NodeContract], **kwargs) -> GameContract:
    """Helper to build a GameContract with sensible defaults."""
    defaults = {
        "title": "Test Game",
        "control_scheme": "wasd",
        "nodes": nodes,
    }
    defaults.update(kwargs)
    return GameContract(**defaults)


# A valid Main.tscn that would be returned by the LLM
_SAMPLE_MAIN_TSCN = """\
[gd_scene load_steps=4 format=3]

[ext_resource type="Script" path="res://player.gd" id="1"]
[ext_resource type="Script" path="res://enemy.gd" id="2"]
[ext_resource type="Script" path="res://hud.gd" id="3"]

[node name="Main" type="Node2D"]

[node name="Player" type="CharacterBody2D" parent="."]
script = ExtResource("1")

[node name="Enemy" type="Area2D" parent="."]
script = ExtResource("2")

[node name="HUD" type="Control" parent="."]
script = ExtResource("3")
"""


def _mock_client(tscn_content: str = _SAMPLE_MAIN_TSCN) -> AsyncMock:
    """Build an AsyncAnthropic mock that returns the given tscn content."""
    client = AsyncMock()
    resp = MagicMock()
    resp.content = [MagicMock(text=tscn_content)]
    client.messages.create = AsyncMock(return_value=resp)
    return client


@pytest.fixture
def three_node_contract():
    """Contract with 3 nodes for testing."""
    nodes = [
        NodeContract(
            script_path="player.gd",
            node_type="CharacterBody2D",
            description="Player character",
        ),
        NodeContract(
            script_path="enemy.gd",
            node_type="Area2D",
            description="Enemy",
        ),
        NodeContract(
            script_path="hud.gd",
            node_type="Control",
            description="HUD overlay",
        ),
    ]
    return _make_contract(nodes)


@pytest.fixture
def generated_files():
    """Simulated generated files from node generator."""
    return {
        "player.gd": "extends CharacterBody2D\nfunc _ready():\n\tpass",
        "enemy.gd": "extends Area2D\nfunc _ready():\n\tpass",
        "hud.gd": "extends Control\nfunc _ready():\n\tpass",
    }


# ---------------------------------------------------------------------------
# Main.tscn generation tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_produces_main_tscn(three_node_contract, generated_files):
    """run_wiring_generator produces a files dict containing 'Main.tscn'."""
    client = _mock_client()
    emit = AsyncMock()

    result = await run_wiring_generator(client, three_node_contract, generated_files, emit)

    assert "Main.tscn" in result


@pytest.mark.anyio
async def test_main_tscn_has_ext_resources(three_node_contract, generated_files):
    """Main.tscn contains [ext_resource] entries for each node's script_path."""
    client = _mock_client()
    emit = AsyncMock()

    result = await run_wiring_generator(client, three_node_contract, generated_files, emit)

    tscn = result["Main.tscn"]
    assert "player.gd" in tscn
    assert "enemy.gd" in tscn
    assert "hud.gd" in tscn


@pytest.mark.anyio
async def test_ext_resource_ids_unique(three_node_contract, generated_files):
    """ExtResource IDs are unique (no duplicates)."""
    client = _mock_client()
    emit = AsyncMock()

    result = await run_wiring_generator(client, three_node_contract, generated_files, emit)

    tscn = result["Main.tscn"]
    ids = re.findall(r'\[ext_resource[^\]]*id="(\d+)"', tscn)
    assert len(ids) == len(set(ids)), f"Duplicate ext_resource IDs found: {ids}"


@pytest.mark.anyio
async def test_each_node_has_scene_entry(three_node_contract, generated_files):
    """Each node in contract.nodes has a corresponding [node] entry in Main.tscn."""
    client = _mock_client()
    emit = AsyncMock()

    result = await run_wiring_generator(client, three_node_contract, generated_files, emit)

    tscn = result["Main.tscn"]
    # Check for node entries (Player, Enemy, HUD)
    node_names = re.findall(r'\[node\s+name="([^"]+)"', tscn)
    # At minimum, each contract node should have a corresponding scene node
    # (node names may differ from script names, but scripts should be referenced)
    assert len(node_names) >= 3  # Main root + child nodes, but at least the children


# ---------------------------------------------------------------------------
# project.godot tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_no_autoloads_no_project_godot(three_node_contract, generated_files):
    """If contract.autoloads is empty, project.godot is NOT in the output."""
    assert three_node_contract.autoloads == []
    client = _mock_client()
    emit = AsyncMock()

    result = await run_wiring_generator(client, three_node_contract, generated_files, emit)

    assert "project.godot" not in result


@pytest.mark.anyio
async def test_autoloads_produces_project_godot(generated_files):
    """If contract.autoloads has entries, project.godot IS in the output with [autoload] section."""
    nodes = [
        NodeContract(
            script_path="player.gd",
            node_type="CharacterBody2D",
            description="Player",
        ),
    ]
    contract = _make_contract(nodes, autoloads=["ScoreManager"])

    # Mock with a simpler tscn for single node
    single_tscn = """\
[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://player.gd" id="1"]

[node name="Main" type="Node2D"]

[node name="Player" type="CharacterBody2D" parent="."]
script = ExtResource("1")
"""
    client = _mock_client(single_tscn)
    emit = AsyncMock()

    # Patch TEMPLATE_DIR to use the real template
    result = await run_wiring_generator(client, contract, {"player.gd": "code"}, emit)

    assert "project.godot" in result
    assert "[autoload]" in result["project.godot"]
    assert "ScoreManager" in result["project.godot"]


@pytest.mark.anyio
async def test_project_godot_preserves_input_section(generated_files):
    """project.godot output preserves the template's [input] section."""
    nodes = [
        NodeContract(
            script_path="player.gd",
            node_type="CharacterBody2D",
            description="Player",
        ),
    ]
    contract = _make_contract(nodes, autoloads=["ScoreManager"])

    single_tscn = """\
[gd_scene load_steps=2 format=3]

[ext_resource type="Script" path="res://player.gd" id="1"]

[node name="Main" type="Node2D"]

[node name="Player" type="CharacterBody2D" parent="."]
script = ExtResource("1")
"""
    client = _mock_client(single_tscn)
    emit = AsyncMock()

    result = await run_wiring_generator(client, contract, {"player.gd": "code"}, emit)

    godot_cfg = result["project.godot"]
    assert "[input]" in godot_cfg
    # Check that standard input actions are preserved
    assert "move_left=" in godot_cfg
    assert "move_right=" in godot_cfg
    assert "jump=" in godot_cfg
    assert "shoot=" in godot_cfg
    assert "pause=" in godot_cfg


# ---------------------------------------------------------------------------
# Progress event test
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_emits_stage_start(three_node_contract, generated_files):
    """Stage emits a ProgressEvent with type='stage_start'."""
    client = _mock_client()
    emitted: list[ProgressEvent] = []

    async def tracking_emit(event):
        emitted.append(event)

    await run_wiring_generator(client, three_node_contract, generated_files, tracking_emit)

    stage_starts = [e for e in emitted if e.type == "stage_start"]
    assert len(stage_starts) >= 1


# ---------------------------------------------------------------------------
# Bug B: Autoload deduplication tests
# ---------------------------------------------------------------------------

_MINIMAL_PROJECT_GODOT = """\
[application]

config/name="TestGame"

[autoload]

GameManager="*res://game_manager.gd"

[input]

move_left={}
"""


def test_gamemanager_autoload_not_duplicated():
    """Passing GameManager in autoloads list must NOT produce a duplicate entry."""
    result = _patch_project_godot_autoloads(_MINIMAL_PROJECT_GODOT, ["GameManager"])

    count = result.count('GameManager="*res://game_manager.gd"')
    assert count == 1, f"GameManager appeared {count} times, expected 1"


def test_non_gamemanager_autoloads_still_added():
    """Non-hardcoded autoloads are added alongside GameManager (no duplication)."""
    result = _patch_project_godot_autoloads(
        _MINIMAL_PROJECT_GODOT, ["GameManager", "AudioBus"]
    )

    gm_count = result.count('GameManager="*res://game_manager.gd"')
    assert gm_count == 1, f"GameManager appeared {gm_count} times, expected 1"
    assert "AudioBus" in result


def test_empty_autoloads_only_gamemanager():
    """Empty autoloads list should still produce the hardcoded GameManager entry."""
    result = _patch_project_godot_autoloads(_MINIMAL_PROJECT_GODOT, [])

    assert 'GameManager="*res://game_manager.gd"' in result
    # No other autoload entries besides GameManager
    autoload_section = result.split("[autoload]")[1].split("[")[0]
    assert autoload_section.count("=") == 1  # only GameManager line


# ---------------------------------------------------------------------------
# Bug E: Dynamic node filtering tests
# ---------------------------------------------------------------------------


def test_dynamic_nodes_excluded_from_wiring_prompt():
    """Contract with static + dynamic nodes -> wiring prompt excludes dynamic node."""
    static_player = NodeContract(
        script_path="player.gd",
        node_type="CharacterBody2D",
        description="Player character",
        spawn_mode="static",
    )
    static_enemy = NodeContract(
        script_path="enemy.gd",
        node_type="Area2D",
        description="Enemy",
        spawn_mode="static",
    )
    dynamic_bullet = NodeContract(
        script_path="bullet.gd",
        node_type="Area2D",
        description="Bullet projectile",
        spawn_mode="dynamic",
    )
    contract = _make_contract([static_player, static_enemy, dynamic_bullet])
    generated_files = {
        "player.gd": "extends CharacterBody2D",
        "enemy.gd": "extends Area2D",
        "bullet.gd": "extends Area2D",
    }

    prompt = _build_wiring_system_prompt(contract, generated_files)

    # The contract JSON in the prompt should contain player.gd and enemy.gd
    # but NOT bullet.gd (dynamic node excluded)
    assert "player.gd" in prompt
    assert "enemy.gd" in prompt
    assert "bullet.gd" not in prompt


def test_all_static_nodes_included_in_wiring_prompt():
    """Contract with only static nodes -> all appear in wiring prompt."""
    nodes = [
        NodeContract(
            script_path="player.gd",
            node_type="CharacterBody2D",
            description="Player",
            spawn_mode="static",
        ),
        NodeContract(
            script_path="enemy.gd",
            node_type="Area2D",
            description="Enemy",
            spawn_mode="static",
        ),
    ]
    contract = _make_contract(nodes)
    generated_files = {
        "player.gd": "extends CharacterBody2D",
        "enemy.gd": "extends Area2D",
    }

    prompt = _build_wiring_system_prompt(contract, generated_files)

    assert "player.gd" in prompt
    assert "enemy.gd" in prompt
