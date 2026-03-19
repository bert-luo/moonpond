"""SceneAssembler — deterministic .tscn generation from contract + .gd files.

Produces all .tscn files needed by a game:
- Main.tscn: root scene with ext_resource refs for all static nodes
- Sub-scene .tscn files: for each node with a non-Main scene_path

Parses @onready %Name references from generated .gd files to discover
what child nodes each sub-scene needs, then builds them with TscnBuilder.

No LLM calls — purely mechanical derivation from the contract.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from backend.pipelines.contract.models import GameContract, NodeContract
from backend.pipelines.contract.tscn_builder import TscnBuilder

# Physics node types that need a default CollisionShape2D child.
PHYSICS_NODE_TYPES: frozenset[str] = frozenset(
    {"CharacterBody2D", "StaticBody2D", "RigidBody2D", "Area2D"}
)

# Regex for @onready var name: Type = %UniqueName
# Captures: (var_name, optional type, unique_name)
ONREADY_PATTERN = re.compile(
    r"^@onready\s+var\s+(\w+)(?:\s*:\s*(\w+))?\s*=\s*%(\w+)",
    re.MULTILINE,
)


def parse_onready_unique_refs(gd_source: str) -> list[dict]:
    """Extract @onready %Name references from a GDScript source string.

    Returns a list of dicts with keys: var_name, node_type (or None), unique_name.
    Ignores @onready lines that use $Path syntax instead of %UniqueName.
    """
    results: list[dict] = []
    for match in ONREADY_PATTERN.finditer(gd_source):
        var_name, node_type, unique_name = match.groups()
        results.append(
            {
                "var_name": var_name,
                "node_type": node_type or None,
                "unique_name": unique_name,
            }
        )
    return results


class SceneAssembler:
    """Assembles all .tscn files from a GameContract and generated .gd files."""

    @staticmethod
    def assemble(contract: GameContract, node_files: dict[str, str]) -> dict[str, str]:
        """Produce all .tscn files as a dict mapping filename -> content.

        Args:
            contract: The full game contract with node definitions.
            node_files: Dict mapping script_path -> .gd source code.

        Returns:
            Dict mapping .tscn filename -> .tscn file content string.
        """
        result: dict[str, str] = {}

        # Pass A: Main.tscn
        result["Main.tscn"] = SceneAssembler._build_main_tscn(contract, node_files)

        # Pass B: Sub-scene .tscn for each non-Main scene_path
        for node in contract.nodes:
            if node.scene_path and node.scene_path != contract.main_scene:
                tscn_content = SceneAssembler._build_sub_scene(node, node_files)
                result[node.scene_path] = tscn_content

        return result

    @staticmethod
    def _build_main_tscn(contract: GameContract, node_files: dict[str, str]) -> str:
        """Build Main.tscn with all static nodes."""
        b = TscnBuilder()

        # Find main script node (scene_path == main_scene)
        main_script_id: str | None = None
        for node in contract.nodes:
            if node.scene_path == contract.main_scene:
                sid = b.add_ext_resource("Script", f"res://{node.script_path}")
                main_script_id = sid
                break

        # Root node
        b.add_node("Main", "Node2D", parent=None, script_id=main_script_id)

        # Add each static node
        for node in contract.nodes:
            # Skip main script node (already attached to root)
            if node.scene_path == contract.main_scene:
                continue
            # Skip dynamic nodes
            if node.spawn_mode == "dynamic":
                continue

            if node.scene_path is not None:
                # Node with scene_path: instance the sub-scene
                ps_id = b.add_ext_resource("PackedScene", f"res://{node.scene_path}")
                node_name = PurePosixPath(node.scene_path).stem
                b.add_node(
                    node_name,
                    None,
                    parent=".",
                    instance_id=ps_id,
                    unique_name=True,
                )
            else:
                # Inline node: add script ext_resource and node with type
                script_id = b.add_ext_resource("Script", f"res://{node.script_path}")
                node_name = (
                    PurePosixPath(node.script_path)
                    .stem.replace("_", " ")
                    .title()
                    .replace(" ", "")
                )
                # Use the script filename stem as Pascal case name
                # But prefer a cleaner approach: capitalize first letter of stem
                node_name = _node_name_from_script(node.script_path)
                b.add_node(
                    node_name,
                    node.node_type,
                    parent=".",
                    script_id=script_id,
                    unique_name=True,
                )

        # No connections — signals are wired in _ready() per design decision
        return b.serialize()

    @staticmethod
    def _build_sub_scene(node: NodeContract, node_files: dict[str, str]) -> str:
        """Build a sub-scene .tscn for a node with scene_path."""
        b = TscnBuilder()

        root_name = PurePosixPath(node.scene_path).stem  # type: ignore[arg-type]

        # Script ext_resource
        script_id = b.add_ext_resource("Script", f"res://{node.script_path}")

        # Root node
        b.add_node(
            root_name,
            node.node_type,
            parent=None,
            script_id=script_id,
            unique_name=True,
        )

        # Parse @onready refs from .gd to find children
        gd_source = node_files.get(node.script_path, "")
        refs = parse_onready_unique_refs(gd_source)
        for ref in refs:
            child_type = ref["node_type"] or "Node2D"
            b.add_node(
                ref["unique_name"],
                child_type,
                parent=".",
                unique_name=True,
            )

        # Physics bodies get a default CollisionShape2D
        if node.node_type in PHYSICS_NODE_TYPES:
            shape_id = b.add_sub_resource(
                "RectangleShape2D", {"size": "Vector2(64, 64)"}
            )
            b.add_node(
                "CollisionShape2D",
                "CollisionShape2D",
                parent=".",
                extra_props={"shape": f'SubResource("{shape_id}")'},
            )

        return b.serialize()


def _node_name_from_script(script_path: str) -> str:
    """Derive a PascalCase node name from a script path.

    'player.gd' -> 'Player'
    'enemy_spawner.gd' -> 'EnemySpawner'
    """
    stem = PurePosixPath(script_path).stem
    return "".join(part.capitalize() for part in stem.split("_"))
