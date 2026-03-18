"""Parallel Node Generator stage — generates GDScript files for each node in the contract.

Nodes are topologically sorted by dependency depth and generated in waves.
All nodes in the same wave run in parallel via asyncio.gather().
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

from anthropic import AsyncAnthropic

from backend.pipelines.base import EmitFn, ProgressEvent
from backend.stages.contract_models import GameContract, NodeContract
from backend.stages.models import (
    INPUT_ACTIONS,
    PARTICLE_PATHS,
    PALETTE_PATHS,
    SHADER_PATHS,
)

logger = logging.getLogger(__name__)

SONNET_MODEL = "claude-sonnet-4-6"


def _build_depth_map(nodes: list[NodeContract]) -> dict[str, int]:
    """Build a depth map: nodes with empty dependencies are depth 0.

    For each node with dependencies, depth = max(depth of each dependency) + 1.
    Raises ValueError on cycles.
    """
    by_path: dict[str, NodeContract] = {n.script_path: n for n in nodes}
    depths: dict[str, int] = {}

    def resolve(path: str, visiting: set[str]) -> int:
        if path in depths:
            return depths[path]
        if path in visiting:
            raise ValueError(f"Cycle detected involving {path}")
        visiting.add(path)
        node = by_path.get(path)
        if node is None or not node.dependencies:
            depths[path] = 0
        else:
            max_dep = 0
            for dep in node.dependencies:
                if dep in by_path:
                    max_dep = max(max_dep, resolve(dep, visiting))
            depths[path] = max_dep + 1
        visiting.discard(path)
        return depths[path]

    for n in nodes:
        resolve(n.script_path, set())

    return depths


def _group_into_waves(
    nodes: list[NodeContract], depth_map: dict[str, int]
) -> list[list[NodeContract]]:
    """Group nodes into ordered waves by depth."""
    max_depth = max(depth_map.values()) if depth_map else 0
    waves: list[list[NodeContract]] = [[] for _ in range(max_depth + 1)]
    for node in nodes:
        d = depth_map.get(node.script_path, 0)
        waves[d].append(node)
    return [w for w in waves if w]  # filter empty


def _build_game_manager_api_block(contract: GameContract) -> str:
    """Build a structured GameManager API text block from contract fields.

    Always includes the base palette/state API. Appends game-specific
    properties, methods, signals, and enums when present in the contract.
    """
    lines = [
        "GameManager API (autoload — available globally via GameManager.xxx):",
        "  Base API (always available):",
        "    Properties: active_palette (Gradient), state (int)",
        "    Methods: set_palette(palette_name: String), get_palette_color(t: float) -> Color, set_state(new_state: int)",
    ]

    # Build game-specific subsections
    game_lines: list[str] = []
    if contract.game_manager_properties:
        game_lines.append(
            f"    Properties: {', '.join(contract.game_manager_properties)}"
        )
    if contract.game_manager_methods:
        game_lines.append(f"    Methods: {', '.join(contract.game_manager_methods)}")
    if contract.game_manager_signals:
        game_lines.append(f"    Signals: {', '.join(contract.game_manager_signals)}")
    if contract.game_manager_enums:
        enum_strs = [
            f"{name} {{ {', '.join(values)} }}"
            for name, values in contract.game_manager_enums.items()
        ]
        game_lines.append(f"    Enums: {', '.join(enum_strs)}")

    if game_lines:
        lines.append("")
        lines.append("  Game-Specific API:")
        lines.extend(game_lines)

    return "\n".join(lines)


def _build_dependency_api_blocks(node: NodeContract, contract: GameContract) -> str:
    """Build API reference blocks for each of this node's declared dependencies.

    Looks up each dependency by script_path in the contract's node list and
    formats its public API (methods, signals, groups). Unknown dependencies
    are silently skipped.
    """
    if not node.dependencies:
        return ""

    by_path: dict[str, NodeContract] = {n.script_path: n for n in contract.nodes}
    blocks: list[str] = []

    for dep_path in node.dependencies:
        dep = by_path.get(dep_path)
        if dep is None:
            continue
        lines = [
            f"  Dependency: {dep.script_path} ({dep.node_type})",
            f"    Description: {dep.description}",
            f"    Methods: {', '.join(dep.methods) if dep.methods else 'none'}",
            f"    Signals: {', '.join(dep.signals) if dep.signals else 'none'}",
            f"    Groups: {', '.join(dep.groups) if dep.groups else 'none'}",
        ]
        blocks.append("\n".join(lines))

    if not blocks:
        return ""

    return "Sibling Node APIs (your declared dependencies):\n" + "\n\n".join(blocks)


def _build_node_system_prompt(node: NodeContract, contract: GameContract) -> str:
    """Build the system prompt for generating a single node's files."""
    parts = [
        "You are generating GDScript for a Godot 4 game. "
        "Generate ONLY the file(s) for this node.",
        "",
        "Do NOT generate game_manager.gd — it is auto-generated separately.",
        "",
        _build_game_manager_api_block(contract),
        "",
        f"Respond with ONLY files for: {node.script_path}",
    ]

    if node.scene_path:
        parts.append(f"Also generate: {node.scene_path}")

    parts.append("")
    parts.append(
        "Use Godot 4 syntax exclusively. "
        f"Use Input.is_action_pressed() with these actions: {INPUT_ACTIONS}"
    )

    # Available assets
    parts.append(f"\nAvailable shaders: {json.dumps(SHADER_PATHS)}")
    parts.append(f"Available palettes: {json.dumps(PALETTE_PATHS)}")
    parts.append(f"Available particles: {json.dumps(PARTICLE_PATHS)}")

    # Dependency API blocks
    dep_block = _build_dependency_api_blocks(node, contract)
    if dep_block:
        parts.append(f"\n{dep_block}")

    # Contract context
    parts.append(
        "\nThe GameManager API block above is the authoritative reference for "
        "GameManager — use those exact method names and signatures."
    )
    parts.append(f"\nFull game contract:\n{contract.model_dump_json(indent=2)}")

    # Method/signal/group constraints
    if node.methods:
        parts.append(
            f"\nImplement EXACTLY these methods: {node.methods}. "
            "Do not rename or add methods not in the contract."
        )
    if node.signals:
        parts.append(f"Emit EXACTLY these signals: {node.signals}")
    if node.groups:
        parts.append(f"Add to EXACTLY these groups: {node.groups}")

    parts.append(
        "\nSCENE TREE REFERENCES — NEVER use @onready with literal node paths "
        "like $UI/ScoreLabel or $Systems/Timer. The scene tree hierarchy is "
        "determined by a separate wiring stage, so hardcoded paths WILL break. "
        "Instead, use Godot 4 unique-name references: %NodeName "
        "(e.g. @onready var score_label: Label = %ScoreLabel). "
        "This requires unique_name_in_owner = true on the target node in the "
        ".tscn, which the wiring stage will set. "
        "For dynamically spawned nodes, use groups: "
        'get_tree().get_nodes_in_group("group_name").'
    )

    parts.append(
        "\nVISUALS — There are NO image/texture assets available. "
        "Draw all visuals programmatically using _draw() overrides. "
        "Use Color constants for all visuals."
    )

    parts.append(
        "\nRespond ONLY with a JSON object where keys are filenames "
        "and values are the full source for that file. "
        "Do NOT include markdown code fences. Respond with raw JSON only."
    )

    return "\n".join(parts)


async def _generate_single_node(
    client: AsyncAnthropic,
    node: NodeContract,
    contract: GameContract,
) -> dict[str, str]:
    """Generate .gd (and optionally .tscn) for a single node.

    Returns dict mapping filename -> file content.
    """
    system_prompt = _build_node_system_prompt(node, contract)
    user_message = f"Generate code for this node:\n{node.model_dump_json(indent=2)}"

    response = await client.messages.create(
        model=SONNET_MODEL,
        max_tokens=8192,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw)

    # Extract JSON object via brace matching
    json_start = raw.find("{")
    if json_start >= 0:
        depth = 0
        for i, ch in enumerate(raw[json_start:], start=json_start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    raw = raw[json_start : i + 1]
                    break

    files: dict[str, str] = json.loads(raw)
    return files


async def run_parallel_node_generation(
    client: AsyncAnthropic,
    contract: GameContract,
    emit: EmitFn,
) -> dict[str, str]:
    """Generate all node scripts in parallel waves by dependency depth.

    Returns dict mapping filename -> file content for all .gd and .tscn files.
    """
    depth_map = _build_depth_map(contract.nodes)
    waves = _group_into_waves(contract.nodes, depth_map)

    await emit(
        ProgressEvent(
            type="stage_start",
            message=f"Generating {len(contract.nodes)} game files in {len(waves)} waves...",
        )
    )

    all_files: dict[str, str] = {}

    for wave_idx, wave_nodes in enumerate(waves):
        await emit(
            ProgressEvent(
                type="stage_start",
                message=f"Wave {wave_idx + 1}/{len(waves)}: generating {len(wave_nodes)} node(s)...",
            )
        )

        results = await asyncio.gather(
            *[_generate_single_node(client, node, contract) for node in wave_nodes],
            return_exceptions=True,
        )

        failed_count = 0
        for node, result in zip(wave_nodes, results):
            if isinstance(result, BaseException):
                failed_count += 1
                logger.warning(
                    "Node generation failed for %s: %s", node.script_path, result
                )
            else:
                all_files.update(result)

        if failed_count > 0:
            await emit(
                ProgressEvent(
                    type="warning",
                    message=f"Wave {wave_idx + 1}: {failed_count} node(s) failed to generate",
                    data={"failed_count": failed_count},
                )
            )

    return all_files
