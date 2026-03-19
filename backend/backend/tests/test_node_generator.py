"""Tests for the parallel node generator stage."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.pipelines.base import ProgressEvent
from backend.pipelines.contract.models import GameContract, NodeContract
from backend.pipelines.contract.node_generator import (
    _build_node_system_prompt,
    _generate_single_node,
    run_parallel_node_generation,
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


def _mock_client_for_nodes(node_responses: dict[str, dict[str, str]]) -> AsyncMock:
    """Build an AsyncAnthropic mock that returns different responses per node.

    node_responses maps script_path -> dict of files that the LLM returns.
    The system prompt contains "Respond with ONLY files for: {script_path}" so we
    match on that exact pattern to avoid false matches when the contract JSON
    contains multiple script_paths.
    """
    client = AsyncMock()

    async def create_side_effect(**kwargs):
        # Match on the system prompt which contains "ONLY files for: {script_path}"
        system_prompt = kwargs.get("system", "")
        for script_path, files in node_responses.items():
            if f"ONLY files for: {script_path}" in system_prompt:
                resp = MagicMock()
                resp.content = [MagicMock(text=json.dumps(files))]
                return resp
        # Fallback
        resp = MagicMock()
        resp.content = [MagicMock(text="{}")]
        return resp

    client.messages.create = AsyncMock(side_effect=create_side_effect)
    return client


@pytest.fixture
def emit():
    """Async emit mock that records calls."""
    return AsyncMock()


# ---------------------------------------------------------------------------
# _generate_single_node tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_generate_single_node_returns_dict(emit):
    """_generate_single_node returns dict mapping script_path to generated code."""
    node = NodeContract(
        script_path="player.gd",
        node_type="CharacterBody2D",
        description="Player character",
        methods=["_ready()", "_process(delta)"],
        signals=["hit"],
    )
    contract = _make_contract([node])
    expected_files = {"player.gd": 'extends CharacterBody2D\nfunc _ready():\n\tpass'}
    client = _mock_client_for_nodes({"player.gd": expected_files})

    result = await _generate_single_node(client, node, contract)
    assert isinstance(result, dict)
    assert "player.gd" in result


@pytest.mark.anyio
async def test_generate_single_node_prompt_includes_methods(emit):
    """Node generator prompt includes the exact method signatures from NodeContract."""
    node = NodeContract(
        script_path="enemy.gd",
        node_type="Area2D",
        description="Enemy",
        methods=["_ready()", "take_damage(amount)"],
        signals=["destroyed"],
    )
    contract = _make_contract([node])
    client = _mock_client_for_nodes({"enemy.gd": {"enemy.gd": "code"}})

    await _generate_single_node(client, node, contract)

    call_kwargs = client.messages.create.call_args
    system_prompt = call_kwargs.kwargs.get("system") or call_kwargs[1].get("system", "")
    assert "_ready()" in system_prompt
    assert "take_damage(amount)" in system_prompt


@pytest.mark.anyio
async def test_generate_single_node_prompt_excludes_game_manager(emit):
    """Node generator prompt instructs 'do NOT generate game_manager.gd'."""
    node = NodeContract(
        script_path="hud.gd",
        node_type="Control",
        description="HUD overlay",
    )
    contract = _make_contract([node])
    client = _mock_client_for_nodes({"hud.gd": {"hud.gd": "code"}})

    await _generate_single_node(client, node, contract)

    call_kwargs = client.messages.create.call_args
    system_prompt = call_kwargs.kwargs.get("system") or call_kwargs[1].get("system", "")
    assert "game_manager.gd" in system_prompt.lower()
    assert "do not" in system_prompt.lower() or "NOT" in system_prompt


@pytest.mark.anyio
async def test_generate_single_node_prompt_only_this_node(emit):
    """Node generator prompt instructs 'respond with ONLY files for THIS node'."""
    node = NodeContract(
        script_path="bullet.gd",
        node_type="Area2D",
        description="Projectile",
    )
    contract = _make_contract([node])
    client = _mock_client_for_nodes({"bullet.gd": {"bullet.gd": "code"}})

    await _generate_single_node(client, node, contract)

    call_kwargs = client.messages.create.call_args
    system_prompt = call_kwargs.kwargs.get("system") or call_kwargs[1].get("system", "")
    assert "bullet.gd" in system_prompt
    assert "ONLY" in system_prompt


# ---------------------------------------------------------------------------
# Topological sorting / wave tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_flat_topology_single_wave(emit):
    """Flat: 4 leaf nodes (no deps) -> all generated in 1 wave."""
    nodes = [
        NodeContract(script_path="a.gd", node_type="Node2D", description="A"),
        NodeContract(script_path="b.gd", node_type="Node2D", description="B"),
        NodeContract(script_path="c.gd", node_type="Node2D", description="C"),
        NodeContract(script_path="d.gd", node_type="Node2D", description="D"),
    ]
    contract = _make_contract(nodes)
    responses = {n.script_path: {n.script_path: f"code_{n.script_path}"} for n in nodes}
    client = _mock_client_for_nodes(responses)

    result = await run_parallel_node_generation(client, contract, emit)

    assert len(result) == 4
    for n in nodes:
        assert n.script_path in result


@pytest.mark.anyio
async def test_two_level_topology(emit):
    """Two-level: 3 leaves + 1 orchestrator depending on 2 leaves -> 2 waves."""
    nodes = [
        NodeContract(script_path="leaf1.gd", node_type="Node2D", description="Leaf 1"),
        NodeContract(script_path="leaf2.gd", node_type="Node2D", description="Leaf 2"),
        NodeContract(script_path="leaf3.gd", node_type="Node2D", description="Leaf 3"),
        NodeContract(
            script_path="orch.gd",
            node_type="Node2D",
            description="Orchestrator",
            dependencies=["leaf1.gd", "leaf2.gd"],
        ),
    ]
    contract = _make_contract(nodes)
    responses = {n.script_path: {n.script_path: f"code_{n.script_path}"} for n in nodes}
    client = _mock_client_for_nodes(responses)

    # Track wave calls via emit messages
    emitted: list[ProgressEvent] = []
    async def tracking_emit(event):
        emitted.append(event)

    result = await run_parallel_node_generation(client, contract, tracking_emit)

    assert len(result) == 4
    assert "orch.gd" in result
    # Check that wave progress events were emitted
    wave_events = [e for e in emitted if "wave" in e.message.lower() or "Wave" in e.message]
    assert len(wave_events) >= 1  # At least one wave progress event


@pytest.mark.anyio
async def test_three_level_topology(emit):
    """Three-level: A (depth 0), B depends on A (depth 1), C depends on B (depth 2) -> 3 waves."""
    nodes = [
        NodeContract(script_path="a.gd", node_type="Node2D", description="A"),
        NodeContract(
            script_path="b.gd",
            node_type="Node2D",
            description="B",
            dependencies=["a.gd"],
        ),
        NodeContract(
            script_path="c.gd",
            node_type="Node2D",
            description="C",
            dependencies=["b.gd"],
        ),
    ]
    contract = _make_contract(nodes)
    responses = {n.script_path: {n.script_path: f"code_{n.script_path}"} for n in nodes}
    client = _mock_client_for_nodes(responses)

    result = await run_parallel_node_generation(client, contract, emit)

    assert len(result) == 3
    # All three nodes generated
    assert set(result.keys()) == {"a.gd", "b.gd", "c.gd"}


@pytest.mark.anyio
async def test_diamond_topology(emit):
    """Diamond: A, B (depth 0), C depends on A+B (depth 1), D depends on C (depth 2) -> 3 waves."""
    nodes = [
        NodeContract(script_path="a.gd", node_type="Node2D", description="A"),
        NodeContract(script_path="b.gd", node_type="Node2D", description="B"),
        NodeContract(
            script_path="c.gd",
            node_type="Node2D",
            description="C",
            dependencies=["a.gd", "b.gd"],
        ),
        NodeContract(
            script_path="d.gd",
            node_type="Node2D",
            description="D",
            dependencies=["c.gd"],
        ),
    ]
    contract = _make_contract(nodes)
    responses = {n.script_path: {n.script_path: f"code_{n.script_path}"} for n in nodes}
    client = _mock_client_for_nodes(responses)

    result = await run_parallel_node_generation(client, contract, emit)

    assert len(result) == 4
    assert set(result.keys()) == {"a.gd", "b.gd", "c.gd", "d.gd"}


# ---------------------------------------------------------------------------
# Failure handling tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_failed_node_does_not_kill_wave(emit):
    """One failed node (Exception) does not prevent other nodes in same wave from returning."""
    nodes = [
        NodeContract(script_path="good1.gd", node_type="Node2D", description="Good 1"),
        NodeContract(script_path="bad.gd", node_type="Node2D", description="Bad"),
        NodeContract(script_path="good2.gd", node_type="Node2D", description="Good 2"),
    ]
    contract = _make_contract(nodes)

    client = AsyncMock()
    call_count = 0

    async def create_side_effect(**kwargs):
        nonlocal call_count
        user_msg = kwargs["messages"][0]["content"]
        if "bad.gd" in user_msg:
            raise RuntimeError("LLM call failed for bad node")
        resp = MagicMock()
        for n in nodes:
            if n.script_path in user_msg and n.script_path != "bad.gd":
                resp.content = [MagicMock(text=json.dumps({n.script_path: "code"}))]
                return resp
        resp.content = [MagicMock(text="{}")]
        return resp

    client.messages.create = AsyncMock(side_effect=create_side_effect)

    result = await run_parallel_node_generation(client, contract, emit)

    # good1 and good2 should be in results, bad should not
    assert "good1.gd" in result
    assert "good2.gd" in result
    assert "bad.gd" not in result


@pytest.mark.anyio
async def test_failed_node_emits_warning(emit):
    """Failed nodes are reported via emitted warning events."""
    nodes = [
        NodeContract(script_path="ok.gd", node_type="Node2D", description="OK"),
        NodeContract(script_path="fail.gd", node_type="Node2D", description="Fail"),
    ]
    contract = _make_contract(nodes)

    client = AsyncMock()

    async def create_side_effect(**kwargs):
        user_msg = kwargs["messages"][0]["content"]
        if "fail.gd" in user_msg:
            raise RuntimeError("boom")
        resp = MagicMock()
        resp.content = [MagicMock(text=json.dumps({"ok.gd": "code"}))]
        return resp

    client.messages.create = AsyncMock(side_effect=create_side_effect)

    emitted: list[ProgressEvent] = []
    async def tracking_emit(event):
        emitted.append(event)

    await run_parallel_node_generation(client, contract, tracking_emit)

    # Should have a warning event about the failure
    warning_events = [e for e in emitted if "fail" in e.message.lower() or "warning" in e.type.lower()]
    assert len(warning_events) >= 1


# ---------------------------------------------------------------------------
# GameManager API block tests (Task 1 — CTXE-02)
# ---------------------------------------------------------------------------


def test_prompt_includes_game_manager_api_block():
    """Contract with game_manager_* fields -> prompt contains GameManager API section."""
    node = NodeContract(
        script_path="player.gd",
        node_type="CharacterBody2D",
        description="Player character",
    )
    contract = _make_contract(
        [node],
        game_manager_properties=["score", "lives"],
        game_manager_methods=["add_score(amount: int)"],
        game_manager_signals=["score_changed"],
        game_manager_enums={"PowerUpType": ["SPEED", "SHIELD"]},
    )
    prompt = _build_node_system_prompt(node, contract)

    assert "GameManager API" in prompt
    assert "score" in prompt
    assert "lives" in prompt
    assert "add_score" in prompt
    assert "score_changed" in prompt
    assert "PowerUpType" in prompt
    assert "SPEED" in prompt


def test_prompt_includes_base_api_even_when_empty():
    """Contract with no game_manager_* fields -> prompt still contains base API."""
    node = NodeContract(
        script_path="player.gd",
        node_type="CharacterBody2D",
        description="Player character",
    )
    contract = _make_contract([node])
    prompt = _build_node_system_prompt(node, contract)

    assert "set_palette" in prompt
    assert "get_palette_color" in prompt
    # GameState no longer hardcoded in base API -- comes from contract enums
    assert "set_state" in prompt


def test_prompt_no_longer_says_preexisting_autoload():
    """Prompt should NOT contain 'pre-existing autoload'."""
    node = NodeContract(
        script_path="player.gd",
        node_type="CharacterBody2D",
        description="Player character",
    )
    contract = _make_contract([node])
    prompt = _build_node_system_prompt(node, contract)

    assert "pre-existing autoload" not in prompt


# ---------------------------------------------------------------------------
# Dependency API block tests (Task 2 — CTXE-03)
# ---------------------------------------------------------------------------


def test_prompt_includes_dependency_api_for_declared_deps():
    """Node with dependencies -> prompt contains dependency API blocks."""
    player = NodeContract(
        script_path="player.gd",
        node_type="CharacterBody2D",
        description="Player character",
        methods=["shoot()", "take_damage(amount: int)"],
        signals=["died"],
        groups=["players"],
    )
    hud = NodeContract(
        script_path="hud.gd",
        node_type="Control",
        description="HUD overlay",
        dependencies=["player.gd"],
    )
    contract = _make_contract([player, hud])
    prompt = _build_node_system_prompt(hud, contract)

    assert "Sibling Node APIs" in prompt
    assert "Dependency: player.gd" in prompt
    assert "shoot()" in prompt
    assert "take_damage" in prompt
    assert "died" in prompt


def test_prompt_no_dependency_block_for_leaf_node():
    """Node with no dependencies -> no Sibling Node APIs block."""
    leaf = NodeContract(
        script_path="particle.gd",
        node_type="GPUParticles2D",
        description="Particle effect",
    )
    contract = _make_contract([leaf])
    prompt = _build_node_system_prompt(leaf, contract)

    assert "Sibling Node APIs" not in prompt


def test_prompt_skips_unknown_dependency():
    """Node depends on script not in contract -> no crash, no block for it."""
    node = NodeContract(
        script_path="spawner.gd",
        node_type="Node2D",
        description="Spawner",
        dependencies=["ghost.gd"],
    )
    contract = _make_contract([node])
    prompt = _build_node_system_prompt(node, contract)

    # ghost.gd is not in the contract, so no dependency block should appear
    assert "ghost.gd" not in prompt.split("Full game contract")[0]
    assert "Sibling Node APIs" not in prompt


def test_signal_signatures_with_args_in_prompt():
    """Node with signal signatures including args -> prompt contains them verbatim."""
    node = NodeContract(
        script_path="bird.gd",
        node_type="CharacterBody2D",
        description="Flappy bird",
        signals=["bird_flapped(velocity: Vector2)", "died"],
    )
    contract = _make_contract([node])
    prompt = _build_node_system_prompt(node, contract)

    assert "bird_flapped(velocity: Vector2)" in prompt
    assert "died" in prompt


def test_spawn_mode_defaults_to_static():
    """NodeContract() without spawn_mode has spawn_mode == 'static'."""
    node = NodeContract(
        script_path="player.gd",
        node_type="CharacterBody2D",
        description="Player",
    )
    assert node.spawn_mode == "static"


def test_spawn_mode_accepts_dynamic():
    """NodeContract(spawn_mode='dynamic', ...) validates successfully."""
    node = NodeContract(
        script_path="bullet.gd",
        node_type="Area2D",
        description="Bullet",
        spawn_mode="dynamic",
    )
    assert node.spawn_mode == "dynamic"


def test_prompt_multiple_dependencies():
    """Node depends on two siblings -> both appear in prompt."""
    player = NodeContract(
        script_path="player.gd",
        node_type="CharacterBody2D",
        description="Player",
        methods=["get_position()"],
        signals=["moved"],
    )
    enemy = NodeContract(
        script_path="enemy.gd",
        node_type="Area2D",
        description="Enemy",
        methods=["patrol()"],
        signals=["spotted_player"],
    )
    manager = NodeContract(
        script_path="level.gd",
        node_type="Node2D",
        description="Level manager",
        dependencies=["player.gd", "enemy.gd"],
    )
    contract = _make_contract([player, enemy, manager])
    prompt = _build_node_system_prompt(manager, contract)

    assert "Dependency: player.gd" in prompt
    assert "Dependency: enemy.gd" in prompt
    assert "get_position()" in prompt
    assert "patrol()" in prompt
